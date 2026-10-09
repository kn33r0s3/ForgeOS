"""Idempotent actual-outcome recording and learning propagation."""

from __future__ import annotations


from sqlalchemy.orm import Session

from app import evidence_source, models
from app.models import utcnow
from app.services import learning_engine




def record_experiment_outcome(
    db: Session,
    experiment_id: int,
    *,
    action_id: int | None = None,
    actual: str,
    success: bool | None = None,
    source: str = "manual",
    actual_value: float | None = None,
    unit: str | None = None,
    lesson: str | None = None,
    prediction_error: float | None = None,
    error_type: str | None = None,
    data_scope: str = "REAL",
    outcome_type: str | None = None,
    product_id: int | None = None,
    commit: bool = True,
) -> dict:
    experiment = db.query(models.Experiment).filter_by(id=experiment_id).first()
    if not experiment:
        raise ValueError(f"Experiment {experiment_id} not found")
    if action_id is not None:
        action = db.query(models.Action).filter_by(id=action_id, experiment_id=experiment_id).first()
        if not action:
            raise ValueError("Action not found for experiment")
        if action.status != "SUCCEEDED":
            raise ValueError("The external adapter must succeed before recording a business outcome")
    data_scope = data_scope.strip().upper()
    if data_scope not in {"REAL", "SANDBOX"} or experiment.data_scope != data_scope:
        raise ValueError("Outcome scope must match experiment scope")
    if experiment.status in ("blocked", "abandoned"):
        raise ValueError("Cannot record outcome on rejected/blocked experiment")
    if experiment.requires_owner_approval and experiment.approved_at is None:
        raise ValueError("Approval required before outcome")
    if experiment.action_type == "customer_interview" and not experiment.started_at:
        raise ValueError("Mark human task executed first")
    existing = db.query(models.Outcome).filter_by(
        experiment_id=experiment_id,
        outcome_type=outcome_type or "QUALITATIVE",
        data_scope=data_scope,
    ).first()
    if existing:
        if existing.qualitative_result != actual or existing.actual_value != actual_value or existing.success != success:
            raise ValueError("An immutable outcome already exists; do not overwrite history")
        learning = db.query(models.LearningEvent).filter_by(
            experiment_id=experiment_id,
            data_scope=data_scope,
            source_kind=existing.source_kind,
        ).first()
        return {"outcome": existing, "learning": learning, "reused": True}
    outcome = models.Outcome(
        action_id=action_id,
        experiment_id=experiment_id,
        product_id=product_id,
        outcome_type=outcome_type or "QUALITATIVE",
        actual_value=actual_value,
        unit=unit,
        qualitative_result=actual,
        source=source,
        success=success,
        verification_state="REPORTED",
        data_scope=data_scope,
        source_kind=evidence_source.MOCK,
    )
    db.add(outcome)
    if action_id is not None:
        action = db.get(models.Action, action_id)
        action.status = "VERIFIED"
        action.verification_state = "VERIFIED_SUCCESS" if success else "VERIFIED_FAILURE"
    experiment.result = actual
    experiment.completed_at = utcnow()
    experiment.status = "completed"
    experiment.execution_status = "completed"
    db.flush()
    existing_learning = db.query(models.LearningEvent).filter_by(experiment_id=experiment_id).first()
    if existing_learning:
        learning = existing_learning
    else:
        derived_error_type = error_type or ("confirmed" if success is True else "qualitative_miss" if success is False else None)
        learning = learning_engine.record_learning_from_experiment(
            db,
            experiment_id,
            prediction=experiment.expected_result or experiment.hypothesis or experiment.action,
            actual=actual,
            lesson=lesson or "Actual outcome recorded; causal explanation remains uncertain unless separately supported.",
            prediction_error=prediction_error,
            error_type=derived_error_type,
            product_id=product_id,
            data_scope=data_scope,
            source_kind=outcome.source_kind,
            commit=False,
        )
    opportunity = db.query(models.Opportunity).filter_by(id=experiment.opportunity_id).first()
    if (
        opportunity
        and data_scope == "REAL"
        and outcome.source_kind == evidence_source.REAL
        and outcome.verification_state == "VERIFIED"
    ):
        opportunity.status = "measured"
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"outcome": outcome, "learning": learning, "reused": False}
