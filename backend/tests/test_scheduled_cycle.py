import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api import scheduled
from app.main import app

import inspect




def test_in_memory_sqlite_database_is_shared_across_threads(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.pool import StaticPool
    from app import database

    previous_engine = database.engine
    previous_session_local = database.SessionLocal
    engine = None
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    try:
        database.engine = None
        database._configure_engine()
        engine = database.engine
        assert isinstance(engine.pool, StaticPool)

        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE thread_probe (value INTEGER NOT NULL)"))
            connection.execute(text("INSERT INTO thread_probe (value) VALUES (7)"))

        def read_probe():
            with engine.connect() as connection:
                return connection.execute(text("SELECT value FROM thread_probe")).scalar_one()

        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(read_probe).result() == 7
    finally:
        if engine is not None:
            engine.dispose()
        database.engine = previous_engine
        database.SessionLocal = previous_session_local


def _fake_postgres_lock_engine(*, lock_acquired=True, fail_on_lock=False):
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class Connection:
        def __init__(self):
            self.statements = []
            self.commit_count = 0
            self.closed = False

        def execute(self, statement, params):
            sql = str(statement)
            self.statements.append((sql, params))
            if "pg_try_advisory_lock" in sql:
                if fail_on_lock:
                    raise RuntimeError("simulated database lock failure")
                return Result(lock_acquired)
            if "pg_advisory_unlock" in sql:
                return Result(True)
            raise AssertionError(f"unexpected SQL: {sql}")

        def commit(self):
            self.commit_count += 1

        def close(self):
            self.closed = True

    class Dialect:
        name = "postgresql"

    class Engine:
        dialect = Dialect()

        def __init__(self, connection):
            self.connection = connection

        def connect(self):
            return self.connection

    connection = Connection()
    return Engine(connection), connection


def test_intelligence_lock_uses_postgres_advisory_lock_and_releases(monkeypatch):
    engine, connection = _fake_postgres_lock_engine()
    monkeypatch.setattr(scheduled.database, "engine", engine)

    release = scheduled._acquire_intelligence_lock()

    assert connection.statements[0][0].startswith("SELECT pg_try_advisory_lock")
    assert connection.statements[0][1] == {
        "lock_id": scheduled._POSTGRES_INTELLIGENCE_LOCK_ID
    }
    assert scheduled._POSTGRES_INTELLIGENCE_LOCK_ID != scheduled._POSTGRES_LOCK_ID

    release()

    assert any("pg_advisory_unlock" in sql for sql, _ in connection.statements)
    assert connection.commit_count == 2
    assert connection.closed


def test_intelligence_lock_rejects_a_concurrent_postgres_run(monkeypatch):
    engine, connection = _fake_postgres_lock_engine(lock_acquired=False)
    monkeypatch.setattr(scheduled.database, "engine", engine)

    try:
        scheduled._acquire_intelligence_lock()
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "An intelligence run is already running"
    else:
        raise AssertionError("a second intelligence run must not acquire the held lock")

    assert connection.closed
    assert not any("pg_advisory_unlock" in sql for sql, _ in connection.statements)


def test_intelligence_lock_fails_closed_when_postgres_lock_check_errors(monkeypatch):
    engine, connection = _fake_postgres_lock_engine(fail_on_lock=True)
    monkeypatch.setattr(scheduled.database, "engine", engine)

    try:
        scheduled._acquire_intelligence_lock()
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail == "Intelligence lock is unavailable"
    else:
        raise AssertionError("lock infrastructure failure must block the run")

    assert connection.closed



def test_scheduled_intelligence_blocks_ephemeral_vercel_sqlite(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.setenv("VERCEL", "1")

    class Dialect:
        name = "sqlite"

    class Engine:
        dialect = Dialect()

    monkeypatch.setattr(scheduled.database, "engine", Engine())
    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/scheduled/intelligence",
        "raw_path": b"/scheduled/intelligence",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 443),
        "client": ("testclient", 12345),
    })

    try:
        scheduled.run_scheduled_intelligence(
            request,
            authorization="Bearer test-cron-secret",
        )
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail == "Durable database is required for scheduled intelligence"
    else:
        raise AssertionError("ephemeral Vercel SQLite must not run scheduled intelligence")

    assert not scheduled._intelligence_lock.locked()



