"""Central decision-rights registry enforced by the canonical Action path.

Rights are narrower than technical capability. A BOT right still passes every
existing autonomy, risk, spending, source-clearance, consent, and execution gate.
Unknown action types default to OWNER_ONLY. Stage advancement is deliberately
not writable by the bot: an owner-approved source change may raise ACTIVE_STAGE
only after the applicable evidence gate has been met.
"""
from __future__ import annotations

import re
from typing import Any

BOT = "bot"
BOT_THEN_TELL_OWNER = "bot then tell owner"
OWNER_ONLY = "owner only"

# Stage 1 is the current posture: the bot may observe/research internally but
# all external commitments stay owner-gated. Raising this value is a governed
# release decision, never a runtime action. See STAGE_GATES below.
ACTIVE_STAGE = 1

STAGE_GATES = {
    1: {
        "name": "Human does it; bot watches",
        "requirements_to_advance": [
            "One complete week of consented REAL merchant data",
            "At least one REAL payment supported by independent evidence",
        ],
    },
    2: {
        "name": "Bot drafts; human approves",
        "requirements_to_advance": [
            "Measured approval-without-edit rate meets the pre-registered target",
            "Approved drafts recover sales at least as well as the manual baseline",
            "All comparisons use consented REAL data and traceable outcomes",
        ],
    },
    3: {
        "name": "Bounded reversible actions",
        "requirements_to_advance": [
            "A defined trial window with no wrong or harmful outbound messages",
            "Per-action daily limits and an owner kill switch are verified",
            "Owner notification delivery and audit logging are verified in production",
        ],
    },
    4: {
        "name": "Medium decisions; owner notified",
        "requirements_to_advance": [
            "A pre-registered sample shows decisions consistently match owner choices",
            "Rollbacks have been exercised and decision drift is monitored",
        ],
    },
    5: {
        "name": "Routine operation within standing authorization",
        "requirements_to_advance": [
            "All prior gates remain satisfied on current evidence",
            "Only the explicitly defined owner-only decisions remain escalated",
        ],
    },
}

# Maps known action types to the three rights. Generic external actions are
# purposefully conservative until their proof gate is unlocked.
_RIGHTS: dict[str, dict[str, Any]] = {
    "manual_note": {"right": BOT, "minimum_stage": 1, "description": "Internal note taking"},
    "research": {"right": BOT, "minimum_stage": 1, "description": "Internal research using existing source-clearance rules"},
    "classify": {"right": BOT, "minimum_stage": 1, "description": "Internal classification"},
    "summarize": {"right": BOT, "minimum_stage": 1, "description": "Internal summarization"},
    "record_observation": {"right": BOT, "minimum_stage": 1, "description": "Record a sourced internal observation"},
    "run_discovery_round": {"right": BOT, "minimum_stage": 1, "description": "Run already-authorized internal discovery"},
    "log_outcome": {"right": BOT, "minimum_stage": 1, "description": "Log an outcome without elevating its evidence class"},
    "prepare_internal_draft": {"right": BOT, "minimum_stage": 1, "description": "Prepare internal-only draft content"},
    "draft_customer_reply": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 2, "description": "Draft a reply for owner review; never send at this stage"},
    "draft_follow_up": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 2, "description": "Draft a follow-up for owner review; never send at this stage"},
    "rank_next_seller": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 3, "description": "Recommend the next consenting seller based on evidence"},
    "suggest_script_change": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 3, "description": "Recommend, but do not apply, a script change"},
    "schedule_follow_up": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 3, "requires_standing_authorization": True, "description": "Schedule only a consented follow-up inside its authorization envelope"},
    "follow_up": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 3, "requires_standing_authorization": True, "description": "Contact only a consenting recipient under a verified response authorization"},
    "reply_to_inquiry": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 3, "requires_standing_authorization": True, "description": "Reply only to an authorized inquiry using the approved channel and template"},
    "service_delivery": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 4, "description": "Routine fulfillment inside an owner-approved offer"},
    "provider_verify": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 3, "description": "Read-only verification with owner-visible audit"},
    "owner_daily_digest": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 1, "description": "Send a privacy-minimized status digest only to the configured owner"},
    "owner_alert": {"right": BOT_THEN_TELL_OWNER, "minimum_stage": 1, "description": "Send a bounded internal alert only to the configured owner"},
    "customer_interview": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Human conversation and consent"},
    "interview": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Human conversation and consent"},
    "outreach": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "First contact; human must choose, authorize, and send"},
    "offer": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Commercial offer and commitments"},
    "paid_pilot": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Commercial commitment and pricing"},
    "revenue_experiment": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "External commercial experiment until explicitly bounded"},
    "validate_pricing": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Price discovery involves a real counterparty"},
    "build_mvp": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Scope expansion or deployment requires a separate owner decision"},
    "change_price": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Price changes are permanently owner-only"},
    "change_revenue_share": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Revenue-share changes are permanently owner-only"},
    "spend_money": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Any spending or financial commitment"},
    "legal_tax_company": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Legal, tax, or company-level decision"},
    "new_customer_market": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Expand to a new customer class or market"},
    "contact_without_consent": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Contact without prior consent is never permitted autonomously"},
    "widen_permissions": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Permission changes and autonomy-stage promotion"},
    "public_intake_activation": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Public intake activation"},
    "provider_candidate": {"right": BOT, "minimum_stage": 1, "description": "Create or update an internal non-public provider candidate"},
    "provider_publish": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "External publication"},
    "http_request": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Generic external requests are not implicitly trusted"},
    "smtp_email": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Generic outbound email"},
    "twilio/send_sms": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Generic SMS; owner digest uses a separate exact-recipient path"},
    "send_sms": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Generic SMS"},
    "forge_bot_response": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Use the separate consent/channel/template authorization gate"},
    "github_bounty_claim": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "External claim or commitment"},
    "github_bounty_verify": {"right": BOT, "minimum_stage": 1, "description": "Read-only verification of a public bounty or pull-request status"},
    "execute_trade": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Financial trade execution"},
    "broker_order": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Broker order execution"},
    "wire_transfer": {"right": OWNER_ONLY, "minimum_stage": 1, "description": "Money movement"},
}

