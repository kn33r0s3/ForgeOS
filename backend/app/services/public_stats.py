"""Public-safe aggregates (renovation, Phase 4).

Every number here counts ONLY rows labeled REAL (see evidence_source.py)
AND with data_scope == "REAL", with attached proof. TEST / MOCK /
HYPOTHESIS rows can never leak into a public figure through this module,
no matter what. Neither can SANDBOX-scoped rows, even when labeled REAL:
a sandbox simulation of a real-world process is still not the real world.

Proof means: Outcome.verification_state == "VERIFIED". A REAL label
without VERIFIED is refused at write time (see
action_engine.record_outcome).

Why a new file: no existing module computes public-safe aggregates.
economic_validation.py validates theses; the revenue miner projects;
orchestrator.py has internal rollups — none answers "what may we show
the public". This module is that seam.

Definitions:
- revenue: sum of ACTUAL_REVENUE outcomes that are REAL scope + REAL
  kind + VERIFIED.
- customers: CustomerEvents at stage "paid_customer" labeled REAL kind
  with REAL scope.
- verified_outcomes: count of outcomes that are REAL scope + REAL kind
  + VERIFIED.
- owner_interventions_per_real_transaction: NOT MEASURABLE until the
  existing canonical evidence path can attribute actual owner
  interventions with provenance and scope. Counting all Action rows
  mismeasures; a verified transaction does not reveal how many owner
  interventions enabled it.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import evidence_source, models

NOT_MEASURABLE = "NOT MEASURABLE"


def _real_verified_revenue_query(db: Session):
    return (
        db.query(models.Outcome)
        .filter(models.Outcome.outcome_type == "ACTUAL_REVENUE")
        .filter(models.Outcome.data_scope == "REAL")
        .filter(models.Outcome.source_kind == evidence_source.REAL)
        .filter(models.Outcome.verification_state == "VERIFIED")
    )


def public_stats(db: Session) -> dict:
    """Revenue, customers, verified outcomes — REAL scope + REAL kind + proof only."""
    revenue = (
        db.query(func.coalesce(func.sum(models.Outcome.actual_value), 0.0))
        .filter(models.Outcome.outcome_type == "ACTUAL_REVENUE")
        .filter(models.Outcome.data_scope == "REAL")
        .filter(models.Outcome.source_kind == evidence_source.REAL)
        .filter(models.Outcome.verification_state == "VERIFIED")
        .scalar()
    )
    customers = (
        db.query(func.count(models.CustomerEvent.id))
        .filter(models.CustomerEvent.stage == "paid_customer")
        .filter(models.CustomerEvent.data_scope == "REAL")
        .filter(models.CustomerEvent.source_kind == evidence_source.REAL)
        .scalar()
    )
    verified_outcomes = (
        db.query(func.count(models.Outcome.id))
        .filter(models.Outcome.data_scope == "REAL")
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

    Returns the string NOT_MEASURABLE always, until the existing canonical
    evidence path can attribute actual owner interventions with provenance
    and scope.

    Why not count Action rows: not every Action was owner-created,
    executed, related to revenue, or even attempted. The Action table
    records proposed/authorized/executed work across all actors and
    purposes. A verified transaction does not reveal how many owner
    interventions enabled it. Dividing total Actions by verified revenue
    outcomes fabricates a ratio from two unrelated counts.

    The metric becomes measurable only when owner interventions are
    attributed with provenance (who acted, in what scope, toward which
    outcome) through the existing EVENT/EVIDENCE substrate. Until then,
    NOT_MEASURABLE is the honest answer — never 0, never a fabricated
    ratio.
    """
    return NOT_MEASURABLE
