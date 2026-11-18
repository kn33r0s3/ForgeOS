"""Meet Hami chat endpoint — checkpoint build (16 Nov 2026).

Lets the owner talk to Hami AI on the deployed site. The chat request is
forwarded to the owner's Mac Ollama (gpt-oss:20b) through a Cloudflare
quick tunnel that points at the guarded gateway (scripts/hami_ollama_gateway.py),
never at Ollama directly. The gateway only allows POST /api/chat and
GET /api/tags, requires the X-Hami-Key header, and runs one generation at
a time — so the public tunnel can never delete, pull, or create models.

Set HAMI_CHAT_OLLAMA_HOST and HAMI_CHAT_KEY in the deployment environment.
Both are required; the endpoint returns 503 when either is unset.

Checkpoint limits (honest):
- No database context is attached: the model answers from the system
  prompt only, not from Hami's evidence store. Retrieval comes next.
- No actions are executed: this endpoint only chats. It cannot contact
  anyone, spend money, or change records.
"""

import json
import os
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/hami", tags=["hami"])

MODEL = "gpt-oss:20b"
TIMEOUT_SECONDS = 90
MAX_RESPONSE_BYTES = 1_048_576

HAMI_SYSTEM_PROMPT = (
    "You are Hami, a living system for understanding and acting on Nepal's economy. "
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
    return os.environ.get("HAMI_CHAT_OLLAMA_HOST", "").strip().rstrip("/")


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
        )
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
        f"{host}/api/chat",
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
            if exc.code in (502, 503, 504) and attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise HTTPException(
                status_code=502, detail=f"Hami AI answered with HTTP {exc.code}."
            ) from exc
        except TimeoutError as exc:
            raise HTTPException(
                status_code=502, detail="Could not reach Hami AI (TimeoutError)."
            ) from exc
        except Exception as exc:
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise HTTPException(
                status_code=502, detail=f"Could not reach Hami AI ({type(exc).__name__})."
            ) from exc
    if raw is None:
        raise HTTPException(status_code=502, detail="Could not reach Hami AI.")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise HTTPException(status_code=502, detail="Hami AI's reply was too large.")
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Hami AI returned an unreadable reply."
        ) from exc
    reply = data.get("message", {}).get("content") if isinstance(data, dict) else None
    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(status_code=502, detail="Hami AI returned an empty reply.")
    return ChatResponse(reply=reply.strip(), model=MODEL)
