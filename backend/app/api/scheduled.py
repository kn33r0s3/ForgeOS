"""Daily privacy maintenance with Hami nervous system and optional legacy Forge cycle."""

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


def run_nervous_system(db) -> dict:
    """Run Hami's non-legacy event-driven nervous system.
    
    This recovers the useful behavior from the historical Forge cycle
    without reviving the legacy intelligence flag:
    - forge_loop.run_cycle: observes state, detects patterns, updates beliefs,
      generates research questions from weak spots (curiosity), plans tasks
    - research_task_engine.resume_running_tasks: requeues stale tasks
    - execution_engine.run_autonomous_action_cycle: proposes (not executes)
      actions for opportunities via policy gate
    
    All engines are non-legacy (no FORGEOS_LEGACY_INTELLIGENCE_ENABLED check).
    No network fetching, no external calls, no spending, no contact.
    Failures are isolated: one engine failing does not stop the others.
    """
    from app.services import forge_loop, research_task_engine, execution_engine
    
    result = {}
    
    # Stage 1: Forge cycle — state → patterns → beliefs → questions → tasks
    try:
        cycle_summary = forge_loop.run_cycle(db)
        result["forge_cycle"] = {
            "status": "ok",
            "signals_processed": cycle_summary.get("signals_processed", 0),
            "patterns_found": len(cycle_summary.get("patterns", [])),
            "beliefs_updated": cycle_summary.get("beliefs_updated", 0),
            "questions_created": len(cycle_summary.get("new_questions", [])),
            "tasks_planned": len(cycle_summary.get("new_tasks", [])),
        }
        # Commit the cycle's work; rollback on failure to keep session clean
        try:
            db.commit()
        except Exception:
            db.rollback()
    except Exception as exc:
        logger.warning("Nervous system forge_cycle failed: %s", type(exc).__name__)
        result["forge_cycle"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        try:
            db.rollback()
        except Exception:
            pass
    
    # Stage 2: Resume stale research tasks — eligible work → requeue
    try:
        resumed = research_task_engine.resume_running_tasks(db, limit=10)
        result["resumed_tasks"] = {"status": "ok", "count": len(resumed), "task_ids": resumed}
        try:
            db.commit()
        except Exception:
            db.rollback()
    except Exception as exc:
        logger.warning("Nervous system resume_tasks failed: %s", type(exc).__name__)
        result["resumed_tasks"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        try:
            db.rollback()
        except Exception:
            pass
    
    # Stage 3: Autonomy cycle — opportunities → proposed (not executed) actions
    try:
        autonomy_summary = execution_engine.run_autonomous_action_cycle(db)
        # Convert to dict if it's an object
        if hasattr(autonomy_summary, "__dict__"):
            autonomy_dict = autonomy_summary.__dict__
        else:
            autonomy_dict = autonomy_summary
        result["autonomy_cycle"] = {
            "status": "ok",
            "proposed": autonomy_dict.get("proposed", 0),
            "allowed": autonomy_dict.get("allowed", 0),
            "blocked": autonomy_dict.get("blocked", 0),
            "require_approval": autonomy_dict.get("require_approval", 0),
        }
        try:
            db.commit()
        except Exception:
            db.rollback()
    except Exception as exc:
        logger.warning("Nervous system autonomy_cycle failed: %s", type(exc).__name__)
        result["autonomy_cycle"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        try:
            db.rollback()
        except Exception:
            pass
    
    return result


@router.get("/cycle")
def run_scheduled_cycle(authorization: str | None = Header(default=None)):
    """Run daily privacy maintenance, Hami nervous system, and legacy cycle if enabled."""
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

    # Hami nervous system: non-legacy event-driven work generation.
    # Runs always (not gated by legacy flag). Recovers the useful behavior
    # from the historical Forge cycle: state → questions → tasks → actions.
    # Failures are isolated and logged; they do not fail the endpoint.
    try:
        with database.SessionLocal() as db:
            nervous_system = run_nervous_system(db)
    except Exception as exc:
        logger.warning("Nervous system failed entirely: %s", type(exc).__name__)
        nervous_system = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        logger.info("legacy cycle disabled; nervous system completed")
        return {
            "status": "completed",
            "reason": "legacy cycle disabled (nervous system active)",
            "maintenance": maintenance,
            "nervous_system": nervous_system,
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
