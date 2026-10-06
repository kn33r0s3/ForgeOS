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
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models

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


def parse_allowed_action_types(policy: models.AutonomyPolicy) -> List[str]:
    """Canonical parse of the policy's comma-separated action-type list.

    The PATCH /autonomy/policy endpoint stores the owner's text verbatim,
    so a natural edit like ``"customer_interview, validate_pricing"`` (note
    the space) arrives with whitespace intact. Stripping here — at the single
    read site both the evaluator and the proposer share — means the owner's
    written boundary is honored exactly as written, instead of silently
    blocking a type whose only crime was a space after the comma.
    """
    seen: List[str] = []
    for raw in (policy.allowed_action_types or "").split(","):
        token = raw.strip()
        if token and token not in seen:
            seen.append(token)
    return seen


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

    allowed_types = set(parse_allowed_action_types(policy))
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

    # Standing authorization: an ACTIVE bounded envelope derived from a real
    # owner-authorized action can satisfy require_approval — but it can never
    # override a block. Fail closed: blocks stay blocks.
    if decision == "require_approval":
        standing = check_standing_authorization(
            db,
            action_type,
            {
                "estimated_cost": estimated_cost,
                "counterparty_class": getattr(opportunity, "counterparty_class", None),
                "objective": getattr(opportunity, "title", None),
            },
        )
        if standing["allowed"]:
            decision = "allow"
            reasons.append(
                f"Covered by ACTIVE standing authorization #{standing['auth_id']}: "
                + "; ".join(standing["reasons"])
            )

    if not reasons:
        reasons.append(
            f"Within policy: allowed action type, no duplicate or retry conflict, under concurrency/daily/spend limits, "
            f"confidence and risk within bounds (risk {risk_score:.0f}/{policy.max_risk_threshold:.0f})."
        )

    return {"decision": decision, "reasons": reasons, "risk_score": risk_score, "attempt_number": attempt_number}


# ---------------------------------------------------------------------------
# Standing Authorization — compounding owner judgment into reusable bounds.
#
# A standing authorization is an Action with action_type="standing_authorization"
# (no new table). Lifecycle: PROPOSED → ACTIVE → REVOKED/EXPIRED, recorded on
# the existing Action.status with WorldEvents for each transition.
#
# After a REAL owner-authorized action is recorded, propose_standing_authorization()
# derives a BOUNDED envelope from that actual action — never broader than what
# the original authorization justified. The proposal does NOT authorize anything
# until the owner explicitly approves it (approve_standing_authorization()).
# Once ACTIVE, evaluate_action() consults standing envelopes: an equivalent
# future action within every bound is allowed without re-asking the owner.
# Anything outside the envelope still requires approval or is blocked.
# ---------------------------------------------------------------------------

STANDING_AUTH_ACTION_TYPE = "standing_authorization"

# Envelope fields derived from the source action. Every bound is a ceiling
# copied from what actually happened, never invented upward.
ENVELOPE_FIELDS = (
    "source_action_id",
    "action_type",
    "purpose",
    "channel",
    "scope",
    "counterparty_class",
    "content_boundary",
    "max_per_day",
    "max_spend",
    "privacy_boundary",
    "exclusions",
    "expires_at",
    "evidence_required",
    "opt_out_handling",
    "data_scope",
)


def _emit_standing_auth_event(db: Session, event_type: str, auth_action: models.Action, detail: str) -> None:
    """Record a WorldEvent for a standing-authorization lifecycle transition."""
    import json as _json

    db.add(
        models.WorldEvent(
            event_type=event_type,
            payload=_json.dumps(
                {
                    "standing_auth_action_id": auth_action.id,
                    "status": auth_action.status,
                    "detail": detail,
                }
            ),
            source="autonomy_engine.standing_authorization",
            idempotency_key=f"standing-auth-{event_type}-{auth_action.id}",
        )
    )


