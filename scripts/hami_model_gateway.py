#!/usr/bin/env python3
"""Authenticated loopback gateway for the Vercel-side Hami chat route.

The existing route in backend/app/api/hami_chat.py runs outside this Mac and
cannot bind its loopback interface. This standalone process exposes only the
authenticated Hami-model operations needed by that route, plus the research
endpoint (POST /api/hami-llm/research, Phase 2) which runs the existing
ForgeOS research planner/discovery/collectors against a local SQLite
research store. No borrowed model or external fallback is allowed.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HAMI_MODEL_BASE_URL = "http://127.0.0.1:11437"
HAMI_MODEL_ID = "hami-model"
MAX_BODY_BYTES = 1_048_576
UPSTREAM_TIMEOUT_SECONDS = 120

# Research endpoint (Phase 2, 22 Nov 2026): POST /api/hami-llm/research.
# Runs the EXISTING ForgeOS research planner/discovery/collectors (the
# backend tree on disk — never a second loop) against a SQLite research
# store under ~/hami. The backend is imported lazily so a research
# failure can never break the plain chat path: if the import fails (for
# example the gateway process cannot read ~/Downloads/ForgeOS), the
# endpoint answers 503 research_unavailable with the honest reason.
RESEARCH_BACKEND_PATH = "/Users/nirojpaudyal/Downloads/ForgeOS/backend"
RESEARCH_DB_URL = "sqlite:////Users/nirojpaudyal/hami/hami-research/research.db"
RESEARCH_MAX_TOOL_ROUNDS = 3

# Self-train slice 1 (21 Nov 2026): every chat turn is logged as a seed, and
# every non-answer (looped / empty / refused) is also logged as a gap.
# Seeds are raw material only — unverified seeds never enter train.jsonl.
# Logging must NEVER break the reply path: writes are try/except-guarded
# and a failure is a stderr line only, never a 500 to the user.
SEED_LOG_PATH = os.path.expanduser("~/hami/chat-seeds.jsonl")
GAP_LOG_PATH = os.path.expanduser("~/hami/chat-gaps.jsonl")

REFUSAL_MARKERS = (
    "i can't",
    "i cannot",
    "i'm unable",
    "i am unable",
    "i won't",
    "i will not",
    "unable to help",
    "can't help",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: str, record: dict) -> None:
    """Append one JSON line. Never raises — a logging failure is silent."""
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        print(
            f"seed log write failed: {type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )


def _classify_outcome(reply: str, looped: bool) -> str:
    if looped:
        return "looped"
    if not reply.strip():
        return "empty"
    lowered = reply.lower()
    if any(marker in lowered for marker in REFUSAL_MARKERS):
        return "refused"
    return "answered"


def _log_seed(
    *,
    prompt: str,
    reply: str,
    latency_ms: int,
    guard: bool,
    outcome: str,
) -> None:
    _append_jsonl(SEED_LOG_PATH, {
        "ts": _utc_now_iso(),
        "prompt": prompt,
        "reply": reply,
        "model": HAMI_MODEL_ID,
        "latency_ms": latency_ms,
        "guard": guard,
        "outcome": outcome,
    })
    if outcome in ("looped", "empty", "refused"):
        _append_jsonl(GAP_LOG_PATH, {
            "ts": _utc_now_iso(),
            "prompt": prompt,
            "outcome": outcome,
            "reply_excerpt": reply[:200],
        })


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


_RESEARCH_BACKEND: dict | None = None
_RESEARCH_BACKEND_ERROR: str | None = None


def _load_research_backend() -> dict:
    """Import the ForgeOS backend once, for the research endpoint.

    The planner, discovery engine and collectors are the existing
    machinery in the repo on disk; the gateway only adds a sys.path
    entry and a research SQLite URL, then calls them. Imported lazily
    and cached per process so a research failure never touches chat.
    Raises RuntimeError with the honest reason when the import fails.
    """
    global _RESEARCH_BACKEND, _RESEARCH_BACKEND_ERROR
    if _RESEARCH_BACKEND is not None:
        return _RESEARCH_BACKEND
    if _RESEARCH_BACKEND_ERROR is not None:
        raise RuntimeError(_RESEARCH_BACKEND_ERROR)
    try:
        if RESEARCH_BACKEND_PATH not in sys.path:
            sys.path.insert(0, RESEARCH_BACKEND_PATH)
        os.environ.setdefault("DATABASE_URL", RESEARCH_DB_URL)
        import app.database as database
        from app import models
        from app.services import collector_runner, research_planner
        from app.services.hami_research import tools as research_tools

        database.Base.metadata.create_all(bind=database.engine)
        _RESEARCH_BACKEND = {
            "database": database,
            "models": models,
            "collector_runner": collector_runner,
            "research_planner": research_planner,
            "research_tools": research_tools,
        }
        return _RESEARCH_BACKEND
    except Exception as exc:
        _RESEARCH_BACKEND_ERROR = f"{type(exc).__name__}: {exc}"
        raise RuntimeError(_RESEARCH_BACKEND_ERROR) from exc


def _run_research(question_text: str) -> dict:
    """Run the planner path for one question against the research store.

    Creates (or reuses, by unique question text) a ResearchQuestion row,
    builds the plan, plans tasks, executes web_search tasks through the
    collector runner, and returns the persisted Evidence rows as sources.
    research_used False means the planner found no current-fact
    requirement: the caller falls back to plain chat.
    """
    backend = _load_research_backend()
    database = backend["database"]
    models = backend["models"]
    research_planner = backend["research_planner"]
    collector_runner = backend["collector_runner"]
    db = database.SessionLocal()
    try:
        question = (
            db.query(models.ResearchQuestion)
            .filter_by(question=question_text)
            .one_or_none()
        )
        if question is None:
            question = models.ResearchQuestion(
                question=question_text, priority_score=50.0, status="open"
            )
            db.add(question)
            db.commit()
        plan = research_planner.build_research_plan(db, question)
        search_requirements = [
            req
            for req in plan.get("requirements", [])
            if req.get("id") == "general_web_search"
        ]
        if not search_requirements:
            return {
                "research_used": False,
                "reason": "planner found no current-fact requirement",
            }
        if not any(
            req.get("selected_capability") is not None
            for req in search_requirements
        ):
            # The question needs current facts but the search provider is
            # down: report the failure honestly, never fall back to a
            # plain-chat answer that pretends no search was needed.
            return {
                "research_used": True,
                "answer": None,
                "reason": (
                    "Search is unavailable right now: the local SearXNG "
                    "instance did not answer, so no search ran and no "
                    "sources were used. I cannot verify current facts "
                    "until it is back."
                ),
                "sources": [],
                "evidence_ids": [],
            }
        tasks = research_planner.plan_tasks_for_question(db, question)
        sources: list[dict] = []
        for task in tasks:
            if task.source != "web_search":
                continue
            result = collector_runner.execute_task(db, task)
            if result.get("status") != "completed":
                continue
            ids = [
                int(value)
                for value in (task.evidence_ids or "").split(",")
                if value.strip().isdigit()
            ]
            if not ids:
                continue
            rows = (
                db.query(models.Evidence)
                .filter(models.Evidence.id.in_(ids))
                .order_by(models.Evidence.id)
                .all()
            )
            for row in rows:
                sources.append(
                    {
                        "title": row.title,
                        "url": row.canonical_url,
                        "snippet": (row.content or "")[:500],
                        "published_at": (
                            row.published_at.isoformat()
                            if row.published_at is not None
                            else None
                        ),
                        "evidence_id": row.id,
                    }
                )
        if not sources:
            return {
                "research_used": True,
                "answer": None,
                "reason": "search ran but returned no usable evidence",
                "sources": [],
                "evidence_ids": [],
            }
        return {
            "research_used": True,
            "answer": None,
            "sources": sources,
            "evidence_ids": [item["evidence_id"] for item in sources],
        }
    finally:
        db.close()


def _is_looped_reply(text: str) -> bool:
    """Same loop guard as the chat path: a repeated tail means the adapter looped."""
    stripped = text.strip()
    for size in range(2, 40):
        unit = stripped[-size:]
        if len(stripped) >= size * 3 and stripped.endswith(unit * 3):
            return True
    return False


# Routing hint only, mirroring research_planner._needs_general_web_search
# (the canonical copy). Used solely to decide whether a follow-up inherits
# an earlier turn's research context. The planner re-checks through the
# requirement specs, so a mismatch here only costs a round-trip, never a
# wrong answer.
_RESEARCH_PATTERN = re.compile(
    r"\b(?:today|current|latest|recent|now|happening|news|"
    r"inflation|price|rate|versus|vs\.?|compare|"
    r"what happened|is happening|source for|verif\w*|is it true)\b",
    re.I,
)
_NEPALI_CURRENT_PATTERN = re.compile(
    r"\b(आज|हाल|ताजा|समाचार|मुद्रास्फीति|मूल्य|दर|अर्थतन्त्र)\b"
)


def _message_needs_research(text: str) -> bool:
    return bool(
        _RESEARCH_PATTERN.search(text) or _NEPALI_CURRENT_PATTERN.search(text)
    )


def _extractive_research_answer(sources: list[dict]) -> str:
    """Fallback answer when model synthesis fails: the evidence verbatim,
    with its sources. Never empty — the policy is to report the search
    result honestly, not to return nothing because a tool failed."""
    parts = []
    for index, source in enumerate(sources[:5], start=1):
        title = source.get("title") or source.get("url") or "untitled"
        parts.append(
            f"[{index}] {title} ({source.get('url')}): "
            f"{source.get('snippet') or ''}"
        )
    return "Here is what the search found:\n" + "\n".join(parts)


class _UpstreamUnavailable(Exception):
    """The pilot server could not be reached (connect error or timeout)."""


def _encode_body(body_dict: dict) -> bytes:
    return json.dumps(
        body_dict, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


# Tools the gateway will execute for the model (Phase 2, step 3): the
# read-only rung-1 tools only. No money, send, sign, or delete tool exists.
_EXECUTABLE_TOOLS = frozenset({"web_search", "fetch_page"})


def _valid_request_tools(value: object) -> list[dict]:
    """Keep only well-formed, executable tool definitions from the caller."""
    if not isinstance(value, list):
        return []
    kept: list[dict] = []
    for item in value:
        if not isinstance(item, dict) or item.get("type") != "function":
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        if function.get("name") not in _EXECUTABLE_TOOLS:
            continue
        kept.append(item)
    return kept


def _extract_tool_calls(response_body: bytes) -> list[dict] | None:
    """Return the model's tool_calls from an upstream response, or None."""
    try:
        upstream = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    choices = upstream.get("choices") if isinstance(upstream, dict) else None
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return None
    return tool_calls


