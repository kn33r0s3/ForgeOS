"""Consent-scoped Forge Bot lead intake and private owner summary."""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect, or_, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import forge_bot_owner_notification
from app.config import settings
from app.database import get_db
from app.services import forge_bot_privacy, forge_bot_response, world_graph

router = APIRouter(prefix="/forge-bot", tags=["forge-bot"])
logger = logging.getLogger(__name__)
CONSENT_PURPOSE = "respond_to_forge_bot_inquiry"
CONSENT_PROVENANCE = "forge_bot_web_form_v1"
RATE_LIMIT = forge_bot_privacy.RATE_LIMIT
RATE_WINDOW_SECONDS = forge_bot_privacy.RATE_WINDOW_SECONDS
OWNER_AUTH_FAILURE_LIMIT = 10
OWNER_LEAD_STAGE_EVENTS = {
    "forge_bot_lead_replied": "REPLIED",
    "forge_bot_lead_booked": "BOOKED",
    "forge_bot_lead_completed": "COMPLETED",
}
OWNER_LEAD_STAGES = frozenset({"REQUESTED", "REPLIED", "BOOKED", "COMPLETED"})


def _enabled() -> bool:
    return bool(
        settings.FORGE_BOT_INTAKE_ENABLED
        and len(settings.FORGE_BOT_CONTACT_HMAC_KEY) >= 32
        and bool(settings.FORGE_API_KEY)
    )


def _normalized_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return "".join(character for character in phone if character in "0123456789")


def _contact_digest(kind: str, value: str | None) -> str | None:
    if not value:
        return None
    key = settings.FORGE_BOT_CONTACT_HMAC_KEY.encode("utf-8")
    message = f"forge-bot:{kind}:{value}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _record_inquiry_event(
    db: Session,
    *,
    event_type: str,
    reference: str,
    evidence_class: str,
    source: str,
    state: str,
    previous_state: str | None = None,
) -> None:
    world_graph.seed_core_types(db)
    payload = {
        "reference": reference,
        "evidence_class": evidence_class,
        "state": state,
    }
    if previous_state is not None:
        payload["previous_state"] = previous_state
    world_graph.create_event(
        db,
        event_type=event_type,
        source=source,
        payload=payload,
        idempotency_key=f"forge-bot-inquiry:{reference}:{event_type}",
    )


def _authorization_values(
    authorization: models.OpForgeBotResponseAuthorization | None,
) -> dict:
    if authorization is None:
        return {
            "configured": False,
            "selected_channel": None,
            "channel_authorized": False,
            "template_ref": None,
            "template_authorized": False,
            "consent_required": True,
            "opt_out_boundary": "permanent_suppression",
            "escalation_boundary": "owner_confirmation_required_for_exceptions",
            "external_send_authorized": False,
            "updated_at": None,
        }
    return {
        "configured": True,
        "selected_channel": authorization.selected_channel,
        "channel_authorized": authorization.channel_authorized,
        "template_ref": authorization.template_ref,
        "template_authorized": authorization.template_authorized,
        "consent_required": authorization.consent_required,
        "opt_out_boundary": authorization.opt_out_boundary,
        "escalation_boundary": authorization.escalation_boundary,
        "external_send_authorized": authorization.external_send_authorized,
        "updated_at": authorization.updated_at,
    }


def _response_readiness_output(
    decision: forge_bot_response.ResponseActionDecision,
    authorization: models.OpForgeBotResponseAuthorization | None,
) -> dict:
    result = decision.as_dict()
    result["status"] = decision.decision
    result["blocking_reasons"] = list(decision.reason_codes)
    result["owner_authorized_response_channel"] = decision.owner_authorized_channel
    result["permitted_template_ref"] = decision.approved_template_reference
    result["external_send_gate_open"] = decision.allowed
    result["external_send_enabled"] = decision.allowed
    result["external_sender_available"] = False
    result["external_message_sent"] = False
    policy = _authorization_values(authorization)
    for key in (
        "consent_required",
        "opt_out_boundary",
        "escalation_boundary",
        "external_send_authorized",
    ):
        result[key] = policy[key]
    return result


