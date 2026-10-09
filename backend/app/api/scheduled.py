"""Daily privacy maintenance with an optional legacy Forge cycle."""

import hmac
import logging
import os
from threading import Lock

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import database
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
            intelligence["forge_cycle"] = {
                "status": "ok",
                "cycle_id": summary.get("cycle_id"),
                "signals_processed": summary.get("signals_processed", 0),
                "stage_errors": summary.get("stage_errors", {}),
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
            intelligence["collection_cycle"] = {
                "status": "ok",
                "tasks_executed": len(collection_outcomes),
                "outcomes": [
                    {
                        "task_id": o.get("task_id"),
                        "source": o.get("source"),
                        "status": o.get("status"),
                        "signals_created": o.get("signals_created", 0),
                    }
                    for o in collection_outcomes
                ],
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

    return {"status": "completed", "intelligence": intelligence}
