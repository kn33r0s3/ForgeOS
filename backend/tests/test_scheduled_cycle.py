from fastapi.testclient import TestClient

from app.api import scheduled
from app.main import app


def test_scheduled_cycle_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    client = TestClient(app)

    response = client.get("/scheduled/cycle", headers={"Authorization": "Bearer anything"})
    api_response = client.get("/api/scheduled/cycle", headers={"Authorization": "Bearer anything"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Scheduled cycle is not configured"}
    assert api_response.status_code == 503


def test_scheduled_cycle_requires_bearer_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    client = TestClient(app)

    response = client.get("/scheduled/cycle")

    assert response.status_code == 401


def test_scheduled_cycle_runs_canonical_runner(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda: {"forge_cycle": {"cycle_id": 27}, "autonomy_cycle": {"status": "ok"}},
    )
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "cycle_id": 27,
        "forge_cycle_failed": False,
        "autonomy_cycle_failed": False,
    }


def test_scheduled_cycle_reports_runner_failure(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda: {"forge_cycle_error": "details stay private", "autonomy_cycle": {"status": "ok"}},
    )
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "The canonical cycle reported a failure"}


def test_scheduled_cycle_reports_timeout_as_incomplete(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda: {"status": "timeout"},
    )
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 504
    assert response.json() == {"detail": "The canonical cycle timed out"}
