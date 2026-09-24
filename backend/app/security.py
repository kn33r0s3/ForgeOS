"""
SECURITY — optional API-key gate (Phase 26)

ForgeOS is local-first and ships with no auth by default so it "just works" on
a personal Mac. For anyone who exposes it (LAN, a production box, or a shared
host), a single env var enables a real gate: set FORGE_API_KEY and every
STATE-CHANGING (non-GET) request must present it via `X-API-Key` header or
`?api_key=` query param, or it's rejected 401. Read endpoints stay open so the
dashboard keeps working without friction when auth is off.

Design:
  * Additive + opt-in: nothing changes unless FORGE_API_KEY is set.
  * Stateless (no sessions/tokens to rotate or leak beyond the one key).
  * Constant-time comparison so a timing side-channel can't leak the key.
  * Explicit 401 with a clear body, never a silent skip.
"""

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

PUBLIC_WRITE_PATHS = {"/analyze", "/public/booking-requests", "/public/domain"}


def _enabled() -> bool:
    return bool(getattr(settings, "FORGE_API_KEY", ""))


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _authorized(request: Request) -> bool:
    key = settings.FORGE_API_KEY
    presented = request.headers.get("X-API-Key") or request.query_params.get("api_key") or ""
    return bool(presented) and _constant_time_eq(str(presented), str(key))


async def api_key_middleware(request: Request, call_next):
    """FastAPI BaseHTTPMiddleware. Only enforced for state-changing methods
    and ONLY when FORGE_API_KEY is set. The public analyze intake remains open
    to support self-serve problem capture without a secret."""
    if _enabled():
        method = request.method.upper()
        path = request.url.path
        allowed_write = path in PUBLIC_WRITE_PATHS or path.startswith("/public/domain/")
        if method in {"POST", "PUT", "PATCH", "DELETE"} and not allowed_write and not _authorized(request):
            # Allow the local dashboard to keep working read-only; protect writes.
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: missing or invalid X-API-Key for a state-changing request."},
            )
    return await call_next(request)
