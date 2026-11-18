import os
import subprocess
import sys
from pathlib import Path


from app.api.scheduled import run_scheduled_cycle
from app.config import settings
from starlette.requests import Request

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _scheduled_request(api_key=None):
    headers = [(b"x-api-key", api_key.encode())] if api_key else []
    return Request({"type": "http", "headers": headers})


def test_app_startup_does_not_import_legacy_intelligence_when_disabled():
    environment = os.environ.copy()
    environment["FORGEOS_LEGACY_INTELLIGENCE_ENABLED"] = "false"
    environment["DATABASE_URL"] = "sqlite:///:memory:"
    code = """
import sys
from sqlalchemy import inspect
from app import database
from app.main import on_startup
assert not inspect(database.engine).has_table("forge_bot_lead_contacts")
on_startup()
assert inspect(database.engine).has_table("forge_bot_lead_contacts")
targets = (
    "app.services.collectors",
    "app.services.collector_runner",
    "app.services.research_planner",
    "app.services.capability_discovery",
    "app.services.demand_understanding",
    "app.services.cycle_scheduler",
    "app.services.worker_manager",
)
loaded = [name for name in targets if name in sys.modules or any(
    module.startswith(name + ".") for module in sys.modules
)]
print("loaded legacy modules:", loaded)
assert not loaded
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "loaded legacy modules: []" in result.stdout


def test_scheduled_cycle_runs_maintenance_when_legacy_flag_is_disabled(
    monkeypatch, caplog
):
    caplog.set_level("INFO")
    monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", False)
    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    monkeypatch.setenv("CRON_SECRET", "test-only-cron-secret")
    from app.api import scheduled

    maintenance = {
        "inquiries_erased": 2,
        "expired_rate_limit_buckets_purged": 3,
    }
    monkeypatch.setattr(scheduled, "run_daily_maintenance", lambda db: maintenance)

    response = run_scheduled_cycle(
        request=_scheduled_request("test-owner-key"),
        authorization="Bearer test-only-cron-secret",
    )

    assert response == {
        "status": "disabled",
        "reason": "legacy cycle disabled",
        "maintenance": maintenance,
    }
    assert "legacy cycle disabled" in caplog.text


def test_scheduled_cycle_keeps_cron_authentication_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", True)
    monkeypatch.setenv("CRON_SECRET", "test-only-cron-secret")

    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as error:
        run_scheduled_cycle(request=_scheduled_request(), authorization=None)

    assert error.value.status_code == 401


def test_background_worker_exits_without_starting_when_disabled(monkeypatch, capsys):
    import worker

    monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", False)

    worker.run_forever(interval=1)

    assert "legacy intelligence disabled; worker will not start" in capsys.readouterr().out
