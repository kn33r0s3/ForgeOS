"""
MONEY EXECUTION ENGINE
========================

Closes the gap between "Forge found and ranked an opportunity" and
"Forge tells the owner exactly what to do next, tracks it through a
real lifecycle, and updates the ranking when it's done." This module
owns the LIFECYCLE (planned -> ready -> in_progress -> completed) and
the explainable ranking formula the owner asked for; it does NOT
reimplement opportunity scoring or the confidence-update math — those
already exist in money_engine.py (score_opportunity(),
record_revenue_result()) and are called into, not duplicated.

    Strategy (strategy_engine.py, a proposal)
        |
        v
    create_action() -> a new Experiment row (v1.5 fields: strategy_id,
                        action_type, status="planned", execution_mode,
                        requires_owner_approval)
        |
        |-- if requires_owner_approval: approve_action() must be called
        |   before start_action() will proceed. This is the actual
        |   safety boundary — anything involving spending or commitment
        |   (paid_pilot, service_delivery) defaults to requiring it.
        v
    start_action() -> status="in_progress", started_at set
        |
        v
    record_action_result() -> delegates to money_engine.record_revenue_
                               result() for the confidence-update math
                               (not duplicated here), then additionally
                               sets completed_at/status/costs — the
                               execution-lifecycle fields money_engine.py
                               doesn't know about
        |
        v
    Opportunity.revenue_confidence/market_confidence/uncertainty updated
    (via the existing money_engine.py logic, unchanged)

PREDICTED vs ATTEMPTED vs COMPLETED vs VERIFIED, made concrete rather
than just asserted:
    predicted  = the Strategy/Opportunity's own confidence/expected_value
                  (nothing has been tried yet)
    attempted   = an Experiment row exists with status >= "in_progress"
                   (started_at is set)
    completed    = status == "completed" (completed_at is set, result
                    recorded)
    verified      = completed AND revenue/costs are non-NULL real numbers,
                     not just a text result — "20 contacted, 4 replied, 1
                     purchased, $39" is verified; "20 contacted, 4
                     replied" with no revenue field set is completed but
                     NOT verified as revenue-producing

Ranking formula (exactly as specified): economic_potential x confidence
x goal_relevance x evidence_quality / execution_cost_time — see
score_action() for how each factor maps to fields that already exist on
Opportunity (money_engine.score_opportunity()'s breakdown) rather than
inventing new ones.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.services import action_engine, money_engine, autonomy_engine
from typing import Optional

# Action types the owner listed. Kept to this small set on purpose —
# "do not create dozens of speculative action types."
ACTION_TYPES = [
    "customer_interview", "outreach", "offer", "paid_pilot",
    "service_delivery", "revenue_experiment", "follow_up",
    "validate_pricing", "build_mvp",
]

# Action types that involve spending or a commitment to a real person —
# historically these defaulted to requiring owner approval directly.
# As of v1.7, approval is decided by autonomy_engine.evaluate_action()
# against the owner's configurable AutonomyPolicy instead of this fixed
# set — kept here only as the execution_mode lookup below, which is a
# different question ("can Forge do this itself") from policy's
# question ("is the owner's boundary satisfied").

# What Forge can actually do itself vs. what needs the owner or an
# external system — Forge NEVER claims to have sent a message, made a
# call, or processed a payment; nothing in this codebase can actually
# do those things (unchanged boundary since v1.0's Strategy Engine).
ACTION_TYPE_EXECUTION_MODE = {
    "customer_interview": "requires_owner_action",
    "outreach": "requires_external_integration",
    "offer": "requires_external_integration",
    "paid_pilot": "requires_owner_action",
    "service_delivery": "requires_owner_action",
    "revenue_experiment": "requires_owner_action",
    "follow_up": "requires_external_integration",
    "validate_pricing": "executable_locally",  # Forge can help draft/reason about pricing tests
    "build_mvp": "requires_owner_action",
}

MIN_COST_TIME_DIVISOR = 1.0  # floor so a $0/same-day action doesn't divide by zero or blow up the score


def utcnow():
    return datetime.now(timezone.utc)


# Order-like action types that must never be executable by ForgeOS,
# regardless of AutonomyPolicy or owner approval. These exist only so
# a proposal can be recorded for *manual* human action in TMS.
ORDER_LIKE_ACTION_TYPES = frozenset({
    "place_order", "buy", "sell", "tms_order", "market_order", "limit_order",
    "broker_order", "execute_trade",
})


def create_action(
    db: Session,
    opportunity_id: int,
    action_type: str,
    description: str,
    strategy_id: Optional[int] = None,
    required_inputs: Optional[str] = None,
    expected_result: Optional[str] = None,
    estimated_cost: Optional[float] = None,
    domain: str = "revenue",
    data_scope: str = "REAL",
) -> Optional[models.Experiment]:
    """
    Create a new executable action against an opportunity — not merely
    advice, a real trackable Experiment row. Evaluated against the
    owner's AutonomyPolicy (v1.7, see autonomy_engine.py) rather than a
    fixed hardcoded set: the resulting decision determines status
    ("blocked" | "planned" | "ready") and requires_owner_approval, and
    the full reasoning is frozen onto the row (policy_decision,
    policy_reason, risk_score) so it's explainable after the fact, not
    just at creation time. A "blocked" action is still created (never
    silently dropped) — it's real information that Forge proposed
    something policy didn't allow.

    v2.0 fail-closed: domain="blocked" or any order-like action_type forces
    execution_allowed=False and cannot be overridden by ALLOW. Owner
    approval of such a proposal only authorizes manual human action,
    never ForgeOS execution.
    """
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == opportunity_id).first()
    if not opportunity:
        return None
    if action_type not in ACTION_TYPES and action_type not in ORDER_LIKE_ACTION_TYPES:
        return None
    if strategy_id is not None and not db.query(models.Strategy).filter(models.Strategy.id == strategy_id).first():
        return None

    is_blocked_or_order = (domain == "blocked") or (action_type in ORDER_LIKE_ACTION_TYPES)

    evaluation = autonomy_engine.evaluate_action(db, opportunity, action_type, estimated_cost)
    decision = evaluation["decision"]

    # Fail-closed for market/order domain: never allow autonomous execution.
    if is_blocked_or_order:
        decision = "block" if decision == "block" else "require_approval"
        # Force status to planned/blocked; never "ready" from creation.
        status = "blocked" if decision == "block" else "planned"
        requires_approval = True
        execution_allowed = False
    else:
        status = "blocked" if decision == "block" else ("ready" if decision == "allow" else "planned")
        requires_approval = (decision != "allow")
        execution_allowed = False  # default remains False even for revenue until explicitly changed by future policy; revenue path still uses existing approval gates

    action = models.Experiment(
        opportunity_id=opportunity_id,
        data_scope=data_scope,
        strategy_id=strategy_id,
        action=description,
        expected_result=expected_result,
        action_type=action_type,
        status="authorizing",
        execution_mode=ACTION_TYPE_EXECUTION_MODE.get(action_type, "requires_owner_action"),
        requires_owner_approval=requires_approval,
        required_inputs=required_inputs,
        estimated_cost=estimated_cost,
        risk_score=evaluation["risk_score"],
        policy_decision=decision,
        policy_reason=" ".join(evaluation["reasons"]),
        attempt_number=evaluation["attempt_number"],
        domain=domain,
        execution_allowed=execution_allowed,
    )
    db.add(action)
    db.flush()

    # Route execution authorization through the canonical Action seam so
    # standing authorization is applied at the same policy boundary used by
    # action_engine.propose_action(). Do not copy Action-only risk/attempt
    # fields onto the Experiment; those remain sourced from evaluate_action().
    proposed_action = action_engine.propose_action(
        db,
        objective=description,
        action_type=action_type,
        opportunity_id=opportunity_id,
        estimated_cost=(estimated_cost if estimated_cost is not None else 0.0),
        experiment_id=action.id,
    )

    if proposed_action is None:
        action.status = "blocked"
        action.requires_owner_approval = True
        action.execution_allowed = False
        action.policy_decision = "BLOCK"
        action.policy_reason = "Canonical Action proposal failed closed."
    else:
        decision = proposed_action.policy_result or "REQUIRE_APPROVAL"
        reason = proposed_action.policy_reason or ""

        # Preserve the execution engine's independent market/order hard stop.
        if is_blocked_or_order:
            decision = "block".upper()
            reason = (reason + " " if reason else "") + (
                "High-risk execution domain/action blocked by default policy."
            )

        action.policy_decision = decision.lower()
        action.policy_reason = reason

        if decision == "BLOCK":
            action.status = "blocked"
            action.requires_owner_approval = True
            action.execution_allowed = False
        elif decision == "ALLOW":
            action.status = "ready"
            action.requires_owner_approval = False
            action.execution_allowed = False
        else:
            action.status = "planned"
            action.requires_owner_approval = True
            action.execution_allowed = False

    db.commit()
    db.refresh(action)
    return action


def approve_action(db: Session, action_id: int) -> Optional[models.Experiment]:
    """Explicit owner approval — the only way an approval-required
    action can ever move to 'ready'/'in_progress'. No auto-approval
    path exists anywhere in this codebase. Cannot approve a
    policy-blocked action (v1.7) — BLOCK is a harder stop than
    REQUIRE_APPROVAL (duplicate, retry limit exhausted, disallowed
    type); overriding it means changing the policy or creating a fresh
    action, not approving the blocked one.

    v2.0: For domain="blocked" or order-like actions, approval only marks
    the proposal as accepted for *manual* human execution. It never
    sets execution_allowed=True and never allows ForgeOS to execute.
    """
    action = db.query(models.Experiment).filter(models.Experiment.id == action_id).first()
    if not action:
        return None
    if action.status == "blocked":
        return None
    if not action.requires_owner_approval:
        return action  # nothing to approve — not an error, just a no-op
    if action.approved_at is None:
        action.approved_at = utcnow()
        # BLOCKED / order proposals stay non-executable by ForgeOS even after approval.
        is_blocked_or_order = (getattr(action, "domain", "revenue") == "blocked") or (
            action.action_type in ORDER_LIKE_ACTION_TYPES
        )
        if is_blocked_or_order:
            action.execution_allowed = False
            # Stay at "planned" or move to a non-executable ready-for-manual state.
            # We deliberately do NOT set status="ready" in a way that start_action
            # would treat as Forge-executable.
            action.status = "planned"
        else:
            action.status = "ready"
        db.commit()
        db.refresh(action)
    return action


def grant_execution_eligibility(db: Session, experiment_id: int, granted_by: str = "system") -> Optional[models.Experiment]:
    """Canonical execution-eligibility gate.

    The ONLY function in the codebase permitted to set
    execution_allowed=True. Every other path (create_action,
    approve_action, experiment_service.authorize_experiment) must
    delegate here; none may set the flag directly.

    Establishes CURRENT authorization at grant time — it does not trust
    a historical ALLOW. Re-runs the canonical policy evaluation via
    autonomy_engine.evaluate_action() using the live AutonomyPolicy, so a
    policy change between proposal and grant cannot leave a stale ALLOW
    executable. Fail-closed on every hard constraint. Never performs an
    external action; it only flips the eligibility flag.

    Authorization basis (one must hold):
    - Standing-authorized: the linked Action carries a standing_auth_id
      whose authorization is still ACTIVE, unexpired, and whose envelope
      still matches at grant time. A valid SA satisfies REQUIRE_APPROVAL
      but never overrides a hard BLOCK.
    - Owner-approved: Experiment.approved_at is set (via approve_action
      or an owner-attributed authorization). Owner approval satisfies
      REQUIRE_APPROVAL but never overrides a hard BLOCK.
    - Direct policy ALLOW: fresh evaluate_action() returns "allow" with
      the CURRENT policy (not the historical proposal-time result).

    Refuses (returns None, flag untouched) on:
    - missing/blocked Experiment, policy_decision == "block"
    - domain == "blocked" or order-like action_type (never executable)
    - linked Action with policy_result == "BLOCK"
    - fresh policy evaluation returns BLOCK (any basis)
    - fresh policy returns REQUIRE_APPROVAL with no valid SA or owner approval
    - SA revoked, expired, or envelope mismatch at grant time
    - requires_owner_approval with no approval and no valid SA
    """
    import json as _json

    action = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    if not action:
        return None
    if action.status == "blocked":
        return None
    if (action.policy_decision or "").lower() == "block":
        return None

    # Hard fail-closed for market / order domain — never executable.
    is_blocked_or_order = (getattr(action, "domain", "revenue") == "blocked") or (
        action.action_type in ORDER_LIKE_ACTION_TYPES
    )
    if is_blocked_or_order:
        return None

    # Find the linked canonical Action (if the Experiment was created
    # through the canonical create_action seam).
    linked = (
        db.query(models.Action)
        .filter(models.Action.experiment_id == action.id)
        .order_by(models.Action.id.desc())
        .first()
    )

    sa_auth_id = None
    linked_params = {}
    if linked is not None:
        if (linked.policy_result or "") == "BLOCK":
            return None
        try:
            linked_params = _json.loads(linked.parameters_json or "{}")
        except Exception:
            linked_params = {}
        if isinstance(linked_params, dict):
            sa_auth_id = linked_params.get("standing_auth_id")

    # --- Fresh policy revalidation ---
    # Re-run the canonical evaluation with the CURRENT policy, using inputs
    # derived from the authoritative Action (not the stale Experiment
    # projection). The Action owns parameters_json; the Experiment's
    # estimated_cost is frozen at creation and may diverge if the Action's
    # params are updated. This does not duplicate policy logic — it calls
    # autonomy_engine.evaluate_action directly. No recursion:
    # evaluate_action never calls this gate.
    #
    # Opportunity-less path: if neither Action nor Experiment has an
    # opportunity, fresh policy evaluation is impossible without inventing
    # context. We do not invent context. The owner's explicit approval
    # (approved_at) stands as the authorization basis; hard static checks
    # (blocked status, policy_decision=="block", blocked/order domain)
    # still apply. This boundary is explicitly tested.
    fresh_decision = None
    opportunity = None

    # Canonical inputs: prefer the durable Action's fields where it owns them.
    grant_action_type = linked.action_type if linked is not None else action.action_type
    grant_opportunity_id = None
    if linked is not None and linked.opportunity_id is not None:
        grant_opportunity_id = linked.opportunity_id
    elif action.opportunity_id is not None:
        grant_opportunity_id = action.opportunity_id

    grant_estimated_cost = None
    if isinstance(linked_params, dict) and linked_params.get("estimated_cost") is not None:
        # Authoritative: the Action's current parameters.
        try:
            grant_estimated_cost = float(linked_params.get("estimated_cost"))
        except (TypeError, ValueError):
            grant_estimated_cost = None
    if grant_estimated_cost is None:
        # Fallback: the Experiment's frozen projection (may be stale).
        grant_estimated_cost = action.estimated_cost

    if grant_opportunity_id is not None:
        opportunity = db.query(models.Opportunity).filter(
            models.Opportunity.id == grant_opportunity_id
        ).first()
    if opportunity is not None:
        fresh = autonomy_engine.evaluate_action(
            db,
            opportunity,
            grant_action_type,
            grant_estimated_cost,
            exclude_experiment_id=action.id,
        )
        fresh_decision = fresh["decision"]
        # Hard BLOCK from current policy overrides every basis.
        if fresh_decision == "block":
            return None

    # --- Authorization basis ---
    if sa_auth_id is not None:
        # Standing-authorized path: the authorization must still be
        # valid RIGHT NOW, not just at proposal time.
        sa = db.get(models.Action, sa_auth_id)
        if sa is None or sa.status != "ACTIVE":
            return None
        active = autonomy_engine.get_active_standing_authorizations(
            db, linked.action_type if linked else None
        )
        if not any(a.id == sa_auth_id for a in active):
            return None
        matched, _ = autonomy_engine.matches_standing_envelope(
            db, sa, linked.action_type, linked_params
        )
        if not matched:
            return None
        # SA valid + no hard BLOCK from fresh policy → eligible.
        # (Fresh REQUIRE_APPROVAL is satisfied by the valid SA.)
    elif action.approved_at is not None:
        # Owner-approved path: explicit human approval on record.
        # Owner approval satisfies fresh REQUIRE_APPROVAL, but a hard
        # BLOCK (already checked above) still refuses.
        # If there is no opportunity for fresh evaluation, the owner's
        # explicit authorization stands on its own.
        pass
    elif fresh_decision == "allow":
        # Direct policy ALLOW: the CURRENT policy allows it outright.
        # Historical proposal-time ALLOW is not trusted.
        pass
    else:
        # No valid authorization basis: fresh policy did not allow, and
        # there is no SA or owner approval to cover REQUIRE_APPROVAL.
        return None

    action.execution_allowed = True
    db.commit()
    db.refresh(action)
    return action


def start_action(db: Session, action_id: int) -> Optional[models.Experiment]:
    """
    Mark an action as actually being carried out. Refuses to start an
    approval-required action that hasn't been approved — this is the
    literal enforcement of "execution != blind autonomy", not just a
    comment. Refuses to start a policy-blocked action outright (v1.7)
    — approval can't override a BLOCK, only a human creating a fresh
    action can. Refuses to double-start an already-started action.

    v2.0 fail-closed: domain="blocked", order-like action_type, or
    execution_allowed=False always rejects start. Owner approval of a
    BLOCKED proposal never authorizes ForgeOS execution.
    """
    action = db.query(models.Experiment).filter(models.Experiment.id == action_id).first()
    if not action:
        return None
    if action.status == "blocked":
        return None
    if action.started_at is not None:
        return action  # already started — no-op, not an error
    if action.requires_owner_approval and action.approved_at is None:
        return None  # blocked: caller must approve_action() first

    # Hard fail-closed for market / order domain
    is_blocked_or_order = (getattr(action, "domain", "revenue") == "blocked") or (
        action.action_type in ORDER_LIKE_ACTION_TYPES
    )
    if is_blocked_or_order or not getattr(action, "execution_allowed", False):
        return None  # cannot start — ForgeOS is not authorized to execute

    action.started_at = utcnow()
    action.status = "in_progress"
    db.commit()
    db.refresh(action)
    return action


def mark_human_action_executed(db: Session, action_id: int) -> Optional[models.Experiment]:
    """Record only that the human/external task was performed.

    This does NOT record a customer response, success, conversion, or revenue.
    It moves an approved human-only action to ``in_progress``, which the
    orchestrator exposes as OUTCOME_PENDING until actual reality is entered.
    """
    action = db.query(models.Experiment).filter(models.Experiment.id == action_id).first()
    if not action or action.status in ("blocked", "abandoned", "completed"):
        return None
    if action.requires_owner_approval and action.approved_at is None:
        return None
    if action.execution_mode not in ("requires_owner_action", "requires_external_integration"):
        return None
    if action.started_at is None:
        action.started_at = utcnow()
        action.status = "in_progress"
        db.commit()
        db.refresh(action)
    return action

def record_action_result(
    db: Session,
    action_id: int,
    result: str,
    revenue: Optional[float] = None,
    conversions: Optional[int] = None,
    costs: Optional[float] = None,
    data_scope: Optional[str] = None,
) -> Optional[models.Experiment]:
    import math
    action = db.get(models.Experiment, action_id)
    if not action:
        return None
    if costs is not None and (not math.isfinite(costs) or costs < 0):
        raise ValueError("Costs must be finite and nonnegative")
    if action.completed_at and action.costs != costs:
        raise ValueError("Conflicting immutable costs")
    try:
        updated = money_engine.record_revenue_result(db, action_id, result, revenue=revenue,
            conversions=conversions, data_scope=data_scope, commit=False)
        updated.costs = costs
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise


def compute_profit(action: models.Experiment) -> Optional[float]:
    """
    Live-computed, never stored/frozen — same principle money_score
    already follows. Requires BOTH revenue and costs to be real
    recorded numbers; either missing means profit is honestly unknown,
    not assumed to be the full revenue figure.
    """
    if action.revenue is None or action.costs is None:
        return None
    return round(action.revenue - action.costs, 2)


def get_action_stage(action: models.Experiment) -> str:
    """predicted | attempted | completed | verified — see module
    docstring for the exact definitions. "predicted" doesn't apply to
    an Experiment row at all (that's the Opportunity/Strategy's own
    confidence before any action exists); this only classifies actions
    that already exist."""
    if action.completed_at is not None:
        if action.revenue is not None and action.costs is not None:
            return "verified"
        return "completed"
    if action.started_at is not None:
        return "attempted"
    return "planned"


def _cost_time_burden(opportunity: models.Opportunity, breakdown: dict) -> float:
    """
    0-100+, higher = more costly/slower to execute — the denominator in
    the owner's ranking formula. Combines whichever real signals exist:
    implementation/acquisition difficulty (via money_engine's existing
    ease factors, always available since difficulty is estimated at
    Opportunity-creation time) as a baseline burden, plus real
    estimated_effort_hours / estimated_startup_cost /
    time_to_first_revenue_days (v1.2 fields) when the owner or Forge has
    actually estimated them. Missing specific numbers don't make an
    opportunity look artificially cheap — the difficulty-based baseline
    always applies regardless.
    """
    ease_avg = (breakdown["ease_implementation"] + breakdown["ease_acquisition"]) / 2.0
    burden = 100.0 - ease_avg  # baseline: always available, from difficulty alone

    if opportunity.estimated_effort_hours is not None:
        burden += min(40.0, opportunity.estimated_effort_hours * 0.4)
    if opportunity.estimated_startup_cost is not None:
        burden += min(40.0, opportunity.estimated_startup_cost * 0.04)  # e.g. $1,000 -> +40 (capped)
    if opportunity.time_to_first_revenue_days is not None:
        burden += min(30.0, opportunity.time_to_first_revenue_days * 0.3)  # e.g. 90 days -> +27

    return max(MIN_COST_TIME_DIVISOR, burden)


def score_action(db: Session, action: models.Experiment) -> dict:
    """
    The owner's own ranking formula, made literal:

        economic_potential x confidence x goal_relevance x evidence_quality
        / execution_cost_time

    Every factor maps to data that already exists on the linked
    Opportunity (via money_engine.score_opportunity()'s breakdown) —
    nothing here is invented. execution_cost_time (see
    _cost_time_burden()) folds in real estimated_effort_hours/
    estimated_startup_cost/time_to_first_revenue_days when set, so a
    genuinely expensive or slow opportunity is penalized using the
    owner's own real numbers, not a difficulty guess alone.
    """
    opportunity = db.query(models.Opportunity).filter(models.Opportunity.id == action.opportunity_id).first()
    if not opportunity:
        return {"action_score": 0.0, "factors": {}}

    breakdown = money_engine.score_opportunity(db, opportunity)

    economic_potential = breakdown["money_score"]  # already 0-100, already evidence-gated, already folds in owner_priority
    confidence = opportunity.revenue_confidence  # 0-100, real evidence only (v1.1)
    goal_relevance = breakdown["goal_priority"]  # 0-100, from the linked Goal if any
    evidence_quality = round((breakdown["problem_evidence"] + breakdown["willingness_evidence"]) / 2, 1)
    execution_cost_time = _cost_time_burden(opportunity, breakdown)

    # Combine the four factors as fractions (0-1) multiplicatively, not
    # additively — a single weak factor (e.g. zero confidence, nothing
    # tested yet) should meaningfully drag the whole score down, matching
    # the owner's literal "x" (multiply) formula. The 4th root brings the
    # product back onto a comparable 0-100 scale rather than collapsing
    # to a near-zero number for any moderately-sized set of factors.
    fractions_product = (
        (economic_potential / 100.0)
        * (confidence / 100.0)
        * (goal_relevance / 100.0)
        * (evidence_quality / 100.0)
    )
    combined_quality = (fractions_product ** 0.25) * 100.0

    # Burden divides the score, but smoothly (100/(100+burden)) rather
    # than as a raw denominator — a raw division by a 0-100+ burden value
    # against 0-100 factors either saturates at the cap or collapses to
    # near-zero for any realistic input, which isn't a useful ranking
    # signal. This decays monotonically with burden and never hits zero.
    cost_time_factor = 100.0 / (100.0 + execution_cost_time)

    base_score = combined_quality * cost_time_factor
    # Small, capped, additive bonus for a strategy with a real
    # completed track record — applied AFTER the core formula, same
    # non-disruptive pattern money_engine.py's v1.3 revenue-source
    # bonus used, specifically to avoid regressing the four already-
    # verified core-formula properties (see v1.5's README section).
    strategy_bonus = _strategy_performance_bonus(db, action)
    action_score = round(max(0.0, min(100.0, base_score + strategy_bonus)), 1)

    return {
        "action_score": action_score,
        "factors": {
            "economic_potential": economic_potential,
            "confidence": confidence,
            "goal_relevance": goal_relevance,
            "evidence_quality": evidence_quality,
            "execution_cost_time_burden": round(execution_cost_time, 1),
        },
    }


def rank_pending_actions(db: Session, limit: int = 10) -> list[dict]:
    """Every action not yet completed AND not policy-blocked (v1.7 —
    a blocked action can never be started, so ranking it alongside
    real pursuable actions would be misleading), scored and ranked
    highest first. Returns [{"action": Experiment, "action_score":
    float, "factors": dict, "stage": str}, ...]."""
    pending = (
        db.query(models.Experiment)
        .filter(
            models.Experiment.action_type.isnot(None),
            models.Experiment.status.notin_(["completed", "blocked"]),
        )
        .all()
    )
    scored = []
    for action in pending:
        result = score_action(db, action)
        scored.append(
            {
                "action": action,
                "action_score": result["action_score"],
                "factors": result["factors"],
                "stage": get_action_stage(action),
            }
        )
    scored.sort(key=lambda item: item["action_score"], reverse=True)
    return scored[:limit]


def recommend_next_money_action(db: Session) -> Optional[dict]:
    """
    "What should I do right now to make money?" — from actual ranked
    pending actions, not a fresh opportunity-level guess. If no
    execution actions exist yet at all, falls back to money_engine.
    recommend_next_action()'s opportunity-level recommendation (still
    real data, just one step earlier in the loop) rather than
    returning nothing.
    """
    pending = rank_pending_actions(db, limit=50)
    ranked = [item for item in pending if item["factors"]]
    if ranked:
        top = ranked[0]
        action = top["action"]
        return {
            "action": action,
            "action_score": top["action_score"],
            "factors": top["factors"],
            "stage": top["stage"],
            "reasoning": (
                f"Ranked highest among pending actions: economic potential "
                f"{top['factors']['economic_potential']:.0f}/100, confidence "
                f"{top['factors']['confidence']:.0f}/100, goal relevance "
                f"{top['factors']['goal_relevance']:.0f}/100, evidence quality "
                f"{top['factors']['evidence_quality']:.0f}/100, execution cost/time burden "
                f"{top['factors']['execution_cost_time_burden']:.0f}."
            ),
            "next_step": (
                "Awaiting owner approval before this can start."
                if action.requires_owner_approval and action.approved_at is None
                else "Ready to start." if action.started_at is None
                else "In progress — record the result when it concludes."
            ),
        }

    # Nothing scoreable yet — fall back one step, still real data.
    fallback = money_engine.recommend_next_action(db)
    if not fallback:
        if not pending:
            return None
        action = pending[0]["action"]
        return {
            "action": action,
            "action_score": 0.0,
            "factors": None,
            "stage": pending[0]["stage"],
            "reasoning": "Pending actions are not linked to an opportunity, so economic potential cannot be scored.",
            "next_step": "Link an opportunity before this action can be ranked.",
        }
    return {
        "action": None,
        "action_score": fallback["money_score"],
        "factors": None,
        "stage": "predicted",
        "reasoning": fallback["reasoning"],
        "next_step": (
            f"Pending actions are not linked to an opportunity, so they cannot be ranked. {fallback['next_step']}"
            if pending
            else f"No execution action created yet. {fallback['next_step']}"
        ),
    }


# --- Autonomous action proposal (v1.7) --------------------------------


def run_autonomous_action_cycle(db: Session) -> dict:
    """
    The autonomous DECISION loop, called from forge_loop.run_cycle()
    (and therefore worker.py). For every opportunity that needs
    validation (money_engine's existing definition: decent money_score,
    zero revenue evidence) and has no pending action yet, propose the
    single lowest-risk allowed action type — evaluated against the real
    AutonomyPolicy, exactly like a manually-created action.

    CRITICAL DISTINCTION, enforced by construction, not just claimed:
    this function creates actions and lets policy decide ALLOW/
    REQUIRE_APPROVAL/BLOCK — that is an AUTONOMOUS DECISION. It never
    calls start_action(). Even an ALLOWed action sits at status="ready"
    until something actually carries it out — and every action type
    Forge can propose today has execution_mode "requires_owner_action"
    or "requires_external_integration" except validate_pricing, which
    is "executable_locally" in the narrow sense of "Forge can help
    reason about a pricing test," not "Forge independently ran one in
    the real world." Nothing in this function is AUTONOMOUS EXECUTION.

    Bounded and idempotent by construction: evaluate_action()'s own
    duplicate/concurrency/daily-limit checks (the same ones a manual
    create_action() call goes through) prevent this from creating
    unbounded actions across repeated cycles — a second cycle with
    nothing new to propose creates nothing.
    """
    proposed = 0
    allowed = 0
    blocked = 0
    require_approval = 0

    policy = autonomy_engine.get_active_policy(db)
    if not policy:
        return {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0, "reason": "no active policy"}

    allowed_types = autonomy_engine.parse_allowed_action_types(policy)
    if not allowed_types:
        return {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0, "reason": "policy allows no action types"}

    # Prefer the lowest-risk allowed type — the "$0-first, learning per
    # dollar" principle: don't propose a paid_pilot when a free
    # customer_interview would test the same underlying opportunity.
    preferred_type = min(allowed_types, key=lambda t: autonomy_engine.BASE_RISK_BY_ACTION_TYPE.get(t, 30.0))

    ranked = money_engine.rank_opportunities(db, limit=50)
    for item in ranked:
        opportunity = item["opportunity"]
        if opportunity.revenue_confidence != 0.0:
            continue  # already has real evidence — not what "needs validation" means here
        if item["money_score"] < policy.min_confidence_required:
            continue  # not promising enough to spend even a free action on

        action = create_action(
            db,
            opportunity.id,
            preferred_type,
            f"Autonomously proposed: {preferred_type} for \"{opportunity.problem[:80]}\"",
            estimated_cost=0.0,
        )
        if not action:
            continue
        proposed += 1
        if action.policy_decision == "allow":
            allowed += 1
        elif action.policy_decision == "block":
            blocked += 1
        else:
            require_approval += 1

    return {"proposed": proposed, "allowed": allowed, "blocked": blocked, "require_approval": require_approval}


# --- Revenue tiers: potential / expected / realized (v1.7) -------------


def get_revenue_breakdown(db: Session) -> dict:
    """
    The three-tier distinction the spec requires, made explicit rather
    than left implicit across separate fields: POTENTIAL (the owner's
    own stated 30/90-day projections — estimates, never facts),
    EXPECTED (money_engine's probability-weighted expected_value —
    real evidence, discounted by how confident that evidence is), and
    REALIZED (actual summed Experiment.revenue from completed actions
    — the only tier that's ever "earned," not projected).
    """
    opportunities = db.query(models.Opportunity).all()
    potential_30d = sum(o.estimated_revenue_30d for o in opportunities if o.estimated_revenue_30d)
    potential_90d = sum(o.estimated_revenue_90d for o in opportunities if o.estimated_revenue_90d)

    expected_total = 0.0
    for o in opportunities:
        breakdown = money_engine.score_opportunity(db, o)
        if breakdown["expected_value"] is not None:
            expected_total += breakdown["expected_value"]

    realized = sum(o.actual_value or 0 for o in db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE", data_scope="REAL").all())

    return {
        "potential_30d": round(potential_30d, 2),
        "potential_90d": round(potential_90d, 2),
        "expected": round(expected_total, 2),
        "realized": round(realized, 2),
    }


# --- Learning from money: strategy performance (v1.7) ------------------


def get_strategy_performance(db: Session, strategy_id: int) -> dict:
    """
    "Strategy A: 10 experiments, 7 successes, $2,400 revenue, $400
    cost" — made concrete from real completed Experiment rows linked
    via strategy_id (v1.5). Only ever computed from recorded evidence;
    a strategy with zero completed actions returns all-zero/unknown
    fields, never an invented performance figure.
    """
    completed = (
        db.query(models.Experiment)
        .filter(models.Experiment.strategy_id == strategy_id, models.Experiment.data_scope == "REAL", models.Experiment.completed_at.isnot(None))
        .all()
    )
    if not completed:
        return {
            "strategy_id": strategy_id,
            "attempts": 0,
            "successes": 0,
            "success_rate": None,
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "net_profit": None,
        }

    successes = sum(1 for a in completed if (a.revenue and a.revenue > 0) or (a.conversions and a.conversions > 0))
    total_revenue = sum(a.revenue for a in completed if a.revenue)
    costed = [a for a in completed if a.costs is not None]
    total_cost = sum(a.costs for a in costed)

    return {
        "strategy_id": strategy_id,
        "attempts": len(completed),
        "successes": successes,
        "success_rate": round(successes / len(completed) * 100.0, 1),
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2) if costed else None,
        "net_profit": round(total_revenue - total_cost, 2) if costed else None,
    }


STRATEGY_PERFORMANCE_BONUS_WEIGHT = 10.0  # small, capped, additive — see score_action()'s docstring for why this doesn't reweight the core formula


def _strategy_performance_bonus(db: Session, action: models.Experiment) -> float:
    """0-10 additive bonus (not a reweighting of score_action()'s
    verified core formula) for actions tied to a strategy with a real,
    recorded track record — "historical strategy success" from the
    spec, folded in the same low-risk way v1.3's revenue-source
    grounding bonus was: added after the core score, capped small,
    zero for the common case (no strategy_id, or a strategy with no
    completed history yet)."""
    if action.strategy_id is None:
        return 0.0
    perf = get_strategy_performance(db, action.strategy_id)
    if perf["success_rate"] is None:
        return 0.0
    return round((perf["success_rate"] / 100.0) * STRATEGY_PERFORMANCE_BONUS_WEIGHT, 1)
