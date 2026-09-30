import json
from pathlib import Path

import pytest

from fastapi.testclient import TestClient


def _health():
    from app.main import app

    return TestClient(app).get("/health")


def test_fastapi_startup_executes_with_isolated_database(db, monkeypatch):
    import app.database as database
    import app.main as main

    assert main.SessionLocal is not None
    monkeypatch.setattr(main, "SessionLocal", database.SessionLocal)

    with TestClient(main.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_local_health_is_ok_and_ready_without_vercel_requirements(db, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CRON_SECRET", raising=False)

    response = _health()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["driver"] == "sqlite"
    assert payload["database"]["durability"] == "configured"
    assert payload["database"]["url_configured"] is False
    assert payload["database"]["available"] is True
    assert payload["database"]["error"] is None
    assert payload["readiness"] == {"ready": True, "blockers": []}


def test_vercel_health_reports_ephemeral_database_and_missing_cron_secret(db, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CRON_SECRET", raising=False)

    response = _health()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"]["driver"] == "sqlite"
    assert payload["database"]["durability"] == "ephemeral"
    assert payload["database"]["url_configured"] is False
    assert payload["database"]["available"] is True
    assert payload["scheduler"]["cron_secret_configured"] is False
    assert payload["scheduler"]["cron_schedule"] == "0 0 * * *"
    assert payload["readiness"] == {
        "ready": False,
        "blockers": [
            "durable_database_not_configured",
            "cron_secret_not_configured",
        ],
    }


def test_health_reports_schedule_from_vercel_configuration(db, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    config_path = Path(__file__).resolve().parents[2] / "vercel.json"
    if not config_path.is_file():
        pytest.skip("vercel.json is absent: the Vercel API service/cron topology was removed in f240f3e and restoring it is an owner deployment decision (docs/CAPABILITY_QUEUE.md)")
    config = json.loads(config_path.read_text())

    assert _health().json()["scheduler"]["cron_schedule"] == config["crons"][0]["schedule"]


def test_health_never_returns_cron_secret_value(db, monkeypatch):
    secret = "health-must-not-return-this-secret-value"
    database_url = "postgresql://health-user:health-password@db.example.test/forge"
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("CRON_SECRET", secret)
    monkeypatch.setenv("DATABASE_URL", database_url)

    response = _health()

    assert response.status_code == 200
    assert response.json()["scheduler"]["cron_secret_configured"] is True
    assert secret not in response.text
    assert database_url not in response.text
    assert "health-password" not in response.text


def test_vercel_health_reports_safe_database_error_class(db, monkeypatch):
    from app import database

    class DatabaseUnavailable(Exception):
        pass

    def unavailable_session():
        raise DatabaseUnavailable("password=must-not-be-returned")

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://private-credentials")
    monkeypatch.setenv("CRON_SECRET", "private-cron-secret")
    monkeypatch.setattr(database, "SessionLocal", unavailable_session)

    response = _health()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"]["available"] is False
    assert payload["database"]["error"] == "DatabaseUnavailable"
    assert "must-not-be-returned" not in response.text
    assert "private-credentials" not in response.text
    assert "private-cron-secret" not in response.text
    assert payload["readiness"] == {
        "ready": False,
        "blockers": ["database_unavailable"],
    }
