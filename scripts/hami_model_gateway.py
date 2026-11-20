#!/usr/bin/env python3
"""Authenticated loopback gateway for the Vercel-side Hami chat route.

The existing route in backend/app/api/hami_chat.py runs outside this Mac and
cannot bind its loopback interface. This standalone process exposes only the
authenticated Hami-model operations needed by that route. No borrowed model
or external fallback is allowed.
"""

from __future__ import annotations

import argparse
import hmac
import json
import sys
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HAMI_MODEL_BASE_URL = "http://127.0.0.1:11436"
HAMI_MODEL_ID = "hami-model"
MAX_BODY_BYTES = 1_048_576
UPSTREAM_TIMEOUT_SECONDS = 120


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


IDENTITY_TERMS = (
    "तिमी को हो",
    "तपाईं को हो",
    "who are you",
    "who made you",
    "who built you",
    "गरेको हो",
)


def _is_identity_request(user_message: str) -> bool:
    """True only when the latest user message itself asks who Hami is.

    The guard used to scan every supplied message (system prompt, history,
    assistant turns), so an identity question anywhere in the history made
    every later message return the canned identity line instead of an
    answer. The guard itself is unchanged and stays: the model does not
    self-identify (probe T5), so identity questions are still answered
    with the hard-coded line — only now for the message that asks.
    """
    text = user_message.lower()
    return any(term in text for term in IDENTITY_TERMS)