def test_scheduled_intelligence_stops_when_run_record_cannot_be_created(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    monkeypatch.delenv("VERCEL", raising=False)

    class Dialect:
        name = "sqlite"

    class Engine:
        dialect = Dialect()

    class BrokenSession:
        def __enter__(self):
            raise RuntimeError("simulated database write failure")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(scheduled.database, "engine", Engine())
    monkeypatch.setattr(scheduled.database, "SessionLocal", lambda: BrokenSession())
    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/scheduled/intelligence",
        "raw_path": b"/scheduled/intelligence",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
    })

    try:
        scheduled.run_scheduled_intelligence(
            request,
            authorization="Bearer test-cron-secret",
        )
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail == "Scheduled intelligence run could not be recorded"
    else:
        raise AssertionError("intelligence work must not start without its run record")

    assert not scheduled._intelligence_lock.locked()



def test_owner_sms_digest_failures_and_ambiguity_mark_cycle_partial():
    failed = scheduled._normalize_owner_sms_digest_result({
        "status": "failed",
        "reason": "provider_did_not_confirm_acceptance",
    })
    assert failed["status"] == "partial"
    assert failed["delivery_status"] == "failed"
    assert scheduled._cycle_stage_summary({"owner_sms_digest": failed})[0] == "PARTIAL"

    ambiguous = scheduled._normalize_owner_sms_digest_result({
        "status": "ambiguous_not_retried",
        "reason": "prior_attempt_not_replayed",
    })
    assert ambiguous["status"] == "partial"
    assert ambiguous["delivery_status"] == "ambiguous_not_retried"

    misconfigured = scheduled._normalize_owner_sms_digest_result({
        "status": "skipped",
        "reason": "twilio_credentials_missing",
    })
    assert misconfigured["status"] == "partial"
    assert misconfigured["delivery_status"] == "skipped"

    disabled = scheduled._normalize_owner_sms_digest_result({
        "status": "skipped",
        "reason": "owner_sms_digest_disabled",
    })
    assert disabled["status"] == "skipped"
    assert scheduled._cycle_stage_summary({"owner_sms_digest": disabled})[0] == "COMPLETED"

    accepted = scheduled._normalize_owner_sms_digest_result({
        "status": "provider_accepted",
        "delivery_claim": "handset delivery is not established",
    })
    assert accepted["status"] == "ok"
    assert accepted["delivery_status"] == "provider_accepted"
    assert "handset delivery is not established" in accepted["delivery_claim"]

    unknown = scheduled._normalize_owner_sms_digest_result({"status": "new_provider_state"})
    assert unknown["status"] == "partial"
    assert unknown["delivery_status"] == "new_provider_state"


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


def test_scheduled_intelligence_respects_dormancy_before_recording(monkeypatch, db):
    """Dormancy blocks the scheduled loop before it creates a CycleRun or runs stages."""
    from app import models
    from app.services import operating_v4

    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    operating_v4.enter_dormancy(db)
    before = db.query(models.CycleRun).count()

    response = TestClient(app).get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 423
    assert response.json() == {
        "detail": "Dormant: agent runs are stopped. Resume only from docs/RUN_STATE.md."
    }
    db.expire_all()
    assert db.query(models.CycleRun).count() == before
    assert not scheduled._intelligence_lock.locked()


