"""Daily privacy maintenance with an optional legacy Forge cycle."""

import hmac
import logging
import os
from threading import Lock

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import database, models
from app.api.forge_bot_owner_notification import send_daily_owner_summary_notification
from app.config import settings
from app.services.forge_bot_privacy import run_daily_maintenance

router = APIRouter(prefix="/scheduled", tags=["scheduled"])
logger = logging.getLogger(__name__)
_local_cycle_lock = Lock()
_POSTGRES_LOCK_ID = 4_706_539_182
_cycle_scheduler = None
if settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
    from app.services.cycle_scheduler import CycleScheduler

    _cycle_scheduler = CycleScheduler(
        backup_interval_seconds=None,
        max_run_seconds=240,
    )


@router.get("/cycle")
def run_scheduled_cycle(authorization: str | None = Header(default=None)):
    """Run daily privacy maintenance and the legacy cycle only when enabled."""
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Scheduled cycle is not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with database.SessionLocal() as db:
            maintenance = run_daily_maintenance(db)
    except SQLAlchemyError as exc:
        logger.error("Forge Bot daily privacy maintenance failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Daily privacy maintenance failed.",
        ) from exc

    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        logger.info("legacy cycle disabled")
        return {
            "status": "disabled",
            "reason": "legacy cycle disabled",
            "maintenance": maintenance,
        }
    if _cycle_scheduler is None:
        raise HTTPException(status_code=503, detail="Legacy cycle is not configured.")

    connection = None
    acquired_postgres_lock = False
    lock_release_deferred = False
    if database.engine.dialect.name == "postgresql":
        connection = database.engine.connect()
        try:
            acquired_postgres_lock = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": _POSTGRES_LOCK_ID},
                ).scalar_one()
            )
            connection.commit()
        except Exception as exc:
            connection.close()
            raise HTTPException(status_code=503, detail="Cycle lock is unavailable") from exc
        if not acquired_postgres_lock:
            connection.close()
            raise HTTPException(status_code=409, detail="A cycle is already running")
    elif not _local_cycle_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A cycle is already running")

    def release_cycle_lock() -> None:
        if connection is not None:
            try:
                if acquired_postgres_lock:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": _POSTGRES_LOCK_ID},
                    )
                    connection.commit()
            finally:
                connection.close()
        elif database.engine.dialect.name != "postgresql":
            _local_cycle_lock.release()

    try:
        record = _cycle_scheduler.run_single_cycle(on_timeout=release_cycle_lock)
        lock_release_deferred = record.get("lock_release_deferred") is True
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cycle failed: {type(exc).__name__}") from exc
    finally:
        if not lock_release_deferred:
            release_cycle_lock()

    if record.get("status") == "timeout":
        raise HTTPException(status_code=504, detail="The canonical cycle timed out")

    forge_error = record.get("forge_cycle_error")
    autonomy_error = record.get("autonomy_cycle_error")
    if forge_error or autonomy_error:
        raise HTTPException(status_code=500, detail="The canonical cycle reported a failure")
    cycle = record.get("forge_cycle") or {}
    try:
        with database.SessionLocal() as db:
            owner_summary = send_daily_owner_summary_notification(db)
    except SQLAlchemyError as exc:
        logger.error(
            "Forge Bot daily owner summary failed with a database error (%s).",
            type(exc).__name__,
        )
        owner_summary_status = "FAILED"
    else:
        owner_summary_status = (
            owner_summary.get("status")
            if owner_summary is not None
            else "SKIPPED_SMTP_NOT_CONFIGURED"
        )
        if owner_summary_status == "FAILED":
            logger.error(
                "Forge Bot daily owner summary failed (delivery=%s).",
                owner_summary.get("delivery_id") if owner_summary else None,
            )
        elif owner_summary_status == "QUEUED":
            logger.warning(
                "Forge Bot daily owner summary remains queued (delivery=%s).",
                owner_summary.get("delivery_id") if owner_summary else None,
            )
    return {
        "status": "completed",
        "maintenance": maintenance,
        "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
        "forge_cycle_failed": bool(forge_error),
        "autonomy_cycle_failed": bool(autonomy_error),
        "owner_summary_status": owner_summary_status,
    }