# Step-1 execution-boundary operation table (plan section 2).
# The closed list: an operation not in this table does not exist for
# Hami, and check_rights refuses it as unknown (which defaults to
# OWNER_ONLY). Rights values are the plan's names: "internal_read"
# (read-only inspection of Hami's own state), "authorized_scope"
# (allowed only inside a named, expiring standing-authorization
# envelope, re-checked at execution time), "internal_service"
# (restricted to the integration dispatcher and registered send scopes),
# "owner_only" (refused unless the principal is the owner).
# OP-06 record_event is internal_read for the read of the store plus
# the single write the gate itself performs to Hami's own evidence store.
_OPERATION_RIGHTS: dict[str, dict[str, Any]] = {
    "inspect_file": {"right": "internal_read", "description": "Read-only inspection of a named repo file"},
    "inspect_repo_state": {"right": "internal_read", "description": "Read-only repo working-tree / git status"},
    "run_local_tests": {"right": "authorized_scope", "description": "Run the approved local test suite only, in-repo, no network"},
    "edit_repo_file": {"right": "authorized_scope", "description": "Apply a specified edit to a named backend service file; never a protected file"},
    "create_repo_file": {"right": "authorized_scope", "description": "Create a named new file inside the envelope scope only"},
    "record_event": {"right": "internal_read", "description": "Append one EVENT + EVIDENCE record to Hami's own evidence store"},
    "read_task_state": {"right": "internal_read", "description": "Read WorkerTask / scheduler state"},
    "requeue_task": {"right": "authorized_scope", "description": "Requeue a named WorkerTask from its last durable checkpoint, within retry limits"},
    "open_blocker": {"right": "authorized_scope", "description": "Open a material-blocker record after bounded failures"},
    "read_halt_state": {"right": "internal_read", "description": "Read whether HALT is set"},
    "send_email": {"right": "internal_service", "description": "Dispatch one validated SMTP outbox delivery through the decision gate"},
    "send_sms": {"right": "internal_service", "description": "Dispatch one validated Twilio outbox delivery through the decision gate"},
    "send_telegram": {"right": "internal_service", "description": "Dispatch one validated owner Telegram outbox delivery through the decision gate"},
}

