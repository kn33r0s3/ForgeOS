#!/usr/bin/env python3
"""Authenticated loopback gateway for the Vercel-side Hami chat route.

The existing route in backend/app/api/hami_chat.py runs outside this Mac and
cannot bind its loopback interface. This standalone process exposes only the
authenticated Ollama operations needed by that route.
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


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MAX_BODY_BYTES = 1_048_576
UPSTREAM_TIMEOUT_SECONDS = 120


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


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
                    f"{OLLAMA_BASE_URL}{path}",
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
                        f"Ollama request failed: {type(error).__name__}",
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
            if self.path != "/api/tags":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if self._is_authorized():
                self._proxy("GET", "/api/tags")

        def do_POST(self) -> None:
            if self.path != "/api/chat":
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
            if not isinstance(payload, dict) or payload.get("stream") is not False:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "stream_must_be_false"})
                return

            self._proxy("POST", "/api/chat", body)

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
    parser = argparse.ArgumentParser(description="Guarded local Ollama gateway")
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
    print(f"Hami Ollama gateway listening on 127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
