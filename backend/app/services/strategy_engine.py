"""
STRATEGY ENGINE
================

Forge's first attempt to answer "given everything I've learned, what
should I try next toward this goal?" — WITHOUT executing anything. This
module only proposes candidate Strategy rows; nothing in ForgeOS calls
out, spends money, or acts on the real world as a result of a Strategy
existing. See the "NO AUTONOMOUS EXECUTION" note at the bottom of this
file.

A strategy is deliberately NOT generated from an AI model's general
knowledge. It's assembled entirely from Forge's own World Model:

    Goal
      + relevant Beliefs (structurally or textually connected)
      + relevant CausalKnowledge (condition -> action -> outcome facts
        that already exist — see causal_engine.py)
      + the experiments and evidence backing that causal knowledge
    -> one candidate Strategy per sufficiently-relevant causal fact,
       scored transparently (see _score_strategy()) — every factor is
       a plain weighted number computed from real rows, nothing hidden
       inside an LLM call.

Strategies are immutable once scored — "preserve history, never
silently overwrite previous strategies or their scores." Re-running
generate_strategies() for a goal after new evidence arrives does NOT
rewrite an existing Strategy's confidence in place; if the underlying
picture has genuinely changed (score moved by more than
RESCORE_CHANGE_THRESHOLD), the OLD row is marked status="superseded"
(a status transition, not a score change — its confidence/rationale
stay exactly as they were) and a NEW row is created with the current
numbers. The full history for a goal is just "every Strategy row for
that goal_id, ordered by created_at" — nothing is deleted or rewritten.

Per-goal relevance (_belief_relevance_to_goal, _causal_relevance_to_goal)
is intentionally separate from goal_engine.belief_goal_relevance():
that function scores a belief against whichever ACTIVE goal matches
best, which is correct for Curiosity Engine's uniform priority
boosting but WRONG here — a goal-scoped view needs "relevant to THIS
named goal specifically," not "relevant to some goal or other." This
isn't duplicating an evidence system; it's a necessary variant of the
scoring math, kept in one place (here) and reused by world_model.py's
goal graph rather than reimplemented there too.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.services.pattern_engine import tokenize
from typing import Optional

# Composite score weights — sum to 1.0. Every factor is a plain 0-100
# number computed from data already in the database.
WEIGHT_GOAL_RELEVANCE = 0.25
WEIGHT_BELIEF_CONFIDENCE = 0.15
WEIGHT_CAUSAL_CONFIDENCE = 0.30
WEIGHT_EVIDENCE_STRENGTH = 0.15
WEIGHT_EXPECTED_IMPACT = 0.15
UNCERTAINTY_PENALTY_WEIGHT = 0.25  # up to 25 points subtracted from the weighted composite

MIN_CANDIDATE_RELEVANCE = 10.0  # a causal fact below this relevance to the goal isn't worth proposing
RESCORE_CHANGE_THRESHOLD = 5.0  # a re-run only supersedes an existing strategy if its score moved by at least this much


def utcnow():
    return datetime.now(timezone.utc)


# --- per-goal relevance (see module docstring for why these are separate from goal_engine.py) ---


def _causal_relevance_to_goal(db: Session, causal: models.CausalKnowledge, goal: models.Goal) -> float:
    """0-100. Strong (100) if this causal knowledge is already
    structurally linked to this exact goal (causal_engine.py already
    derived belief -> pattern -> opportunity -> this goal_id when the
    causal fact was recorded). Otherwise, weaker textual relevance
    between the underlying belief's statement and this goal's
    statement, or 0.0 if there's no usable link at all."""
    if causal.goal_id == goal.id:
        return 100.0
    if causal.belief_id is None:
        return 0.0
    belief = db.query(models.Belief).filter(models.Belief.id == causal.belief_id).first()
    if not belief:
        return 0.0
    overlap = tokenize(belief.statement) & tokenize(goal.statement)
    if not overlap:
        return 0.0
    return round(min(60.0, len(overlap) * 15.0), 1)


def _belief_relevance_to_goal(db: Session, belief: models.Belief, goal: models.Goal) -> float:
    """0-100 relevance of ONE belief to ONE specific goal."""
    structural = 0.0
    if belief.pattern_id is not None:
        linked = (
            db.query(models.Opportunity)
            .filter(models.Opportunity.pattern_id == belief.pattern_id, models.Opportunity.goal_id == goal.id)
            .first()
        )
        if linked:
            structural = 60.0

    overlap = tokenize(belief.statement) & tokenize(goal.statement)
    textual = min(40.0, len(overlap) * 10.0) if overlap else 0.0

    return round(min(100.0, structural + textual), 1)