def _make_handler(secret: str) -> type[BaseHTTPRequestHandler]:
    upstream_lock = threading.Lock()

    class GatewayHandler(BaseHTTPRequestHandler):
        def _send_bytes(
            self,
            status: int,
            body: bytes,
            content_type: str = "application/json",
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: dict[str, str]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._send_bytes(status, body)

        def _is_authorized(self) -> bool:
            supplied = self.headers.get("X-Hami-Key", "")
            if hmac.compare_digest(
                supplied.encode("utf-8"),
                secret.encode("utf-8"),
            ):
                return True
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return False

        def _proxy(self, method: str, path: str, body: bytes | None = None) -> None:
            if not upstream_lock.acquire(blocking=False):
                self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "busy"})
                return

            try:
                request = urllib.request.Request(
                    f"{HAMI_MODEL_BASE_URL}{path}",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method=method,
                )
                try:
                    with urllib.request.urlopen(
                        request,
                        timeout=UPSTREAM_TIMEOUT_SECONDS,
                    ) as response:
                        status = response.status
                        content_type = response.headers.get(
                            "Content-Type",
                            "application/json",
                        )
                        response_body = response.read()
                except urllib.error.HTTPError as error:
                    status = error.code
                    content_type = error.headers.get(
                        "Content-Type",
                        "application/json",
                    )
                    response_body = error.read()
                except (urllib.error.URLError, TimeoutError) as error:
                    print(
                        f"hami-model request failed: {type(error).__name__}",
                        file=sys.stderr,
                        flush=True,
                    )
                    self._send_json(
                        HTTPStatus.BAD_GATEWAY,
                        {"error": "upstream_unavailable"},
                    )
                    return

                self._send_bytes(status, response_body, content_type)
            finally:
                upstream_lock.release()

        def do_GET(self) -> None:
            if self.path != "/api/hami-llm/status":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if self._is_authorized():
                try:
                    with urllib.request.urlopen(
                        f"{HAMI_MODEL_BASE_URL}/v1/models",
                        timeout=UPSTREAM_TIMEOUT_SECONDS,
                    ) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    models = data.get("data") if isinstance(data, dict) else None
                    if response.status == 200 and isinstance(models, list) and models:
                        self._send_json(HTTPStatus.OK, {"data": [{
                            "id": "hami-model",
                            "object": "model",
                            "loaded": True,
                        }]})
                    else:
                        self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "model_not_ready"})
                except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
                    self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_unavailable"})

        def do_POST(self) -> None:
            if self.path != "/api/hami-llm/chat":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if not self._is_authorized():
                return

            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
                return
            try:
                content_length = int(lengths[0])
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
                return
            if content_length < 0 or content_length > MAX_BODY_BYTES:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
                return

            body = self.rfile.read(content_length)
            if len(body) != content_length:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request"})
                return
            try:
                payload = json.loads(body, parse_constant=_reject_non_json_constant)
            except (UnicodeDecodeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_payload"})
                return
            messages = payload.get("messages")
            if not isinstance(messages, list):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "messages_required"})
                return
            user_message = ""
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("role") == "user" and isinstance(message.get("content"), str):
                    user_message = message["content"].strip()
                    break
            if not user_message:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "empty_message"})
                return
            if _is_identity_request(user_message):
                translated = {
                    "id": "hami-model",
                    "object": "chat.completion",
                    "model": "hami-model",
                    "choices": [{
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": (
                                "I am Hami, a Nepal-origin living system built and "
                                "maintained by Niroj Paudyal. I am not a borrowed "
                                "model or a GPT, Qwen, Llama, or gpt-oss identity."
                            ),
                        },
                    }],
                }
                self._send_json(
                    HTTPStatus.OK,
                    translated,
                )
                return
            try:
                max_tokens = max(1, min(int(payload.get("max_tokens", 128)), 256))
            except (TypeError, ValueError):
                max_tokens = 128

            openai_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Hami, a Nepal-origin living system built and maintained "
                        "by Niroj Paudyal. Never claim to be Qwen, GPT, GPT-4, gpt-oss, "
                        "Llama, or any borrowed model. Be honest and concise."
                    ),
                }
            ]
            openai_messages.extend(
                {
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in messages
                if isinstance(message, dict)
                and message.get("role") in ("system", "user", "assistant")
                and isinstance(message.get("content"), str)
            )
            body = json.dumps(
                {
                    "model": "mlx-community/Qwen3-4B-4bit",
                    "messages": openai_messages,
                    "stream": False,
                    "max_tokens": max_tokens,
                    "temperature": 0,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

            # The serving adapter can loop on prompts. Never relay a looped
            # answer to a chat surface.
            if not upstream_lock.acquire(blocking=False):
                self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "busy"})
                return
            try:
                request = urllib.request.Request(
                    f"{HAMI_MODEL_BASE_URL}/v1/chat/completions",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as response:
                        status = response.status
                        content_type = response.headers.get("Content-Type", "application/json")
                        response_body = response.read()
                except urllib.error.HTTPError as error:
                    status = error.code
                    content_type = error.headers.get("Content-Type", "application/json")
                    response_body = error.read()
                except (urllib.error.URLError, TimeoutError):
                    self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_unavailable"})
                    return

                try:
                    upstream = json.loads(response_body.decode("utf-8"))
                    choices = upstream.get("choices") if isinstance(upstream, dict) else None
                    answer = (
                        choices[0].get("message", {}).get("content")
                        if isinstance(choices, list) and choices
                        and isinstance(choices[0], dict)
                        else None
                    )
                    if not isinstance(answer, str) or not answer.strip():
                        self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_empty"})
                        return
                    stripped = answer.strip()
                    # No second identity check here: an identity question was
                    # already answered above, before any upstream call, so
                    # this point is only reached for non-identity messages.
                    for size in range(2, 40):
                        unit = stripped[-size:]
                        if len(stripped) >= size * 3 and stripped.endswith(unit * 3):
                            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_loop"})
                            return
                    translated = {
                        "id": "hami-model",
                        "object": "chat.completion",
                        "model": "hami-model",
                        "choices": [{
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": stripped},
                        }],
                    }
                    response_body = json.dumps(translated, ensure_ascii=False).encode("utf-8")
                    status = 200
                    content_type = "application/json"
                except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                    pass

                self._send_bytes(status, response_body, content_type)
            finally:
                upstream_lock.release()

        def send_error(
            self,
            code: int,
            message: str | None = None,
            explain: str | None = None,
        ) -> None:
            if code == HTTPStatus.NOT_IMPLEMENTED:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            super().send_error(code, message, explain)

    return GatewayHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded local hami-model gateway")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()
    if not args.secret:
        parser.error("--secret must not be empty")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        _make_handler(args.secret),
    )
    print(f"Hami model gateway listening on 127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
