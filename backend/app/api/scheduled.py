"""Authenticated entry point for the canonical daily Forge cycle."""

import hmac
import logging
import os
from threading import Lock

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.forge_bot_owner_notification import send_daily_owner_summary_notification
from app.database import SessionLocal, engine
from app.services.cycle_scheduler import CycleScheduler

router = APIRouter(prefix="/scheduled", tags=["scheduled"])
logger = logging.getLogger(__name__)
_local_cycle_lock = Lock()
_POSTGRES_LOCK_ID = 4_706_539_182
_cycle_scheduler = CycleScheduler(backup_interval_seconds=None, max_run_seconds=240)


@router.get("/cycle")
def run_scheduled_cycle(authorization: str | None = Header(default=None)):
    """Run one canonical cycle when invoked by the configured Vercel cron.

    The endpoint fails closed if CRON_SECRET is missing or invalid. A
    PostgreSQL advisory lock prevents two serverless instances from running
    the stateful cycle at the same time; local SQLite runs use a process lock.
    """
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Scheduled cycle is not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    connection = None
    acquired_postgres_lock = False
    lock_release_deferred = False
    if engine.dialect.name == "postgresql":
        connection = engine.connect()
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
        elif engine.dialect.name != "postgresql":
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
        with SessionLocal() as db:
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
        "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
        "forge_cycle_failed": bool(forge_error),
        "autonomy_cycle_failed": bool(autonomy_error),
        "owner_summary_status": owner_summary_status,
    }