# --- scoring factors ---


def _experiment_id_count(supporting_experiment_ids: Optional[str]) -> int:
    """How many experiment ids a comma-separated id list actually names.
    Filters empty tokens so a trailing or double comma ("1,2,", "1,,2")
    doesn't inflate the count."""
    if not supporting_experiment_ids:
        return 0
    return len([t for t in supporting_experiment_ids.split(",") if t.strip()])


def _evidence_strength(causal: models.CausalKnowledge) -> float:
    """0-100, from how many experiments support this causal fact. More
    supporting experiments = stronger evidence a repeated relationship
    actually holds, not a one-off result."""
    return round(min(100.0, _experiment_id_count(causal.supporting_experiment_ids) * 25.0), 1)


def _uncertainty(evidence_strength: float, causal_confidence: float) -> float:
    """0-100, higher = less trustworthy right now. Primarily driven by
    thin evidence; boosted further if the causal fact's confidence
    sits in the "contested" range (35-65) that
    curiosity_engine.find_contradictory_causal_knowledge() already uses
    to flag mixed/conflicting outcomes — the same threshold, reused
    rather than redefined."""
    base = max(0.0, 100.0 - evidence_strength)
    if 35.0 <= causal_confidence <= 65.0:
        base = min(100.0, base + 20.0)
    return round(base, 1)


def _score_strategy(
    goal_relevance: float,
    belief_confidence: float,
    causal_confidence: float,
    evidence_strength: float,
    expected_impact: float,
    uncertainty: float,
) -> float:
    """The transparent composite score. Every input is a plain 0-100
    number computed above from real database rows — nothing here is
    hidden inside an LLM call or a black-box model."""
    weighted = (
        goal_relevance * WEIGHT_GOAL_RELEVANCE
        + belief_confidence * WEIGHT_BELIEF_CONFIDENCE
        + causal_confidence * WEIGHT_CAUSAL_CONFIDENCE
        + evidence_strength * WEIGHT_EVIDENCE_STRENGTH
        + expected_impact * WEIGHT_EXPECTED_IMPACT
    )
    penalized = weighted - (uncertainty * UNCERTAINTY_PENALTY_WEIGHT)
    return round(max(0.0, min(100.0, penalized)), 1)


def _build_rationale(
    causal: models.CausalKnowledge,
    goal_relevance: float,
    belief_confidence: float,
    evidence_strength: float,
    support_count: int,
    uncertainty: float,
) -> str:
    """Plain-text explanation of WHY this strategy scored the way it
    did, generated from the same numbers used to score it — not an LLM
    call. Frozen onto the Strategy row at creation time, so it stays
    true to what was actually known then even if later evidence shifts
    the picture (a later shift creates a NEW strategy, it doesn't edit
    this rationale)."""
    parts = [
        f'Grounded in causal knowledge ("{causal.action}") with {causal.confidence:.0f}% confidence '
        f"from {support_count} supporting experiment{'s' if support_count != 1 else ''}.",
        f"Goal relevance: {goal_relevance:.0f}/100.",
        f"Underlying belief confidence: {belief_confidence:.0f}%.",
    ]
    if evidence_strength < 50.0:
        parts.append(
            f"Evidence is thin ({support_count} experiment{'s' if support_count != 1 else ''}) — "
            "more testing would meaningfully raise confidence."
        )
    if uncertainty >= 50.0:
        parts.append("Uncertainty is elevated; treat this as exploratory rather than settled.")
    return " ".join(parts)


# --- public API ---


