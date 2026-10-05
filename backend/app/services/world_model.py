"""
WORLD MODEL
============

Forge doesn't just store facts in separate tables — Signal, Pattern,
Belief, Evidence, Prediction, BeliefExperiment, Goal, Opportunity, and
Knowledge all already exist and are already linked via foreign keys.
What's been missing is a single place that WALKS those links and
returns one connected view: for a given belief, which Pattern caused
it to exist, which Opportunities and Goals that pattern connects to
(so Forge can answer not just "where did this belief come from" but
"why does it matter"), every piece of supporting and contradicting
evidence, which sources produced it (and how reliable each currently
is), when it was last tested against reality, which other beliefs are
similar (reusing the same embeddings the Memory Layer already computes
— see memory_layer.py), every real-world experiment run against it,
and how its confidence has actually changed over time.

This is a deliberate design choice: a "World Model" doesn't need its
own database if every fact is already reachable through existing
tables — it needs one reliable place that reaches all of them
together. This module is read-only synthesis; it never writes.

The Goal-Aware layer (related_opportunities, related_goals,
goal_relevance_score) walks belief -> pattern -> opportunity -> goal,
a chain that's been structurally possible since Opportunity gained
pattern_id/goal_id and Belief gained pattern_id, but was never actually
queried together until now. goal_relevance_score reuses
goal_engine.belief_goal_relevance() rather than duplicating scoring
logic here.

confidence_changes reads from ConfidenceEvent (models.py) — an
append-only history log belief_engine.py writes to at its one
confidence-change choke point. Never overwritten, so a belief's
confidence trajectory survives even though confidence_score itself is
always just the current value.

stability_score and confidence_trend (v0.8) turn that history into a
temporal read on the belief — see belief_stability.py. Computed here
by reusing data already fetched (contradicting_evidence, predictions,
confidence_changes), not by re-querying.

related_causal_knowledge / successful_actions / failed_actions (v0.9)
surface what Forge has actually learned from testing real actions
under this belief — see causal_engine.py, which converts completed
BeliefExperiments into structured condition/action/outcome facts as a
side effect of experiment_runner.record_result().

Belief.pattern_id is what makes "which pattern created this belief"
answerable at all — before that FK existed, a Pattern's id was read
once to build a belief's statement and then discarded, so there was no
way to trace a belief back to its cause. See belief_engine.py's module
docstring.

Evidence (the table) is treated as the single source of truth for
"what supports/contradicts this belief" — NOT Belief.supporting_
signal_ids, which is a legacy comma-string field from before the
Evidence table existed and is never updated by the Reality Checker.
That's a duplication worth naming explicitly rather than quietly
picking one: the string field still exists (no destructive migration),
but nothing here reads it.

get_goal_graph() (v1.0) is the GOAL-scoped counterpart to
get_belief_graph()'s BELIEF-scoped view — added, not merged in, so the
existing belief-centric function stays completely unchanged. It
surfaces every belief and causal fact relevant to one specific goal,
plus every candidate strategy generated for it — see strategy_engine.py,
which owns the actual relevance/scoring logic; this function only
assembles what strategy_engine.py already knows how to compute.

get_goal_graph() (v1.1) now also surfaces every Opportunity linked to
the goal, each with its live money_score (see money_engine.py) — Goal
-> Opportunity was already a real FK relationship (Opportunity.goal_id),
just never surfaced in this view before. get_opportunity_money_graph()
(v1.1, new) is the OPPORTUNITY-scoped counterpart: full monetization
breakdown, every revenue experiment (the complete, immutable history —
nothing here is ever deleted or rewritten), and any Strategies sharing
the same goal.
"""

from sqlalchemy.orm import Session

from typing import Optional

from app import models
from app.services import (
    reality_memory,
    memory_layer,
    experiment_runner,
    source_manager,
    goal_engine,
    belief_stability,
    causal_engine,
    strategy_engine,
    money_engine,
)


