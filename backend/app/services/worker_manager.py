"""Worker manager service

This module provides a very simple persistent worker orchestration layer.
It reads queued :class:`WorkerTask` rows from the database, dispatches them
to concrete handler functions and updates their status.
"""

from datetime import timedelta
from typing import Callable, Dict

from sqlalchemy.orm import Session

from app.models import WorkerTask, utcnow
from app.config import settings


def process_worker_task_by_id(
    db: Session,
    task_id: int,
    *,
    worker_type: str | None = None,
) -> bool:
    """Atomically claim and execute one queued task, if it is eligible."""
    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        return False

    # Dormancy guard: agent runs are stopped while dormant.
    # Wire check_agent_run_allowed into the single worker-task choke point.
    from app.services import operating_v4 as _opv4

    try:
        _opv4.check_agent_run_allowed(db)
    except ValueError:
        return False

    now = utcnow()
    claim = db.query(WorkerTask).filter(
        WorkerTask.id == task_id,
        WorkerTask.status == "queued",
        (WorkerTask.next_run_at == None) | (WorkerTask.next_run_at <= now),
    )
    if worker_type is not None:
        claim = claim.filter(WorkerTask.worker_type == worker_type)
    claimed = claim.update(
        {"status": "running", "updated_at": now},
        synchronize_session=False,
    )
    db.commit()
    if not claimed:
        return False

    db.expire_all()
    task = db.get(WorkerTask, task_id)
    if task is None:
        return False
    handler = HANDLERS.get(task.worker_type)
    if not handler:
        task.status = "failed"
        task.error = f"no handler for worker_type='{task.worker_type}'"
    else:
        try:
            task.outputs = handler(db, task)
            task.status = "completed"
        except Exception as exc:  # pylint: disable=broad-except
            # A handler that fails mid-flush leaves the session's transaction
            # in a must-rollback state (Postgres raises on any further use).
            # Without an explicit rollback the commit below raises, the retry
            # scheduling never lands, and the task is wedged in "running"
            # forever. Roll back first: the claim commit above is already
            # durable, so the row survives; only the handler's partial writes
            # are discarded.
            db.rollback()
            task = db.get(WorkerTask, task_id)
            if task is None:
                return False
            task.error = str(exc)
            _schedule_retry(task)
    task.updated_at = utcnow()
    db.commit()
    return True


def process_demand_task_in_background(task_id: int) -> None:
    """Run a queued local-only demand interpretation outside the request path."""
    from app.database import SessionLocal

    with SessionLocal() as db:
        process_worker_task_by_id(
            db,
            task_id,
            worker_type="demand_understanding",
        )


# ---------------------------------------------------------------------------
# Handlers – deferred imports keep the legacy-intelligence gate honest:
# importing this module must not pull the collectors/cycle/ML stack at
# startup when FORGEOS_LEGACY_INTELLIGENCE_ENABLED=false (see
# test_legacy_intelligence_gate.py).
# ---------------------------------------------------------------------------

def discovery_handler(db: Session, task: WorkerTask) -> dict:
    from app.services import collector_runner

    default_results = collector_runner.run_default_collection(db)
    task_results = collector_runner.run_pending_tasks(db, limit=5)
    
    output = {"default_results": default_results, "task_results": task_results}
    
    # Schedule research worker
    follow_up = WorkerTask(
        worker_type="research",
        task_name="research_from_discovery",
        priority=task.priority,
        inputs=output,
    )
    db.add(follow_up)
    return output


def research_handler(db: Session, task: WorkerTask) -> dict:
    from app.services import forge_loop

    cycle_summary = forge_loop.run_cycle(db)
    
    output = {"cycle_summary": cycle_summary}
    follow_up = WorkerTask(
        worker_type="opportunity",
        task_name="process_opportunities",
        priority=task.priority,
        inputs=output,
    )
    db.add(follow_up)
    return output