def _require_owner_key(request: Request, db: Session) -> None:
    if not settings.FORGE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Owner access is unavailable.",
        )
    presented = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(
        presented.encode("utf-8"),
        settings.FORGE_API_KEY.encode("utf-8"),
    ):
        hash_key = settings.FORGE_BOT_CONTACT_HMAC_KEY or settings.FORGE_API_KEY
        try:
            within_limit = forge_bot_privacy.consume_rate_limited_request(
                db,
                request,
                hmac_key=hash_key,
                scope="forge-bot-owner-auth-failure",
                limit=OWNER_AUTH_FAILURE_LIMIT,
            )
        except (HTTPException, SQLAlchemyError) as exc:
            logger.error("Forge Bot owner authentication limit unavailable (%s).", type(exc).__name__)
            raise HTTPException(
                status_code=503,
                detail="Owner authentication is temporarily unavailable.",
            ) from exc
        if not within_limit:
            raise HTTPException(
                status_code=429,
                detail="Too many unsuccessful owner sign-in attempts. Try again later.",
            )
        raise HTTPException(status_code=401, detail="Owner authentication failed.")


def _lead_stage(db: Session, lead: models.ForgeBotLeadContact) -> str:
    if lead.stage == "OPTED_OUT":
        return "OPTED_OUT"
    current = "REQUESTED"
    events = (
        db.query(models.WorldEvent)
        .filter(
            or_(
                models.WorldEvent.event_type == "state_changed",
                models.WorldEvent.event_type.in_(OWNER_LEAD_STAGE_EVENTS),
            ),
            models.WorldEvent.payload.contains(lead.public_ref),
        )
        .order_by(models.WorldEvent.occurred_at, models.WorldEvent.id)
        .all()
    )
    for event in events:
        try:
            payload = json.loads(event.payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if payload.get("reference") == lead.public_ref:
            if event.event_type == "state_changed" and event.source == "forge_bot_owner_console":
                if payload.get("state") in OWNER_LEAD_STAGES:
                    current = payload["state"]
            elif event.event_type in OWNER_LEAD_STAGE_EVENTS:
                current = OWNER_LEAD_STAGE_EVENTS[event.event_type]
    return current


def _lead_event_payload(
    db: Session,
    reference: str,
) -> dict:
    lead = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(public_ref=reference, opted_out=False, erased_at=None)
        .with_for_update()
        .one_or_none()
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Active inquiry not found.")
    return {"lead": lead, "stage": _lead_stage(db, lead)}


def _record_owner_lead_transition(
    db: Session,
    *,
    lead: models.ForgeBotLeadContact,
    event_type: str,
    next_stage: str,
    details: dict | None = None,
) -> None:
    previous_stage = _lead_stage(db, lead)
    payload = {
        "reference": lead.public_ref,
        "evidence_class": lead.evidence_class,
        "previous_state": previous_stage,
        "state": next_stage,
        "transition": next_stage,
        **(details or {}),
    }
    world_graph.seed_core_types(db)
    world_graph.create_event(
        db,
        event_type="state_changed",
        source="forge_bot_owner_console",
        payload=payload,
        idempotency_key=f"forge-bot-inquiry:{lead.public_ref}:{event_type}",
        occurred_at=datetime.now(timezone.utc),
    )
    db.commit()


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return normalized.astimezone(timezone.utc).isoformat()


def _readiness_payload(db: Session) -> dict:
    result = {
        "database_ok": False,
        "migrations_ok": False,
        "smtp_configured": bool(
            settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD
        ),
        "hmac_key_configured": len(settings.FORGE_BOT_CONTACT_HMAC_KEY) >= 32,
        "intake_enabled": bool(settings.FORGE_BOT_INTAKE_ENABLED),
        "live_enabled": bool(settings.FORGE_BOT_LIVE),
        "last_maintenance_at": None,
        "last_maintenance_age_seconds": None,
        "last_test_email_at": None,
        "last_test_email_result": "UNKNOWN",
        "oldest_unsent_or_failed_owner_email_at": None,
        "deployed_commit": None,
        "lead_counts_by_stage": {
            "REQUESTED": 0,
            "REPLIED": 0,
            "BOOKED": 0,
            "COMPLETED": 0,
        },
        "lead_counts_by_evidence_class": {"REAL": 0, "TEST": 0},
        "new_leads_last_24h": 0,
    }
    deployed_commit = (
        os.getenv("VERCEL_GIT_COMMIT_SHA")
        or os.getenv("GIT_COMMIT_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    )
    if re.fullmatch(r"[0-9a-fA-F]{7,40}", deployed_commit):
        result["deployed_commit"] = deployed_commit

    try:
        db.execute(text("SELECT 1"))
        result["database_ok"] = True
        inspector = inspect(db.get_bind())
        table_names = set(inspector.get_table_names())
        from app.database import Base

        owner_tables = {
            "forge_bot_lead_contacts",
            "forge_bot_intake_rate_limits",
            "events",
            "integration_deliveries",
            "actions",
            models.TypeRegistry.__tablename__,
        }
        required_tables = {
            table.name: {column.name for column in table.columns}
            for table in Base.metadata.tables.values()
            if table.name in owner_tables
        }
        # The migration runner is additive and has no revision table; readiness
        # therefore checks the live schema against its current ORM contract.
        result["migrations_ok"] = all(
            table_name in table_names
            and expected_columns
            <= {column["name"] for column in inspector.get_columns(table_name)}
            for table_name, expected_columns in required_tables.items()
        )
        if not result["migrations_ok"]:
            return result

        now = datetime.now(timezone.utc)
        heartbeat = (
            db.query(models.WorldEvent)
            .filter_by(event_type="state_changed", source="forge_bot_daily_maintenance")
            .order_by(models.WorldEvent.occurred_at.desc(), models.WorldEvent.id.desc())
            .first()
        )
        if heartbeat is not None:
            result["last_maintenance_at"] = _iso_timestamp(heartbeat.occurred_at)
            occurred_at = heartbeat.occurred_at
            occurred_at = occurred_at.replace(tzinfo=timezone.utc) if occurred_at.tzinfo is None else occurred_at
            result["last_maintenance_age_seconds"] = max(
                0, int((now - occurred_at.astimezone(timezone.utc)).total_seconds())
            )

        test_delivery = (
            db.query(models.IntegrationDelivery)
            .filter_by(idempotency_key=forge_bot_owner_notification.OWNER_TEST_IDEMPOTENCY_KEY)
            .one_or_none()
        )
        if test_delivery is not None:
            result["last_test_email_at"] = _iso_timestamp(
                test_delivery.updated_at or test_delivery.created_at
            )
            result["last_test_email_result"] = test_delivery.status

        owner_recipients = {
            recipient
            for recipient in (
                settings.FORGE_BOT_CONTACT_EMAIL,
                forge_bot_owner_notification.OWNER_TEST_RECIPIENT,
            )
            if recipient
        }
        pending_email_filter = or_(
            *(models.IntegrationDelivery.request_json.contains(recipient) for recipient in owner_recipients)
        )
        pending_delivery = (
            db.query(models.IntegrationDelivery)
            .filter(
                models.IntegrationDelivery.integration_name == "smtp",
                models.IntegrationDelivery.operation == "send_email",
                models.IntegrationDelivery.status.notin_(
                    ("ACCEPTED_BY_SMTP", "SUCCEEDED", "DELIVERED")
                ),
                pending_email_filter,
            )
            .order_by(models.IntegrationDelivery.created_at.asc())
            .first()
        )
        if pending_delivery is not None:
            result["oldest_unsent_or_failed_owner_email_at"] = _iso_timestamp(
                pending_delivery.created_at
            )

        active_leads = (
            db.query(models.ForgeBotLeadContact)
            .filter(
                models.ForgeBotLeadContact.opted_out.is_(False),
                models.ForgeBotLeadContact.erased_at.is_(None),
            )
            .order_by(models.ForgeBotLeadContact.created_at.desc())
            .all()
        )
        day_ago = now - timedelta(days=1)
        for lead in active_leads:
            result["lead_counts_by_stage"][_lead_stage(db, lead)] += 1
            result["lead_counts_by_evidence_class"][lead.evidence_class] += 1
            created_at = lead.created_at
            created_at = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at
            if created_at >= day_ago:
                result["new_leads_last_24h"] += 1
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Forge Bot owner readiness query failed (%s).", type(exc).__name__)
        result["database_ok"] = False
        result["migrations_ok"] = False
    return result


@router.post("/owner-notification/test-send")
def send_owner_notification_test(
    request: Request,
    db: Session = Depends(get_db),
):
    """Send one fixed owner-only test email; never expose provider details."""
    _require_owner_key(request, db)
    try:
        result = forge_bot_owner_notification.send_owner_test_notification(db)
    except Exception as exc:
        logger.error("Forge Bot owner test notification failed (%s).", type(exc).__name__)
        return {"status": "failed"}
    return {
        "status": "sent"
        if result is not None and result.get("status") == "ACCEPTED_BY_SMTP"
        else "failed"
    }


@router.get("/config")
def get_forge_bot_config():
    """Return only public contact settings and whether intake is currently enabled."""
    return {
        "intake_enabled": _enabled(),
        "booking_url": settings.FORGE_BOT_BOOKING_URL,
        "consent_version": CONSENT_PROVENANCE,
    }


@router.get("/owner/readiness")
def get_owner_console_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return operational booleans, timestamps, commit, and aggregate counts only."""
    _require_owner_key(request, db)
    return _readiness_payload(db)


@router.get("/owner/leads")
def list_owner_console_leads(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
):
    """List references and non-contact qualification details for owner review."""
    _require_owner_key(request, db)
    leads = (
        db.query(models.ForgeBotLeadContact)
        .filter(
            models.ForgeBotLeadContact.opted_out.is_(False),
            models.ForgeBotLeadContact.erased_at.is_(None),
        )
        .order_by(models.ForgeBotLeadContact.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "reference": lead.public_ref,
            "received_at": _iso_timestamp(lead.created_at),
            "stage": _lead_stage(db, lead),
            "evidence_class": lead.evidence_class,
            "channel": lead.preferred_channel,
            "destination": lead.destination,
            "course": lead.course,
        }
        for lead in leads
    ]


@router.get("/owner/leads/{reference}")
def get_owner_console_lead(
    reference: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return contact details only within the owner-key boundary."""
    _require_owner_key(request, db)
    lead = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(public_ref=reference, opted_out=False, erased_at=None)
        .one_or_none()
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Active inquiry not found.")
    events = (
        db.query(models.WorldEvent)
        .filter(
            or_(
                models.WorldEvent.event_type.in_(
                    ("forge_bot_inquiry_received", "forge_bot_inquiry_erased")
                ),
                models.WorldEvent.event_type == "state_changed",
            ),
            models.WorldEvent.payload.contains(lead.public_ref),
        )
        .order_by(models.WorldEvent.occurred_at, models.WorldEvent.id)
        .all()
    )
    history = []
    for event in events:
        try:
            payload = json.loads(event.payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if payload.get("reference") != lead.public_ref:
            continue
        history.append({
            "event": payload.get("transition", event.event_type),
            "at": _iso_timestamp(event.occurred_at),
            "previous_state": payload.get("previous_state"),
            "state": payload.get("state"),
            "evidence_reference": payload.get("evidence_reference"),
            "outcome_note": payload.get("outcome_note"),
        })
    return {
        "reference": lead.public_ref,
        "received_at": _iso_timestamp(lead.created_at),
        "stage": _lead_stage(db, lead),
        "evidence_class": lead.evidence_class,
        "channel": lead.preferred_channel,
        "email": lead.email,
        "phone": lead.phone,
        "destination": lead.destination,
        "course": lead.course,
        "timeline": lead.timeline,
        "budget_minimum": lead.budget_minimum,
        "budget_maximum": lead.budget_maximum,
        "consent_at": _iso_timestamp(lead.consent_at),
        "history": history,
    }


@router.post("/owner/leads/{reference}/replied")
def mark_owner_console_lead_replied(
    reference: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_owner_key(request, db)
    result = _lead_event_payload(db, reference)
    if result["stage"] != "REQUESTED":
        raise HTTPException(status_code=409, detail="Only a requested inquiry can be marked replied.")
    _record_owner_lead_transition(
        db,
        lead=result["lead"],
        event_type="forge_bot_lead_replied",
        next_stage="REPLIED",
    )
    return {"reference": reference, "stage": "REPLIED"}


@router.post("/owner/leads/{reference}/booked")
def mark_owner_console_lead_booked(
    reference: str,
    payload: schemas.ForgeBotLeadBooked,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_owner_key(request, db)
    result = _lead_event_payload(db, reference)
    if result["stage"] != "REPLIED":
        raise HTTPException(status_code=409, detail="Reply must be recorded before booking.")
    _record_owner_lead_transition(
        db,
        lead=result["lead"],
        event_type="forge_bot_lead_booked",
        next_stage="BOOKED",
        details={"evidence_reference": payload.evidence_reference},
    )
    return {"reference": reference, "stage": "BOOKED"}


@router.post("/owner/leads/{reference}/completed")
def mark_owner_console_lead_completed(
    reference: str,
    payload: schemas.ForgeBotLeadCompleted,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_owner_key(request, db)
    result = _lead_event_payload(db, reference)
    if result["stage"] != "BOOKED":
        raise HTTPException(status_code=409, detail="Booking must be recorded before completion.")
    _record_owner_lead_transition(
        db,
        lead=result["lead"],
        event_type="forge_bot_lead_completed",
        next_stage="COMPLETED",
        details={"outcome_note": payload.outcome_note},
    )
    return {"reference": reference, "stage": "COMPLETED"}


@router.delete("/owner/leads/{reference}")
def erase_owner_console_lead(
    reference: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete private inquiry data while retaining its non-contact erasure event."""
    _require_owner_key(request, db)
    lead = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(public_ref=reference, opted_out=False, erased_at=None)
        .with_for_update()
        .one_or_none()
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Active inquiry not found.")
    _record_inquiry_event(
        db,
        event_type="forge_bot_inquiry_erased",
        reference=lead.public_ref,
        evidence_class=lead.evidence_class,
        source="forge_bot_owner_console",
        state="ERASED",
        previous_state=_lead_stage(db, lead),
    )
    db.delete(lead)
    db.commit()
    return {"reference": reference, "status": "erased"}


@router.get("/response-authorization")
def get_forge_bot_response_authorization(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return the owner-only response authorization state; absent means closed."""
    _require_owner_key(request, db)
    authorization = db.get(models.OpForgeBotResponseAuthorization, 1)
    return _authorization_values(authorization)


@router.put("/response-authorization")
def set_forge_bot_response_authorization(
    payload: schemas.ForgeBotResponseAuthorizationUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Replace the singleton response policy and record its transition."""
    _require_owner_key(request, db)
    values = payload.model_dump()
    authorization = db.get(models.OpForgeBotResponseAuthorization, 1)
    previous_values = (
        {
            key: getattr(authorization, key)
            for key in values
        }
        if authorization is not None
        else None
    )
    changed = previous_values is None or any(
        previous_values[key] != value for key, value in values.items()
    )
    if authorization is None:
        authorization = models.OpForgeBotResponseAuthorization(id=1, **values)
        db.add(authorization)
    elif changed:
        for key, value in values.items():
            setattr(authorization, key, value)
        authorization.updated_at = datetime.now(timezone.utc)

    if changed:
        world_graph.seed_core_types(db)
        world_graph.create_event(
            db,
            event_type="forge_bot_response_authorization_changed",
            source="forge_bot_owner_response_authorization",
            payload={
                "previous": previous_values,
                "current": values,
            },
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(authorization)
    return _authorization_values(authorization)


@router.get("/leads/{reference}/response-readiness")
def get_forge_bot_response_readiness(
    reference: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Evaluate internal response readiness without creating outbound work."""
    _require_owner_key(request, db)
    authorization = db.get(models.OpForgeBotResponseAuthorization, 1)
    decision = forge_bot_response.decide_response_action(
        db,
        inquiry_reference=reference,
        action=None,
        requested_channel=authorization.selected_channel if authorization else None,
        requested_template_ref=authorization.template_ref if authorization else None,
    )
    return _response_readiness_output(decision, authorization)


@router.post("/response-actions", status_code=202)
def create_forge_bot_response_action(
    payload: schemas.ForgeBotResponseActionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create an owner-confirmed ACTION record; this does not send a message."""
    _require_owner_key(request, db)
    lead = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(
            public_ref=payload.inquiry_reference,
            opted_out=False,
            erased_at=None,
        )
        .with_for_update()
        .one_or_none()
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Active inquiry not found.")
    action = forge_bot_response.propose_response_action(
        db,
        inquiry_reference=payload.inquiry_reference,
        channel=payload.channel,
        template_ref=payload.template_ref,
    )
    return {
        "action_id": action.id,
        "status": action.status,
        "decision": "PENDING_OWNER_CONFIRMATION",
        "external_message_sent": False,
    }


@router.post("/response-actions/{action_id}/approve")
def approve_forge_bot_response_action(
    action_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record owner confirmation on one response ACTION."""
    _require_owner_key(request, db)
    action = forge_bot_response.approve_response_action(db, action_id=action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Forge Bot response ACTION not found.")
    return {
        "action_id": action.id,
        "status": action.status,
        "approved_at": action.approved_at,
        "external_message_sent": False,
    }


@router.post("/response-actions/{action_id}/execute")
def execute_forge_bot_response_action(
    action_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Run the authorization-only ACTION adapter; no customer sender is wired."""
    _require_owner_key(request, db)
    action = db.get(models.Action, action_id)
    if action is None or action.action_type != "forge_bot_response":
        raise HTTPException(status_code=404, detail="Forge Bot response ACTION not found.")
    from app.services import action_engine

    executed = action_engine.start_and_execute_action(db, action_id)
    if executed is None:
        raise HTTPException(status_code=404, detail="Forge Bot response ACTION not found.")
    return {
        "action_id": executed.id,
        "status": executed.status,
        "execution_error": executed.execution_error,
        "verification_state": executed.verification_state,
        "external_message_sent": False,
    }


@router.post(
    "/leads",
    response_model=schemas.ForgeBotLeadReceipt,
    status_code=202,
)
def create_forge_bot_lead(
    payload: schemas.ForgeBotLeadCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Store one consented web inquiry without sending or exposing contact data."""
    reference = f"FB-{secrets.token_hex(6).upper()}"
    token = secrets.token_urlsafe(32)
    receipt = schemas.ForgeBotLeadReceipt(
        reference=reference,
        manage_token=token,
        message=(
            "This page confirms receipt for owner review only. No reply was "
            "sent through your selected contact channel and no booking was "
            "made. Keep this one-time control code private."
        ),
    )
    if not _enabled():
        raise HTTPException(status_code=503, detail="Forge Bot web intake is not enabled.")
    if not payload.consent_granted:
        raise HTTPException(status_code=422, detail="Explicit consent is required.")
    if payload.budget_maximum < payload.budget_minimum:
        raise HTTPException(status_code=422, detail="Budget maximum must be at least minimum.")
    if payload.preferred_channel == "email" and not payload.email:
        raise HTTPException(status_code=422, detail="An email address is required for email contact.")
    if payload.preferred_channel == "phone" and not payload.phone:
        raise HTTPException(status_code=422, detail="A phone number is required for phone contact.")
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=422, detail="Provide an email address or phone number.")
    if payload.website:
        return receipt
    if not forge_bot_privacy.consume_intake_submission(
        db,
        request,
        hmac_key=settings.FORGE_BOT_CONTACT_HMAC_KEY,
    ):
        raise HTTPException(
            status_code=429,
            detail="Hourly submission limit reached: no more than 5 inquiries per visitor per hour.",
        )

    normalized_email = payload.email.lower() if payload.email else None
    normalized_phone = _normalized_phone(payload.phone)
    is_test_phone = bool(
        normalized_phone and re.fullmatch(r"(?:1)?20255501[0-9]{2}", normalized_phone)
    )
    evidence_class = "TEST" if (
        (normalized_email and normalized_email.endswith("@example.test"))
        or is_test_phone
    ) else "REAL"
    if evidence_class == "REAL" and not settings.FORGE_BOT_LIVE:
        raise HTTPException(
            status_code=403,
            detail="Real lead intake requires FORGE_BOT_LIVE=true.",
        )
    email_suppression_hmac = _contact_digest("email", normalized_email)
    phone_suppression_hmac = _contact_digest("phone", normalized_phone)
    match_conditions = []
    if normalized_email:
        match_conditions.extend(
            [
                models.ForgeBotLeadContact.normalized_email == normalized_email,
                models.ForgeBotLeadContact.email_suppression_hmac == email_suppression_hmac,
            ]
        )
    if normalized_phone:
        match_conditions.extend(
            [
                models.ForgeBotLeadContact.normalized_phone == normalized_phone,
                models.ForgeBotLeadContact.phone_suppression_hmac == phone_suppression_hmac,
            ]
        )
    existing = db.query(models.ForgeBotLeadContact).filter(or_(*match_conditions)).first()
    if existing is not None:
        # The fixed receipt shape avoids disclosing whether an address is already known.
        return receipt

    row = models.ForgeBotLeadContact(
        public_ref=reference,
        email=payload.email,
        normalized_email=normalized_email,
        phone=payload.phone,
        normalized_phone=normalized_phone,
        email_suppression_hmac=email_suppression_hmac,
        phone_suppression_hmac=phone_suppression_hmac,
        manage_token_hash=_token_hash(token),
        preferred_channel=payload.preferred_channel,
        destination=payload.destination,
        course=payload.course,
        timeline=payload.timeline,
        budget_minimum=payload.budget_minimum,
        budget_maximum=payload.budget_maximum,
        stage="READY_FOR_OWNER_REVIEW",
        evidence_class=evidence_class,
        consent_granted=True,
        consent_at=datetime.now(timezone.utc),
        consent_purpose=CONSENT_PURPOSE,
        consent_provenance=CONSENT_PROVENANCE,
    )
    db.add(row)
    _record_inquiry_event(
        db,
        event_type="forge_bot_inquiry_received",
        reference=reference,
        evidence_class=evidence_class,
        source="forge_bot_web_form",
        state=row.stage,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent duplicate submissions are acknowledged without returning
        # the other lead's reference or control token.
        duplicate = (
            db.query(models.ForgeBotLeadContact)
            .filter(or_(*match_conditions))
            .first()
        )
        if duplicate is not None:
            return receipt
        raise
    if evidence_class == "REAL":
        try:
            forge_bot_owner_notification.send_owner_summary_notification(
                db,
                reference,
                {
                    "evidence_class": row.evidence_class,
                    "stage": row.stage,
                    "preferred_channel": row.preferred_channel,
                    "email": row.email,
                    "phone": row.phone,
                    "destination": row.destination,
                    "course": row.course,
                    "timeline": row.timeline,
                    "budget_minimum": row.budget_minimum,
                    "budget_maximum": row.budget_maximum,
                    "consent_granted": row.consent_granted,
                    "consent_at": row.consent_at.isoformat(),
                    "consent_purpose": row.consent_purpose,
                    "consent_provenance": row.consent_provenance,
                },
                idempotency_key=f"forge-bot-lead-owner-notification:{reference}",
            )
        except Exception as exc:
            logger.error(
                "Forge Bot owner notification failed for %s (%s).",
                reference,
                type(exc).__name__,
            )
    return receipt


@router.post("/leads/opt-out", status_code=202)
def opt_out_forge_bot_lead(
    payload: schemas.ForgeBotLeadControl,
    db: Session = Depends(get_db),
):
    """Permanently suppress a lead using the private one-time control code."""
    token = payload.manage_token
    row = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(manage_token_hash=_token_hash(token), opted_out=False, erased_at=None)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Control code not found.")
    reference = row.public_ref
    evidence_class = row.evidence_class
    previous_state = row.stage
    row.opted_out = True
    row.opted_out_at = datetime.now(timezone.utc)
    row.erased_at = datetime.now(timezone.utc)
    row.email = None
    row.normalized_email = None
    row.phone = None
    row.normalized_phone = None
    row.destination = None
    row.course = None
    row.timeline = None
    row.budget_minimum = None
    row.budget_maximum = None
    row.manage_token_hash = None
    row.stage = "OPTED_OUT"
    row.public_ref = f"FB-SUPP-{secrets.token_hex(8).upper()}"
    _record_inquiry_event(
        db,
        event_type="forge_bot_inquiry_opted_out",
        reference=reference,
        evidence_class=evidence_class,
        source="forge_bot_self_service_control",
        state=row.stage,
        previous_state=previous_state,
    )
    db.commit()
    return {
        "status": "opted_out",
        "message": (
            "Contact fields and qualification answers were erased. HMAC-only "
            "suppression tokens remain to prevent re-entry or future contact."
        ),
    }


@router.post("/leads/delete", status_code=204)
def delete_forge_bot_lead(
    payload: schemas.ForgeBotLeadControl,
    db: Session = Depends(get_db),
):
    """Erase a lead record using its private one-time control code."""
    token = payload.manage_token
    row = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(manage_token_hash=_token_hash(token), opted_out=False, erased_at=None)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Control code not found.")
    _record_inquiry_event(
        db,
        event_type="forge_bot_inquiry_erased",
        reference=row.public_ref,
        evidence_class=row.evidence_class,
        source="forge_bot_self_service_control",
        state="ERASED",
        previous_state=row.stage,
    )
    db.delete(row)
    db.commit()
    return None


@router.get("/leads/summary")
def get_owner_lead_summary(request: Request, db: Session = Depends(get_db)):
    """Return active lead rows only after mandatory owner API-key authorization."""
    _require_owner_key(request, db)
    rows = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(opted_out=False, erased_at=None)
        .order_by(models.ForgeBotLeadContact.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "reference": row.public_ref,
            "email": row.email,
            "phone": row.phone,
            "preferred_channel": row.preferred_channel,
            "destination": row.destination,
            "course": row.course,
            "timeline": row.timeline,
            "budget_minimum": row.budget_minimum,
            "budget_maximum": row.budget_maximum,
            "stage": row.stage,
            "evidence_class": row.evidence_class,
            "consent_at": row.consent_at,
        }
        for row in rows
    ]
