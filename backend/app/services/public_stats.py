"""Public-safe aggregates (renovation, Phase 4).

Every number here counts ONLY rows labeled REAL (see evidence_source.py)
with attached proof. TEST / MOCK / HYPOTHESIS rows can never leak into a
public figure through this module, no matter what.

Proof means: Outcome.verification_state == "VERIFIED". A REAL label
without VERIFIED is refused at write time (see
action_engine.record_outcome).

Why a new file: no existing module computes public-safe aggregates.
economic_validation.py validates theses; the revenue miner projects;
orchestrator.py has internal rollups — none answers "what may we show
the public". This module is that seam.

Definitions:
- revenue: sum of ACTUAL_REVENUE outcomes that are REAL + VERIFIED.
- customers: CustomerEvents at stage "paid_customer" labeled REAL.
- verified_outcomes: count of outcomes that are REAL + VERIFIED.
- owner_interventions_per_real_transaction: Action rows (each an
  owner-authorized intervention) divided by REAL + VERIFIED revenue
  outcomes; NOT_MEASURABLE when there are no real transactions yet.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import evidence_source, models

NOT_MEASURABLE = "NOT MEASURABLE"


def _real_verified_revenue_query(db: Session):
    return (
        db.query(models.Outcome)
        .filter(models.Outcome.outcome_type == "ACTUAL_REVENUE")
        .filter(models.Outcome.source_kind == evidence_source.REAL)
        .filter(models.Outcome.verification_state == "VERIFIED")
    )


def public_stats(db: Session) -> dict:
    """Revenue, customers, verified outcomes — REAL + proof only."""
    revenue = (
        db.query(func.coalesce(func.sum(models.Outcome.actual_value), 0.0))
        .filter(models.Outcome.outcome_type == "ACTUAL_REVENUE")
        .filter(models.Outcome.source_kind == evidence_source.REAL)
        .filter(models.Outcome.verification_state == "VERIFIED")
        .scalar()
    )
    customers = (
        db.query(func.count(models.CustomerEvent.id))
        .filter(models.CustomerEvent.stage == "paid_customer")
        .filter(models.CustomerEvent.source_kind == evidence_source.REAL)
        .scalar()
    )
    verified_outcomes = (
        db.query(func.count(models.Outcome.id))
        .filter(models.Outcome.source_kind == evidence_source.REAL)
        .filter(models.Outcome.verification_state == "VERIFIED")
        .scalar()
    )
    return {
        "revenue": float(revenue or 0.0),
        "customers": int(customers or 0),
        "verified_outcomes": int(verified_outcomes or 0),
    }


def owner_interventions_per_real_transaction(db: Session):
    """Owner actions per verified real transaction.

    Returns the string NOT_MEASURABLE (never the number 0) when there are
    no REAL transactions yet — per the repo's standing rule, the metric
    is only defined over verified real transactions.
    """
    transactions = _real_verified_revenue_query(db).count()
    if transactions == 0:
        return NOT_MEASURABLE
    interventions = db.query(func.count(models.Action.id)).scalar() or 0
    return interventions / transactions