def opportunity_handler(db: Session, task: WorkerTask) -> dict:
    from app.services import opportunity_engine

    results = opportunity_engine.run_autonomous_opportunity_discovery(db)
    
    output = {"opportunity_results": results}
    follow_up = WorkerTask(
        worker_type="builder",
        task_name="implement_opportunity",
        priority=task.priority,
        inputs=output,
    )
    db.add(follow_up)
    return output


def builder_handler(db: Session, task: WorkerTask) -> dict:
    """No build ran. Do not report success or queue a QA pass."""
    return {
        "build_success": False,
        "message": "No build was run. No artifact was produced.",
    }


def qa_handler(db: Session, task: WorkerTask) -> dict:
    """No inspection ran. A build flag is not an inspected artifact."""
    if not (task.inputs and task.inputs.get("build_success")):
        message = "No successful build was recorded. No QA inspection ran."
    else:
        message = "No QA inspection ran. A build flag is not an inspected artifact."
    return {"qa_passed": False, "message": message}


def revenue_miner_handler(db: Session, task: WorkerTask) -> dict:
    """Review recorded paid offers. Do not schedule collection, contact, or payment."""
    from app.services.revenue_miner import mine_revenue_proposals

    proposals = mine_revenue_proposals(db)
    return {
        "proposals_created": len(proposals),
        "executed": False,
        "task": task.task_name,
    }


def demand_understanding_handler(db: Session, task: WorkerTask) -> dict:
    """Process demand asynchronously without contacting people or providers."""
    from app.services import demand_understanding

    return demand_understanding.process_understanding_task(db, task)


def cognitive_handler(db: Session, task: WorkerTask) -> dict:
    from app.services.cognitive_worker import cognitive_handler as handle_task

    return handle_task(db, task)


def evolution_handler(db: Session, task: WorkerTask) -> dict:
    output = {"next": "discovery", "message": "Scheduled the next discovery. No system evaluation ran."}

    existing_pending = (
        db.query(WorkerTask)
        .filter(WorkerTask.worker_type == "discovery")
        .filter(WorkerTask.task_name == "next_discovery_cycle")
        .filter(WorkerTask.status.in_(["queued", "running"]))
        .first()
    )
    if not existing_pending:
        follow_up = WorkerTask(
            worker_type="discovery",
            task_name="next_discovery_cycle",
            priority=task.priority,
            inputs={},
            # Give a small delay before next discovery to prevent infinite runaway loop immediately
            next_run_at=utcnow() + timedelta(seconds=10)
        )
        db.add(follow_up)
    return output


HANDLERS: Dict[str, Callable[[Session, WorkerTask], dict]] = {
    "discovery": discovery_handler,
    "research": research_handler,
    "opportunity": opportunity_handler,
    "builder": builder_handler,
    "qa": qa_handler,
    "evolution": evolution_handler,
    "revenue_miner": revenue_miner_handler,
    "demand_understanding": demand_understanding_handler,
    "cognitive": cognitive_handler,
}


def _schedule_retry(task: WorkerTask) -> None:
    task.attempts += 1
    if task.attempts >= task.max_attempts:
        task.status = "failed"
        task.error = "max attempts reached"
        return
    delay = timedelta(minutes=2 ** task.attempts)
    task.next_run_at = utcnow() + delay
    task.status = "queued"


def process_worker_tasks(db: Session) -> None:
    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        return

    now = utcnow()
    task_ids = (
        db.query(WorkerTask.id)
        .filter(WorkerTask.status == "queued")
        .filter((WorkerTask.next_run_at == None) | (WorkerTask.next_run_at <= now))
        .order_by(WorkerTask.priority.desc(), WorkerTask.created_at)
        .limit(20)
        .all()
    )

    for (task_id,) in task_ids:
        process_worker_task_by_id(db, task_id)

    retention = now - timedelta(days=7)
    db.query(WorkerTask).filter(WorkerTask.status == "completed", WorkerTask.updated_at < retention).delete()
    db.commit()
