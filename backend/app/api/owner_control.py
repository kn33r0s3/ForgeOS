"""Private Telegram webhook and authenticated owner-console ASK endpoints."""
import json
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.database import get_db
from app.security import require_owner_api_key
from app.services import owner_control

router = APIRouter(prefix="/owner-control", tags=["owner-control"])
logger = logging.getLogger(__name__)

class AskOption(BaseModel):
    key: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=160)

class AskBody(BaseModel):
    decision_ref: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=1600)
    options: list[AskOption] = Field(min_length=2, max_length=3)
    action_type: str | None = Field(default=None, max_length=100)
    action_id: int | None = Field(default=None, ge=1)
    high_impact: bool = False

class AnswerBody(BaseModel):
    code: str = Field(min_length=8, max_length=80)
    option: str = Field(min_length=1, max_length=32)

def _error(exc: owner_control.OwnerControlError) -> HTTPException:
    code = exc.reason
    statuses = {
        "telegram_control_not_configured": 503, "telegram_ask_delivery_failed": 503,
        "durable_database_required": 503,
        "action_not_eligible_for_ask": 409, "action_ask_requires_approve_reject_options": 422,
        "ask_requires_two_or_three_options": 422, "ask_option_invalid": 422,
        "ask_option_invalid_or_contains_protected_contact": 422, "ask_question_invalid": 422,
        "ask_contains_protected_contact": 422, "ask_message_too_long": 422,
        "ask_daily_limit_reached": 429, "ask_not_found": 404, "ask_not_open": 409,
        "ask_not_open_or_expired": 409, "ask_resend_limit_reached": 429,
        "ask_expired": 410, "ask_code_expired": 410, "ask_code_invalid": 401,
        "owner_console_required": 403, "blocked_action_cannot_be_approved": 409,
        "safe_mode_not_active": 409, "answer_channel_invalid": 422,
    }
    return HTTPException(status_code=statuses.get(code, 400), detail=code)

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    if not owner_control.control_ready():
        raise HTTPException(status_code=503, detail="Telegram owner control is not configured.")
    if not owner_control.verify_webhook_secret(request.headers.get("x-telegram-bot-api-secret-token")):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret.")
    if not owner_control.durable_database(db):
        raise HTTPException(status_code=503, detail="Durable PostgreSQL is required for owner control.")
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Telegram update.") from None
    if not isinstance(update, dict) or type(update.get("update_id")) is not int or update["update_id"] < 0:
        return {"ok": True, "ignored": True}
    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True, "ignored": True}
    chat, sender = message.get("chat"), message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return {"ok": True, "ignored": True}
    if (
        chat.get("type") != "private" or sender.get("is_bot") is True
        or str(chat.get("id")) != str(settings.HAMI_TELEGRAM_OWNER_CHAT_ID).strip()
        or str(sender.get("id")) != str(settings.HAMI_TELEGRAM_OWNER_USER_ID).strip()
    ):
        return {"ok": True, "ignored": True}
    try:
        state = owner_control.ensure_state(db)
        if state.last_telegram_update_id is not None and update["update_id"] <= state.last_telegram_update_id:
            return {"ok": True, "ignored": True, "reason": "duplicate_or_stale_update"}
        reply = owner_control.handle_owner_message(db, update_id=update["update_id"], message=message)
        raw = message.get("text") if isinstance(message.get("text"), str) else ""
        from app.services import telegram_transport
        kind = "alert" if raw.strip().upper() == "HALT" or raw.strip().lower().startswith("/halt") else "status"
        telegram_transport.send_owner_message(reply, message_type=kind)
    except owner_control.OwnerControlError as exc:
        raise _error(exc) from None
    except Exception as exc:
        db.rollback()
        logger.warning("Telegram owner webhook failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Owner control temporarily unavailable.") from None
    return {"ok": True}

