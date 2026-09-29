"""
SECURITY — optional API-key gate (Phase 26)

ForgeOS is local-first and ships with no auth by default so it "just works" on
a personal Mac. For anyone who exposes it (LAN, a production box, or a shared
host), a single env var enables a real gate: set FORGE_API_KEY and every
state-changing request plus reads from the private substrate API must present
it via `X-API-Key` header or `?api_key=` query param, or it's rejected 401.
Other reads stay open so the dashboard keeps working without friction when
auth is off.

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

PUBLIC_WRITE_PATHS = {
    "/analyze",
    "/public/booking-requests",
    "/public/domain",
    "/signals/public-request",
    "/api/signals/public-request",
}


def _enabled() -> bool:
    return bool(getattr(settings, "FORGE_API_KEY", ""))


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _authorized(request: Request) -> bool:
    key = settings.FORGE_API_KEY
    presented = request.headers.get("X-API-Key") or request.query_params.get("api_key") or ""
    return bool(presented) and _constant_time_eq(str(presented), str(key))


async def api_key_middleware(request: Request, call_next):
    """Apply the optional key to writes and to private substrate reads.

    Other read endpoints stay open for the existing dashboard behavior. The
    substrate API exposes identity, provenance, and capability records, so it
    is protected when an API key is configured.
    """
    if _enabled():
        method = request.method.upper()
        path = request.url.path
        allowed_write = path in PUBLIC_WRITE_PATHS or path.startswith("/public/domain/")
        private_substrate_read = path.startswith(("/forge/substrate/", "/api/forge/substrate/"))
        state_change = method in {"POST", "PUT", "PATCH", "DELETE"} and not allowed_write
        if (state_change or private_substrate_read) and not _authorized(request):
            message = (
                "Unauthorized: missing or invalid X-API-Key for substrate access."
                if private_substrate_read
                else "Unauthorized: missing or invalid X-API-Key for a state-changing request."
            )
            return JSONResponse(
                status_code=401,
                content={"detail": message},
            )
    return await call_next(request)