@router.get("/intelligence")
def run_scheduled_intelligence(authorization: str | None = Header(default=None)):
    """Run Hami's non-legacy intelligence cycle (current lineage, no legacy flag).

    Uses only existing non-legacy engines, called directly (no wrapper):
    - forge_loop.run_cycle: state → patterns → beliefs → questions → tasks.
      Pure DB reasoning; creates plans/proposals, executes nothing.
    - collector_runner.run_pending_tasks: execute planned ResearchTasks via
      collectors. Idempotent per (question_id, source, query); enforces
      source clearance before network access; per-task failure isolation.
    - research_task_engine.resume_running_tasks: requeue stale running tasks.
    - execution_engine.run_autonomous_action_cycle: propose (never execute)
      actions via the owner's AutonomyPolicy gate.

    Safety: bounded network calls via cleared sources only, no spending, no human contact, no external
    commitments. Network access occurs only through collector_runner.run_pending_tasks,
    which enforces source clearance (source_clearance_registry.py) before any fetch.
    Only the five governed sources (OpenAlex, Crossref, World Bank, GDELT, GovInfo)
    are permitted, each with its authorized purpose and rate limits. Idempotent:
    re-running with unchanged state creates minimal new work (engines skip
    already-tasked questions, duplicate actions, etc.).
    Each engine runs in its own DB session with per-engine failure isolation:
    one engine failing is recorded and the others still run.

    This endpoint is separate from /scheduled/cycle (privacy-only contract)
    and is not gated by the legacy intelligence flag.
    """
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Scheduled intelligence is not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    intelligence: dict = {}

    # Stage 1: reasoning cycle — plans questions/tasks/opportunities/proposals.
    try:
        with database.SessionLocal() as db:
            from app.services import forge_loop

            summary = forge_loop.run_cycle(db)
            stage_errors = summary.get("stage_errors", {})
            # Truthful status: ok only when no internal errors; partial when
            # the cycle completed but one or more sub-operations failed.
            stage1_status = "partial" if stage_errors else "ok"
            intelligence["forge_cycle"] = {
                "status": stage1_status,
                "cycle_id": summary.get("cycle_id"),
                "signals_processed": summary.get("signals_processed", 0),
                "stage_errors": stage_errors,
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: forge_cycle failed (%s)", type(exc).__name__)
        intelligence["forge_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 2: collection cycle — execute planned ResearchTasks via collectors.
    # Uses the existing collector_runner.run_pending_tasks() which:
    # - processes tasks planned by research_planner (explicit, not indiscriminate)
    # - enforces source clearance via require_cleared_source() before network access
    # - is idempotent per (question_id, source, query) via uq_research_tasks_idempotency_key
    # - handles failures per-task (max_attempts=3) without killing the cycle
    # Does NOT call run_default_collection() — that deliberately skips uncleared feeds.
    try:
        with database.SessionLocal() as db:
            from app.services import collector_runner

            collection_outcomes = collector_runner.run_pending_tasks(db, limit=5)
            outcomes_list = [
                {
                    "task_id": o.get("task_id"),
                    "source": o.get("source"),
                    "status": o.get("status"),
                    "signals_created": o.get("signals_created", 0),
                }
                for o in collection_outcomes
            ]
            # Truthful status: ok only when all outcomes completed; partial
            # when any failed or were deferred. A returned list is not proof
            # of success — check each outcome's status.
            failed_or_deferred = [
                o for o in outcomes_list
                if o.get("status") in ("failed", "deferred")
            ]
            stage2_status = "partial" if failed_or_deferred else "ok"
            intelligence["collection_cycle"] = {
                "status": stage2_status,
                "tasks_executed": len(outcomes_list),
                "tasks_failed": len([o for o in outcomes_list if o.get("status") == "failed"]),
                "tasks_deferred": len([o for o in outcomes_list if o.get("status") == "deferred"]),
                "outcomes": outcomes_list,
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: collection_cycle failed (%s)", type(exc).__name__)
        intelligence["collection_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 3: requeue stale research tasks so eligible work is not stuck.
    try:
        with database.SessionLocal() as db:
            from app.services import research_task_engine

            resumed = research_task_engine.resume_running_tasks(db, limit=10)
            intelligence["resumed_tasks"] = {"status": "ok", "count": len(resumed)}
    except Exception as exc:
        logger.warning("scheduled intelligence: resume_tasks failed (%s)", type(exc).__name__)
        intelligence["resumed_tasks"] = {"status": "error", "error": type(exc).__name__}

    # Stage 4: propose (never execute) actions for opportunities via policy.
    try:
        with database.SessionLocal() as db:
            from app.services import execution_engine

            autonomy = execution_engine.run_autonomous_action_cycle(db)
            counts = autonomy.__dict__ if hasattr(autonomy, "__dict__") else autonomy
            intelligence["autonomy_cycle"] = {
                "status": "ok",
                "proposed": counts.get("proposed", 0),
                "allowed": counts.get("allowed", 0),
                "blocked": counts.get("blocked", 0),
                "require_approval": counts.get("require_approval", 0),
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: autonomy_cycle failed (%s)", type(exc).__name__)
        intelligence["autonomy_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 5: discovery — run the generalized discovery engine over the substrate.
    # Uses app.services.discovery_engine.run_discovery with the DEFAULT_REGISTRY
    # (14 methods including curiosity_questions). Each method runs with per-method
    # failure isolation; findings are validated and persisted via the existing
    # discovery lifecycle (idempotent by fingerprint). Findings are emitted with
    # honest epistemic states (hypothesized/possible) — never as validated.
    # Bounded: max_findings_per_method=10 uses itertools.islice for genuine
    # early-stop (does not materialize the full iterable first). This bounds
    # findings consumed, not DB rows scanned or time spent — see method
    # docstrings for per-method work characteristics.
    # Separate DB session; commit only on success, rollback on failure.
    # Returns only an operational summary (counts), never raw internal details
    # or private records.
    try:
        with database.SessionLocal() as db:
            from app.services import discovery_engine

            try:
                report = discovery_engine.run_discovery(db, max_findings_per_method=10)
                db.commit()
                # Count actually executed methods (status=="ran"), not blocked/errored
                methods_executed = sum(
                    1 for m in report.get("methods", []) if m.get("status") == "ran"
                )
                errors_count = len(report.get("errors", []))
                deferred_count = len(report.get("deferred", []))
                # Truthful status: ok only with no errors and no deferred work;
                # partial when the discovery ran but some methods errored or
                # were deferred. Preserve the distinction among errors,
                # deferred, rejected, and normal no-result findings.
                stage5_status = "partial" if (errors_count or deferred_count) else "ok"
                intelligence["discovery_cycle"] = {
                    "status": stage5_status,
                    "methods_run": methods_executed,
                    "methods_total": len(report.get("methods", [])),
                    "surfaced": len(report.get("surfaced", [])),
                    "existing": len(report.get("existing", [])),
                    "rejected": len(report.get("rejected", [])),
                    "deferred": deferred_count,
                    "errors": errors_count,
                    "capability_gaps": len(report.get("capability_gaps", [])),
                }
                # Close the loop: convert surfaced question findings into
                # ResearchQuestion rows so the next cycle's research planner
                # can pick them up. This is what makes discovery actionable
                # rather than merely reported.
                questions_created = 0
                for surfaced in report.get("surfaced", []):
                    if surfaced.get("kind") != "question":
                        continue
                    statement = (surfaced.get("statement") or "").strip()
                    if not statement or len(statement) > 2000:
                        continue
                    # Deduplicate: skip if an open question with same text exists
                    existing_q = (
                        db.query(models.ResearchQuestion)
                        .filter(
                            models.ResearchQuestion.question == statement,
                            models.ResearchQuestion.status.in_(["open", "proposed"]),
                        )
                        .first()
                    )
                    if existing_q:
                        continue
                    q = models.ResearchQuestion(
                        question=statement,
                        status="open",
                        priority_score=50.0,  # Discovery-sourced; planner will reprioritize
                    )
                    db.add(q)
                    questions_created += 1
                if questions_created:
                    db.commit()
                intelligence["discovery_cycle"]["questions_created"] = questions_created
            except Exception:
                db.rollback()
                raise
    except Exception as exc:
        logger.warning("scheduled intelligence: discovery_cycle failed (%s)", type(exc).__name__)
        intelligence["discovery_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 6: retry already-queued owner notifications (retry-only).
    # Isolated: separate DB session, isolated exception handling. Retries
    # only existing due queued deliveries via the existing retry helper's
    # filters. Never constructs or enqueues a new daily digest. Does not
    # authorize customer messages or change intake flags. A retry failure
    # does not fail or conceal the other stages.
    try:
        with database.SessionLocal() as db:
            from app.api import forge_bot_owner_notification

            retry_result = forge_bot_owner_notification.retry_queued_owner_notifications(db)
            db.commit()
            if retry_result["status"] == "skipped":
                intelligence["owner_notification_retry"] = {
                    "status": "skipped",
                    "reason": retry_result["reason"],
                    "retried": 0,
                }
            else:
                intelligence["owner_notification_retry"] = {
                    "status": "ok",
                    "retried": retry_result["retried"],
                }
    except Exception as exc:
        logger.warning("scheduled intelligence: owner_notification_retry failed (%s)", type(exc).__name__)
        intelligence["owner_notification_retry"] = {"status": "error", "error": type(exc).__name__}

    # Stage 7: scout cycle — autonomous candidate processing.
    # Scores and ranks registered candidates, generates drafts for top
    # eligible ones (draft only, never sends). Uses existing scout.py seams.
    # Isolated: separate DB session, isolated exception handling.
    # A scout failure does not fail or conceal the other stages.
    try:
        with database.SessionLocal() as db:
            from app.services import scout

            scout_result = scout.run_scout_cycle(db)
            db.commit()
            err_count = len(scout_result.get("errors", []))
            stage7_status = "partial" if err_count else "ok"
            intelligence["scout_cycle"] = {
                "status": stage7_status,
                "candidates_ranked": scout_result.get("candidates_ranked", 0),
                "candidates_scored": scout_result.get("candidates_scored", 0),
                "drafts_generated": scout_result.get("drafts_generated", 0),
                "blocked": scout_result.get("blocked", 0),
                "errors": err_count,
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: scout_cycle failed (%s)", type(exc).__name__)
        intelligence["scout_cycle"] = {"status": "error", "error": type(exc).__name__}

    return {"status": "completed", "intelligence": intelligence}
