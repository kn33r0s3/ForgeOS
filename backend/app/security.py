"""
SECURITY — optional API-key gate (Phase 26)

ForgeOS is local-first and ships with no auth by default for personal development.
A deployed runtime (Vercel or NODE_ENV=production) fails closed on state-changing
requests and private substrate/contact reads if FORGE_API_KEY is missing; when
configured, those paths require X-API-Key. Explicitly allowlisted public submissions
and public reads remain open.

Design:
  * Local-first by default; deployed runtimes fail closed for privileged paths.
  * Stateless (no sessions/tokens to rotate or leak beyond the one key).
  * Constant-time comparison so a timing side-channel can't leak the key.
  * Explicit 401 for a bad key and 503 for missing deployed configuration.
"""

import hmac
import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings

PUBLIC_WRITE_PATHS = {
    "/analyze",
    "/api/analyze",
    "/public/booking-requests",
    "/api/public/booking-requests",
    "/public/domain",
    "/api/public/domain",
    "/forge-bot/leads",
    "/forge-bot/leads/opt-out",
    "/forge-bot/leads/delete",
    "/api/forge-bot/leads",
    "/api/forge-bot/leads/opt-out",
    "/api/forge-bot/leads/delete",
    "/signals/public-request",
    "/api/signals/public-request",
}
PRIVATE_CONTACT_READ_PATH_PREFIXES = (
    "/products/customers",
    "/products/pipeline",
    "/repair-shop/work-items",
    "/forge-bot/leads/summary",
    "/forge-bot/response-authorization",
    "/forge-bot/leads",
    # /orchestrate/flow embeds customer_events rows with contact_name and
    # contact_identifier (orchestrator._row dumps every column), so the
    # public /orchestrate/flow* reads carry the same contact PII as
    # /products/customers and must be key-gated in production.
    "/orchestrate/flow",
)


def _enabled() -> bool:
    return bool(getattr(settings, "FORGE_API_KEY", ""))


def _deployed_runtime() -> bool:
    """Treat Vercel and explicit production runtimes as fail-closed deployments."""
    vercel = os.getenv("VERCEL", "").strip().lower()
    node_env = os.getenv("NODE_ENV", "").strip().lower()
    return vercel not in {"", "0", "false", "no"} or node_env == "production"


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _authorized(request: Request) -> bool:
    key = settings.FORGE_API_KEY
    presented = request.headers.get("X-API-Key", "")
    return bool(presented) and _constant_time_eq(str(presented), str(key))


def require_owner_api_key(request: Request) -> None:
    """Require the owner key even when the optional global gate is disabled."""
    if not _enabled():
        raise HTTPException(
            status_code=503,
            detail="Owner access is unavailable until FORGE_API_KEY is configured.",
        )
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Valid X-API-Key required.")


def _public_payment_reconciliation_path(path: str) -> bool:
    """Allow only the two attempt-bound public payment recovery POST routes.

    The routes prove possession of a high-entropy public intent reference or the
    original checkout idempotency key and enforce their own rate limit. Checkout
    initiation and broader /payments/* paths are deliberately not allowlisted.
    """
    normalized = path.removeprefix("/api")
    parts = normalized.strip("/").split("/")
    if (
        len(parts) == 4
        and parts[0] == "payments"
        and parts[1] == "intent"
        and parts[3] == "reconcile"
    ):
        return 16 <= len(parts[2]) <= 128
    if (
        len(parts) == 5
        and parts[0] == "payments"
        and parts[1] == "products"
        and parts[2].isascii()
        and parts[2].isdigit()
        and parts[3] == "checkout"
        and parts[4] == "reconcile"
    ):
        return True
    return False


def _forge_bot_owner_route(path: str) -> bool:
    normalized = path.removeprefix("/api")
    return (
        normalized.startswith("/forge-bot/owner/")
        or normalized in {
            "/forge-bot/owner-notification/test-send",
            "/forge-bot/response-authorization",
            "/forge-bot/response-actions",
            "/forge-bot/leads/summary",
        }
        or normalized.startswith("/forge-bot/response-actions/")
        or (
            normalized.startswith("/forge-bot/leads/")
            and normalized.endswith("/response-readiness")
        )
    )


async def api_key_middleware(request: Request, call_next):
    """Apply the optional key to writes and private contact/substrate reads.

    Public projections and local-first reads stay open. Customer-event and
    repair-work-item reads contain contact details and require the configured
    key when one is present.
    """
    key_configured = _enabled()
    if key_configured or _deployed_runtime():
        method = request.method.upper()
        path = request.url.path
        allowed_write = (
            path in PUBLIC_WRITE_PATHS
            or path.startswith("/public/domain/")
            or path.startswith("/api/public/domain/")
            or _public_payment_reconciliation_path(path)
        )
        private_substrate_read = path.startswith(("/forge/substrate/", "/api/forge/substrate/"))
        owner_guarded_forge_bot_route = _forge_bot_owner_route(path)
        private_contact_read = method in {"GET", "HEAD"} and any(
            path == prefix
            or path.startswith(f"{prefix}/")
            or path == f"/api{prefix}"
            or path.startswith(f"/api{prefix}/")
            for prefix in PRIVATE_CONTACT_READ_PATH_PREFIXES
        )
        state_change = method in {"POST", "PUT", "PATCH", "DELETE"} and not allowed_write
        requires_key = (
            (state_change and not owner_guarded_forge_bot_route)
            or private_substrate_read
            or (private_contact_read and not owner_guarded_forge_bot_route)
        )
        if requires_key:
            if not key_configured:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": "FORGE_API_KEY must be configured before deployed private or state-changing API access is enabled."
                    },
                )
            if not _authorized(request):
                if private_substrate_read:
                    message = "Unauthorized: missing or invalid X-API-Key for substrate access."
                elif private_contact_read:
                    message = "Unauthorized: missing or invalid X-API-Key for private customer data."
                else:
                    message = "Unauthorized: missing or invalid X-API-Key for a state-changing request."
                return JSONResponse(status_code=401, content={"detail": message})
    return await call_next(request)
