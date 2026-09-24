"""Vercel sends /api/health. The existing routes are /health and /public."""

from app.main import app as fastapi_app


class StripApiPrefix:
    def __init__(self, asgi):
        self.asgi = asgi

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path") or ""
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope)
                stripped = path[4:] or "/"
                scope["path"] = stripped
                scope["raw_path"] = stripped.encode()
        await self.asgi(scope, receive, send)


app = StripApiPrefix(fastapi_app)
