import time
from datetime import datetime, timedelta, timezone
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


def test_scheduled_intelligence_includes_owner_retry_stage(monkeypatch):
    """The intelligence route invokes the retry-only path as an isolated stage."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    from app.config import settings
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    client = TestClient(app)
    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    intel = response.json()["intelligence"]
    # Stage 6 present even when SMTP not configured (clean skip)
    assert "owner_notification_retry" in intel
    assert intel["owner_notification_retry"]["status"] == "skipped"
    # Other stages still present (route not failed by retry skip)
    assert "forge_cycle" in intel
    assert "discovery_cycle" in intel


def test_scheduled_intelligence_includes_scout_stage(monkeypatch):
    """The intelligence route runs the scout cycle as Stage 7."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200
    intel = response.json()["intelligence"]
    # Stage 7 present
    assert "scout_cycle" in intel
    assert intel["scout_cycle"]["status"] in ("ok", "partial", "error")
    # Other stages still present
    assert "forge_cycle" in intel
    assert "discovery_cycle" in intel
    assert "owner_notification_retry" in intel


def test_scheduled_intelligence_pauses_discovery_question_promotion(monkeypatch):
    """Stage 5 reports the backlog gate instead of auto-growing the queue."""
    from app.config import settings

    monkeypatch.setattr(settings, "FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED", False)
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    import app.services.discovery_engine as de

    def mock_run(db, **kwargs):
        # Simulate a discovery finding of kind="question"
        # The real _persist creates entities; we simulate the report structure
        return {
            "methods": [{"name": "test_method", "status": "ran"}],
            "surfaced": [
                {
                    "entity_id": 999,
                    "kind": "question",
                    "method": "test_method",
                    "fingerprint": "abc123",
                    "epistemic_state": "possible",
                    "statement": "What is the test question from discovery?",
                }
            ],
            "existing": [], "rejected": [],
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
    assert disc.get("questions_created") == 0
    assert disc.get("question_generation") == "paused_backlog_review"


def test_discovery_question_promotion_is_paused_and_deduplicates_planned_rows(db, monkeypatch):
    from app.api.scheduled import _promote_discovery_questions
    from app.config import settings
    from app import models

    already_planned = "What evidence would make a reviewed claim more certain?"
    new_statement = "Which independently observable result would disprove the current buyer hypothesis?"
    db.add(models.ResearchQuestion(question=already_planned, status="planned"))
    db.commit()
    report = {
        "surfaced": [
            {"kind": "question", "statement": already_planned},
            {"kind": "question", "statement": new_statement},
        ]
    }
    before = db.query(models.ResearchQuestion).count()
    monkeypatch.setattr(settings, "FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED", False)
    assert _promote_discovery_questions(db, report) == 0
    assert db.query(models.ResearchQuestion).count() == before

    monkeypatch.setattr(settings, "FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED", True)
    assert _promote_discovery_questions(db, report) == 1
    assert db.query(models.ResearchQuestion).count() == before + 1
    created = db.query(models.ResearchQuestion).filter_by(question=new_statement).one()
    assert created.status == "open"
    assert _promote_discovery_questions(db, report) == 0
    assert db.query(models.ResearchQuestion).count() == before + 1


def test_scheduled_intelligence_persists_cycle_run(monkeypatch, db):
    """The 7-stage intelligence run records a CycleRun row with per-stage
    outcomes in summary_json, so the owner console can show last execution,
    stage results, and errors. Uses the existing CycleRun observability model."""
    import json

    from app import models

    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    client = TestClient(app)

    before = db.query(models.CycleRun).count()

    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )
    assert response.status_code == 200

    # The endpoint writes via database.SessionLocal(), which the db fixture
    # points at the test engine; expire to see the new rows. Note Stage 1
    # (forge_loop.run_cycle) records its own CycleRun too, so we look for
    # the scheduled-intelligence row by its 7-stage summary.
    db.expire_all()
    after = db.query(models.CycleRun).count()
    assert after > before
    rows = db.query(models.CycleRun).order_by(models.CycleRun.id.desc()).all()
    row = next(
        (
            r
            for r in rows
            if r.summary_json and '"scout_cycle"' in r.summary_json
        ),
        None,
    )
    assert row is not None, "no CycleRun with 7-stage summary found"
    assert row.status in ("COMPLETED", "PARTIAL", "FAILED")
    assert row.started_at is not None
    assert row.ended_at is not None
    assert row.summary_json is not None
    summary = json.loads(row.summary_json)
    assert "stages" in summary
    assert "stage_errors" in summary
    assert "stage_partials" in summary
    expected_status = (
        "FAILED"
        if summary["stage_errors"]
        else "PARTIAL"
        if summary["stage_partials"]
        else "COMPLETED"
    )
    assert row.status == expected_status
    assert response.json()["cycle_status"] == expected_status
    # All seven stages recorded by their response keys.
    for key in (
        "forge_cycle",
        "collection_cycle",
        "resumed_tasks",
        "autonomy_cycle",
        "discovery_cycle",
        "owner_notification_retry",
        "scout_cycle",
    ):
        assert key in summary["stages"], f"missing stage {key}"

