import time
from threading import Event

from fastapi.testclient import TestClient

from app.api import scheduled
from app.main import app

import inspect


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
        scheduled,
        "run_daily_maintenance",
        lambda db: {
            "inquiries_erased": 0,
            "expired_rate_limit_buckets_purged": 0,
        },
    )
    monkeypatch.setattr(
        scheduled,
        "send_daily_owner_summary_notification",
        lambda db: {"status": "ACCEPTED_BY_SMTP", "delivery_id": 1},
    )
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda **kwargs: {"forge_cycle": {"cycle_id": 27}, "autonomy_cycle": {"status": "ok"}},
    )
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "maintenance": {
            "inquiries_erased": 0,
            "expired_rate_limit_buckets_purged": 0,
        },
        "cycle_id": 27,
        "forge_cycle_failed": False,
        "autonomy_cycle_failed": False,
        "owner_summary_status": "ACCEPTED_BY_SMTP",
    }


def test_scheduled_cycle_reports_owner_summary_skipped_without_smtp(monkeypatch):
    secret = "test-cron-secret"
    monkeypatch.setenv("CRON_SECRET", secret)
    monkeypatch.setattr(scheduled, "run_daily_maintenance", lambda db: {})
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda **kwargs: {"forge_cycle": {"cycle_id": 28}},
    )
    monkeypatch.setattr(
        scheduled,
        "send_daily_owner_summary_notification",
        lambda db: None,
    )
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 200
    assert response.json()["owner_summary_status"] == "SKIPPED_SMTP_NOT_CONFIGURED"


def test_scheduled_cycle_reports_runner_failure(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setattr(scheduled, "run_daily_maintenance", lambda db: {})
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda **kwargs: {"forge_cycle_error": "details stay private", "autonomy_cycle": {"status": "ok"}},
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
    monkeypatch.setattr(scheduled, "run_daily_maintenance", lambda db: {})
    monkeypatch.setattr(
        scheduled._cycle_scheduler,
        "run_single_cycle",
        lambda **kwargs: {"status": "timeout"},
    )
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 504
    assert response.json() == {"detail": "The canonical cycle timed out"}


def test_scheduled_cycle_holds_its_lock_until_timed_out_worker_finishes(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "audit-only-secret")
    monkeypatch.setattr(scheduled, "run_daily_maintenance", lambda db: {})
    entered = Event()
    release = Event()
    calls = []

    def slow_cycle():
        calls.append(len(calls) + 1)
        entered.set()
        release.wait(2)
        return {"forge_cycle": {}, "autonomy_cycle": {}}

    monkeypatch.setattr(scheduled._cycle_scheduler, "max_run_seconds", 1)
    monkeypatch.setattr(scheduled._cycle_scheduler, "_run_cycle", slow_cycle)
    client = TestClient(app)
    headers = {"Authorization": "Bearer audit-only-secret"}

    try:
        first = client.get("/scheduled/cycle", headers=headers)
        assert first.status_code == 504
        assert entered.is_set()

        second = client.get("/scheduled/cycle", headers=headers)
        assert second.status_code == 409
        assert calls == [1]
    finally:
        release.set()
        deadline = time.monotonic() + 1
        while scheduled._local_cycle_lock.locked() and time.monotonic() < deadline:
            time.sleep(0.01)


# ---------------------------------------------------------------------------
# /scheduled/intelligence — non-legacy current-lineage intelligence cycle.
# Separate route, separate contract from /scheduled/cycle (privacy-only).
# ---------------------------------------------------------------------------


def test_scheduled_intelligence_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence", headers={"Authorization": "Bearer anything"}
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Scheduled intelligence is not configured"}


def test_scheduled_intelligence_requires_bearer_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    client = TestClient(app)

    response = client.get("/scheduled/intelligence")

    assert response.status_code == 401


def test_scheduled_intelligence_runs_three_engines(monkeypatch):
    """A+B: state → work → execution. The endpoint runs all three engines
    for real (they are safe: no network, no spending, no contact)."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    intel = body["intelligence"]
    # All three engines executed and reported.
    assert intel["forge_cycle"]["status"] == "ok"
    assert "cycle_id" in intel["forge_cycle"]
    assert intel["resumed_tasks"]["status"] == "ok"
    assert intel["autonomy_cycle"]["status"] == "ok"
def test_scheduled_intelligence_does_not_check_legacy_flag(monkeypatch):
    """The intelligence endpoint must not reference the legacy flag."""
    import inspect

    source = inspect.getsource(scheduled.run_scheduled_intelligence)
    assert "FORGEOS_LEGACY_INTELLIGENCE_ENABLED" not in source


def test_scheduled_intelligence_leaves_cycle_contract_untouched(monkeypatch):
    """E: the privacy endpoint contract is unchanged by the new route."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setattr(scheduled, "run_daily_maintenance", lambda db: {"ok": True})
    # Legacy flag is true in test env (conftest); force the disabled path.
    monkeypatch.setattr(scheduled.settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", False)
    client = TestClient(app)

    response = client.get(
        "/scheduled/cycle",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "disabled",
        "reason": "legacy cycle disabled",
        "maintenance": {"ok": True},
    }
