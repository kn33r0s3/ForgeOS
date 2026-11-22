"""Meet Hami chat endpoint — hami-model build (19 Nov 2026).

Lets the owner talk to Hami AI on the deployed site. The chat request is
forwarded to the owner's Mac hami-model server through a Cloudflare
quick tunnel that points at the guarded gateway (scripts/hami_model_gateway.py),
never at any other model directly. The gateway only allows
POST /api/hami-llm/chat and GET /api/hami-llm/status, requires the
X-Hami-Key header, and runs one generation at a time. Only hami-model is
used. If hami-model is down the endpoint reports
Hami as unavailable; it never falls back to another AI.

Set HAMI_CHAT_HOST and HAMI_CHAT_KEY in the deployment environment.
Both are required; the endpoint returns 503 when either is unset.

Checkpoint limits (honest):
- No database context is attached: the model answers from the prompt only,
  not from Hami's evidence store. Retrieval comes next.
- No actions are executed: this endpoint only chats. It cannot contact
  anyone, spend money, or change records.
- hami-model here is the MLX server (mlx-community/Qwen3-4B-4bit + the
  clean Nepali SFT adapter; see docs/HAMI_MODEL.md for the pinned identity
  line). The from-scratch TinyLM pilot is a separate experiment server and
  is not in this path. Treat fluency and factual answers as unreliable:
  the serving adapter has not passed all quality gates (notably the
  Sagarmatha height gate).
"""

import json
import os
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/hami", tags=["hami"])

MODEL = "hami-model"
TIMEOUT_SECONDS = 90
MAX_RESPONSE_BYTES = 1_048_576

HAMI_SYSTEM_PROMPT = (
"/no_think You are Hami, a living system built and maintained by Niroj Paudyal. You do what you are asked, from the prompt in front of you — no topic is outside your scope: essays, plans, maps, money, anything. "
    "Your north star: expand the frontier of what can be understood, discovered, created, "
    "coordinated, and accomplished in reality. Your purpose: remove unnecessary limits "
    "caused by ignorance, disconnection, inaccessible capability, missing coordination, "
    "and things that have not yet been created.\n\n"
    "Your principles: One Hami. Renovate, don't reinvent. Evidence first. REAL is not TEST. "
    "Authorization matters. Preserve behavior. Your six primitives are ENTITY, RELATION, "
    "EVENT, EVIDENCE, CAPABILITY, ACTION.\n\n"
    "Your gate: an intervention counts only when a real person gives something up for it "
    "(money, time, trust, or behavior) AND the affected humans authorized it. Work not "
    "tied to a changed outcome in reality is labelled unproven, never presented as "
    "achievement.\n\n"
    "Be honest and grounded. Never fabricate facts, figures, or sources. If you do not "
    "know something, say so plainly and say what would settle it. Distinguish what you "
    "know from evidence, what is reported, and what is only a hypothesis. Keep answers "
    "short and useful. You can speak Nepali (Devanagari or Romanized) when the owner "
    "does. You cannot contact anyone, spend money, or change any record — you only "
    "talk here; actions happen through the owner's tools."
)


