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


def test_scheduled_intelligence_runs_five_stages(monkeypatch):
    """A+B: state → work → execution → discovery. The endpoint runs all engines
    for real (they are safe: no network, no spending, no contact).
    Engines report ok or error per-engine; the endpoint always answers."""
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
    # All five stages reported (ok, partial, or isolated error).
    assert intel["forge_cycle"]["status"] in ("ok", "partial", "error")
    assert intel["collection_cycle"]["status"] in ("ok", "partial", "error")
    assert intel["resumed_tasks"]["status"] in ("ok", "error")
    assert intel["autonomy_cycle"]["status"] in ("ok", "error")
    assert intel["discovery_cycle"]["status"] in ("ok", "partial", "error")


def test_scheduled_intelligence_discovery_returns_operational_summary(monkeypatch):
    """Discovery stage returns only counts, never raw internal details."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    intel = response.json()["intelligence"]
    disc = intel["discovery_cycle"]
    assert disc["status"] in ("ok", "error")
    if disc["status"] == "ok":
        # Operational summary only: counts, not raw findings or private records
        for key in ("methods_run", "surfaced", "existing", "rejected",
                    "deferred", "errors", "capability_gaps"):
            assert key in disc
            assert isinstance(disc[key], int)
        # Must not leak raw findings, statements, or private data
        assert "surfaced" not in disc or isinstance(disc["surfaced"], int)
        assert "findings" not in disc
        assert "statements" not in disc


def test_scheduled_intelligence_discovery_failure_isolated(monkeypatch):
    """A discovery-stage failure does not prevent other stages from running."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    # Force discovery to fail
    import app.services.discovery_engine as de
    def _fail(*args, **kwargs):
        raise RuntimeError("simulated discovery failure")
    monkeypatch.setattr(de, "run_discovery", _fail)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    intel = response.json()["intelligence"]
    # Discovery reported error, but other stages still ran
    assert intel["discovery_cycle"]["status"] == "error"
    assert intel["forge_cycle"]["status"] in ("ok", "error")
    assert intel["autonomy_cycle"]["status"] in ("ok", "error")
def test_scheduled_intelligence_does_not_check_legacy_flag(monkeypatch):
    """The intelligence endpoint must not reference the legacy flag."""

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


def test_scheduled_intelligence_discovery_uses_bounded_limit(monkeypatch):
    """Discovery receives max_findings_per_method=10 and does not over-consume lazy iterators."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.discovery_engine as de

    captured = {}
    consumed_count = [0]

    def mock_run(db, *, registry=None, methods=None, persist=True, actor="test", max_findings_per_method=50):
        captured["max_findings_per_method"] = max_findings_per_method
        # Simulate a lazy method that would yield 1000 if fully consumed
        def lazy_method(ctx):
            for i in range(1000):
                consumed_count[0] += 1
                from app.services.discovery_engine import Finding
                yield Finding(kind="observation", key=f"test:{i}", statement=f"test {i}")
                if consumed_count[0] >= max_findings_per_method:
                    break
        # Return a minimal report
        return {
            "methods": [{"name": "test", "status": "ran"}],
            "surfaced": [], "existing": [], "rejected": [],
            "deferred": [], "errors": [], "capability_gaps": [],
        }

    monkeypatch.setattr(de, "run_discovery", mock_run)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    # Verify the intended limit was passed
    assert captured.get("max_findings_per_method") == 10


def test_scheduled_intelligence_discovery_counts_executed_methods(monkeypatch):
    """methods_run counts only status=='ran', not blocked or errored methods."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.discovery_engine as de

    def mock_run(db, **kwargs):
        return {
            "methods": [
                {"name": "m1", "status": "ran"},
                {"name": "m2", "status": "blocked_by_capability"},
                {"name": "m3", "status": "ran"},
                {"name": "m4", "status": "error"},
            ],
            "surfaced": [], "existing": [], "rejected": [],
            "deferred": [], "errors": [], "capability_gaps": [],
        }

    monkeypatch.setattr(de, "run_discovery", mock_run)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    disc = response.json()["intelligence"]["discovery_cycle"]
    assert disc["status"] == "ok"
    assert disc["methods_run"] == 2  # Only m1 and m3 ran
    assert disc["methods_total"] == 4  # All 4 in registry


def test_scheduled_intelligence_forge_partial_on_stage_errors(monkeypatch):
    """Stage 1 reports partial (not ok) when forge_cycle has stage_errors."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.forge_loop as fl

    def mock_run_cycle(db):
        return {
            "cycle_id": "test-123",
            "signals_processed": 5,
            "stage_errors": {"planner": "simulated failure"},
        }

    monkeypatch.setattr(fl, "run_cycle", mock_run_cycle)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    forge = response.json()["intelligence"]["forge_cycle"]
    assert forge["status"] == "partial"
    assert forge["stage_errors"] == {"planner": "simulated failure"}


def test_scheduled_intelligence_collection_partial_on_failed_deferred(monkeypatch):
    """Stage 2 reports partial when outcomes include failed/deferred."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.collector_runner as cr

    def mock_run_pending(db, limit=5):
        return [
            {"task_id": 1, "source": "web", "status": "completed", "signals_created": 3},
            {"task_id": 2, "source": "rss", "status": "failed", "signals_created": 0},
            {"task_id": 3, "source": "api", "status": "deferred", "signals_created": 0},
        ]

    monkeypatch.setattr(cr, "run_pending_tasks", mock_run_pending)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    coll = response.json()["intelligence"]["collection_cycle"]
    assert coll["status"] == "partial"
    assert coll["tasks_executed"] == 3
    assert coll["tasks_failed"] == 1
    assert coll["tasks_deferred"] == 1


def test_scheduled_intelligence_discovery_partial_on_errors(monkeypatch):
    """Stage 5 reports partial (not ok) when discovery has errors/deferred."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.discovery_engine as de

    def mock_run(db, **kwargs):
        return {
            "methods": [
                {"name": "m1", "status": "ran"},
                {"name": "m2", "status": "error"},
            ],
            "surfaced": [], "existing": [], "rejected": [],
            "deferred": [{"method": "m3", "reason": "blocked"}],
            "errors": [{"method": "m2", "error": "simulated"}],
            "capability_gaps": [],
        }

    monkeypatch.setattr(de, "run_discovery", mock_run)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    disc = response.json()["intelligence"]["discovery_cycle"]
    assert disc["status"] == "partial"
    assert disc["errors"] == 1
    assert disc["deferred"] == 1


def test_scheduled_intelligence_stage_error_isolated(monkeypatch):
    """A stage that throws is reported as error without failing other stages."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.forge_loop as fl

    def mock_run_cycle(db):
        raise RuntimeError("simulated stage failure")

    monkeypatch.setattr(fl, "run_cycle", mock_run_cycle)
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    intel = response.json()["intelligence"]
    # Failed stage reports error
    assert intel["forge_cycle"]["status"] == "error"
    # Other stages still run (ok, partial, or error — but present)
    assert "collection_cycle" in intel
    assert "discovery_cycle" in intel
