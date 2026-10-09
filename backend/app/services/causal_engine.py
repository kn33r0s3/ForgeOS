"""
CAUSAL KNOWLEDGE ENGINE
=========================

Turns "an experiment happened" into reusable causal knowledge — not
just a hypothesis/method/result triple sitting in BeliefExperiment,
but a structured, queryable fact Forge can reuse:

    Condition:  "When restaurants miss phone calls"
    Action:      "AI phone answering system"
    Outcome:      "More orders captured"
    Confidence:    72

CausalKnowledge rows are built automatically as a side effect of
experiment_runner.record_result() — the same "structured data ->
structured knowledge" pipeline pattern belief_engine.py already uses
for Pattern -> Belief, applied one level further down the chain.

Deliberately NOT a reasoning system: there is no NLP, no sentiment
analysis on free text, no new classification logic. Success/failure is
read directly from the SAME confidence_change sign the experimenter
already provides when recording a result — a signal that already
exists, not one invented here. Condition is derived from the belief's
originating Pattern (its description already reads as a "when X
happens" statement) when available, falling back to the belief's own
statement; action is the experiment's own method text, unchanged.

Repeated experiments testing the SAME (condition, action) pair update
the SAME CausalKnowledge row rather than creating duplicates — matched
by exact text, the same dedup convention pattern_engine.py and
belief_engine.py already use.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from typing import Optional

SUCCESS_CONFIDENCE_BOOST = 15.0
# Asymmetric on purpose — a failed action costs more than a success
# earns, same principle as reality_memory.py's source reliability
# adjustment (RELIABILITY_ADJUST_ON_FAILURE > ON_SUCCESS).
FAILURE_CONFIDENCE_PENALTY = 20.0
NEW_CAUSAL_KNOWLEDGE_BASE_CONFIDENCE = 50.0

MAX_CAUSAL_GOAL_BOOST = 20.0




def _derive_condition(db: Session, belief: models.Belief) -> str:
    """The circumstances under which the action was tested. Prefers
    the belief's originating Pattern's description (already phrased as
    "N signals repeatedly mention X" — close enough to a condition
    statement without inventing new NLP), falling back to the belief's
    own statement if no pattern is linked."""
    if belief.pattern_id is not None:
        pattern = db.query(models.Pattern).filter(models.Pattern.id == belief.pattern_id).first()
        if pattern:
            return pattern.description
    return belief.statement


def _derive_goal_id(db: Session, belief: models.Belief) -> Optional[int]:
    """Reuses the same belief -> pattern -> opportunity -> goal
    traversal world_model.py already does, rather than duplicating
    that lookup here — takes the first connected goal with an active
    Opportunity link, if any."""
    if belief.pattern_id is None:
        return None
    opportunity = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.pattern_id == belief.pattern_id, models.Opportunity.goal_id.isnot(None))
        .first()
    )
    return opportunity.goal_id if opportunity else None


def record_causal_outcome(
    db: Session, experiment: models.BeliefExperiment, belief: models.Belief
) -> models.CausalKnowledge:
    """
    Called by experiment_runner.record_result() right after an
    experiment's result is recorded. Creates a new CausalKnowledge row,
    or — if this exact (condition, action) pair already has one —
    updates it in place: appends this experiment as supporting
    evidence and adjusts confidence based on whether THIS outcome was
    a success or failure (read from experiment.confidence_change's
    sign, not re-judged here). This is what makes "successful repeated
    outcomes increase confidence" concrete: a second, third, fourth
    experiment testing the same action under the same condition keeps
    nudging the SAME row rather than starting over.
    """
    condition = _derive_condition(db, belief)
    action = experiment.method
    was_successful = (experiment.confidence_change or 0.0) > 0
    adjustment = SUCCESS_CONFIDENCE_BOOST if was_successful else -FAILURE_CONFIDENCE_PENALTY

    existing = (
        db.query(models.CausalKnowledge)
        .filter(models.CausalKnowledge.condition == condition, models.CausalKnowledge.action == action)
        .first()
    )

    if existing:
        supporting_ids = (
            set(existing.supporting_experiment_ids.split(","))
            if existing.supporting_experiment_ids
            else set()
        )
        supporting_ids.add(str(experiment.id))
        existing.supporting_experiment_ids = ",".join(sorted(supporting_ids, key=int))
        existing.actual_outcome = experiment.result or existing.actual_outcome
        existing.confidence = round(max(0.0, min(100.0, existing.confidence + adjustment)), 1)
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    causal = models.CausalKnowledge(
        condition=condition,
        action=action,
        expected_outcome=experiment.hypothesis,
        actual_outcome=experiment.result,
        confidence=round(
            max(0.0, min(100.0, NEW_CAUSAL_KNOWLEDGE_BASE_CONFIDENCE + adjustment)), 1
        ),
        belief_id=belief.id,
        goal_id=_derive_goal_id(db, belief),
        supporting_experiment_ids=str(experiment.id),
    )
    db.add(causal)
    db.commit()
    db.refresh(causal)
    return causal


def list_causal_knowledge(
    db: Session, belief_id: Optional[int] = None, goal_id: Optional[int] = None, limit: int = 100
) -> list[models.CausalKnowledge]:
    query = db.query(models.CausalKnowledge)
    if belief_id is not None:
        query = query.filter(models.CausalKnowledge.belief_id == belief_id)
    if goal_id is not None:
        query = query.filter(models.CausalKnowledge.goal_id == goal_id)
    return query.order_by(models.CausalKnowledge.confidence.desc()).limit(limit).all()


def causal_goal_boost(db: Session, causal: models.CausalKnowledge) -> float:
    """Additive priority boost (0 to MAX_CAUSAL_GOAL_BOOST) when a
    piece of causal knowledge is linked to an active goal, weighted by
    that goal's priority. Used by Curiosity Engine to prioritize
    resolving contradictory causal knowledge that actually matters —
    see curiosity_engine.py's find_contradictory_causal_knowledge()."""
    if causal.goal_id is None:
        return 0.0
    goal = db.query(models.Goal).filter(models.Goal.id == causal.goal_id, models.Goal.status == "active").first()
    if not goal:
        return 0.0
    return round(min(MAX_CAUSAL_GOAL_BOOST, goal.priority * (MAX_CAUSAL_GOAL_BOOST / 100.0)), 1)