def generate_strategies(db: Session, goal: models.Goal) -> list[models.Strategy]:
    """
    Construct candidate strategies for one Goal from Forge's existing
    CausalKnowledge — one candidate per causal fact relevant enough to
    the goal (see MIN_CANDIDATE_RELEVANCE). Purely reads Beliefs/
    CausalKnowledge/Opportunities; never modifies them.
    """
    results: list[models.Strategy] = []

    for causal in db.query(models.CausalKnowledge).all():
        goal_relevance = _causal_relevance_to_goal(db, causal, goal)
        if goal_relevance < MIN_CANDIDATE_RELEVANCE:
            continue

        belief = (
            db.query(models.Belief).filter(models.Belief.id == causal.belief_id).first()
            if causal.belief_id is not None
            else None
        )
        belief_confidence = belief.confidence_score if belief else 50.0

        evidence_strength = _evidence_strength(causal)
        support_count = _experiment_id_count(causal.supporting_experiment_ids)
        expected_impact = round((goal.priority + causal.confidence) / 2, 1)
        uncertainty = _uncertainty(evidence_strength, causal.confidence)
        confidence = _score_strategy(
            goal_relevance, belief_confidence, causal.confidence, evidence_strength, expected_impact, uncertainty
        )

        title = f"{causal.action.strip()[:80]} (for: {goal.statement.strip()[:60]})"
        rationale = _build_rationale(
            causal, goal_relevance, belief_confidence, evidence_strength, support_count, uncertainty
        )

        existing = (
            db.query(models.Strategy)
            .filter(
                models.Strategy.goal_id == goal.id,
                models.Strategy.title == title,
                models.Strategy.status == "candidate",
            )
            .first()
        )

        if existing and abs(existing.confidence - confidence) < RESCORE_CHANGE_THRESHOLD:
            # Nothing meaningfully changed — return the existing row
            # as-is rather than creating a near-duplicate.
            results.append(existing)
            continue

        if existing:
            # The picture genuinely changed. Supersede, don't overwrite
            # — existing.confidence/rationale/etc. are left exactly as
            # they were; only status moves.
            existing.status = "superseded"
            existing.updated_at = utcnow()
            db.commit()

        strategy = models.Strategy(
            goal_id=goal.id,
            title=title,
            description=f'Apply "{causal.action}" under the condition: {causal.condition}',
            rationale=rationale,
            expected_outcome=causal.expected_outcome or causal.actual_outcome,
            confidence=confidence,
            estimated_impact=expected_impact,
            uncertainty=uncertainty,
            status="candidate",
            supporting_belief_ids=str(belief.id) if belief else None,
            supporting_causal_knowledge_ids=str(causal.id),
            supporting_experiment_ids=causal.supporting_experiment_ids,
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        results.append(strategy)

    return results


def list_strategies(
    db: Session, goal_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100
) -> list[models.Strategy]:
    query = db.query(models.Strategy)
    if goal_id is not None:
        query = query.filter(models.Strategy.goal_id == goal_id)
    if status:
        query = query.filter(models.Strategy.status == status)
    return query.order_by(models.Strategy.confidence.desc()).limit(limit).all()


def compare_strategies(db: Session, strategy_id_a: int, strategy_id_b: int) -> Optional[dict]:
    """Side-by-side comparison of two already-scored strategies, using
    their FROZEN stored numbers — not a live recomputation, which
    could drift from what was actually true when each was created.
    Returns which one scores higher, by how much, and both rationales
    so the 'why' is inspectable without guessing."""
    strategy_a = db.query(models.Strategy).filter(models.Strategy.id == strategy_id_a).first()
    strategy_b = db.query(models.Strategy).filter(models.Strategy.id == strategy_id_b).first()
    if not strategy_a or not strategy_b:
        return None

    higher = strategy_a if strategy_a.confidence >= strategy_b.confidence else strategy_b
    lower = strategy_b if higher is strategy_a else strategy_a

    return {
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "higher_scoring": higher.id,
        "score_difference": round(abs(strategy_a.confidence - strategy_b.confidence), 1),
        "explanation": (
            f'Strategy "{higher.title}" scores higher ({higher.confidence:.1f} vs {lower.confidence:.1f}). '
            f"{higher.rationale}"
        ),
    }


def find_relevant_beliefs_for_goal(db: Session, goal: models.Goal, min_relevance: float = 10.0) -> list[models.Belief]:
    """Beliefs with at least min_relevance relevance to THIS specific
    goal — used by world_model.get_goal_graph()."""
    return [
        belief
        for belief in db.query(models.Belief).all()
        if _belief_relevance_to_goal(db, belief, goal) >= min_relevance
    ]


def find_relevant_causal_knowledge_for_goal(
    db: Session, goal: models.Goal, min_relevance: float = 10.0
) -> list[models.CausalKnowledge]:
    """Causal facts with at least min_relevance relevance to THIS
    specific goal — used by world_model.get_goal_graph()."""
    return [
        causal
        for causal in db.query(models.CausalKnowledge).all()
        if _causal_relevance_to_goal(db, causal, goal) >= min_relevance
    ]


# ---------------------------------------------------------------------
# NO AUTONOMOUS EXECUTION.
#
# This module only ever reads existing Forge data and writes Strategy
# rows. It never calls an external API, sends a message, spends money,
# modifies anything outside Forge's own database, or takes any
# irreversible action. A Strategy is a proposal Forge can explain, not
# a command Forge can carry out — that boundary is intentional and
# permanent for this module.
# ---------------------------------------------------------------------