def _execute_tool_calls(tool_calls: list[dict], research_tools) -> list[dict]:
    """Execute the model's tool calls deterministically (read-only tools).

    Each result goes back as a tool message. Bad arguments are reported
    to the model as an error result — never invented, never silent.
    """
    messages: list[dict] = []
    for call in tool_calls:
        call_id = call.get("id") if isinstance(call, dict) else None
        function = call.get("function") if isinstance(call, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        raw_arguments = function.get("arguments") if isinstance(function, dict) else None
        try:
            arguments = (
                json.loads(raw_arguments)
                if isinstance(raw_arguments, str)
                else raw_arguments or {}
            )
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be an object")
        except (ValueError, json.JSONDecodeError) as exc:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(
                        {"error": f"invalid tool arguments: {exc}"}
                    ),
                }
            )
            continue
        if name == "web_search":
            if not isinstance(arguments.get("query"), str) or not arguments["query"].strip():
                result = {"error": "web_search needs a non-empty 'query' string"}
            else:
                result = research_tools.web_search(
                    arguments["query"],
                    max_results=int(arguments.get("max_results", 5) or 5),
                )
        elif name == "fetch_page":
            if not isinstance(arguments.get("url"), str) or not arguments["url"].strip():
                result = {"error": "fetch_page needs a non-empty 'url' string"}
            else:
                result = research_tools.fetch_page(arguments["url"])
        else:
            result = {"error": f"tool not available: {name}"}
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
    return messages


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

        def _model_completion(
            self, openai_messages: list[dict], max_tokens: int
        ) -> str | None:
            """One upstream chat call under the lock. The stripped answer, or None."""
            if not upstream_lock.acquire(blocking=False):
                return None
            try:
                body = _encode_body(
                    {
                        "model": "hami-pilot",
                        "messages": openai_messages,
                        "stream": False,
                        "max_tokens": max_tokens,
                        "temperature": 0,
                    }
                )
                request = urllib.request.Request(
                    f"{HAMI_MODEL_BASE_URL}/v1/chat/completions",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(
                        request, timeout=UPSTREAM_TIMEOUT_SECONDS
                    ) as response:
                        upstream = json.loads(response.read().decode("utf-8"))
                except (
                    urllib.error.HTTPError,
                    urllib.error.URLError,
                    TimeoutError,
                    ValueError,
                    json.JSONDecodeError,
                ):
                    return None
                choices = upstream.get("choices") if isinstance(upstream, dict) else None
                answer = (
                    choices[0].get("message", {}).get("content")
                    if isinstance(choices, list)
                    and choices
                    and isinstance(choices[0], dict)
                    else None
                )
                if (
                    not isinstance(answer, str)
                    or not answer.strip()
                    or _is_looped_reply(answer)
                ):
                    return None
                return answer.strip()
            finally:
                upstream_lock.release()

        def _synthesize_research(
            self, question: str, sources: list[dict], max_tokens: int
        ) -> str | None:
            """One pilot call: answer ONLY from the evidence below, with [n] cites."""
            lines = []
            for index, source in enumerate(sources[:8], start=1):
                lines.append(
                    f"[{index}] {source.get('title') or source.get('url')}\n"
                    f"{source.get('url')}\n"
                    f"{source.get('snippet') or ''}"
                )
            evidence_text = "\n\n".join(lines)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Hami, a Nepal-origin living system built and "
                        "maintained by Niroj Paudyal. Answer ONLY from the "
                        "evidence below. Cite sources as [1], [2]. If the "
                        "evidence does not cover the question, say so plainly. "
                        "Never invent facts, figures, or sources. Keep it short "
                        "and useful."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\nEvidence:\n{evidence_text}\n\n"
                        "Answer with citations."
                    ),
                },
            ]
            return self._model_completion(messages, max_tokens)

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
            started = time.monotonic()
            if self.path not in ("/api/hami-llm/chat", "/api/hami-llm/research"):
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
                identity_reply = translated["choices"][0]["message"]["content"]
                _log_seed(
                    prompt=user_message,
                    reply=identity_reply,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    guard=True,
                    outcome=_classify_outcome(identity_reply, looped=False),
                )
                self._send_json(
                    HTTPStatus.OK,
                    translated,
                )
                return
            # Niroj (22 Nov 21:40): unlimited and free. No token cap — the
            # model generates until it stops on its own. Backstops are the
            # 120 s upstream timeout and the loop detector below; the run
            # is still $0 (local pilot on the owner's Mac, no paid API).
            try:
                requested = payload.get("max_tokens")
                max_tokens = int(requested) if requested is not None else 8192
                if max_tokens < 1:
                    max_tokens = 8192
            except (TypeError, ValueError):
                max_tokens = 8192

            # Research path (Phase 2): the planner runs first. When it finds
            # no current-fact requirement, research_used is False and the
            # request falls through to the plain chat flow below — the
            # gateway, not the caller, is the authority on whether research
            # ran. When research ran, the answer is synthesized from the
            # persisted Evidence rows, never from the model's memory alone.
            if self.path == "/api/hami-llm/research":
                # Follow-ups: the last message alone may not trigger
                # research ("And what was it last year?"), but an earlier
                # user turn in this conversation did. Combine the earlier
                # question with the follow-up as the search question.
                research_question = user_message
                if not _message_needs_research(user_message):
                    for message in reversed(messages):
                        if (
                            isinstance(message, dict)
                            and message.get("role") == "user"
                            and isinstance(message.get("content"), str)
                            and _message_needs_research(message["content"])
                        ):
                            research_question = (
                                message["content"].strip() + " " + user_message
                            )
                            break
                try:
                    research_result = _run_research(research_question)
                except RuntimeError as exc:
                    self._send_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {"error": "research_unavailable", "detail": str(exc)},
                    )
                    return
                if research_result.get("research_used"):
                    sources = research_result.get("sources") or []
                    if sources:
                        answer = self._synthesize_research(
                            research_question, sources, max_tokens
                        )
                        if answer is None:
                            answer = _extractive_research_answer(sources)
                    else:
                        answer = research_result.get("reason") or (
                            "I searched for this, but found no usable "
                            "evidence to answer from."
                        )
                    research_payload = {
                        "id": "hami-model",
                        "object": "chat.completion",
                        "model": "hami-model",
                        "choices": [{
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": answer},
                        }],
                        "research_used": True,
                        "sources": sources,
                        "evidence_ids": research_result.get("evidence_ids") or [],
                    }
                    _log_seed(
                        prompt=user_message,
                        reply=answer,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        guard=False,
                        outcome=_classify_outcome(answer, looped=False),
                    )
                    self._send_json(HTTPStatus.OK, research_payload)
                    return
                # No current-fact requirement: fall through to plain chat.

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
            body_dict = {
                "model": "hami-pilot",
                "messages": openai_messages,
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": 0,
            }

            # The pilot can loop on prompts. Never relay a looped
            # answer to a chat surface.
            if not upstream_lock.acquire(blocking=False):
                self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "busy"})
                return
            try:
                def call_upstream(body_bytes: bytes) -> tuple[int, str, bytes]:
                    """One upstream POST. Returns (status, content_type, body).

                    Raises _UpstreamUnavailable on connect/timeout failure.
                    """
                    request = urllib.request.Request(
                        f"{HAMI_MODEL_BASE_URL}/v1/chat/completions",
                        data=body_bytes,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(
                            request, timeout=UPSTREAM_TIMEOUT_SECONDS
                        ) as response:
                            return (
                                response.status,
                                response.headers.get(
                                    "Content-Type", "application/json"
                                ),
                                response.read(),
                            )
                    except urllib.error.HTTPError as error:
                        return (
                            error.code,
                            error.headers.get(
                                "Content-Type", "application/json"
                            ),
                            error.read(),
                        )
                    except (urllib.error.URLError, TimeoutError) as exc:
                        raise _UpstreamUnavailable() from exc

                # Tool definitions at inference time (Phase 2, step 3): when
                # the caller supplies tools, they are forwarded to the model;
                # when the model returns tool_calls, this deterministic layer
                # executes them (read-only rung-1 tools only) and feeds the
                # results back, up to RESEARCH_MAX_TOOL_ROUNDS rounds. The
                # model decides; the layer executes; the two never mix.
                # If the research backend cannot load, the tools are dropped
                # and the model answers unaided rather than failing the chat.
                request_tools = _valid_request_tools(payload.get("tools"))
                research_tools = None
                if request_tools:
                    try:
                        research_tools = _load_research_backend()["research_tools"]
                    except RuntimeError as exc:
                        print(
                            f"tools unavailable, answering unaided: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                        request_tools = []
                if request_tools:
                    body_dict["tools"] = request_tools
                try:
                    status, content_type, response_body = call_upstream(
                        _encode_body(body_dict)
                    )
                except _UpstreamUnavailable:
                    self._send_json(
                        HTTPStatus.BAD_GATEWAY, {"error": "upstream_unavailable"}
                    )
                    return
                if request_tools:
                    for _ in range(RESEARCH_MAX_TOOL_ROUNDS):
                        tool_calls = _extract_tool_calls(response_body)
                        if not tool_calls:
                            break
                        tool_messages = _execute_tool_calls(
                            tool_calls, research_tools
                        )
                        openai_messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": tool_calls,
                            }
                        )
                        openai_messages.extend(tool_messages)
                        body_dict["messages"] = openai_messages
                        try:
                            status, content_type, response_body = call_upstream(
                                _encode_body(body_dict)
                            )
                        except _UpstreamUnavailable:
                            self._send_json(
                                HTTPStatus.BAD_GATEWAY,
                                {"error": "upstream_unavailable"},
                            )
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
                        _log_seed(
                            prompt=user_message,
                            reply=answer if isinstance(answer, str) else "",
                            latency_ms=int((time.monotonic() - started) * 1000),
                            guard=False,
                            outcome="empty",
                        )
                        self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_empty"})
                        return
                    stripped = answer.strip()
                    # No second identity check here: an identity question was
                    # already answered above, before any upstream call, so
                    # this point is only reached for non-identity messages.
                    for size in range(2, 40):
                        unit = stripped[-size:]
                        if len(stripped) >= size * 3 and stripped.endswith(unit * 3):
                            _log_seed(
                                prompt=user_message,
                                reply=stripped,
                                latency_ms=int((time.monotonic() - started) * 1000),
                                guard=False,
                                outcome="looped",
                            )
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
                    _log_seed(
                        prompt=user_message,
                        reply=stripped,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        guard=False,
                        outcome=_classify_outcome(stripped, looped=False),
                    )
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
