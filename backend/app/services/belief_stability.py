"""
BELIEF STABILITY SCORING
==========================

Forge's temporal read on a belief: not just "what does it believe now"
(confidence_score) but "how settled is that understanding" — has it
been repeatedly validated and left alone, or is it swinging around and
picking up contradictions?

  High stability: unchanged for a while, and any predictions made
                   about it have been confirmed rather than failed.
  Low stability:  frequent recent confidence changes, large swings,
                   accumulating contradicting evidence, or failed
                   predictions ("Forge was wrong about this").

Heuristic, not a model call — same tradeoff as everywhere else in
Forge. Reads from data that already exists (ConfidenceEvent history,
Evidence, Prediction outcomes) and adds no new storage of its own.

Two ways this gets used:
  1. Display — world_model.py calls compute_stability_score() /
     compute_trend() directly with data it has already fetched (no
     extra queries).
  2. Prioritization — curiosity_engine.py calls instability_boost(),
     which combines stability with the Goal Engine's existing
     importance signal ("unstable important beliefs should create more
     investigation" — an unstable belief nobody cares about gets a
     small boost; an unstable belief tied to an active goal gets the
     full boost).
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import goal_engine

STABILITY_WINDOW_DAYS = 30

RECENT_CHANGE_PENALTY = 10.0
MAX_RECENT_CHANGE_PENALTY = 50.0

VOLATILITY_PENALTY_SCALE = 0.5
MAX_VOLATILITY_PENALTY = 30.0

CONTRADICTION_PENALTY = 5.0
MAX_CONTRADICTION_PENALTY = 20.0

CONFIRMED_PREDICTION_BONUS = 5.0
MAX_CONFIRMED_BONUS = 20.0

FAILED_PREDICTION_PENALTY = 15.0
MAX_FAILED_PENALTY = 40.0

TREND_THRESHOLD = 2.0  # net confidence movement below this within the window still reads as "stable", not noise

MAX_INSTABILITY_BOOST = 25.0
UNSTABLE_THRESHOLD = 50.0  # stability_score below this counts as "unstable enough to investigate"




def _recent_events(
    events: list[models.ConfidenceEvent], window_days: int = STABILITY_WINDOW_DAYS
) -> list[models.ConfidenceEvent]:
    cutoff = utcnow() - timedelta(days=window_days)
    return [e for e in events if e.created_at and e.created_at.replace(tzinfo=timezone.utc) >= cutoff]


def compute_trend(events: list[models.ConfidenceEvent]) -> str:
    """"increasing" | "decreasing" | "stable", based on the net
    confidence movement within the recent window. A belief with no
    events, or only events outside the window, reads as "stable" — no
    news is stability, not an unknown."""
    recent = _recent_events(events)
    if not recent:
        return "stable"
    net_delta = sum(e.delta for e in recent)
    if net_delta > TREND_THRESHOLD:
        return "increasing"
    if net_delta < -TREND_THRESHOLD:
        return "decreasing"
    return "stable"


def compute_stability_score(
    events: list[models.ConfidenceEvent],
    contradicting_evidence_count: int,
    predictions: list[models.Prediction],
) -> float:
    """
    0-100, higher = more stable/settled. Starts at 100 (a brand-new
    belief with no history yet is treated as provisionally stable —
    there's nothing to suggest otherwise), then:
      - subtracts for recent confidence-change frequency (churn)
      - subtracts for recent confidence-change volatility (swing size)
      - subtracts for contradicting evidence accumulating
      - subtracts for failed predictions ("Forge was wrong")
      + adds for confirmed predictions ("repeatedly validated")
    """
    recent = _recent_events(events)

    change_penalty = min(MAX_RECENT_CHANGE_PENALTY, len(recent) * RECENT_CHANGE_PENALTY)

    if recent:
        avg_abs_delta = sum(abs(e.delta) for e in recent) / len(recent)
        volatility_penalty = min(MAX_VOLATILITY_PENALTY, avg_abs_delta * VOLATILITY_PENALTY_SCALE)
    else:
        volatility_penalty = 0.0

    contradiction_penalty = min(
        MAX_CONTRADICTION_PENALTY, contradicting_evidence_count * CONTRADICTION_PENALTY
    )

    confirmed_count = sum(1 for p in predictions if p.status == "confirmed")
    failed_count = sum(1 for p in predictions if p.status == "failed")
    confirmed_bonus = min(MAX_CONFIRMED_BONUS, confirmed_count * CONFIRMED_PREDICTION_BONUS)
    failed_penalty = min(MAX_FAILED_PENALTY, failed_count * FAILED_PREDICTION_PENALTY)

    score = (
        100.0
        - change_penalty
        - volatility_penalty
        - contradiction_penalty
        - failed_penalty
        + confirmed_bonus
    )
    return round(max(0.0, min(100.0, score)), 1)


def get_belief_stability(db: Session, belief_id: int) -> dict:
    """Convenience entry point for callers that don't already have the
    underlying data fetched (e.g. curiosity_engine.py's scan, which
    iterates many beliefs rather than assembling one full graph).
    world_model.py does NOT use this — it already has events/evidence/
    predictions on hand from assembling the rest of the belief graph,
    so it calls compute_stability_score()/compute_trend() directly to
    avoid duplicate queries."""
    events = (
        db.query(models.ConfidenceEvent)
        .filter(models.ConfidenceEvent.belief_id == belief_id)
        .order_by(models.ConfidenceEvent.created_at.asc())
        .all()
    )
    contradicting_count = (
        db.query(models.Evidence)
        .filter(models.Evidence.belief_id == belief_id, models.Evidence.direction == "contradicts")
        .count()
    )
    predictions = db.query(models.Prediction).filter(models.Prediction.belief_id == belief_id).all()

    return {
        "stability_score": compute_stability_score(events, contradicting_count, predictions),
        "trend": compute_trend(events),
    }


def instability_boost(db: Session, belief: models.Belief) -> float:
    """
    Additive research-question priority boost (0 to
    MAX_INSTABILITY_BOOST) for a belief that's unstable — weighted up
    when it's also goal-relevant ("unstable important beliefs should
    create more investigation"). Only a belief with zero instability
    (stability_score exactly 100) returns 0.0 — below that, even a
    mildly unsettled belief gets a small nonzero boost scaled by the
    0.3 importance floor, because instability is somewhat worth
    investigating on its own; importance just amplifies it.
    """
    stability = get_belief_stability(db, belief.id)["stability_score"]
    instability = 100.0 - stability
    if instability <= 0:
        return 0.0

    # Reuses the Goal Engine's existing relevance scoring rather than
    # recomputing importance here — avoids duplicating that logic
    # across two modules for the same concept.
    importance = goal_engine.belief_goal_relevance(db, belief) / 100.0  # 0.0-1.0
    weight = 0.3 + (0.7 * importance)

    return round(min(MAX_INSTABILITY_BOOST, (instability / 100.0) * MAX_INSTABILITY_BOOST * weight), 1)