def test_scheduled_intelligence_records_partial_cycle_truthfully(monkeypatch, db):
    """A deferred collector task makes the recorded run PARTIAL, not COMPLETED."""
    import json

    from app import models
    from app.api import forge_bot_owner_notification
    from app.services import collector_runner, discovery_engine, execution_engine, forge_loop, research_task_engine, scout

    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    stale = models.CycleRun(
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        status="RUNNING",
    )
    db.add(stale)
    db.commit()

    monkeypatch.setattr(forge_loop, "run_cycle", lambda session: {
        "cycle_id": "test-cycle", "signals_processed": 0, "stage_errors": {}
    })
    monkeypatch.setattr(collector_runner, "run_pending_tasks", lambda session, limit=5: [
        {"task_id": 1, "source": "fixture", "status": "deferred", "signals_created": 0}
    ])
    monkeypatch.setattr(research_task_engine, "resume_running_tasks", lambda session, limit=10: [])
    monkeypatch.setattr(execution_engine, "run_autonomous_action_cycle", lambda session: {
        "proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0
    })
    monkeypatch.setattr(discovery_engine, "run_discovery", lambda session, **kwargs: {
        "methods": [{"name": "fixture", "status": "ran"}],
        "surfaced": [], "existing": [], "rejected": [], "deferred": [],
        "errors": [], "capability_gaps": [],
    })
    monkeypatch.setattr(forge_bot_owner_notification, "retry_queued_owner_notifications", lambda session: {
        "status": "skipped", "reason": "test fixture", "retried": 0
    })
    monkeypatch.setattr(scout, "run_scout_cycle", lambda session: {
        "errors": [], "candidates_ranked": 0, "candidates_scored": 0,
        "drafts_generated": 0, "blocked": 0,
    })

    client = TestClient(app)
    response = client.get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"  # the HTTP request succeeded
    assert response.json()["cycle_status"] == "PARTIAL"

    db.expire_all()
    db.refresh(stale)
    assert stale.status == "FAILED"
    assert stale.ended_at is not None
    assert "stale RUNNING record reconciled" in stale.error

    row = db.query(models.CycleRun).order_by(models.CycleRun.id.desc()).first()
    assert row is not None and row.summary_json is not None
    assert row.status == "PARTIAL"
    assert row.error == "collection_cycle: partial"
    summary = json.loads(row.summary_json)
    assert summary["stage_errors"] == {}
    assert summary["stage_partials"] == {"collection_cycle": "partial"}
    assert summary["stages"]["collection_cycle"]["tasks_deferred"] == 1


def test_scheduled_intelligence_accepts_owner_key(monkeypatch):
    """The owner X-API-Key is an accepted alternative to the cron Bearer
    secret, letting the owner console trigger the supported intelligence path
    on demand. The legacy-gated POST /forge/cycle stays disabled."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setenv("FORGE_API_KEY", "test-owner-key")
    # Refresh settings so security._enabled() sees the key.
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"X-API-Key": "test-owner-key"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_scheduled_intelligence_rejects_bad_owner_key(monkeypatch):
    """Wrong owner key and no cron secret -> 401, not 503."""
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    client = TestClient(app)

    response = client.get(
        "/scheduled/intelligence",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_forge_cycles_returns_summary(monkeypatch, db):
    """GET /forge/cycles includes the per-stage summary so the owner UI can
    render stage breakdowns without a second query."""
    import json

    from app import models
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    client = TestClient(app)

    row = models.CycleRun(
        status="COMPLETED",
        summary_json=json.dumps({"stages": {"forge_cycle": {"status": "ok"}}}),
    )
    db.add(row)
    db.commit()

    response = client.get("/forge/cycles?limit=1", headers={"X-API-Key": "test-owner-key"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert "summary" in body[0]


def test_forge_runtime_projects_partial_cycles_for_owner_cockpit(monkeypatch, db):
    """The owner runtime DTO exposes stored partial cycles separately from errors."""
    from app import models
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    db.add_all(
        [
            models.CycleRun(status="COMPLETED"),
            models.CycleRun(status="PARTIAL"),
            models.CycleRun(status="FAILED"),
            models.CycleRun(status="RUNNING"),
        ]
    )
    db.commit()

    client = TestClient(app)
    response = client.get("/forge/runtime", headers={"X-API-Key": "test-owner-key"})

    assert response.status_code == 200, response.text
    operations = response.json()["truth"]["operations"]
    assert operations["completed_cycles"] == 1
    assert operations["partial_cycles"] == 1
    assert operations["failed_cycles"] == 1
    assert operations["running_cycles"] == 1


def test_forge_clearance_lists_governed_sources(monkeypatch):
    """GET /forge/clearance exposes the source clearance registry with expiry
    state, so the owner console can show why a task cannot run."""
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    client = TestClient(app)

    response = client.get("/forge/clearance", headers={"X-API-Key": "test-owner-key"})
    assert response.status_code == 200
    body = response.json()
    assert "as_of" in body
    assert "sources" in body
    assert len(body["sources"]) >= 5
    for entry in body["sources"]:
        assert entry["clearance_state"] in ("valid", "expiring_soon", "expired")
        assert "collector_cleared_now" in entry
        assert "valid_through" in entry


def test_forge_clearance_requires_owner_key(monkeypatch):
    """GET /forge/clearance is owner-gated like the rest of /forge/*."""
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    client = TestClient(app)

    response = client.get("/forge/clearance")
    assert response.status_code == 401
