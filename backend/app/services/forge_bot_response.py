"""Canonical authorization boundary for Forge Bot customer-response Actions."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import world_graph

CONSENT_PURPOSE = "respond_to_forge_bot_inquiry"
CONSENT_PROVENANCE = "forge_bot_web_form_v1"
OPT_OUT_BOUNDARY = "permanent_suppression"
ESCALATION_BOUNDARY = "owner_confirmation_required_for_exceptions"
ALLOWED_CHANNELS = {"email", "phone"}
_TEMPLATE_REFERENCE = re.compile(r"(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9._:/#-]{0,199}")
_FORGE_BOT_ACTION_KEY = "_forge_bot_response_action"


@dataclass(frozen=True)
class ResponseActionDecision:
    decision: Literal["ALLOWED", "BLOCKED"]
    authorization_decision: Literal["ALLOWED", "BLOCKED"]
    reason_codes: tuple[str, ...]
    inquiry_reference: str | None
    action_id: int | None
    observed_submitter_preference: str | None
    owner_authorized_channel: str | None
    approved_template_reference: str | None

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOWED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "authorization_decision": self.authorization_decision,
            "reason_codes": list(self.reason_codes),
            "inquiry_reference": self.inquiry_reference,
            "action_id": self.action_id,
            "observed_submitter_preference": self.observed_submitter_preference,
            "owner_authorized_channel": self.owner_authorized_channel,
            "approved_template_reference": self.approved_template_reference,
        }


def _is_valid_template_reference(value: Any) -> bool:
    return isinstance(value, str) and _TEMPLATE_REFERENCE.fullmatch(value) is not None


def _response_action_parameters(
    action: models.Action | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if action is None:
        return None, ["response_action_missing", "owner_confirmation_missing"]
    if action.action_type != "forge_bot_response":
        return None, ["malformed_action_state"]
    try:
        parameters = json.loads(action.parameters_json or "{}")
    except (TypeError, ValueError):
        return None, ["malformed_action_state"]
    if not isinstance(parameters, dict):
        return None, ["malformed_action_state"]
    if (
        set(parameters)
        != {
            "inquiry_reference",
            "channel",
            "template_ref",
            "requires_owner_confirmation",
        }
        or not isinstance(parameters.get("inquiry_reference"), str)
        or not parameters["inquiry_reference"].strip()
        or not isinstance(parameters.get("channel"), str)
        or parameters.get("channel") not in ALLOWED_CHANNELS
        or not _is_valid_template_reference(parameters.get("template_ref"))
        or parameters.get("requires_owner_confirmation") is not True
    ):
        return parameters, ["malformed_action_state"]
    return parameters, []


def _action_is_owner_confirmed(action: models.Action | None) -> bool:
    return bool(
        action is not None
        and action.action_type == "forge_bot_response"
        and action.status in {"APPROVED", "RUNNING"}
        and action.approved_at is not None
    )


def _authorization_errors(
    authorization: models.OpForgeBotResponseAuthorization | None,
) -> list[str]:
    if authorization is None:
        return ["owner_authorization_missing"]
    if authorization.id != 1:
        return ["malformed_authorization_state"]

    reasons: list[str] = []
    channel = authorization.selected_channel
    if channel is None:
        reasons.append("selected_channel_missing")
    elif channel not in ALLOWED_CHANNELS:
        reasons.append("unknown_channel")

    if type(authorization.channel_authorized) is not bool:
        reasons.append("malformed_authorization_state")
    elif channel in ALLOWED_CHANNELS and not authorization.channel_authorized:
        reasons.append("channel_not_authorized")

    if authorization.template_ref is None or authorization.template_ref == "":
        reasons.append("approved_template_missing")
    elif not _is_valid_template_reference(authorization.template_ref):
        reasons.append("unknown_template")
    if type(authorization.template_authorized) is not bool:
        reasons.append("malformed_authorization_state")
    elif authorization.template_ref and not authorization.template_authorized:
        reasons.append("template_not_authorized")

    if type(authorization.consent_required) is not bool:
        reasons.append("malformed_authorization_state")
    elif not authorization.consent_required:
        reasons.append("consent_requirement_disabled")
    if authorization.opt_out_boundary != OPT_OUT_BOUNDARY:
        reasons.append("malformed_authorization_state")
    if authorization.escalation_boundary != ESCALATION_BOUNDARY:
        reasons.append("malformed_authorization_state")
    if type(authorization.external_send_authorized) is not bool:
        reasons.append("malformed_authorization_state")
    elif not authorization.external_send_authorized:
        reasons.append("external_send_not_authorized")
    return reasons


def decide_response_action(
    db: Session,
    *,
    inquiry_reference: str | None,
    action: models.Action | None,
    requested_channel: str | None = None,
    requested_template_ref: str | None = None,
) -> ResponseActionDecision:
    """Return the only decision future Forge Bot customer-response Actions may use."""
    reasons: list[str] = []
    authorization = db.get(models.OpForgeBotResponseAuthorization, 1)
    policy_reasons = _authorization_errors(authorization)
    reasons.extend(policy_reasons)

    parameters, action_reasons = _response_action_parameters(action)
    reasons.extend(action_reasons)
    if parameters is not None:
        if (
            requested_channel is not None
            and requested_channel != parameters.get("channel")
        ):
            reasons.append("channel_mismatch")
        if (
            requested_template_ref is not None
            and requested_template_ref != parameters.get("template_ref")
        ):
            reasons.append("unknown_template")
        inquiry_reference = parameters.get("inquiry_reference")
        requested_channel = parameters.get("channel")
        requested_template_ref = parameters.get("template_ref")

    lead = None
    if inquiry_reference and isinstance(inquiry_reference, str):
        lead = (
            db.query(models.ForgeBotLeadContact)
            .filter_by(public_ref=inquiry_reference)
            .one_or_none()
        )
    if lead is None:
        reasons.append("inquiry_not_found")

    owner_channel = authorization.selected_channel if authorization else None
    approved_template = authorization.template_ref if authorization else None
    preference = lead.preferred_channel if lead else None
    if requested_channel is not None and (
        not isinstance(requested_channel, str)
        or requested_channel not in ALLOWED_CHANNELS
    ):
        reasons.append("unknown_channel")
    elif requested_channel is None:
        reasons.append("selected_channel_missing")
    elif owner_channel in ALLOWED_CHANNELS and requested_channel != owner_channel:
        reasons.append("channel_mismatch")
    if requested_template_ref is None or requested_template_ref == "":
        reasons.append("approved_template_missing")
    elif not _is_valid_template_reference(requested_template_ref):
        reasons.append("unknown_template")
    elif approved_template and requested_template_ref != approved_template:
        reasons.append("unknown_template")

    if lead is not None:
        if lead.consent_granted is not True:
            reasons.append("consent_missing")
        if (
            lead.consent_purpose != CONSENT_PURPOSE
            or lead.consent_provenance != CONSENT_PROVENANCE
        ):
            reasons.append("consent_provenance_invalid")
        if lead.opted_out:
            reasons.append("inquiry_opted_out")
        if lead.erased_at is not None:
            reasons.append("inquiry_erased")
        if not lead.email and not lead.phone:
            reasons.append("contact_unavailable")
        elif owner_channel == "email" and not lead.email:
            reasons.append("contact_unavailable")
        elif owner_channel == "phone" and not lead.phone:
            reasons.append("contact_unavailable")
        if preference not in ALLOWED_CHANNELS:
            reasons.append("unknown_channel")
        elif owner_channel in ALLOWED_CHANNELS and preference != owner_channel:
            reasons.append("channel_mismatch")
        if lead.evidence_class != "REAL":
            reasons.append("test_evidence_not_real")

    if not _action_is_owner_confirmed(action):
        reasons.append("owner_confirmation_missing")

    if not settings.FORGE_BOT_INTAKE_ENABLED:
        reasons.append("intake_disabled")
    if len(settings.FORGE_BOT_CONTACT_HMAC_KEY) < 32:
        reasons.append("contact_suppression_key_missing")
    if not settings.FORGE_API_KEY:
        reasons.append("owner_access_configuration_missing")
    if not settings.FORGE_BOT_LIVE:
        reasons.append("forge_bot_live_disabled")
    if not settings.FORGE_BOT_RESPONSE_SEND_ENABLED:
        reasons.append("external_send_disabled")
    # There is currently no Forge Bot customer-response sender implementation.
    reasons.append("sender_unavailable")

    authorization_reasons = {
        "owner_authorization_missing",
        "selected_channel_missing",
        "unknown_channel",
        "channel_not_authorized",
        "approved_template_missing",
        "unknown_template",
        "template_not_authorized",
        "consent_requirement_disabled",
        "malformed_authorization_state",
        "external_send_not_authorized",
        "malformed_action_state",
        "inquiry_not_found",
        "consent_missing",
        "consent_provenance_invalid",
        "inquiry_opted_out",
        "inquiry_erased",
        "contact_unavailable",
        "channel_mismatch",
    }
    unique_reasons = tuple(dict.fromkeys(reasons))
    authorization_blocked = any(code in authorization_reasons for code in unique_reasons)
    return ResponseActionDecision(
        decision="BLOCKED" if unique_reasons else "ALLOWED",
        authorization_decision="BLOCKED" if authorization_blocked else "ALLOWED",
        reason_codes=unique_reasons,
        inquiry_reference=lead.public_ref if lead else None,
        action_id=action.id if action else None,
        observed_submitter_preference=preference,
        owner_authorized_channel=(
            owner_channel
            if authorization is not None
            and owner_channel in ALLOWED_CHANNELS
            and authorization.channel_authorized is True
            else None
        ),
        approved_template_reference=(
            approved_template
            if authorization is not None
            and _is_valid_template_reference(approved_template)
            and authorization.template_authorized is True
            else None
        ),
    )


def decision_for_action_id(
    db: Session,
    *,
    action_id: int | None,
    requested_channel: str | None = None,
    requested_template_ref: str | None = None,
) -> ResponseActionDecision:
    action = db.get(models.Action, action_id) if action_id is not None else None
    parameters, _ = _response_action_parameters(action)
    reference = (
        parameters.get("inquiry_reference")
        if parameters is not None
        else None
    )
    return decide_response_action(
        db,
        inquiry_reference=reference,
        action=action,
        requested_channel=requested_channel,
        requested_template_ref=requested_template_ref,
    )


def record_action_decision(
    db: Session,
    decision: ResponseActionDecision,
) -> None:
    if decision.action_id is None:
        raise ValueError("Forge Bot response ACTION is required for decision audit")
    world_graph.seed_core_types(db)
    world_graph.create_event(
        db,
        event_type="forge_bot_response_action_authorization_decided",
        source="forge_bot_response_action_boundary",
        payload={
            "inquiry_reference": decision.inquiry_reference,
            "action_id": decision.action_id,
            "decision": decision.decision,
            "authorization_decision": decision.authorization_decision,
            "reason_codes": list(decision.reason_codes),
        },
        idempotency_key=f"forge-bot-response-action-decision:{decision.action_id}",
    )


def propose_response_action(
    db: Session,
    *,
    inquiry_reference: str,
    channel: str,
    template_ref: str,
) -> models.Action:
    """Create the existing ACTION primitive under owner confirmation."""
    if not inquiry_reference.strip():
        raise ValueError("inquiry_reference is required")
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("unknown Forge Bot response channel")
    if not _is_valid_template_reference(template_ref):
        raise ValueError("unknown Forge Bot response template reference")

    action = models.Action(
        action_type="forge_bot_response",
        objective="Review one Forge Bot customer-response action",
        parameters_json=json.dumps(
            {
                "inquiry_reference": inquiry_reference,
                "channel": channel,
                "template_ref": template_ref,
                "requires_owner_confirmation": True,
            },
            sort_keys=True,
        ),
        status="APPROVAL_REQUIRED",
        policy_result="REQUIRE_APPROVAL",
        policy_reason="Forge Bot customer-response ACTIONs require owner confirmation",
        adapter_name="forge_bot_response",
        verification_state="UNVERIFIED",
    )
    db.add(action)
    db.flush()
    world_graph.seed_core_types(db)
    world_graph.create_event(
        db,
        event_type="forge_bot_response_action_proposed",
        source="forge_bot_response_action_boundary",
        payload={
            "action_id": action.id,
            "inquiry_reference": inquiry_reference,
            "channel": channel,
            "template_ref": template_ref,
        },
        idempotency_key=f"forge-bot-response-action-proposed:{action.id}",
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(action)
    return action


def approve_response_action(
    db: Session,
    *,
    action_id: int,
) -> models.Action | None:
    """Record explicit owner confirmation on an existing Forge Bot ACTION."""
    action = db.get(models.Action, action_id)
    if action is None or action.action_type != "forge_bot_response":
        return None
    if action.status != "APPROVAL_REQUIRED":
        return action
    action.status = "APPROVED"
    action.approved_at = models.utcnow()
    world_graph.seed_core_types(db)
    world_graph.create_event(
        db,
        event_type="forge_bot_response_action_owner_approved",
        source="forge_bot_response_action_boundary",
        payload={"action_id": action.id},
        idempotency_key=f"forge-bot-response-action-owner-approved:{action.id}",
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(action)
    return action


def execute_response_action(
    db: Session,
    *,
    action: models.Action,
) -> dict[str, Any]:
    """Evaluate and audit an ACTION; intentionally performs no external send."""
    decision = decide_response_action(
        db,
        inquiry_reference=None,
        action=action,
    )
    record_action_decision(db, decision)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    if decision.allowed:
        return {
            "status": "FAILED",
            "execution_result": None,
            "execution_error": (
                "Authorization boundary passed, but no Forge Bot sender is implemented."
            ),
            "verification_state": "AUTHORIZED_NO_DELIVERY",
        }
    return {
        "status": "FAILED",
        "execution_result": None,
        "execution_error": "Forge Bot response ACTION blocked: " + ",".join(decision.reason_codes),
        "verification_state": "BLOCKED",
    }


def _normalized_phone(value: str) -> str:
    return "".join(character for character in value if character in "0123456789")


def _contact_hmac(kind: str, normalized_value: str) -> str | None:
    if len(settings.FORGE_BOT_CONTACT_HMAC_KEY) < 32:
        return None
    message = f"forge-bot:{kind}:{normalized_value}".encode("utf-8")
    return hmac.new(
        settings.FORGE_BOT_CONTACT_HMAC_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def decision_for_generic_delivery(
    db: Session,
    *,
    integration_name: str,
    operation: str,
    request: dict[str, Any],
) -> ResponseActionDecision | None:
    """Reject generic provider paths that target a known or suppressed Forge Bot contact."""
    if (integration_name, operation) == ("smtp", "send_email"):
        recipient = request.get("to") or request.get("recipient")
        if not isinstance(recipient, str) or not recipient.strip():
            return None
        normalized = recipient.strip().lower()
        suppression = _contact_hmac("email", normalized)
        conditions = [models.ForgeBotLeadContact.normalized_email == normalized]
        if suppression is not None:
            conditions.append(
                models.ForgeBotLeadContact.email_suppression_hmac == suppression
            )
        lead = (
            db.query(models.ForgeBotLeadContact)
            .filter(or_(*conditions))
            .first()
        )
        channel = "email"
    elif (integration_name, operation) == ("twilio", "send_sms"):
        recipient = request.get("to")
        if not isinstance(recipient, str) or not recipient.strip():
            return None
        normalized = _normalized_phone(recipient)
        suppression = _contact_hmac("phone", normalized)
        conditions = [models.ForgeBotLeadContact.normalized_phone == normalized]
        if suppression is not None:
            conditions.append(
                models.ForgeBotLeadContact.phone_suppression_hmac == suppression
            )
        lead = (
            db.query(models.ForgeBotLeadContact)
            .filter(or_(*conditions))
            .first()
        )
        channel = "phone"
    else:
        return None

    if lead is None:
        return None
    return decide_response_action(
        db,
        inquiry_reference=lead.public_ref,
        action=None,
        requested_channel=channel,
        requested_template_ref=request.get("template_ref"),
    )


def decision_for_marked_delivery(
    db: Session,
    request: dict[str, Any],
) -> ResponseActionDecision | None:
    metadata = request.get(_FORGE_BOT_ACTION_KEY)
    if metadata is None:
        return None
    if (
        not isinstance(metadata, dict)
        or set(metadata)
        != {"action_id", "inquiry_reference", "channel", "template_ref"}
        or type(metadata.get("action_id")) is not int
    ):
        return ResponseActionDecision(
            decision="BLOCKED",
            authorization_decision="BLOCKED",
            reason_codes=("malformed_action_state",),
            inquiry_reference=None,
            action_id=None,
            observed_submitter_preference=None,
            owner_authorized_channel=None,
            approved_template_reference=None,
        )
    decision = decision_for_action_id(
        db,
        action_id=metadata["action_id"],
        requested_channel=metadata.get("channel"),
        requested_template_ref=metadata.get("template_ref"),
    )
    if metadata.get("inquiry_reference") != decision.inquiry_reference:
        return ResponseActionDecision(
            decision="BLOCKED",
            authorization_decision="BLOCKED",
            reason_codes=tuple(
                dict.fromkeys((*decision.reason_codes, "malformed_action_state"))
            ),
            inquiry_reference=decision.inquiry_reference,
            action_id=decision.action_id,
            observed_submitter_preference=decision.observed_submitter_preference,
            owner_authorized_channel=decision.owner_authorized_channel,
            approved_template_reference=decision.approved_template_reference,
        )
    return decision


def response_action_marker(
    action: models.Action,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        _FORGE_BOT_ACTION_KEY: {
            "action_id": action.id,
            "inquiry_reference": parameters["inquiry_reference"],
            "channel": parameters["channel"],
            "template_ref": parameters["template_ref"],
        }
    }


def enforce_delivery_boundary(
    db: Session,
    *,
    integration_name: str,
    operation: str,
    request: dict[str, Any],
    action_decision: ResponseActionDecision | None = None,
) -> None:
    """Validate Forge Bot provenance before generic outbox or provider dispatch."""
    marked_decision = decision_for_marked_delivery(db, request)
    if request.get(_FORGE_BOT_ACTION_KEY) is not None:
        metadata = request.get(_FORGE_BOT_ACTION_KEY)
        provider_for_channel = {
            "email": ("smtp", "send_email"),
            "phone": ("twilio", "send_sms"),
        }
        marked_channel = metadata.get("channel") if isinstance(metadata, dict) else None
        expected_provider = (
            provider_for_channel.get(marked_channel)
            if isinstance(marked_channel, str)
            else None
        )
        if (
            action_decision is None
            or not action_decision.allowed
            or marked_decision is None
            or not marked_decision.allowed
            or action_decision.action_id != marked_decision.action_id
            or expected_provider != (integration_name, operation)
        ):
            codes = (
                marked_decision.reason_codes
                if marked_decision is not None
                else ("malformed_action_state",)
            )
            if expected_provider != (integration_name, operation):
                codes = tuple(dict.fromkeys((*codes, "channel_mismatch")))
            raise ForgeBotResponseBlocked(codes)
        return

    generic_decision = decision_for_generic_delivery(
        db,
        integration_name=integration_name,
        operation=operation,
        request=request,
    )
    if generic_decision is not None:
        raise ForgeBotResponseBlocked(generic_decision.reason_codes)


class ForgeBotResponseBlocked(RuntimeError):
    def __init__(self, reason_codes: tuple[str, ...]):
        self.reason_codes = reason_codes
        super().__init__("Forge Bot response action blocked: " + ",".join(reason_codes))
