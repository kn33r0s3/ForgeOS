"""Bound public write request bodies before JSON parsing or route execution."""

from fastapi.responses import JSONResponse

MAX_PUBLIC_WRITE_BODY_BYTES = 16 * 1024
_LIMITED_PATHS = {
    "/analyze",
    "/public/booking-requests",
    "/public/domain",
    "/signals/public-request",
}


def _is_limited_write(method: str, path: str) -> bool:
    if method != "POST":
        return False
    normalized = path.removeprefix("/api")
    if normalized == "/public/domain":
        return True
    if normalized in _LIMITED_PATHS:
        return True
    if not normalized.startswith("/public/domain/"):
        return False
    parts = normalized.strip("/").split("/")
    return (
        len(parts) == 4 and parts[3] in {"close", "dispute"}
    ) or (
        len(parts) == 6 and parts[3] == "connections" and parts[5] == "response"
    )


class PublicWriteSizeLimitMiddleware:
    """Enforce a 16 KiB body ceiling on selected anonymous POST endpoints."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not _is_limited_write(
            scope["method"].upper(), scope["path"]
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > MAX_PUBLIC_WRITE_BODY_BYTES:
                    await self._too_large(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )
                await response(scope, receive, send)
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > MAX_PUBLIC_WRITE_BODY_BYTES:
                await self._too_large(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if replayed:
                return {"type": "http.disconnect"}
            replayed = True
            return {
                "type": "http.request",
                "body": bytes(body),
                "more_body": False,
            }

        await self.app(scope, replay_receive, send)

    async def _too_large(self, scope, receive, send):
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body must be 16 KB or smaller."},
        )
        await response(scope, receive, send)