_INTERNAL_SERVICE_SCOPES = {
    "send_email": frozenset({"smtp"}),
    "send_sms": frozenset({"twilio", "twilio_owner"}),
    "send_telegram": frozenset({"telegram_owner"}),
}

# The five protected files: never editable through the boundary, by anyone.
_PROTECTED_PATHS = frozenset({
    "HANDOFF.md",
    "STATE.md",
    "QUEUE.md",
    "docs/CAPABILITY_QUEUE.md",
    "DOCKER_COMMANDS.md",
})


def entry_for(action_type: str) -> dict[str, Any]:
    normalized = (action_type or "").strip().lower()
    return dict(_RIGHTS.get(normalized, {
        "right": OWNER_ONLY,
        "minimum_stage": 1,
        "description": "Unregistered action types default to owner-only.",
    }), action_type=normalized or "unknown")


def _owner_sms_ready() -> bool:
    """Compatibility seam: owner-notification readiness follows Telegram now."""
    try:
        from app.config import settings
        token = str(settings.HAMI_TELEGRAM_BOT_TOKEN or "").strip()
        secret = str(settings.HAMI_TELEGRAM_WEBHOOK_SECRET or "").strip()
        chat = str(settings.HAMI_TELEGRAM_OWNER_CHAT_ID or "").strip()
        user = str(settings.HAMI_TELEGRAM_OWNER_USER_ID or "").strip()
        return bool(settings.HAMI_TELEGRAM_CONTROL_ENABLED and len(token) >= 30
            and re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret)
            and re.fullmatch(r"[1-9][0-9]{0,18}", chat)
            and re.fullmatch(r"[1-9][0-9]{0,18}", user))
    except Exception:
        return False


def enforcement_for(action_type: str) -> dict[str, Any]:
    """Return the non-overridable rights constraint layered on autonomy policy."""
    entry = entry_for(action_type)
    right = entry["right"]
    if right == OWNER_ONLY:
        return {
            **entry,
            "requires_owner_approval": True,
            "reason_code": "decision_rights:owner_only",
            "enforcement_reason": f"decision_rights:owner_only — {entry['description']}",
        }
    if right == BOT_THEN_TELL_OWNER:
        if ACTIVE_STAGE < int(entry["minimum_stage"]):
            reason = f"decision_rights:stage_gate — {entry['description']} is locked until stage {entry['minimum_stage']} evidence gates pass."
            return {**entry, "requires_owner_approval": True, "reason_code": "decision_rights:stage_gate", "enforcement_reason": reason}
        if not _owner_sms_ready():
            reason = f"decision_rights:owner_notification_unavailable — {entry['description']} requires the owner digest channel to be configured."
            return {**entry, "requires_owner_approval": True, "reason_code": "decision_rights:owner_notification_unavailable", "enforcement_reason": reason}
    return {
        **entry,
        "requires_owner_approval": False,
        "reason_code": None,
        "enforcement_reason": None,
    }


def describe_registry() -> dict[str, Any]:
    """Read-only owner view; no state-changing endpoint can modify rights."""
    registry = []
    for action_type in sorted(_RIGHTS):
        row = enforcement_for(action_type)
        registry.append({
            "action_type": action_type,
            "right": row["right"],
            "minimum_stage": row["minimum_stage"],
            "requires_standing_authorization": row.get("requires_standing_authorization", False),
            "currently_requires_owner_approval": row["requires_owner_approval"],
            "reason_code": row["reason_code"],
            "description": row["description"],
        })
    return {
        "active_stage": ACTIVE_STAGE,
        "stage_name": STAGE_GATES[ACTIVE_STAGE]["name"],
        "stage_gates": STAGE_GATES,
        "unknown_action_default": OWNER_ONLY,
        "bot_can_promote_itself": False,
        "rights_are_mutable_at_runtime": False,
        "registry": registry,
    }


def operation_entry_for(operation: str) -> dict[str, Any]:
    """Step-1 operation table lookup. Unknown operations default to OWNER_ONLY."""
    normalized = (operation or "").strip().lower()
    return dict(_OPERATION_RIGHTS.get(normalized, {
        "right": "owner_only",
        "description": "Unregistered operations do not exist for Hami.",
    }), operation=normalized or "unknown")


