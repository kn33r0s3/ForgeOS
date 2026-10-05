"""Truth and provenance metrics for the ForgeOS operator dashboard.

These metrics deliberately distinguish database volume from knowledge gained
from reality. Historical/raw records remain intact; only their interpretation
changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def _count(db: Session, model, *criteria) -> int:
    query = db.query(func.count()).select_from(model)
    if criteria:
        query = query.filter(*criteria)
    return int(query.scalar() or 0)


def reconcile_stale_cycles(db: Session, *, stale_after_minutes: int = 60) -> int:
    """Close abandoned RUNNING records without deleting their history."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=stale_after_minutes)
    rows = (
        db.query(models.CycleRun)
        .filter(models.CycleRun.status == "RUNNING", models.CycleRun.started_at < cutoff)
        .all()
    )
    if not rows:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        row.status = "FAILED"
        row.ended_at = now
        prior = (row.error or "").strip()
        reason = f"stale RUNNING record reconciled after {stale_after_minutes} minutes"
        row.error = f"{prior}; {reason}" if prior else reason
    db.commit()
    return len(rows)


def snapshot(db: Session) -> dict:
    """Return a truthful operator-facing snapshot, never a success claim."""
    raw_signals = _count(db, models.Signal)
    collected_signals = _count(db, models.Signal, models.Signal.collection_status == "collected")
    observed_signals = _count(db, models.Signal, models.Signal.collection_status != "collected")
    duplicate_signals = _count(db, models.Signal, models.Signal.is_duplicate_of.isnot(None))
    verified_claims = (
        _count(db, models.Claim, models.Claim.epistemic_state == "verified")
        if hasattr(models, "Claim")
        else 0
    )
    human_validated = _count(db, models.Opportunity, models.Opportunity.status == "validated")
    real_experiments = _count(db, models.Experiment, models.Experiment.data_scope == "REAL")
    real_outcomes = _count(db, models.Outcome, models.Outcome.data_scope == "REAL")
    real_learning = _count(db, models.LearningEvent, models.LearningEvent.data_scope == "REAL")
    actual_revenue = float(
        db.query(func.coalesce(func.sum(models.Outcome.actual_value), 0.0))
        .filter(models.Outcome.data_scope == "REAL", models.Outcome.outcome_type == "ACTUAL_REVENUE")
        .scalar() or 0.0
    )
    source_rows = db.query(models.Signal.source, func.count()).group_by(models.Signal.source).all()
    canonical_signals = _count(db, models.Signal, models.Signal.is_duplicate_of.is_(None))
    quality_rows = (
        db.query(models.Signal.quality_score, func.count())
        .filter(models.Signal.is_duplicate_of.is_(None))
        .group_by(models.Signal.quality_score)
        .order_by(models.Signal.quality_score.asc())
        .all()
    )
    evidence_total = _count(db, models.Evidence)
    evidence_with_provenance = _count(db, models.Evidence, models.Evidence.provenance.isnot(None))
    failed_cycles = _count(db, models.CycleRun, models.CycleRun.status == "FAILED")
    completed_cycles = _count(db, models.CycleRun, models.CycleRun.status == "COMPLETED")
    pending_actions = _count(db, models.Action, models.Action.status.in_(["PENDING", "PROPOSED", "APPROVAL_REQUIRED"]))
    queued_tasks = _count(db, models.WorkerTask, models.WorkerTask.status == "queued")
    outbox_queued = _count(db, models.IntegrationDelivery, models.IntegrationDelivery.status == "QUEUED")
    outbox_failed = _count(db, models.IntegrationDelivery, models.IntegrationDelivery.status == "FAILED")
    return {
        "epistemic_labels": {
            "raw_signals": raw_signals,
            "historical_or_observed_signals": observed_signals,
            "currently_collected_signals": collected_signals,
            "duplicate_signals": duplicate_signals,
            "inferred_patterns": _count(db, models.Pattern),
            "opportunity_hypotheses": _count(db, models.Opportunity),
            "verified_claims": verified_claims,
            "human_validated_problems": human_validated,
            "real_experiments": real_experiments,
            "actual_outcomes": real_outcomes,
            "reality_learning_events": real_learning,
            "actual_revenue": actual_revenue,
        },
        "provenance": {
            "signal_sources": {source or "unknown": count for source, count in source_rows},
            "collection_status": {
                "collected": collected_signals,
                "historical_or_observed": observed_signals,
            },
            "canonical_signals": canonical_signals,
            "evidence_with_provenance": evidence_with_provenance,
            "evidence_without_provenance": max(evidence_total - evidence_with_provenance, 0),
        },
        "signal_quality": {
            "canonical_distribution": [
                {"score": score, "count": count} for score, count in quality_rows
            ],
            "canonical_average": round(
                sum((score or 0.0) * count for score, count in quality_rows) / canonical_signals,
                2,
            ) if canonical_signals else None,
        },
        "operations": {
            "completed_cycles": completed_cycles,
            "failed_cycles": failed_cycles,
            "running_cycles": _count(db, models.CycleRun, models.CycleRun.status == "RUNNING"),
            "pending_actions": pending_actions,
            "queued_tasks": queued_tasks,
            "outbox_queued": outbox_queued,
            "outbox_failed": outbox_failed,
        },
        "interpretation": {
            "signals_are_raw_observations": True,
            "evidence_is_not_verified_truth": True,
            "opportunities_are_hypotheses_until_human_validated": True,
            "actual_revenue_is_real_scope_only": True,
        },
    }