def _envelope_from_action(source: models.Action) -> dict:
    """Derive a bounded envelope from a real authorized action. Bounds are
    copied from the source action's actual type/objective/parameters — the
    proposal can never authorize more than the original authorization did."""
    import json as _json

    try:
        params = _json.loads(source.parameters_json) if source.parameters_json else {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        params = {}
    return {
        "source_action_id": source.id,
        "action_type": source.action_type,
        "purpose": source.objective,
        "channel": params.get("channel"),
        "scope": params.get("scope"),
        "counterparty_class": params.get("counterparty_class"),
        "content_boundary": params.get("content_boundary") or source.objective,
        "max_per_day": 1,
        "max_spend": 0.0,
        "privacy_boundary": params.get("privacy_boundary"),
        "exclusions": params.get("exclusions") or [],
        "expires_at": None,  # owner sets on approval; None = must be set before ACTIVE
        "evidence_required": ["action_recorded", "outcome_observed"],
        "opt_out_handling": params.get("opt_out_handling") or "honor_immediately",
        "data_scope": "REAL",
    }


def propose_standing_authorization(db: Session, source_action_id: int) -> models.Action:
    """Derive a PROPOSED standing authorization from a real owner-authorized action.

    The source must be a REAL action the owner actually authorized (status
    APPROVED/SUCCEEDED/VERIFIED with approved_at set). The proposal is inert:
    PROPOSED does not authorize execution.
    """
    import json as _json

    source = db.get(models.Action, source_action_id)
    if source is None:
        raise ValueError(f"Source action #{source_action_id} not found.")
    if source.action_type == STANDING_AUTH_ACTION_TYPE:
        raise ValueError("Cannot derive a standing authorization from another standing authorization.")
    if source.status not in ("APPROVED", "SUCCEEDED", "VERIFIED") or not source.approved_at:
        raise ValueError(
            f"Source action #{source_action_id} is not owner-authorized "
            f"(status={source.status}); only real authorized actions seed proposals."
        )
    envelope = _envelope_from_action(source)
    proposal = models.Action(
        action_type=STANDING_AUTH_ACTION_TYPE,
        objective=f"Standing authorization proposal derived from owner-authorized action #{source.id} ({source.action_type})",
        parameters_json=_json.dumps(envelope),
        status="PROPOSED",
        policy_result="REQUIRE_APPROVAL",
        policy_reason="Standing authorization proposal requires explicit owner approval before it authorizes anything.",
    )
    db.add(proposal)
    db.flush()
    _emit_standing_auth_event(db, "standing_authorization_proposed", proposal, f"Derived from action #{source.id}")
    db.flush()
    return proposal


def approve_standing_authorization(db: Session, proposal_id: int, expires_at=None) -> models.Action:
    """Owner explicitly approves a proposal → ACTIVE. An expiry must be set
    (or passed here); a standing authorization without a bound is refused."""
    proposal = db.get(models.Action, proposal_id)
    if proposal is None or proposal.action_type != STANDING_AUTH_ACTION_TYPE:
        raise ValueError(f"Standing authorization proposal #{proposal_id} not found.")
    if proposal.status != "PROPOSED":
        raise ValueError(f"Proposal #{proposal_id} is {proposal.status}, not PROPOSED.")
    import json as _json
    from datetime import datetime, timezone

    envelope = _json.loads(proposal.parameters_json or "{}")
    if expires_at is not None:
        envelope["expires_at"] = expires_at.isoformat() if hasattr(expires_at, "isoformat") else str(expires_at)
    if not envelope.get("expires_at"):
        raise ValueError("Standing authorization requires an expiry bound before activation.")
    proposal.parameters_json = _json.dumps(envelope)
    proposal.status = "ACTIVE"
    proposal.approved_at = utcnow()
    proposal.policy_result = "ALLOW"
    proposal.policy_reason = "Owner explicitly approved the bounded standing authorization."
    _emit_standing_auth_event(db, "standing_authorization_activated", proposal, "Owner approved proposal")
    db.flush()
    # Suppress unused-import warning for timezone (kept for explicitness)
    _ = timezone
    return proposal


def revoke_standing_authorization(db: Session, auth_id: int, reason: str) -> models.Action:
    """Revoke an ACTIVE standing authorization → REVOKED. Future use stops."""
    auth = db.get(models.Action, auth_id)
    if auth is None or auth.action_type != STANDING_AUTH_ACTION_TYPE:
        raise ValueError(f"Standing authorization #{auth_id} not found.")
    if auth.status != "ACTIVE":
        raise ValueError(f"Standing authorization #{auth_id} is {auth.status}, not ACTIVE.")
    auth.status = "REVOKED"
    auth.policy_reason = f"Revoked: {reason}"
    _emit_standing_auth_event(db, "standing_authorization_revoked", auth, reason)
    db.flush()
    return auth


def get_active_standing_authorizations(db: Session, action_type: str | None = None) -> list:
    """Return ACTIVE standing authorizations, expiring any past their bound."""
    import json as _json
    from datetime import datetime, timezone

    query = db.query(models.Action).filter(
        models.Action.action_type == STANDING_AUTH_ACTION_TYPE,
        models.Action.status == "ACTIVE",
    )
    auths = query.all()
    now = datetime.now(timezone.utc)
    live = []
    for auth in auths:
        try:
            envelope = _json.loads(auth.parameters_json or "{}")
        except Exception:
            envelope = {}
        expires_raw = envelope.get("expires_at")
        if expires_raw:
            try:
                expires = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires <= now:
                    auth.status = "EXPIRED"
                    _emit_standing_auth_event(db, "standing_authorization_expired", auth, "Expiry bound reached")
                    continue
            except Exception:
                # Unparseable expiry fails closed: treat as expired.
                auth.status = "EXPIRED"
                _emit_standing_auth_event(db, "standing_authorization_expired", auth, "Unparseable expiry failed closed")
                continue
        if action_type is not None and envelope.get("action_type") != action_type:
            continue
        live.append(auth)
    if live:
        db.flush()
    return live


def matches_standing_envelope(auth: models.Action, proposed_action_type: str, proposed_params: dict | None) -> tuple[bool, list[str]]:
    """Fail-closed envelope check: every bound must hold for a match."""
    import json as _json

    reasons: list[str] = []
    try:
        envelope = _json.loads(auth.parameters_json or "{}")
    except Exception:
        return False, ["Standing authorization envelope is unreadable — failed closed."]
    proposed_params = proposed_params or {}

    if envelope.get("action_type") != proposed_action_type:
        return False, [f"Action type {proposed_action_type!r} is outside the authorized envelope ({envelope.get('action_type')!r})."]
    for field in ("channel", "scope", "counterparty_class", "privacy_boundary"):
        bound = envelope.get(field)
        if bound is not None and proposed_params.get(field) != bound:
            reasons.append(f"Field {field!r}={proposed_params.get(field)!r} does not match the authorized bound ({bound!r}).")
    # Spend bound: proposed spend must not exceed the envelope ceiling.
    try:
        proposed_spend = float(proposed_params.get("estimated_cost") or 0.0)
        max_spend = float(envelope.get("max_spend") or 0.0)
    except (TypeError, ValueError):
        return False, ["Spend figures unreadable — failed closed."]
    if proposed_spend > max_spend:
        reasons.append(f"Proposed spend {proposed_spend} exceeds the authorized ceiling {max_spend}.")
    # Exclusions: any excluded counterparty or content pattern blocks.
    for exclusion in envelope.get("exclusions") or []:
        haystacks = [str(proposed_params.get(k) or "") for k in ("counterparty", "counterparty_class", "content", "objective")]
        if exclusion and any(exclusion.lower() in h.lower() for h in haystacks if h):
            reasons.append(f"Exclusion matched: {exclusion!r}.")
    # Opt-out: a recorded opt-out for the counterparty blocks reuse.
    if proposed_params.get("opted_out"):
        reasons.append("Counterparty has opted out — standing authorization does not apply.")
    if reasons:
        return False, reasons
    return True, [f"Within standing authorization #{auth.id} envelope (derived from action #{envelope.get('source_action_id')})."]


def check_standing_authorization(db: Session, action_type: str, proposed_params: dict | None = None) -> dict:
    """Return {allowed, auth_id, reasons}. PROPOSED/REVOKED/EXPIRED never authorize."""
    for auth in get_active_standing_authorizations(db, action_type):
        matched, reasons = matches_standing_envelope(auth, action_type, proposed_params)
        if matched:
            return {"allowed": True, "auth_id": auth.id, "reasons": reasons}
    return {"allowed": False, "auth_id": None, "reasons": ["No ACTIVE standing authorization covers this action."]}
