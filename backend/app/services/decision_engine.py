"""
DECISION ENGINE
================

Records explicit decisions with rationale. Does not auto-execute.
Links goals, opportunities, beliefs, and strategies to a chosen path.

A Decision answers: "Why this action, and not the alternatives?"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow




def propose_decision(
    db: Session,
    *,
    title: str,
    rationale: str,
    opportunity_id: Optional[int] = None,
    goal_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    belief_id: Optional[int] = None,
    alternatives_considered: Optional[str] = None,
    expected_outcome: Optional[str] = None,
    expected_cost: Optional[float] = None,
    expected_value: Optional[float] = None,
    risk_notes: Optional[str] = None,
    confidence_at_decision: Optional[float] = None,
) -> models.Decision:
    d = models.Decision(
        title=title,
        rationale=rationale,
        opportunity_id=opportunity_id,
        goal_id=goal_id,
        strategy_id=strategy_id,
        belief_id=belief_id,
        alternatives_considered=alternatives_considered,
        expected_outcome=expected_outcome,
        expected_cost=expected_cost,  # ESTIMATE
        expected_value=expected_value,  # ESTIMATE
        risk_notes=risk_notes,
        confidence_at_decision=confidence_at_decision,
        status="proposed",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def accept_decision(db: Session, decision_id: int) -> Optional[models.Decision]:
    d = db.query(models.Decision).filter_by(id=decision_id).first()
    if not d:
        return None
    d.status = "accepted"
    d.decided_at = utcnow()
    db.commit()
    db.refresh(d)
    return d


def list_decisions(db: Session, limit: int = 50) -> list[models.Decision]:
    return (
        db.query(models.Decision)
        .order_by(models.Decision.created_at.desc())
        .limit(limit)
        .all()
    )


def suggest_next_experiment_decision(
    db: Session,
    opportunity_id: int,
    data_scope: str = "REAL",
) -> Optional[models.Decision]:
    """Given an opportunity with high uncertainty, propose a low-cost
    validation decision (e.g. customer interviews before building)."""
    opp = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opp:
        return None

    rationale_parts = [
        f"Opportunity: {opp.problem[:200]}",
        f"Current score: {opp.score} (heuristic, not proof of demand).",
        "Willingness-to-pay and acquisition path are typically UNKNOWN until tested.",
        "A low-cost experiment (interviews / landing page) reduces uncertainty before larger investment.",
    ]
    if opp.market_confidence is not None and opp.market_confidence < 40:
        rationale_parts.append(f"Market confidence is only {opp.market_confidence}/100 — evidence is thin.")

    # Lessons Memory recall (v2.10): if this exact opportunity (or a themed one)
    # has real past learning, surface it verbatim so the decision is informed by
    # what was actually learned — never an invented claim. Mirrors how the
    # operator's assistant recalls filed memories when reasoning.
    recalled = []
    try:
        from app.services import lessons_engine
        recalled = lessons_engine.recall_lessons(db, opportunity_id=opportunity_id, limit=3, data_scope=data_scope)
        if recalled:
            for l in recalled:
                rationale_parts.append(
                    f"Recalled lesson ({l.theme_key}{' x%s' % l.hit_count if l.hit_count > 1 else ''}): {l.summary[:160]}"
                )
    except Exception:
        # Recall is advisory; a failure must not block decision proposal.
        db.rollback()

    price_lessons = [l for l in recalled if "Price sensitivity" in (l.summary or "")]
    recommendation = "Validate demand before building: interview/outreach"
    if price_lessons:
        recommendation = "Modify pricing test using recorded lower-price feedback"
        rationale_parts.append("Next test: " + price_lessons[0].summary)

    return propose_decision(
        db,
        title=f"[{data_scope}] {recommendation} for opportunity #{opportunity_id}",
        rationale="\n".join(rationale_parts),
        opportunity_id=opportunity_id,
        alternatives_considered="Build full MVP immediately (higher cost, slower feedback); do nothing (zero learning).",
        expected_outcome="At least qualitative signal on willingness to pay and problem severity from 5–20 prospects.",
        expected_cost=0.0,  # ESTIMATE — time only
        risk_notes="Low financial risk; main cost is time. Reversible.",
        confidence_at_decision=opp.market_confidence,
    )