@router.get("/status")
def owner_status(request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        state = owner_control.ensure_state(db)
        inactivity = owner_control.evaluate_owner_inactivity(db)
        state = owner_control.ensure_state(db)
    except Exception:
        raise HTTPException(status_code=503, detail="Runtime control state unavailable.") from None
    last = owner_control.normalize_dt(state.last_owner_contact_at)
    active = bool(settings.FORGE_BOT_LIVE and not state.safe_mode_enabled and last
                  and owner_control.now() - last < timedelta(days=7))
    from app.services import decision_rights
    return {
        "safe_mode_enabled": bool(state.safe_mode_enabled), "safe_mode_reason": state.safe_mode_reason,
        "last_owner_contact_at_utc": last.isoformat() + "Z" if last else None,
        "owner_contact_stale": inactivity.get("owner_contact_stale"),
        "customer_sending_effective": "ON" if active else "OFF",
        "active_stage": decision_rights.ACTIVE_STAGE, "telegram_control_configured": owner_control.control_ready(),
        "telegram_digest_enabled": settings.HAMI_TELEGRAM_OWNER_DIGEST_ENABLED,
        "sms_digest_enabled": settings.HAMI_OWNER_SMS_DIGEST_ENABLED,
        "intake_enabled": settings.FORGE_BOT_INTAKE_ENABLED, "public_checkout_enabled": settings.FORGEOS_PUBLIC_CHECKOUT_ENABLED,
        "note": "Configuration is not delivery proof; secrets and owner IDs are not returned.",
    }

@router.get("/asks")
def list_asks(request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    rows = db.query(models.OpHamiOwnerAsk).order_by(models.OpHamiOwnerAsk.created_at.desc()).limit(30).all()
    return [{
        "ask_ref": row.public_ref, "decision_ref": row.decision_ref, "action_type": row.action_type,
        "action_id": row.action_id, "question": row.question, "options": json.loads(row.options_json),
        "high_impact": bool(row.high_impact), "status": row.status, "notification_status": row.notification_status,
        "code_expires_at_utc": row.code_expires_at.isoformat() + "Z" if row.code_expires_at else None,
        "expires_at_utc": row.expires_at.isoformat() + "Z" if row.expires_at else None, "answer_option": row.answer_option,
    } for row in rows]

@router.post("/asks")
def create_ask(body: AskBody, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        row = owner_control.create_ask(
            db, decision_ref=body.decision_ref, question=body.question,
            options=[item.model_dump() for item in body.options], action_type=body.action_type,
            action_id=body.action_id, high_impact=body.high_impact,
        )
    except owner_control.OwnerControlError as exc:
        raise _error(exc) from None
    return {"ask_ref": row.public_ref, "status": row.status, "high_impact": row.high_impact,
            "notification_status": row.notification_status, "code_returned_by_api": False, "action_executed": False}

@router.post("/asks/{ask_ref}/answer")
def answer_ask(ask_ref: str, body: AnswerBody, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return owner_control.answer_ask(db, ask_ref=ask_ref, code=body.code, option=body.option, channel="owner_console")
    except owner_control.OwnerControlError as exc:
        raise _error(exc) from None
    except Exception as exc:
        db.rollback()
        logger.warning("Owner ASK answer failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=409, detail="Decision could not be recorded; no Action was executed.") from None

@router.post("/asks/{ask_ref}/resend")
def resend_ask(ask_ref: str, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        row = owner_control.resend_ask(db, ask_ref)
    except owner_control.OwnerControlError as exc:
        raise _error(exc) from None
    return {"ask_ref": row.public_ref, "status": row.status, "notification_status": row.notification_status, "code_returned_by_api": False}

@router.post("/resume/request")
def request_resume(request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        row = owner_control.create_resume_ask(db)
    except owner_control.OwnerControlError as exc:
        raise _error(exc) from None
    return {"ask_ref": row.public_ref, "high_impact": True, "status": row.status,
            "next_step": "Use authenticated owner console and the one-time code delivered to Telegram; Telegram alone cannot resume."}
