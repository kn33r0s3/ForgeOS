"""
AUTONOMY POLICY ENGINE
=========================

Represents the owner's operating AUTHORITY as data, not a hardcoded
constant. Before v1.7, whether an action needed approval was decided
by one fixed set in execution_engine.py
(`{"paid_pilot", "service_delivery"}`) — the same for every owner,
every opportunity, forever. This module replaces that with a real,
owner-configurable boundary (`AutonomyPolicy`) and a transparent
evaluation function: given a candidate action, decide ALLOW /
REQUIRE_APPROVAL / BLOCK, with every contributing reason listed, not
just a final verdict.

    candidate action (opportunity, action_type, estimated_cost)
        |
        v
    evaluate_action() checks, in order, against the active policy:
        1. action_type allowed at all?              -> BLOCK if not
        2. duplicate already pending?                 -> BLOCK
        3. retry limit exhausted for this pair?         -> BLOCK
        4. concurrency limit reached?                     -> REQUIRE_APPROVAL
        5. daily action limit reached?                      -> REQUIRE_APPROVAL
        6. cost exceeds (or is unknown against) the spend
           boundary?                                          -> REQUIRE_APPROVAL
        7. opportunity confidence below the floor?                -> REQUIRE_APPROVAL
        8. computed risk_score above the ceiling?                    -> REQUIRE_APPROVAL
        else                                                          -> ALLOW
        |
        v
    {"decision": ..., "reasons": [...], "risk_score": ...}

BLOCK always wins over REQUIRE_APPROVAL, which always wins over ALLOW —
the decision returned is the single worst outcome triggered, but ALL
triggered reasons are returned, not just the first, so the explanation
is complete ("the decision must be explainable").

Every check reads real data (the policy row, the opportunity's own
evidence-gated fields, actual pending/completed Experiment rows) —
nothing here is a fabricated judgment call. Unknown cost against a
nonzero spend boundary is treated as REQUIRE_APPROVAL, not ALLOW —
"never assume a cost is safe just because it wasn't stated."

CRITICAL DISTINCTION this module exists to make precise: an ALLOW
decision means the action is AUTHORIZED to proceed within policy. It
does NOT mean Forge can carry it out. Whether Forge can actually DO the
thing is execution_mode's job (executable_locally vs
requires_owner_action vs requires_external_integration — see
execution_engine.py), a completely separate question. Policy answers
"is the owner's boundary satisfied"; execution_mode answers "can Forge
actually do this itself." Conflating the two would let an autonomously
AUTHORIZED action look like an autonomously EXECUTED one, which is
exactly the false claim this whole engine is built to prevent.

FORGEOS TOP RULE: drive owner dependency to zero. Reduce repeated
approval only when the active policy explicitly covers the action and a
real execution adapter can perform it. An ALLOW verdict alone never
removes an owner action, grants external permission, or proves an
economic outcome.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from typing import Optional

# Conservative seed — "do not create unlimited real-world authority
# without safeguards" enforced by what this actually seeds to, not
# just asserted. Zero autonomous spend; only the genuinely free,
# lowest-risk action types allowed without approval.
DEFAULT_POLICY = {
    "name": "default",
    "active": True,
    "max_experiment_spend": 0.0,
    "max_concurrent_experiments": 1,
    "max_daily_actions": 3,
    "max_retries": 1,
    "min_confidence_required": 50.0,
    "max_risk_threshold": 40.0,
    "allowed_action_types": "customer_interview,validate_pricing,follow_up",
}

# Inherent risk tier per action type — a small, transparent lookup, not
# a model judgment. Higher = more consequential if it goes wrong
# (spending money, committing to a real person) vs. lower (research,
# reasoning Forge can do without touching the outside world).
BASE_RISK_BY_ACTION_TYPE = {
    "validate_pricing": 5.0,
    "customer_interview": 10.0,
    "follow_up": 10.0,
    "revenue_experiment": 20.0,
    "outreach": 20.0,
    "build_mvp": 30.0,
    "offer": 30.0,
    "paid_pilot": 50.0,
    "service_delivery": 55.0,
}


def utcnow():
    return datetime.now(timezone.utc)


def seed_default_policy(db: Session) -> None:
    """Insert the default AutonomyPolicy if no active policy exists
    yet. Safe to call every startup — a no-op once a policy exists,
    same pattern as source_manager.seed_default_sources() and
    money_engine.seed_default_revenue_sources()."""
    existing = db.query(models.AutonomyPolicy).filter(models.AutonomyPolicy.active.is_(True)).first()
    if existing:
        return
    db.add(models.AutonomyPolicy(**DEFAULT_POLICY))
    db.commit()


def get_active_policy(db: Session) -> Optional[models.AutonomyPolicy]:
    return db.query(models.AutonomyPolicy).filter(models.AutonomyPolicy.active.is_(True)).first()


def compute_risk_score(
    action_type: str, opportunity: models.Opportunity, estimated_cost: Optional[float], policy: models.AutonomyPolicy
) -> float:
    """
    0-100, higher = riskier. Transparent weighted sum, not a
    fabricated judgment: the action type's inherent risk tier, plus
    how uncertain the underlying opportunity still is (real
    Opportunity.uncertainty, evidence-gated since v1.1), plus how much
    of the spend boundary this action would consume.
    """
    base = BASE_RISK_BY_ACTION_TYPE.get(action_type, 30.0)
    uncertainty_component = opportunity.uncertainty * 0.2  # up to 20 points from an unvalidated opportunity

    spend_component = 0.0
    if estimated_cost is not None and policy.max_experiment_spend is not None and policy.max_experiment_spend > 0:
        spend_component = min(20.0, (estimated_cost / policy.max_experiment_spend) * 20.0)
    elif estimated_cost is not None and estimated_cost > 0 and (policy.max_experiment_spend or 0) == 0:
        # Any real spend against a $0 boundary is maximally risky by definition.
        spend_component = 20.0

    return round(min(100.0, base + uncertainty_component + spend_component), 1)


def _count_pending_actions(db: Session) -> int:
    return (
        db.query(models.Experiment)
        .filter(models.Experiment.action_type.isnot(None), models.Experiment.status.in_(["ready", "in_progress"]))
        .count()
    )


def _count_actions_today(db: Session) -> int:
    start_of_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(models.Experiment)
        .filter(models.Experiment.action_type.isnot(None), models.Experiment.created_at >= start_of_day)
        .count()
    )


def _find_duplicate_pending(db: Session, opportunity_id: int, action_type: str) -> Optional[models.Experiment]:
    return (
        db.query(models.Experiment)
        .filter(
            models.Experiment.opportunity_id == opportunity_id,
            models.Experiment.action_type == action_type,
            models.Experiment.status.in_(["planned", "ready", "in_progress"]),
        )
        .first()
    )


def _count_failed_attempts(db: Session, opportunity_id: int, action_type: str) -> int:
    """A "failed attempt" is a completed action with no revenue and no
    conversions recorded — a real, recorded non-success, not a guess."""
    completed = (
        db.query(models.Experiment)
        .filter(
            models.Experiment.opportunity_id == opportunity_id,
            models.Experiment.action_type == action_type,
            models.Experiment.completed_at.isnot(None),
        )
        .all()
    )
    return sum(1 for a in completed if not (a.revenue and a.revenue > 0) and not (a.conversions and a.conversions > 0))


def evaluate_action(
    db: Session, opportunity: models.Opportunity, action_type: str, estimated_cost: Optional[float]
) -> dict:
    """
    The core policy evaluation. Returns {"decision": "allow" |
    "require_approval" | "block", "reasons": [...], "risk_score": float,
    "attempt_number": int}. Every reason is a plain sentence built from
    the real number that triggered it — nothing here is a template
    with the numbers hidden.
    """
    policy = get_active_policy(db)
    if not policy:
        # No policy configured at all — the safest possible default is
        # to require approval for everything rather than silently
        # allowing anything. Never bypass policy by having none.
        return {
            "decision": "require_approval",
            "reasons": ["No autonomy policy is configured — every action requires approval until one is set."],
            "risk_score": 100.0,
            "attempt_number": 1,
        }

    reasons: list[str] = []
    decision = "allow"

    def escalate(new_decision: str, reason: str):
        nonlocal decision
        reasons.append(reason)
        if new_decision == "block" or decision != "block":
            if new_decision == "block":
                decision = "block"
            elif decision == "allow":
                decision = "require_approval"

    allowed_types = set((policy.allowed_action_types or "").split(",")) - {""}
    if action_type not in allowed_types:
        escalate("block", f'Action type "{action_type}" is not in the currently allowed set ({sorted(allowed_types) or "none"}).')

    duplicate = _find_duplicate_pending(db, opportunity.id, action_type)
    if duplicate:
        escalate("block", f"A {action_type} action (#{duplicate.id}) is already pending for this opportunity.")

    failed_attempts = _count_failed_attempts(db, opportunity.id, action_type)
    attempt_number = failed_attempts + 1
    if failed_attempts >= policy.max_retries:
        escalate(
            "block",
            f"Retry limit reached: {failed_attempts} prior {action_type} attempt(s) on this opportunity failed (limit {policy.max_retries}).",
        )

    pending_count = _count_pending_actions(db)
    if pending_count >= policy.max_concurrent_experiments:
        escalate(
            "require_approval",
            f"{pending_count} action(s) already active, at the concurrency limit ({policy.max_concurrent_experiments}).",
        )

    today_count = _count_actions_today(db)
    if today_count >= policy.max_daily_actions:
        escalate(
            "require_approval",
            f"{today_count} action(s) already created today, at the daily limit ({policy.max_daily_actions}).",
        )

    if policy.max_experiment_spend is not None:
        if estimated_cost is None:
            escalate("require_approval", "Estimated cost was not provided — an unknown cost is never treated as safe.")
        elif estimated_cost > policy.max_experiment_spend:
            escalate(
                "require_approval",
                f"Estimated cost ${estimated_cost:.2f} exceeds the autonomous spend limit (${policy.max_experiment_spend:.2f}).",
            )
    elif estimated_cost is not None and estimated_cost > 0:
        escalate("require_approval", "No autonomous spending is permitted at all under the current policy.")

    if opportunity.revenue_confidence < policy.min_confidence_required:
        # revenue_confidence, not money_score: the same "did anything
        # real validate this yet" signal money_engine.py already uses,
        # not a separate invented metric.
        escalate(
            "require_approval",
            f"Opportunity confidence ({opportunity.revenue_confidence:.0f}%) is below the required floor ({policy.min_confidence_required:.0f}%).",
        )

    risk_score = compute_risk_score(action_type, opportunity, estimated_cost, policy)
    if risk_score > policy.max_risk_threshold:
        escalate("require_approval", f"Computed risk {risk_score:.0f} exceeds the policy ceiling ({policy.max_risk_threshold:.0f}).")

    if not reasons:
        reasons.append(
            f"Within policy: allowed action type, no duplicate or retry conflict, under concurrency/daily/spend limits, "
            f"confidence and risk within bounds (risk {risk_score:.0f}/{policy.max_risk_threshold:.0f})."
        )

    return {"decision": decision, "reasons": reasons, "risk_score": risk_score, "attempt_number": attempt_number}
