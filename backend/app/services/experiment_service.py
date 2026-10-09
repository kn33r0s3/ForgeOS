from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.schemas import AnalyzeResponse
from app.schemas.experiment import ExperimentAuthorize, ExperimentOutcomeCreate, ExperimentProposalCreate




def _normalize_auth_status(raw_value: str | None) -> str:
    status = (raw_value or "allowed").strip().lower()
    aliases = {
        "approved": "allowed",
        "allowed": "allowed",
        "rejected": "blocked",
        "blocked": "blocked",
        "require_approval": "require_approval",
    }
    return aliases.get(status, status)


def build_experiment_from_analyze(data: AnalyzeResponse | dict[str, Any]) -> ExperimentProposalCreate:
    """Build a proposal only from a research response whose requirements are grounded."""
    analyze = data if isinstance(data, AnalyzeResponse) else AnalyzeResponse.model_validate(data)
    requirements = analyze.research_plan.get("requirements", [])
    if (
        analyze.research_status != "research_complete"
        or not requirements
        or any(row.get("status") != "satisfied" for row in requirements if isinstance(row, dict))
    ):
        raise ValueError("Experiment proposals require all research requirements to be evidence-grounded")
    if analyze.signal_id is None or analyze.research_question_id is None or not analyze.research_task_ids:
        raise ValueError("Completed research response is missing provenance")

    return ExperimentProposalCreate(
        source_signal_id=analyze.signal_id,
        source_research_question_id=analyze.research_question_id,
        source_research_task_ids=analyze.research_task_ids,
        problem_statement=analyze.problem,
        hypothesis=analyze.recommended_next_experiment or analyze.findings_summary or analyze.problem,
        evidence_summary=analyze.findings_summary,
        target=analyze.target_customer,
        offer=analyze.solution,
    )


def assert_executable(experiment: models.Experiment) -> None:
    if experiment is None:
        raise ValueError("Experiment not found")
    if experiment.execution_status == "executed":
        raise ValueError("Experiment has already been executed")
    if _normalize_auth_status(experiment.authorization_status) != "allowed" or not experiment.authorized_at:
        raise ValueError("Experiment is not authorized for execution")
    # Canonical execution gate: execution_allowed is the authoritative
    # execution-eligibility flag, written only by
    # execution_engine.grant_execution_eligibility(). authorization_status
    # =="allowed" records owner authorization; it does NOT itself mean the
    # safety gate cleared this specific execution. Fail closed.
    if not getattr(experiment, "execution_allowed", False):
        raise ValueError("Experiment has not been cleared by the canonical execution gate")


def create_proposed(db: Session, data: ExperimentProposalCreate) -> models.Experiment:
    experiment = models.Experiment(
        opportunity_id=None,
        action=data.action_type or "research",
        result=None,
        lesson=None,
        source_analyze_id=data.source_analyze_id,
        source_signal_id=data.source_signal_id,
        source_research_question_id=data.source_research_question_id,
        source_research_task_ids=data.source_research_task_ids or None,
        authorization_status="require_approval",
        authorization_reason="Research-first proposal requires explicit authorization before execution.",
        execution_status="proposed",
        response_received="none",
        revenue_amount=0.0,
        revenue_currency="USD",
        # compatibility projection
        hypothesis=data.hypothesis,
        expected_result=data.evidence_summary,
        action_type=data.action_type,
        status="planned",
        requires_owner_approval=True,
        execution_allowed=False,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def authorize_experiment(db: Session, experiment_id: int, data: ExperimentAuthorize) -> models.Experiment:
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        raise ValueError("Experiment not found")

    status = _normalize_auth_status(data.authorization_status)
    if status not in {"allowed", "blocked", "require_approval"}:
        raise ValueError("Unsupported authorization status")

    experiment.authorization_status = status
    experiment.authorization_reason = data.authorization_reason or experiment.authorization_reason
    experiment.authorized_by = data.authorized_by or experiment.authorized_by
    experiment.authorized_at = utcnow() if status == "allowed" else None
    experiment.approved_at = experiment.authorized_at
    experiment.requires_owner_approval = status in {"allowed", "require_approval"} or experiment.requires_owner_approval
    experiment.execution_status = "authorized" if status == "allowed" else experiment.execution_status

    # Execution eligibility is granted ONLY through the canonical gate
    # in execution_engine. This function must not set
    # execution_allowed=True directly — the gate re-verifies
    # authorization state and fail-closes on every hard constraint.
    # (Pre-seam behavior set the flag here unconditionally; that bypass
    # is removed. There is exactly one code path that grants the flag.)
    experiment.execution_allowed = False
    db.commit()
    db.refresh(experiment)

    if status == "allowed":
        from app.services import execution_engine as _execution_engine

        granted = _execution_engine.grant_execution_eligibility(
            db, experiment.id, granted_by=(data.authorized_by or "system")
        )
        if granted is not None:
            experiment = granted

    db.refresh(experiment)
    return experiment


def execute_experiment(db: Session, experiment_id: int) -> models.Experiment:
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        raise ValueError("Experiment not found")

    db.refresh(experiment)
    assert_executable(experiment)

    experiment.execution_status = "executed"
    experiment.executed_at = utcnow()
    experiment.execution_notes = (
        experiment.execution_notes or "Execution attempt recorded; actual market response is recorded separately."
    )
    experiment.response_received = experiment.response_received or "none"
    experiment.status = "in_progress"
    experiment.started_at = experiment.executed_at

    db.commit()
    db.refresh(experiment)
    return experiment


def mark_executed(db: Session, experiment_id: int) -> models.Experiment:
    return execute_experiment(db, experiment_id)


def record_outcome(db: Session, experiment_id: int, data: ExperimentOutcomeCreate) -> models.Experiment:
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        raise ValueError("Experiment not found")
    if experiment.execution_status != "executed":
        raise ValueError("Experiment must be marked executed before recording an outcome")

    response_received = (data.response_received or "none").strip().lower()
    if response_received not in {"none", "rejection", "interest", "payment"}:
        raise ValueError("Unsupported outcome response")

    revenue_amount = float(data.revenue_amount or 0.0)
    if response_received == "payment":
        if revenue_amount <= 0:
            raise ValueError("Payment outcome requires actual revenue greater than zero")
    elif revenue_amount > 0:
        raise ValueError(f"{response_received} outcome cannot include positive revenue")

    experiment.response_received = response_received
    experiment.response_raw = data.response_raw or response_received
    experiment.response_received_at = utcnow()
    experiment.revenue_amount = revenue_amount
    experiment.revenue_currency = data.revenue_currency or experiment.revenue_currency or "USD"
    experiment.revenue_recorded_at = utcnow() if revenue_amount > 0 else None
    experiment.execution_notes = data.execution_notes or experiment.execution_notes
    experiment.learning_event_id = data.learning_event_id or experiment.learning_event_id
    experiment.next_decision = data.next_decision or experiment.next_decision
    experiment.result = experiment.response_raw
    experiment.completed_at = utcnow()
    experiment.status = "completed"
    experiment.execution_status = "completed"

    db.commit()
    db.refresh(experiment)
    return experiment
