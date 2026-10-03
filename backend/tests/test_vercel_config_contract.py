"""Deployment contract between vercel.json and the FastAPI application.

vercel.json was deleted in f240f3e, which silently took the production API and
daily cycle offline (every /api/* answered Vercel 404). These tests make the
file's existence and its routing/cron contract part of the backend suite, and
check that every path it relies on is actually served by ``app.main:app``.
They read configuration and route tables only; no cycle is run.
"""

import importlib
import json
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Match

from app.database import get_db

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "vercel.json"


def _config():
    assert CONFIG_PATH.is_file(), "vercel.json must exist at the repository root"
    return json.loads(CONFIG_PATH.read_text())


def _serves_get(app, path):
    """Match ``path`` against the app's route table without invoking it.

    FastAPI nests included routers, so ``app.routes`` is not a flat path list;
    Starlette matching is what the ASGI app itself does per request.
    """
    scope = {"type": "http", "path": path, "method": "GET", "root_path": "", "query_string": b"", "headers": []}
    return any(route.matches(scope)[0] == Match.FULL for route in app.router.routes)


def test_vercel_services_route_api_to_fastapi_and_everything_else_to_web():
    config = _config()
    assert config["services"] == {
        "web": {
            "root": ".",
            "framework": "vite",
            "installCommand": "npm install",
            "buildCommand": "npm run build",
        },
        "api": {
            "root": "backend/",
            "framework": "fastapi",
            "entrypoint": "app.main:app",
        },
    }
    # Better Auth belongs to the web service; its specific route precedes FastAPI and the catch-all.
    assert config["rewrites"] == [
        {"source": "/api/auth/(.*)", "destination": {"service": "web"}},
        {"source": "/api/(.*)", "destination": {"service": "api"}},
        {"source": "/(.*)", "destination": {"service": "web"}},
    ]


def test_vercel_cron_targets_the_gated_daily_cycle():
    config = _config()
    assert config["crons"] == [{"path": "/api/scheduled/cycle", "schedule": "0 0 * * *"}]
    from app.main import CRON_SCHEDULE

    assert CRON_SCHEDULE == config["crons"][0]["schedule"]


def test_api_entrypoint_imports_and_serves_the_paths_vercel_relies_on():
    config = _config()
    backend_root = (ROOT / config["services"]["api"]["root"]).resolve()
    assert (backend_root / "app" / "main.py").is_file()
    module_name, attribute = config["services"]["api"]["entrypoint"].split(":")
    app = getattr(importlib.import_module(module_name), attribute)

    for cron in config["crons"]:
        assert _serves_get(app, cron["path"]), cron["path"]
    for path in (
        "/api/health",
        "/api/public/feed",
        "/api/public/network",
        "/api/public/providers",
        "/api/public/discoveries",
    ):
        assert _serves_get(app, path), path
    # Negative control: matching is not vacuous.
    assert not _serves_get(app, "/api/public/not-a-route")
    assert not _serves_get(app, "/api/not-a-router")

    # The cron path resolves to the legacy-gated scheduled-cycle handler.
    from app.api import scheduled

    handlers = {
        (route.path, method): route.endpoint.__name__
        for route in scheduled.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert handlers[("/scheduled/cycle", "GET")] == "run_scheduled_cycle"


def test_api_health_and_public_feed_answer_under_the_api_prefix(db, monkeypatch):
    from app import security
    from app.main import app

    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        assert health.json() == {"status": "ok", "ready": True}
        feed = client.get("/api/public/feed")
        assert feed.status_code == 200, feed.text
    finally:
        app.dependency_overrides.clear()