def get_belief_graph(db: Session, belief_id: int) -> Optional[dict]:
    """Assemble the full connected view of one belief. Returns None if
    the belief doesn't exist."""
    belief = db.query(models.Belief).filter(models.Belief.id == belief_id).first()
    if not belief:
        return None

    originating_pattern = None
    if belief.pattern_id is not None:
        originating_pattern = (
            db.query(models.Pattern).filter(models.Pattern.id == belief.pattern_id).first()
        )

    # Goal-aware layer: belief -> pattern -> opportunity -> goal. Only
    # possible when the belief has a recorded pattern_id (see
    # belief_engine.py) and that pattern has Opportunities built from
    # it — both are common-but-not-universal, so this degrades to
    # empty lists / a 0.0 score rather than erroring.
    related_opportunities: list[models.Opportunity] = []
    related_goals: list[models.Goal] = []
    if belief.pattern_id is not None:
        related_opportunities = (
            db.query(models.Opportunity)
            .filter(models.Opportunity.pattern_id == belief.pattern_id)
            .all()
        )
        linked_goal_ids = {o.goal_id for o in related_opportunities if o.goal_id is not None}
        if linked_goal_ids:
            related_goals = db.query(models.Goal).filter(models.Goal.id.in_(linked_goal_ids)).all()

    goal_relevance_score = goal_engine.belief_goal_relevance(db, belief)

    evidence_rows = reality_memory.list_evidence(db, belief_id=belief_id, limit=200)
    supporting_evidence = [e for e in evidence_rows if e.direction == "supports"]
    contradicting_evidence = [e for e in evidence_rows if e.direction == "contradicts"]

    # Originating sources + their CURRENT reliability (not a snapshot —
    # this reflects any adjustments reality_memory.py has made since).
    origin_sources = sorted({e.source for e in evidence_rows if e.source})
    source_reliability = {name: source_manager.get_reliability(db, name) for name in origin_sources}

    predictions = reality_memory.list_predictions(db, belief_id=belief_id, limit=50)
    resolved_at_dates = [p.resolved_at for p in predictions if p.resolved_at]
    last_verification = max(resolved_at_dates) if resolved_at_dates else None

    # Related beliefs via the Memory Layer's existing embeddings — no
    # new similarity logic needed, this reuses memory_layer.search_knowledge
    # exactly as ai_engine.answer_question() does.
    related_matches = memory_layer.search_knowledge(db, belief.statement, top_k=6, source_type="belief")
    related_beliefs = [
        {
            "belief_id": knowledge.source_id,
            "statement": knowledge.content,
            "confidence_score": knowledge.confidence_score,
            "similarity": round(similarity, 4),
        }
        for knowledge, similarity in related_matches
        if knowledge.source_id != belief.id
    ][:5]

    experiments = experiment_runner.ExperimentRunner(db).list_experiments(belief_id=belief_id)

    confidence_changes = (
        db.query(models.ConfidenceEvent)
        .filter(models.ConfidenceEvent.belief_id == belief_id)
        .order_by(models.ConfidenceEvent.created_at.desc())
        .limit(50)
        .all()
    )

    # Stability/trend reuse data already fetched above (contradicting
    # evidence count, predictions, confidence_changes) rather than
    # re-querying — see belief_stability.py's module docstring for why
    # world_model.py calls the pure scoring functions directly instead
    # of the get_belief_stability() convenience wrapper.
    stability_score = belief_stability.compute_stability_score(
        confidence_changes, len(contradicting_evidence), predictions
    )
    confidence_trend = belief_stability.compute_trend(confidence_changes)

    # Causal knowledge linked to this belief — the reusable
    # condition/action/outcome facts built from its BeliefExperiments
    # (see causal_engine.py). Bucketed into successful/failed by
    # confidence for quick scanning; the full list is also returned so
    # nothing contested in the middle gets silently dropped.
    related_causal_knowledge = causal_engine.list_causal_knowledge(db, belief_id=belief_id)
    successful_actions = [c for c in related_causal_knowledge if c.confidence >= 60.0]
    failed_actions = [c for c in related_causal_knowledge if c.confidence <= 40.0]

    return {
        "belief": belief,
        "originating_pattern": originating_pattern,
        "related_opportunities": related_opportunities,
        "related_goals": related_goals,
        "goal_relevance_score": goal_relevance_score,
        "stability_score": stability_score,
        "confidence_trend": confidence_trend,
        "related_causal_knowledge": related_causal_knowledge,
        "successful_actions": successful_actions,
        "failed_actions": failed_actions,
        "last_verification": last_verification,
        "supporting_evidence": supporting_evidence,
        "contradicting_evidence": contradicting_evidence,
        "origin_sources": origin_sources,
        "source_reliability": source_reliability,
        "related_beliefs": related_beliefs,
        "experiments": experiments,
        "predictions": predictions,
        "confidence_changes": confidence_changes,
    }


