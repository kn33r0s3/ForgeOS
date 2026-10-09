"""Persistent, resumable research task state machine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.models import utcnow

STEP_NAMES = ("plan", "select_tools", "execute", "evaluate")




def create_task(
    db: Session,
    *,
    question_id: int,
    source: str,
    query: str,
    objective: str | None = None,
    claim_id: int | None = None,
    idempotency_key: str | None = None,
) -> models.ResearchTask:
    """Create or reuse the durable task for one question/source/query."""
    supplied_identity = idempotency_key is not None
    idempotency_key = idempotency_key or hashlib.sha256(
        f"{question_id}\0{source}\0{query}".encode("utf-8")
    ).hexdigest()
    existing = (
        db.query(models.ResearchTask)
        .filter_by(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        return existing
    if not supplied_identity:
        existing = (
            db.query(models.ResearchTask)
            .filter_by(question_id=question_id, source=source, query=query)
            .order_by(models.ResearchTask.id.asc())
            .first()
        )
    if existing:
        if existing.idempotency_key not in (None, idempotency_key):
            raise ValueError("Existing research task identity has a conflicting idempotency key")
        if existing.idempotency_key is None:
            existing.idempotency_key = idempotency_key
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                winner = (
                    db.query(models.ResearchTask)
                    .filter_by(idempotency_key=idempotency_key)
                    .first()
                )
                if winner:
                    return winner
                raise
        return existing
    task = models.ResearchTask(
        question_id=question_id,
        claim_id=claim_id,
        idempotency_key=idempotency_key,
        source=source,
        query=query,
        objective=objective or query,
        status="planned",
        plan=[{"name": name, "position": index} for index, name in enumerate(STEP_NAMES)],
        tools_used=[],
        evidence_ids="",
        claims=[],
        judgments=[],
        contradictions=[],
        remaining_questions=[],
        results={},
        errors=[],
        current_step="plan",
    )
    db.add(task)
    try:
        db.flush()
        _ensure_steps(db, task)
        _event(db, task, "created", details={"objective": task.objective})
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = (
            db.query(models.ResearchTask)
            .filter_by(idempotency_key=idempotency_key)
            .first()
        )
        if winner:
            return winner
        raise
    db.refresh(task)
    return task


def _ensure_steps(db: Session, task: models.ResearchTask) -> list[models.ResearchTaskStep]:
    existing = {step.name: step for step in task.steps}
    for position, name in enumerate(STEP_NAMES):
        if name not in existing:
            db.add(models.ResearchTaskStep(task_id=task.id, name=name, position=position))
    db.flush()
    return sorted(task.steps, key=lambda step: step.position)


def _event(
    db: Session,
    task: models.ResearchTask,
    event_type: str,
    *,
    step_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> models.ResearchTaskEvent:
    event = models.ResearchTaskEvent(
        task_id=task.id,
        event_type=event_type,
        step_name=step_name,
        details=details or {},
    )
    db.add(event)
    return event


def _set_step(
    db: Session,
    task: models.ResearchTask,
    name: str,
    status: str,
    *,
    output: dict[str, Any] | None = None,
    error: str | None = None,
) -> models.ResearchTaskStep:
    steps = _ensure_steps(db, task)
    step = next(step for step in steps if step.name == name)
    now = utcnow()
    if status == "running" and step.started_at is None:
        step.started_at = now
    if status in {"completed", "failed"}:
        step.completed_at = now
    step.status = status
    if output is not None:
        step.output_data = output
    if error:
        step.error = error
    task.current_step = name
    _event(db, task, f"step_{status}", step_name=name, details=output or ({"error": error} if error else {}))
    return step


def begin_task(db: Session, task: models.ResearchTask) -> bool:
    """Start or resume a task. Returns False for completed/exhausted tasks."""
    previous_status = task.status
    previous_attempts = task.attempts or 0
    if previous_status not in {"planned", "failed"}:
        return False
    if previous_attempts >= task.max_attempts:
        return False

    now = utcnow()
    claimed = (
        db.query(models.ResearchTask)
        .filter(
            models.ResearchTask.id == task.id,
            models.ResearchTask.status == previous_status,
            models.ResearchTask.attempts == previous_attempts,
        )
        .update(
            {
                models.ResearchTask.status: "running",
                models.ResearchTask.started_at: func.coalesce(
                    models.ResearchTask.started_at, now
                ),
                models.ResearchTask.updated_at: now,
                models.ResearchTask.attempts: models.ResearchTask.attempts + 1,
            },
            synchronize_session=False,
        )
    )
    if claimed != 1:
        db.expire(task)
        return False
    db.commit()
    db.refresh(task)
    _ensure_steps(db, task)
    if previous_status == "failed":
        _event(db, task, "retry_requested", details={"attempt": task.attempts})
    _set_step(db, task, "plan", "completed", output={"objective": task.objective or task.query})
    from app.services.tool_registry import default_registry

    selection = default_registry().select(
        category="reasoning",
        capability="completion",
        preferred=("local-qwen3-coder",),
        fallback="offline-mock",
        db=db,
        exploration_key=f"research:{task.id}:{task.query}",
    )
    selected_tools = sorted(set((task.tools_used or []) + [task.source, selection.tool.capability.name]))
    task.tools_used = selected_tools
    _set_step(
        db,
        task,
        "select_tools",
        "completed",
        output={"source": task.source, "reasoning_tool": selection.tool.capability.name, "reason": selection.reason},
    )
    _set_step(db, task, "execute", "running", output={"query": task.query})
    _event(db, task, "started", details={"attempt": task.attempts})
    db.commit()
    return True


def finish_task(
    db: Session,
    task: models.ResearchTask,
    *,
    signal_ids: list[int],
    evidence_ids: list[int],
    retrieval_observation: dict[str, Any] | None = None,
) -> models.ResearchTask:
    unique_evidence = list(dict.fromkeys(evidence_ids))
    task.evidence_ids = ",".join(str(value) for value in unique_evidence)
    task.claims = [{"type": "observed", "evidence_id": value} for value in unique_evidence]
    task.judgments = [
        {
            "evidence_count": len(unique_evidence),
            "status": "evidence_collected" if unique_evidence else "no_evidence",
        }
    ]
    from app.services.research_evidence_assessment import explicit_contradiction_edges

    task.contradictions = explicit_contradiction_edges(db, unique_evidence)
    task.results = {
        **(task.results or {}),
        "signal_ids": signal_ids,
        "evidence_ids": unique_evidence,
        **(
            {"retrieval_observation": retrieval_observation}
            if retrieval_observation is not None
            else {}
        ),
    }
    _set_step(db, task, "execute", "completed", output=task.results)
    _set_step(db, task, "evaluate", "completed", output=task.judgments[0])
    if unique_evidence:
        task.status = "completed"
        task.remaining_questions = []
        task.completed_at = utcnow()
        _event(db, task, "completed", details=task.results)
    else:
        task.status = "needs_research"
        task.remaining_questions = [task.objective or task.query]
        _event(db, task, "remaining_question", details={"question": task.objective or task.query})
    task.updated_at = utcnow()
    _refresh_question_status(db, task.question_id)
    db.commit()
    db.refresh(task)
    return task


def evaluate_claim_after_research(
    db: Session,
    task: models.ResearchTask,
    evidence_ids: list[int],
) -> dict[str, Any] | None:
    """Re-run P3 against all evidence currently linked to this claim."""
    if task.claim_id is None or not evidence_ids:
        return None

    requested_evidence_ids = sorted(set(evidence_ids))
    evidence_rows = (
        db.query(models.Evidence)
        .filter(models.Evidence.id.in_(requested_evidence_ids))
        .all()
    )
    metadata_only_ids = sorted(
        row.id for row in evidence_rows if _evidence_is_metadata_only(row)
    )
    evidence_ids = sorted(
        row.id for row in evidence_rows if not _evidence_is_metadata_only(row)
    )
    if not evidence_ids:
        task.judgments = [
            {
                "status": "unassessed_metadata_only",
                "evidence_ids": metadata_only_ids,
            }
        ]
        task.results = {
            **(task.results or {}),
            "comparison_outcome": "unassessed",
            "claim_support": "not_inferred",
            "excluded_metadata_only_evidence_ids": metadata_only_ids,
            "contradictions": [],
        }
        _event(db, task, "judgment_skipped", details=task.results)
        db.commit()
        db.refresh(task)
        return None
    from app.services import multi_judge

    question = task.objective or task.query
    judgments = multi_judge.run_judgments(
        db,
        question=question,
        evidence_ids=sorted(set(evidence_ids)),
        claim_id=task.claim_id,
        research_task_id=task.id,
    )
    comparison = multi_judge.compare_judgments(
        db,
        question=question,
        judgment_ids=[judgment.id for judgment in judgments],
        evidence_ids=sorted(set(evidence_ids)),
        claim_id=task.claim_id,
    )
    task.judgments = [{"id": judgment.id, "status": judgment.status} for judgment in judgments]
    task.contradictions = comparison.contradictory_claims or []
    task.results = {
        **(task.results or {}),
        "judgment_ids": [judgment.id for judgment in judgments],
        "comparison_id": comparison.id,
        "comparison_outcome": comparison.outcome,
        "excluded_metadata_only_evidence_ids": metadata_only_ids,
    }
    if comparison.follow_up_question_id:
        task.remaining_questions = [comparison.summary]
    task.updated_at = utcnow()
    _event(db, task, "judged", details=task.results)
    db.commit()
    db.refresh(task)
    return {"judgments": judgments, "comparison": comparison}


def _evidence_is_metadata_only(evidence: models.Evidence) -> bool:
    import json

    for value in (evidence.provenance, evidence.substrate_provenance):
        if not value:
            continue
        try:
            provenance = json.loads(value) if isinstance(value, str) else value
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(provenance, dict) and provenance.get("metadata_only") is True:
            return True
    return False


def fail_task(db: Session, task: models.ResearchTask, error: str) -> models.ResearchTask:
    task.status = "failed"
    task.updated_at = utcnow()
    task.errors = list(task.errors or []) + [{"attempt": task.attempts, "error": error}]
    _set_step(db, task, task.current_step or "execute", "failed", error=error)
    _event(db, task, "failed", details={"error": error, "attempt": task.attempts})
    _refresh_question_status(db, task.question_id)
    db.commit()
    db.refresh(task)
    question = db.get(models.ResearchQuestion, task.question_id)
    if question is not None and isinstance(question.research_plan, dict):
        from app.services import research_planner

        research_planner.plan_tasks_for_question(db, question)
        db.refresh(task)
    return task


def defer_task(db: Session, task: models.ResearchTask, reason: str) -> models.ResearchTask:
    """Return a temporarily rate-limited task to the queue without using an attempt."""
    if task.status == "running" and task.attempts > 0:
        task.attempts -= 1
    task.status = "planned"
    task.updated_at = utcnow()
    task.current_step = "execute"
    _set_step(db, task, "execute", "pending", output={"deferred": reason})
    _event(db, task, "deferred", details={"reason": reason, "attempts": task.attempts})
    db.commit()
    db.refresh(task)
    return task


def retry_task(db: Session, task: models.ResearchTask) -> models.ResearchTask:
    if task.status not in {"failed", "needs_research"}:
        return task
    if task.attempts >= task.max_attempts:
        return task
    task.status = "planned"
    task.current_step = "execute"
    task.updated_at = utcnow()
    _event(db, task, "retry_queued", details={"next_attempt": task.attempts + 1})
    db.commit()
    db.refresh(task)
    return task


def _refresh_question_status(db: Session, question_id: int) -> None:
    """Keep unanswered questions open after every task has settled without evidence."""
    question = db.get(models.ResearchQuestion, question_id)
    if question is None or question.status == "closed":
        return
    tasks = db.query(models.ResearchTask).filter_by(question_id=question_id).all()
    pending = any(task.status in {"planned", "running"} for task in tasks)
    has_evidence = any(bool((task.evidence_ids or "").strip()) for task in tasks)
    question.status = "planned" if pending or has_evidence else "open"


def resume_running_tasks(
    db: Session,
    limit: int = 10,
    *,
    stale_after_seconds: int = 300,
    now: datetime | None = None,
) -> list[int]:
    """Requeue only stale running tasks; a live worker retains its lease."""
    if limit <= 0:
        return []
    current = now or utcnow()
    cutoff = current - timedelta(seconds=stale_after_seconds)
    tasks = (
        db.query(models.ResearchTask)
        .filter(
            models.ResearchTask.status == "running",
            or_(
                models.ResearchTask.updated_at.is_(None),
                models.ResearchTask.updated_at <= cutoff,
            ),
        )
        .order_by(models.ResearchTask.id.asc())
        .limit(limit)
        .all()
    )
    resumed: list[int] = []
    for task in tasks:
        if resume_task(
            db,
            task,
            stale_after_seconds=stale_after_seconds,
            now=current,
        ).status == "planned":
            resumed.append(task.id)
    return resumed


def resume_task(
    db: Session,
    task: models.ResearchTask,
    *,
    stale_after_seconds: int = 300,
    now: datetime | None = None,
) -> models.ResearchTask:
    """Return an abandoned persisted task to the queue with a conditional update."""
    current = now or utcnow()
    cutoff = current - timedelta(seconds=stale_after_seconds)
    if task.status == "running":
        resumed = (
            db.query(models.ResearchTask)
            .filter(
                models.ResearchTask.id == task.id,
                models.ResearchTask.status == "running",
                or_(
                    models.ResearchTask.updated_at.is_(None),
                    models.ResearchTask.updated_at <= cutoff,
                ),
            )
            .update(
                {
                    models.ResearchTask.status: "planned",
                    models.ResearchTask.updated_at: current,
                },
                synchronize_session=False,
            )
        )
        if resumed:
            db.expire(task)
            db.refresh(task)
            _event(db, task, "resumed", details={"step": task.current_step})
            db.commit()
    return task
