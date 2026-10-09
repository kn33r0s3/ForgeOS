"""Evidence package for a require_approval action, a human outcome, and
separately verified revenue.

The package only cites rows already stored. Recording a human-reported
result requires owner approval and a human-execution mark. Revenue stays
unset until a separate, independently verified payment event is recorded.
"""

import math

from sqlalchemy.orm import Session

from app import evidence_source, models
from app.services import execution_engine


def build_action_package(db: Session, action_id: int) -> dict | None:
    action = db.get(models.Experiment, action_id)
    if action is None or action.policy_decision != "require_approval":
        return None
    opportunity = db.get(models.Opportunity, action.opportunity_id)
    if opportunity is None:
        return None
    return {
        "action_id": action.id,
        "opportunity_id": opportunity.id,
        "action_type": action.action_type,
        "status": action.status,
        "policy_decision": action.policy_decision,
        "requires_owner_approval": action.requires_owner_approval,
        "approved": action.approved_at is not None,
        "execution_allowed": action.execution_allowed,
        "problem": opportunity.problem,
        "proposed_action": action.action,
        "evidence": _evidence(db, opportunity),
        "result": action.result,
        "revenue": action.revenue,
    }


def record_human_result(
    db: Session,
    action_id: int,
    result: str,
    revenue: float | None = None,
    conversions: int | None = None,
) -> dict:
    """Persist a human-supplied result. Does not invent revenue."""
    if revenue is not None or conversions is not None:
        raise ValueError("Revenue is recorded only from verified payment evidence")
    package = build_action_package(db, action_id)
    if package is None:
        raise ValueError("No require_approval action")
    if not package["approved"]:
        raise ValueError("Owner approval required before a result")
    text = result.strip()
    if not text:
        raise ValueError("Result must be nonempty")

    marked = execution_engine.mark_human_action_executed(db, action_id)
    if marked is None or marked.started_at is None:
        raise ValueError("Human execution was not recorded")

    updated = execution_engine.record_action_result(db, action_id, text)
    if updated is None:
        raise ValueError("Result was not recorded")
    if revenue is None and updated.revenue is not None:
        raise ValueError("Revenue was written without an amount")
    return build_action_package(db, action_id)


def record_verified_revenue_evidence(
    db: Session,
    action_id: int,
    *,
    amount: float,
    currency: str,
    source: str,
    reference: str,
    notes: str | None = None,
) -> models.Outcome:
    """Persist only independently verified revenue evidence.

    This is intentionally separate from the human outcome record. Approval,
    human execution, and actual outcome remain distinct from revenue.
    """
    action = db.get(models.Experiment, action_id)
    if action is None:
        raise ValueError("Action not found")
    if action.policy_decision != "require_approval":
        raise ValueError("Only require_approval actions may record verified revenue")
    if action.approved_at is None:
        raise ValueError("Owner approval required before verified revenue evidence")
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("Revenue must be finite and nonnegative")
    if not source.strip() or not reference.strip():
        raise ValueError("Verified revenue requires a source and a reference")
    if (currency or "").strip().upper() not in {"USD", "NPR"}:
        raise ValueError("Currency must be a supported tracked currency")
    qualitative = (
        db.query(models.Outcome)
        .filter_by(experiment_id=action.id, outcome_type="QUALITATIVE", data_scope=action.data_scope)
        .first()
    )
    if qualitative is None:
        raise ValueError("A human outcome must be recorded before verified revenue")
    existing = (
        db.query(models.Outcome)
        .filter_by(
            experiment_id=action.id,
            outcome_type="ACTUAL_REVENUE",
            data_scope=action.data_scope,
            source_kind=evidence_source.REAL,
            verification_state="VERIFIED",
        )
        .first()
    )
    if existing is not None:
        if existing.actual_value != float(amount):
            raise ValueError("Verified revenue already recorded")
        return existing

    # experiment_id is the execution action. action_id belongs to the
    # separate actions table and stays empty here.
    outcome = models.Outcome(
        experiment_id=action.id,
        outcome_type="ACTUAL_REVENUE",
        actual_value=float(amount),
        unit=(currency or "USD").upper(),
        source=source.strip(),
        verification_state="VERIFIED",
        notes=(notes or f"Provider reference: {reference.strip()}"),
        data_scope=action.data_scope,
        source_kind="REAL",  # this seam demands proof (source + reference); genuinely real
    )
    db.add(outcome)
    action.revenue = float(amount)
    action.completed_at = action.completed_at or action.started_at
    action.status = "completed"
    db.commit()
    db.refresh(outcome)
    return outcome


def _evidence(db: Session, opportunity: models.Opportunity) -> list[dict]:
    raw = opportunity.problem_evidence_signal_ids or ""
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    rows = []
    for signal_id in ids:
        signal = db.get(models.Signal, signal_id)
        if signal is None:
            continue
        rows.append({"signal_id": signal.id, "source": signal.source, "text": signal.content})
    return rows
