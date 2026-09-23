"""Worker manager service

This module provides a very simple persistent worker orchestration layer.
It reads queued :class:`WorkerTask` rows from the database, dispatches them
to concrete handler functions and updates their status.
"""

from datetime import datetime, timezone, timedelta
from typing import Callable, Dict

from sqlalchemy.orm import Session

from app.models import WorkerTask, utcnow
from app.services import collector_runner, forge_loop, opportunity_engine

# ---------------------------------------------------------------------------
# Handlers – in a real system these would import the actual worker modules.
# ---------------------------------------------------------------------------

def discovery_handler(db: Session, task: WorkerTask) -> dict:
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
    output = {"build_success": True, "message": "No build tasks pending"}
    follow_up = WorkerTask(
        worker_type="qa",
        task_name="qa_opportunity",
        priority=task.priority,
        inputs=output,
    )
    db.add(follow_up)
    return output


def qa_handler(db: Session, task: WorkerTask) -> dict:
    if not (task.inputs and task.inputs.get("build_success")):
        raise RuntimeError("Build failed – cannot QA")
    output = {"qa_passed": True, "message": "System QA passed"}
    follow_up = WorkerTask(
        worker_type="evolution",
        task_name="evolve_system",
        priority=task.priority,
        inputs=output,
    )
    db.add(follow_up)
    return output


def evolution_handler(db: Session, task: WorkerTask) -> dict:
    output = {"next": "discovery", "message": "Evolution evaluated the system and scheduled discovery"}
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
    now = utcnow()
    tasks = (
        db.query(WorkerTask)
        .filter(WorkerTask.status == "queued")
        .filter((WorkerTask.next_run_at == None) | (WorkerTask.next_run_at <= now))
        .order_by(WorkerTask.priority.desc(), WorkerTask.created_at)
        .limit(20)
        .all()
    )

    for task in tasks:
        handler = HANDLERS.get(task.worker_type)
        if not handler:
            task.status = "failed"
            task.error = f"no handler for worker_type='{task.worker_type}'"
            continue
        task.status = "running"
        task.updated_at = utcnow()
        db.commit()
        try:
            result = handler(db, task)
            task.outputs = result
            task.status = "completed"
        except Exception as exc:  # pylint: disable=broad-except
            task.error = str(exc)
            _schedule_retry(task)
        finally:
            task.updated_at = utcnow()
            db.commit()

    retention = now - timedelta(days=7)
    db.query(WorkerTask).filter(WorkerTask.status == "completed", WorkerTask.updated_at < retention).delete()
    db.commit()