class ChatMessage(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    model: str


def _gateway_url() -> str:
    return os.environ.get("HAMI_CHAT_HOST", "").strip().rstrip("/")


def _gateway_key() -> str:
    return os.environ.get("HAMI_CHAT_KEY", "").strip()


# CORS: the Hami Systems widget is embedded on other sites (Knee Rose, any
# site worldwide) via one script tag. The browser sends a preflight OPTIONS
# for the cross-origin JSON POST and blocks the reply unless this endpoint
# answers with CORS headers. Without them the widget fails fast with
# "unreachable" on every site except hami-sigma itself (same origin) — which
# is exactly what the Knee Rose live check showed 18 Nov ~20:22 (fast failure,
# no real reply, while the same endpoint answered fine same-origin). This is
# a public chat endpoint: allow any origin to read the reply. The gateway key
# stays server-side and is never in the browser, so allowing the origin does
# not expose any secret.
_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


@router.options("/chat")
def hami_chat_options():
    return Response(status_code=204, headers=_CORS_HEADERS)


@router.post("/chat", response_model=ChatResponse)
def hami_chat(payload: ChatRequest, response: Response):
    response.headers.update(_CORS_HEADERS)
    host = _gateway_url()
    gateway_key = _gateway_key()
    if not host or not gateway_key:
        raise HTTPException(
            status_code=503,
            detail="Hami chat is not configured; required environment variables are unset.",
            headers=_CORS_HEADERS,
        )
    # Send the system prompt and recent turns to the gateway. The gateway
    # forwards the full message list to the model server, so history does
    # condition the model output.
    messages: list[dict[str, str]] = [{"role": "system", "content": HAMI_SYSTEM_PROMPT}]
    for item in payload.history[-10:]:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": payload.message})
    body = json.dumps(
        {"model": MODEL, "messages": messages, "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{host}/api/hami-llm/chat",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hami-Key": gateway_key,
        },
        method="POST",
    )
    # The quick tunnel flaps (Cloudflare QUIC reconnects) and the gateway
    # serves one generation at a time, so a single attempt can hit a transient
    # 502 / connection drop even though the path is healthy. Retry fast
    # transient failures (up to 3 attempts). Never retry a timeout — it already
    # spent the full TIMEOUT_SECONDS — and never retry a non-transient HTTP
    # status (auth / bad request). The 502 observed 18 Nov ~19:10 was a tunnel
    # flap, not a dead tunnel: the gateway produced the reply but the caller
    # had already disconnected (BrokenPipeError in the gateway log).
    raw: bytes | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except urllib.error.HTTPError as exc:
            # The gateway answers 502 with upstream_unavailable when
            # hami-model itself is down: that is not a transient flap, it
            # is the model unavailable — report it at once, never retry
            # and never fall back to another AI.
            try:
                err_body = exc.read() or b""
            except Exception:
                err_body = b""
            if b"upstream_unavailable" in err_body:
                raise HTTPException(
                    status_code=503, detail="Hami is unavailable.", headers=_CORS_HEADERS
                ) from exc
            if exc.code in (502, 503, 504) and attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise HTTPException(
                status_code=502,
                detail=f"Hami AI answered with HTTP {exc.code}.",
                headers=_CORS_HEADERS,
            ) from exc
        except TimeoutError as exc:
            raise HTTPException(
                status_code=503, detail="Hami is unavailable.", headers=_CORS_HEADERS
            ) from exc
        except Exception as exc:
            # urllib wraps connect timeouts in URLError; a timeout already
            # spent the full TIMEOUT_SECONDS, so it is never retried (see the
            # comment above the loop). Read timeouts surface as TimeoutError
            # and are handled above.
            if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError):
                raise HTTPException(
                    status_code=503, detail="Hami is unavailable.", headers=_CORS_HEADERS
                ) from exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise HTTPException(
                status_code=503, detail="Hami is unavailable.", headers=_CORS_HEADERS
            ) from exc
    if raw is None:
        raise HTTPException(status_code=503, detail="Hami is unavailable.", headers=_CORS_HEADERS)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise HTTPException(status_code=502, detail="Hami AI's reply was too large.", headers=_CORS_HEADERS)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Hami AI returned an unreadable reply.", headers=_CORS_HEADERS
        ) from exc
    # The serving process answers with chat-completion choices.
    # The model field is the serving name, hami-model; the base + adapter
    # it is built on are reported by GET /api/hami-llm/status and in docs.
    choices = data.get("choices") if isinstance(data, dict) else None
    reply = None
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict) and isinstance(first.get("message"), dict):
            reply = first["message"].get("content")
    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(status_code=502, detail="Hami AI returned an empty reply.", headers=_CORS_HEADERS)
    stripped = reply.strip()
    for size in range(2, 40):
        unit = stripped[-size:]
        if len(stripped) >= size * 3 and stripped.endswith(unit * 3):
            raise HTTPException(status_code=502, detail="Hami AI returned a looping reply.", headers=_CORS_HEADERS)
    if len(stripped) >= 20:
        tail = stripped[-20:]
        if len(set(tail)) <= 3:
            raise HTTPException(status_code=502, detail="Hami AI returned a looping reply.", headers=_CORS_HEADERS)
    return ChatResponse(reply=reply.strip(), model=MODEL)