def get_goal_graph(db: Session, goal_id: int) -> Optional[dict]:
    """
    The Strategic view of one Goal (v1.0, extended v1.1): every belief
    and piece of causal knowledge Forge already has that's relevant to
    it, every candidate strategy generated so far, and every
    Opportunity linked to it with its live money_score. Returns None
    if the goal doesn't exist.

    This is read-only synthesis, same principle as get_belief_graph() —
    it does NOT generate new strategies or opportunities (those are
    writes, triggered separately). Calling this repeatedly is always
    safe and never changes anything.
    """
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal:
        return None

    relevant_beliefs = strategy_engine.find_relevant_beliefs_for_goal(db, goal)
    relevant_causal_knowledge = strategy_engine.find_relevant_causal_knowledge_for_goal(db, goal)
    candidate_strategies = strategy_engine.list_strategies(db, goal_id=goal_id, status="candidate")
    ranked_opportunities = money_engine.rank_opportunities(db, goal_id=goal_id, limit=50)

    return {
        "goal": goal,
        "opportunities": [
            {"opportunity": item["opportunity"], "money_score": item["money_score"], "expected_value": item["expected_value"]}
            for item in ranked_opportunities
        ],
        "relevant_beliefs": relevant_beliefs,
        "relevant_causal_knowledge": relevant_causal_knowledge,
        "candidate_strategies": candidate_strategies,
    }


def get_opportunity_money_graph(db: Session, opportunity_id: int) -> Optional[dict]:
    """
    The Money Engine view of one Opportunity (v1.1): its live
    money_score breakdown, its COMPLETE revenue experiment history
    (every Experiment row ever recorded against it — nothing here is
    ever deleted or edited after completion, see money_engine.py), the
    total real revenue recorded so far, and any Strategies that share
    its goal. Returns None if the opportunity doesn't exist.

    Read-only synthesis, same principle as get_belief_graph() and
    get_goal_graph() — it does not run new experiments or change
    scores; it assembles what money_engine.py and strategy_engine.py
    already know how to compute.
    """
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        return None

    score = money_engine.score_opportunity(db, opportunity)
    revenue_experiments = money_engine.list_revenue_experiments(db, opportunity_id=opportunity_id)
    total_revenue_recorded = round(sum(e.revenue for e in revenue_experiments if e.revenue and e.data_scope == "REAL"), 2)

    related_strategies = []
    if opportunity.goal_id is not None:
        related_strategies = strategy_engine.list_strategies(db, goal_id=opportunity.goal_id, status="candidate")

    return {
        "opportunity": opportunity,
        "money_score": score["money_score"],
        "expected_value": score["expected_value"],
        "score_breakdown": score,
        "revenue_experiments": revenue_experiments,
        "total_revenue_recorded": total_revenue_recorded,
        "related_strategies": related_strategies,
    }
