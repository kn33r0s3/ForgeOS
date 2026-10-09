"""
REALITY MEMORY
================

Forge's long-term memory of *why* it believes what it believes, and
whether its beliefs have held up over time.

Two things live here that didn't exist before:

  - Evidence:    persists what the Reality Checker finds (previously
                   only returned in an API response and discarded)
  - Prediction:   a testable claim generated from a confident Belief,
                   later resolved as confirmed or failed

Resolving a Prediction is the actual "learn from being wrong"
mechanism: when a belief's confidence drops significantly after a
prediction was made, the sources that supplied its evidence get their
reliability_score nudged down; when it holds up, they get nudged up.
Over time, sources that consistently produce evidence for beliefs that
turn out to be wrong become less trusted — without any of that logic
needing to live in the collectors themselves.
"""

from datetime import datetime, timezone

from typing import Optional

from sqlalchemy.orm import Session
from app import models
from app.models import utcnow

CONFIDENCE_DROP_FOR_FAILURE = 10.0  # belief must fall at least this much to count as a failed prediction
PREDICTION_CONFIDENCE_THRESHOLD = 60.0  # only confident beliefs get predictions generated
RELIABILITY_ADJUST_ON_SUCCESS = 2.0
RELIABILITY_ADJUST_ON_FAILURE = -3.0  # failures cost more than successes earn — protects against overconfidence




# --- Evidence -------------------------------------------------------------


def record_evidence(db: Session, belief: models.Belief, evidence_items: list[dict]) -> list[models.Evidence]:
    """Persist evidence found by the Reality Checker. Deduped per
    (belief, signal) pair so re-checking the same belief repeatedly
    doesn't pile up duplicate rows for the same piece of evidence."""
    created: list[models.Evidence] = []

    for item in evidence_items:
        signal_id = item.get("signal_id")
        already_recorded = (
            db.query(models.Evidence)
            .filter(models.Evidence.belief_id == belief.id, models.Evidence.signal_id == signal_id)
            .first()
        )
        if already_recorded:
            continue

        evidence = models.Evidence(
            belief_id=belief.id,
            signal_id=signal_id,
            source=_signal_source(db, signal_id),
            content=item.get("content", ""),
            direction=item.get("direction", "supports"),
            confidence=0.0,
            idempotency_key=f"belief-signal:{belief.id}:{signal_id}",
        )
        db.add(evidence)
        created.append(evidence)

    if created:
        db.commit()
        for evidence in created:
            db.refresh(evidence)

    return created


def _signal_source(db: Session, signal_id: Optional[int]) -> Optional[str]:
    if not signal_id:
        return None
    signal = db.query(models.Signal).filter(models.Signal.id == signal_id).first()
    return signal.source if signal else None


def list_evidence(db: Session, belief_id: Optional[int] = None, limit: int = 100) -> list[models.Evidence]:
    query = db.query(models.Evidence)
    if belief_id is not None:
        query = query.filter(models.Evidence.belief_id == belief_id)
    return query.order_by(models.Evidence.created_at.desc()).limit(limit).all()


# --- Predictions ------------------------------------------------------------


def generate_prediction(
    db: Session, belief: models.Belief, threshold: float = PREDICTION_CONFIDENCE_THRESHOLD
) -> Optional[models.Prediction]:
    """If a belief is confident enough, generate a testable prediction
    from it. Returns None if the belief isn't confident enough, or if
    it already has an unresolved (pending) prediction — one live
    prediction per belief at a time."""
    if belief.confidence_score < threshold:
        return None

    existing_pending = (
        db.query(models.Prediction)
        .filter(models.Prediction.belief_id == belief.id, models.Prediction.status == "pending")
        .first()
    )
    if existing_pending:
        return existing_pending

    statement = (
        f'If "{belief.statement}" is true, new evidence should keep supporting it '
        "and its confidence should not drop significantly."
    )
    prediction = models.Prediction(
        belief_id=belief.id,
        statement=statement,
        status="pending",
        confidence_before=belief.confidence_score,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def resolve_pending_predictions(db: Session) -> list[models.Prediction]:
    """Check every pending prediction against its belief's current
    confidence. Only resolves predictions whose belief has actually
    been re-checked since the prediction was made (last_updated is
    newer than the prediction) — otherwise there's no new evidence to
    judge it on yet."""
    resolved: list[models.Prediction] = []
    pending = db.query(models.Prediction).filter(models.Prediction.status == "pending").all()

    for prediction in pending:
        belief = db.query(models.Belief).filter(models.Belief.id == prediction.belief_id).first()
        if not belief or belief.last_updated <= prediction.created_at:
            continue

        delta = belief.confidence_score - prediction.confidence_before
        confirmed = delta > -CONFIDENCE_DROP_FOR_FAILURE

        prediction.status = "confirmed" if confirmed else "failed"
        prediction.confidence_after = belief.confidence_score
        prediction.resolved_at = utcnow()
        db.commit()
        db.refresh(prediction)
        resolved.append(prediction)

        _adjust_source_reliability(db, belief, confirmed)

    return resolved


def _adjust_source_reliability(db: Session, belief: models.Belief, confirmed: bool) -> None:
    """Nudge the reliability of every source that contributed evidence
    to this belief, based on whether the prediction built on it held
    up. This is the mechanism, not just the concept, of Forge learning
    from being wrong."""
    evidence_rows = db.query(models.Evidence).filter(models.Evidence.belief_id == belief.id).all()
    sources_touched = {e.source for e in evidence_rows if e.source}
    delta = RELIABILITY_ADJUST_ON_SUCCESS if confirmed else RELIABILITY_ADJUST_ON_FAILURE

    for source_name in sources_touched:
        source = db.query(models.Source).filter(models.Source.name == source_name).first()
        if source:
            source.reliability_score = round(max(10.0, min(95.0, source.reliability_score + delta)), 1)
            source.last_checked = utcnow()

    db.commit()


def list_predictions(
    db: Session, status: Optional[str] = None, belief_id: Optional[int] = None, limit: int = 100
) -> list[models.Prediction]:
    query = db.query(models.Prediction)
    if status:
        query = query.filter(models.Prediction.status == status)
    if belief_id is not None:
        query = query.filter(models.Prediction.belief_id == belief_id)
    return query.order_by(models.Prediction.created_at.desc()).limit(limit).all()
