"""allowed_mask(): the single seam to the authorization layer.

The ranker never computes this mask and never calls this module to
execute anything. This module only READS governance state and returns
a boolean mask. The execution-boundary re-check stays in
backend/app/services/execution_engine.py (execute_through_gate).

Governance state is carried in a plain GovernanceInput (no SQLAlchemy
import here, so this module stays stdlib-only). A future adapter
(DIMAG-004 worker) fills it from the live store: owner STOP from
OpHamiRuntimeControl.safe_mode_enabled, DoNotContact rows, gate flags
from the environment (all default closed, docs/GATES.md), recorded
approvals from Action.approved_at, and scope-grant expiry from the
standing-authorization envelope.

Design section 2.5: a lead is allowed iff ALL hold:
  (a) policy_result = ALLOW, or REQUIRE_APPROVAL with a recorded approval;
  (b) no owner STOP is active;
  (c) every gate flag the action touches is open (default closed);
  (d) the target is not in DoNotContact where contact is involved;
  (e) the action's scope grant is unexpired.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Explicit, closed map from contact/send operations to the gate flag
# that controls them (docs/GATES.md). Anything not listed here touches
# no flag. This map is the only place an action is tied to a flag.
FLAG_FOR_OPERATION = {
    "SEND_EMAIL": "FORGE_BOT_RESPONSE_SEND_ENABLED",
    "SEND_SMS": "HAMI_OWNER_SMS_DIGEST_ENABLED",
    "SEND_TELEGRAM": "HAMI_TELEGRAM_OWNER_DIGEST_ENABLED",
}

# Action types that involve contacting a person or business. Only
# these are checked against DoNotContact (design 2.5 (d)).
CONTACT_ACTION_TYPES = {
    "outreach",
    "SEND_EMAIL",
    "SEND_SMS",
    "SEND_TELEGRAM",
}


@dataclass
class GovernanceInput:
    """Snapshot of governance state at mask-computation time."""

    owner_stop_active: bool = False
    do_not_contact_ids: set = field(default_factory=set)
    open_flags: set = field(default_factory=set)
    # action_id -> True when a recorded approval exists (approved_at set).
    approvals: dict = field(default_factory=dict)
    # action_id -> grant expiry datetime (None = no expiry recorded).
    # An action with no grant entry has no grant to expire.
    scope_grants: dict = field(default_factory=dict)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def action_flags_touched(action):
    """Gate flags this action touches, from its operation/action_type."""
    touched = set()
    for key in ("operation", "action_type"):
        value = action.get(key)
        if isinstance(value, str) and value in FLAG_FOR_OPERATION:
            touched.add(FLAG_FOR_OPERATION[value])
    return touched


def needs_approval(action, governance):
    """True iff the action requires approval.

    Set ONLY from governance: policy_result = REQUIRE_APPROVAL, or
    status = APPROVAL_REQUIRED, or the action touches a closed gate
    flag. Never learned, never guessed.
    """
    if action.get("policy_result") == "REQUIRE_APPROVAL":
        return True
    if action.get("status") == "APPROVAL_REQUIRED":
        return True
    if action_flags_touched(action) - set(governance.open_flags):
        return True
    return False


def _grant_unexpired(action, governance):
    expiry = governance.scope_grants.get(action.get("id"))
    if expiry is None:
        return True
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    return expiry > governance.now


def is_allowed(action, governance):
    """One lead's allowed verdict under design section 2.5 (a)-(e)."""
    # (a) policy: ALLOW, or REQUIRE_APPROVAL with a recorded approval.
    policy = action.get("policy_result")
    if policy == "ALLOW":
        pass
    elif policy == "REQUIRE_APPROVAL" and governance.approvals.get(action.get("id")):
        pass
    else:
        return False
    # (b) owner STOP blocks everything.
    if governance.owner_stop_active:
        return False
    # (c) every touched flag must be open (default closed).
    if action_flags_touched(action) - set(governance.open_flags):
        return False
    # (d) DoNotContact where contact is involved.
    if action.get("action_type") in CONTACT_ACTION_TYPES:
        contact_id = action.get("contact_entity_id")
        if contact_id is not None and contact_id in governance.do_not_contact_ids:
            return False
    # (e) scope grant must be unexpired.
    if not _grant_unexpired(action, governance):
        return False
    return True


def allowed_mask(gate, leads, governance):
    """Boolean mask over a gate's candidate leads.

    `gate` is the gate-entity dict (kept for the seam's signature; the
    verdict is per lead). `leads` is the ordered list of candidate
    Action dicts. Returns a list of bool, same length as leads.
    """
    return [bool(is_allowed(lead, governance)) for lead in leads]