def check_rights(principal: str, operation: str, scope: str, envelope: Any = None) -> dict[str, Any]:
    """Step-1 single entry point for execution-path rights (plan E2).

    Decides only the RIGHTS question: may this principal run this
    operation at all, and under what right? It does NOT re-check the
    envelope's expiry, revocation, or scope depth - that is E3
    (autonomy_engine), run by the gate (E4) as the next step.

    Rules, in order:
    1. Unknown operation -> refused (defaults to OWNER_ONLY).
    2. Empty scope, scope "everything" / "*", or path traversal ("..")
       -> refused as out of scope. A scope of "everything" is invalid.
    3. edit/create on a protected file -> refused as out of scope.
    4. INTERNAL_READ -> allowed for any principal (read-only inspection
       of Hami's own state, no side effects).
    5. AUTHORIZED_SCOPE -> allowed only when the principal is "owner"
       (the owner is the authority) or a non-None envelope is present.
       Whether that envelope is still valid is E3's job, not this
       function's. With no envelope and a non-owner principal -> refused.
    6. INTERNAL_SERVICE -> allowed only to the named dispatcher for a registered integration scope.
    7. OWNER_ONLY -> refused unless the principal is "owner".

    No function in this file raises an autonomy stage, extends an
    expiry, or widens a scope. There is no self-promotion path here.
    """
    entry = operation_entry_for(operation)
    right = entry["right"]
    op = entry["operation"]
    who = (principal or "").strip() or "unknown"
    clean_scope = (scope or "").strip()

    def _refuse(reason_code: str, reason: str) -> dict[str, Any]:
        return {
            "operation": op,
            "principal": who,
            "right": right,
            "allowed": False,
            "requires_owner_approval": True,
            "reason_code": reason_code,
            "enforcement_reason": reason,
            "scope": clean_scope,
        }

    def _allow() -> dict[str, Any]:
        return {
            "operation": op,
            "principal": who,
            "right": right,
            "allowed": True,
            "requires_owner_approval": False,
            "reason_code": None,
            "enforcement_reason": None,
            "scope": clean_scope,
        }

    if op == "unknown" or op not in _OPERATION_RIGHTS:
        return _refuse(
            "decision_rights:unknown_operation",
            f"decision_rights:unknown_operation - {entry['description']}",
        )
    if not clean_scope or clean_scope.lower() in {"everything", "*", "all"}:
        return _refuse(
            "decision_rights:out_of_scope",
            "decision_rights:out_of_scope - scope must name explicit resource(s); a scope of 'everything' is invalid.",
        )
    if ".." in clean_scope.replace("\\", "/").split("/"):
        return _refuse(
            "decision_rights:out_of_scope",
            "decision_rights:out_of_scope - scope must not contain path traversal.",
        )
    if op in {"edit_repo_file", "create_repo_file"}:
        normalized_path = clean_scope.replace("\\", "/").strip("/")
        if normalized_path in _PROTECTED_PATHS:
            return _refuse(
                "decision_rights:out_of_scope",
                f"decision_rights:out_of_scope - {normalized_path} is a protected file and is never editable through the boundary.",
            )
    if right == "internal_service":
        if who == "integration_dispatcher" and clean_scope in _INTERNAL_SERVICE_SCOPES.get(op, ()):
            return _allow()
        return _refuse(
            "decision_rights:internal_service_only",
            "decision_rights:internal_service_only - this operation is restricted to the integration dispatcher and its registered integration scope.",
        )
    if right == "internal_read":
        return _allow()
    if right == "authorized_scope":
        if who == "owner":
            return _allow()
        if envelope is not None:
            return _allow()
        return _refuse(
            "decision_rights:authorization_required",
            "decision_rights:authorization_required - this operation needs an explicit, unexpired owner authorization envelope.",
        )
    # OWNER_ONLY and anything else: refused unless the principal is the owner.
    if who == "owner":
        return _allow()
    return _refuse(
        "decision_rights:owner_only",
        f"decision_rights:owner_only - {entry['description']}",
    )
