"""Bridge research-first Experiments into the canonical Action loop."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import models
from app.services import action_engine, outcome_learning


def _action_payload(action: models.Action) -> dict:
    return {
        "id": action.id,
        "experiment_id": action.experiment_id,
        "action_type": action.action_type,
        "objective": action.objective,
        "status": action.status,
        "policy_result": action.policy_result,
        "policy_reason": action.policy_reason,
        "proposed_at": action.proposed_at,
        "approved_at": action.approved_at,
        "started_at": action.started_at,
        "completed_at": action.completed_at,
        "execution_result": action.execution_result,
        "execution_error": action.execution_error,
        "verification_state": action.verification_state,
        "adapter_name": action.adapter_name,
    }


def _authorized_experiment(db: Session, experiment_id: int) -> models.Experiment:
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        raise ValueError("Experiment not found")
    if experiment.authorization_status != "allowed" or experiment.authorized_at is None:
        raise ValueError("Experiment is not authorized for external execution")
    return experiment


def propose_action(db: Session, experiment_id: int) -> dict:
    experiment = _authorized_experiment(db, experiment_id)
    existing = db.query(models.Action).filter_by(experiment_id=experiment.id).first()
    if existing:
        return _action_payload(existing)

    action = action_engine.propose_action(
        db,
        objective=experiment.action or experiment.hypothesis or "Execute authorized experiment",
        action_type=experiment.action_type or "research",
        experiment_id=experiment.id,
        parameters={
            "source_signal_id": experiment.source_signal_id,
            "source_research_question_id": experiment.source_research_question_id,
            "source_research_task_ids": experiment.source_research_task_ids,
        },
    )
    return _action_payload(action)


def approve_action(db: Session, experiment_id: int) -> dict:
    experiment = _authorized_experiment(db, experiment_id)
    action = db.query(models.Action).filter_by(experiment_id=experiment.id).first()
    if action is None:
        raise ValueError("Create the experiment action before approving it")
    approved = action_engine.approve_action(db, action.id)
    return _action_payload(approved)


def execute_action(db: Session, experiment_id: int) -> dict:
    experiment = _authorized_experiment(db, experiment_id)
    action = db.query(models.Action).filter_by(experiment_id=experiment.id).first()
    if action is None:
        raise ValueError("Create the experiment action before executing it")
    if action.policy_result == "REQUIRE_APPROVAL" and action.approved_at is None:
        raise ValueError("Action approval is required before adapter execution")

    executed = action_engine.start_and_execute_action(db, action.id)
    if executed.status == "SUCCEEDED":
        experiment.execution_status = "executed"
        experiment.executed_at = executed.completed_at
        experiment.execution_notes = executed.execution_result
        experiment.status = "in_progress"
    db.commit()
    db.refresh(executed)
    return _action_payload(executed)


def record_actual_response(
    db: Session,
    experiment_id: int,
    *,
    actual: str,
    success: bool | None = None,
    source: str = "manual",
    actual_value: float | None = None,
    unit: str | None = None,
    lesson: str | None = None,
) -> dict:
    experiment = _authorized_experiment(db, experiment_id)
    action = db.query(models.Action).filter_by(experiment_id=experiment.id).first()
    if action is None:
        raise ValueError("Create the experiment action before recording its response")
    result = outcome_learning.record_experiment_outcome(
        db,
        experiment.id,
        action_id=action.id,
        actual=actual,
        success=success,
        source=source,
        actual_value=actual_value,
        unit=unit,
        lesson=lesson,
        outcome_type="ACTUAL_RESPONSE",
    )
    return {
        "action": _action_payload(db.get(models.Action, action.id)),
        "outcome": result["outcome"],
        "learning": result["learning"],
    }