def test_scheduled_intelligence_prioritizes_contact_and_freezes_build(monkeypatch, db):
    """When contact is overdue, Scout runs before collection and starvation freezes drafting."""
    from app.api import forge_bot_owner_notification
    from app.services import (
        collector_runner,
        content_loop,
        discovery_engine,
        execution_engine,
        forge_loop,
        operating_v4,
        research_task_engine,
        scout,
    )

    monkeypatch.setenv("CRON_SECRET", "test-cron-secret")
    calls = []
    monkeypatch.setattr(operating_v4, "contact_state", lambda _db: {
        "days_since_last_contact": 14,
        "contact_priority_due": True,
        "starved": True,
    })
    monkeypatch.setattr(scout, "run_scout_cycle", lambda _db: (
        calls.append("scout") or {
            "candidates_ranked": 1,
            "candidates_scored": 1,
            "drafts_generated": 0,
            "drafts_already_open": 1,
            "blocked": 0,
            "errors": [],
        }
    ))
    monkeypatch.setattr(forge_loop, "run_cycle", lambda _db: (
        calls.append("forge") or {
            "cycle_id": "test-cycle",
            "signals_processed": 0,
            "stage_errors": {},
        }
    ))
    monkeypatch.setattr(collector_runner, "run_pending_tasks", lambda _db, limit=5: (
        calls.append("collection") or []
    ))
    monkeypatch.setattr(research_task_engine, "resume_running_tasks", lambda _db, limit=10: [])
    monkeypatch.setattr(execution_engine, "run_autonomous_action_cycle", lambda _db: {
        "proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0
    })
    monkeypatch.setattr(discovery_engine, "run_discovery", lambda _db, **_kwargs: {
        "methods": [],
        "surfaced": [],
        "existing": [],
        "rejected": [],
        "deferred": [],
        "errors": [],
        "capability_gaps": [],
    })
    monkeypatch.setattr(
        forge_bot_owner_notification,
        "retry_queued_owner_notifications",
        lambda _db: {"status": "skipped", "reason": "test fixture", "retried": 0},
    )
    monkeypatch.setattr(
        forge_bot_owner_notification,
        "send_daily_owner_status_sms",
        lambda _db: {"status": "skipped", "reason": "owner_sms_digest_disabled"},
    )

    def content_must_not_run(_db):
        raise AssertionError("STARVED must freeze non-obligatory content drafting")

    monkeypatch.setattr(content_loop, "run_content_draft_cycle", content_must_not_run)
    response = TestClient(app).get(
        "/scheduled/intelligence",
        headers={"Authorization": "Bearer test-cron-secret"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    stages = body["intelligence"]
    assert stages["operating_priority"]["next_priority"] == "contact_preparation"
    assert stages["scout_cycle"]["priority"] == "contact_preparation"
    assert stages["scout_cycle"]["drafts_already_open"] == 1
    assert calls.index("scout") < calls.index("collection")
    assert calls.count("scout") == 1
    assert stages["content_drafts"]["status"] == "skipped"
    assert "STARVED" in stages["content_drafts"]["reason"]


def test_cycle_effect_summary_keeps_world_observations_separate_from_internal_work():
    no_effect = scheduled._cycle_effect_summary({})
    assert no_effect["status"] == "no_new_effect"
    assert no_effect["source_observations"] == []
    assert no_effect["internal_work"] == []

    internal_only = scheduled._cycle_effect_summary({
        "discovery_cycle": {"surfaced": 1, "questions_created": 1},
        "forge_cycle": {"research_tasks_created": 2, "actions_from_decisions": 1},
        "autonomy_cycle": {"proposed": 3},
        "scout_cycle": {"drafts_generated": 1, "drafts_already_open": 0},
    })
    assert internal_only["status"] == "internal_work_only"
    assert internal_only["source_observations"] == []
    assert internal_only["internal_work"] == [
        "discovery_proposals_surfaced",
        "research_questions_created",
        "research_tasks_created",
        "autonomy_actions_proposed",
        "decision_actions_proposed",
        "contact_drafts_prepared",
    ]
    assert internal_only["next_owner_attention"] == "review_prepared_contact_draft"

    source_data = scheduled._cycle_effect_summary({
        "collection_cycle": {"outcomes": [
            {"status": "completed", "signals_created": 2},
            {"status": "deferred", "signals_created": 100},
            {"status": "completed", "signals_created": True},
        ]},
        "scout_cycle": {"drafts_generated": 1, "drafts_already_open": 0},
    })
    assert source_data["status"] == "source_data_collected"
    assert source_data["source_observations"] == ["source_signals_created"]
    assert source_data["counts"]["source_signals_created"] == 2
    assert source_data["internal_work"] == ["contact_drafts_prepared"]
    assert "do not establish a real conversation" in source_data["reality_boundary"]


def test_cycle_without_new_effect_is_not_marked_completed():
    status, errors, partials = scheduled._cycle_stage_summary({
        "forge_cycle": {"status": "ok"},
        "cycle_effect": {"status": "no_new_effect"},
    })
    assert status == "PARTIAL"
    assert errors == {}
    assert partials == {"cycle_effect": "no_new_effect"}


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
    assert response.json()["cycle_run_id"] == row.id
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
