"""Persisted owner-control safety boundary and Telegram ASK processing."""
import hashlib, hmac, json, logging, re, secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import models
from app.config import settings
from app.services import telegram_transport

logger = logging.getLogger(__name__)
INACTIVITY_DAYS = 7
ASK_LIMIT = 5
MAX_FAILURES = 5
MAX_RESENDS = 3
RESUME_REF = "hami.safe_mode.resume"
_ID = re.compile(r"^[1-9][0-9]{0,18}$")
_SECRET = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_OPTION = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


class OwnerControlError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_dt(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value


def control_ready() -> bool:
    token = str(settings.HAMI_TELEGRAM_BOT_TOKEN or "").strip()
    return bool(
        settings.HAMI_TELEGRAM_CONTROL_ENABLED and len(token) >= 30
        and _SECRET.fullmatch(str(settings.HAMI_TELEGRAM_WEBHOOK_SECRET or "").strip())
        and _ID.fullmatch(str(settings.HAMI_TELEGRAM_OWNER_CHAT_ID or "").strip())
        and _ID.fullmatch(str(settings.HAMI_TELEGRAM_OWNER_USER_ID or "").strip())
    )


def verify_webhook_secret(value: str | None) -> bool:
    expected = str(settings.HAMI_TELEGRAM_WEBHOOK_SECRET or "").strip()
    return bool(control_ready() and isinstance(value, str) and value and hmac.compare_digest(value, expected))


def durable_database(db: Session) -> bool:
    try:
        return db.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


def ensure_state(db: Session) -> models.OpHamiRuntimeControl:
    row = db.get(models.OpHamiRuntimeControl, 1)
    if row is not None:
        return row
    row = models.OpHamiRuntimeControl(
        id=1, safe_mode_enabled=True, safe_mode_reason="initial_default_safe",
        halted_at=now(), updated_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.get(models.OpHamiRuntimeControl, 1)
        if row is None:
            raise
        return row
    db.refresh(row)
    return row


def _event(db: Session, transition: str, key: str, reason: str | None = None, ask_ref: str | None = None) -> None:
    try:
        from app.services import world_graph
        world_graph.seed_core_types(db)
        db.commit()
        payload = {"subsystem": "owner_control", "transition": transition}
        if reason:
            payload["reason"] = reason
        if ask_ref:
            payload["ask_ref"] = ask_ref
        world_graph.create_event(db, event_type="state_changed", source="hami_owner_control",
                                 payload=payload, idempotency_key=key)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("owner_control_event_failed transition=%s", transition)


def set_safe_mode(db: Session, reason: str, update_id: int | None = None) -> models.OpHamiRuntimeControl:
    allowed = {"initial_default_safe", "halt_command", "owner_inactive", "incident",
               "health_check_failed", "spend_cap_reached", "owner_resumed"}
    if reason not in allowed:
        raise OwnerControlError("safe_mode_reason_invalid")
    row = ensure_state(db)
    changed = not row.safe_mode_enabled or row.safe_mode_reason != reason
    row.safe_mode_enabled, row.safe_mode_reason = True, reason
    row.halted_at, row.updated_at = now(), now()
    if update_id is not None and (row.last_telegram_update_id is None or update_id > row.last_telegram_update_id):
        row.last_telegram_update_id = update_id
    db.commit()
    db.refresh(row)
    if changed:
        _event(db, "safe_mode_enabled", f"hami-owner-control:safe:{reason}:{update_id or int(row.updated_at.timestamp())}", reason)
    return row


def record_contact(db: Session, update_id: int) -> tuple[models.OpHamiRuntimeControl, bool]:
    row = ensure_state(db)
    if row.last_telegram_update_id is not None and update_id <= row.last_telegram_update_id:
        return row, False
    last = normalize_dt(row.last_owner_contact_at)
    stale = last is None or now() - last >= timedelta(days=INACTIVITY_DAYS)
    if stale:
        row.safe_mode_enabled, row.safe_mode_reason, row.halted_at = True, "owner_inactive", now()
    row.last_owner_contact_at, row.last_telegram_update_id, row.updated_at = now(), update_id, now()
    db.commit()
    db.refresh(row)
    _event(db, "owner_contact_after_inactivity" if stale else "owner_contact_recorded",
           f"hami-owner-control:contact:{update_id}", "owner_inactive" if stale else None)
    return row, True


def evaluate_owner_inactivity(db: Session) -> dict[str, Any]:
    try:
        row = ensure_state(db)
        last = normalize_dt(row.last_owner_contact_at)
        stale = last is None or now() - last >= timedelta(days=INACTIVITY_DAYS)
        if stale and (not row.safe_mode_enabled or row.safe_mode_reason != "owner_inactive"):
            row = set_safe_mode(db, "owner_inactive")
        return {"status": "safe_mode" if row.safe_mode_enabled else "active",
                "reason": row.safe_mode_reason, "owner_contact_stale": stale}
    except Exception:
        return {"status": "unavailable", "reason": "runtime_control_unavailable", "owner_contact_stale": None}


def block_customer_delivery(db: Session, *, integration_name: str, operation: str, request_data: dict[str, Any]) -> str | None:
    """Fail closed for the currently wired generic customer SMS/email channels."""
    if (integration_name, operation) not in {("twilio", "send_sms"), ("smtp", "send_email")}:
        return None
    if (integration_name, operation) == ("smtp", "send_email"):
        owner = str(settings.FORGE_BOT_CONTACT_EMAIL or "").strip().lower()
        actual = str(request_data.get("to") or request_data.get("recipient") or "").strip().lower()
        if owner and actual and hmac.compare_digest(owner, actual):
            return None
    if not settings.FORGE_BOT_LIVE:
        return "customer_sending_disabled"
    try:
        row = ensure_state(db)
        last = normalize_dt(row.last_owner_contact_at)
        if last is None or now() - last >= timedelta(days=INACTIVITY_DAYS):
            set_safe_mode(db, "owner_inactive")
            return "owner_inactive"
        return "safe_mode_enabled" if row.safe_mode_enabled else None
    except Exception:
        return "runtime_control_unavailable"


def valid_owner_delivery(name: str, operation: str, payload: dict[str, Any]) -> bool:
    if (name, operation) != ("telegram_owner", "send_telegram_owner") or not control_ready():
        return False
    if set(payload) != {"chat_id", "body", "message_type"}:
        return False
    chat, body, kind = str(payload.get("chat_id") or "").strip(), payload.get("body"), payload.get("message_type")
    return bool(chat == str(settings.HAMI_TELEGRAM_OWNER_CHAT_ID).strip() and _ID.fullmatch(chat)
                and kind in {"daily_digest", "alert"} and isinstance(body, str) and body.strip()
                and len(body) <= 4096 and not _EMAIL.search(body) and not _PHONE.search(body))


def _sensitive(text: str) -> bool:
    return bool(_EMAIL.search(text) or _PHONE.search(text))


def _options(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not 2 <= len(raw) <= 3:
        raise OwnerControlError("ask_requires_two_or_three_options")
    output, seen = [], set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"key", "label"}:
            raise OwnerControlError("ask_option_invalid")
        key, label = item.get("key"), item.get("label")
        if not isinstance(key, str) or not _OPTION.fullmatch(key.strip().upper()):
            raise OwnerControlError("ask_option_invalid")
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 160:
            raise OwnerControlError("ask_option_invalid")
        key, label = key.strip().upper(), label.strip()
        if key in seen or _sensitive(label):
            raise OwnerControlError("ask_option_invalid_or_contains_protected_contact")
        seen.add(key)
        output.append({"key": key, "label": label})
    return output


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _ask_text(ask: models.OpHamiOwnerAsk, code: str) -> str:
    choices = "\n".join(f"{x['key']} — {x['label']}" for x in json.loads(ask.options_json))
    ttl = max(60, min(3600, int(settings.HAMI_TELEGRAM_ASK_CODE_TTL_SECONDS)))
    high = "HIGH IMPACT: sign in to owner console and submit this code; Telegram alone cannot approve." if ask.high_impact else "Routine ASK: reply /answer ASK-REF CODE OPTION as a new message."
    text = f"Hami ASK {ask.public_ref}\nDecision: {ask.question}\nOptions:\n{choices}\nCode: {code}\nExpires in {ttl // 60} minute(s); one-time only.\n{high}\nDefault if unanswered: DO NOTHING."
    if len(text) > 4096:
        raise OwnerControlError("ask_message_too_long")
    return text


def create_ask(db: Session, *, decision_ref: str, question: str, options: Any,
               action_type: str | None = None, action_id: int | None = None,
               high_impact: bool = False) -> models.OpHamiOwnerAsk:
    if not control_ready():
        raise OwnerControlError("telegram_control_not_configured")
    if not durable_database(db):
        raise OwnerControlError("durable_database_required")
    decision_ref, question = str(decision_ref or "").strip(), str(question or "").strip()
    if not decision_ref or len(decision_ref) > 200 or not question or len(question) > 1600:
        raise OwnerControlError("ask_question_invalid")
    if _sensitive(decision_ref) or _sensitive(question):
        raise OwnerControlError("ask_contains_protected_contact")
    choices, action = _options(options), None
    if action_id is not None:
        action = db.get(models.Action, action_id)
        if action is None or action.status not in {"PROPOSED", "APPROVAL_REQUIRED"}:
            raise OwnerControlError("action_not_eligible_for_ask")
        action_type, decision_ref = action.action_type, f"action:{action.id}"
        if {x["key"] for x in choices} != {"APPROVE", "REJECT"}:
            raise OwnerControlError("action_ask_requires_approve_reject_options")
    action_type = str(action_type or "unknown").strip().lower() or "unknown"
    from app.services import decision_rights
    high = bool(high_impact or decision_rights.entry_for(action_type)["right"] == decision_rights.OWNER_ONLY or decision_ref == RESUME_REF)
    stamp = now()
    day_start = stamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if db.query(models.OpHamiOwnerAsk).filter(models.OpHamiOwnerAsk.created_at >= day_start).count() >= ASK_LIMIT:
        raise OwnerControlError("ask_daily_limit_reached")
    code = secrets.token_urlsafe(18)
    ttl = max(60, min(3600, int(settings.HAMI_TELEGRAM_ASK_CODE_TTL_SECONDS)))
    ask = models.OpHamiOwnerAsk(
        public_ref="ASK-" + secrets.token_hex(4).upper(), decision_ref=decision_ref, action_type=action_type,
        action_id=action.id if action else None, question=question,
        options_json=json.dumps(choices, separators=(",", ":")), high_impact=high, code_hash=_code_hash(code),
        code_expires_at=stamp + timedelta(seconds=ttl), expires_at=stamp + timedelta(hours=24),
        status="OPEN", failed_attempts=0, code_resend_count=0, created_at=stamp, notification_status="PENDING",
    )
    db.add(ask)
    db.commit()
    db.refresh(ask)
    try:
        sent = telegram_transport.send_owner_message(_ask_text(ask, code), message_type="ask")
    except Exception:
        ask.code_hash, ask.status, ask.notification_status = None, "NOTIFIED_FAILED", "FAILED"
        db.commit()
        _event(db, "ask_notification_failed", f"hami-owner-control:{ask.public_ref}:failed", ask_ref=ask.public_ref)
        raise OwnerControlError("telegram_ask_delivery_failed") from None
    ask.telegram_message_id, ask.notified_at, ask.notification_status = str(sent["message_id"]), now(), "SENT"
    db.commit()
    _event(db, "ask_created", f"hami-owner-control:{ask.public_ref}:created", ask_ref=ask.public_ref)
    return ask


def resend_ask(db: Session, ask_ref: str) -> models.OpHamiOwnerAsk:
    if not durable_database(db):
        raise OwnerControlError("durable_database_required")
    ask = db.query(models.OpHamiOwnerAsk).filter_by(public_ref=ask_ref).one_or_none()
    if ask is None:
        raise OwnerControlError("ask_not_found")
    expiry = normalize_dt(ask.expires_at)
    if ask.status not in {"OPEN", "NOTIFIED_FAILED"} or expiry is None or now() >= expiry:
        raise OwnerControlError("ask_not_open_or_expired")
    if ask.code_resend_count >= MAX_RESENDS:
        raise OwnerControlError("ask_resend_limit_reached")
    code, stamp = secrets.token_urlsafe(18), now()
    ttl = max(60, min(3600, int(settings.HAMI_TELEGRAM_ASK_CODE_TTL_SECONDS)))
    ask.status, ask.code_hash = "OPEN", _code_hash(code)
    ask.code_expires_at, ask.failed_attempts = stamp + timedelta(seconds=ttl), 0
    ask.code_resend_count += 1
    ask.notification_status = "PENDING"
    db.commit()
    try:
        sent = telegram_transport.send_owner_message(_ask_text(ask, code), message_type="ask")
    except Exception:
        ask.code_hash, ask.status, ask.notification_status = None, "NOTIFIED_FAILED", "FAILED"
        db.commit()
        raise OwnerControlError("telegram_ask_delivery_failed") from None
    ask.telegram_message_id, ask.notified_at, ask.notification_status = str(sent["message_id"]), now(), "SENT"
    db.commit()
    _event(db, "ask_code_resent", f"hami-owner-control:{ask.public_ref}:resent:{ask.code_resend_count}", ask_ref=ask.public_ref)
    return ask


def answer_ask(db: Session, *, ask_ref: str, code: str, option: str, channel: str) -> dict[str, Any]:
    if not durable_database(db):
        raise OwnerControlError("durable_database_required")
    if channel not in {"telegram", "owner_console"}:
        raise OwnerControlError("answer_channel_invalid")
    ask = db.query(models.OpHamiOwnerAsk).filter_by(public_ref=ask_ref).one_or_none()
    if ask is None:
        raise OwnerControlError("ask_not_found")
    if ask.status != "OPEN":
        raise OwnerControlError("ask_not_open")
    if ask.high_impact and channel != "owner_console":
        raise OwnerControlError("owner_console_required")
    stamp, expiry, code_expiry = now(), normalize_dt(ask.expires_at), normalize_dt(ask.code_expires_at)
    if expiry is None or stamp >= expiry:
        ask.status, ask.code_hash = "EXPIRED", None
        db.commit()
        _event(db, "ask_expired", f"hami-owner-control:{ask.public_ref}:expired", ask_ref=ask.public_ref)
        raise OwnerControlError("ask_expired")
    if code_expiry is None or stamp >= code_expiry or not ask.code_hash:
        raise OwnerControlError("ask_code_expired")
    choice = str(option or "").strip().upper()
    if choice not in {x["key"] for x in json.loads(ask.options_json)}:
        raise OwnerControlError("ask_option_invalid")
    if not hmac.compare_digest(_code_hash(str(code or "")), ask.code_hash):
        ask.failed_attempts += 1
        if ask.failed_attempts >= MAX_FAILURES:
            ask.status, ask.code_hash = "LOCKED", None
        db.commit()
        raise OwnerControlError("ask_code_invalid")
    action = db.get(models.Action, ask.action_id) if ask.action_id is not None else None
    if ask.action_id is not None:
        if action is None or action.status not in {"PROPOSED", "APPROVAL_REQUIRED"}:
            raise OwnerControlError("action_not_eligible_for_ask")
        if choice == "APPROVE":
            if action.policy_result == "BLOCK":
                raise OwnerControlError("blocked_action_cannot_be_approved")
            from app.services import intervention_gate
            intervention_gate.assert_single_active_intervention(db, action)
            action.status, action.approved_at, action.execution_error = "APPROVED", stamp, None
        elif choice == "REJECT":
            action.status, action.policy_result = "CANCELLED", "BLOCK"
            action.policy_reason = f"owner_rejected_ask:{ask.public_ref}"
            action.execution_error, action.completed_at = "Owner rejected through authenticated ASK.", stamp
        else:
            raise OwnerControlError("action_ask_requires_approve_reject_options")
    state = ensure_state(db)
    if ask.decision_ref == RESUME_REF:
        if choice == "RESUME":
            state.safe_mode_enabled, state.safe_mode_reason, state.halted_at = False, None, None
        elif choice == "KEEP_HALTED":
            state.safe_mode_enabled = True
            state.safe_mode_reason = state.safe_mode_reason or "halt_command"
            state.halted_at = state.halted_at or stamp
    ask.status, ask.answer_option, ask.answer_channel, ask.answered_at, ask.code_hash = "ANSWERED", choice, channel, stamp, None
    state.last_owner_contact_at, state.updated_at = stamp, stamp
    db.commit()
    db.refresh(ask)
    db.refresh(state)
    _event(db, "ask_answered", f"hami-owner-control:{ask.public_ref}:answered", ask_ref=ask.public_ref)
    if ask.decision_ref == RESUME_REF and choice == "RESUME":
        _event(db, "safe_mode_resumed_by_owner_console", f"hami-owner-control:resume:{ask.public_ref}", ask_ref=ask.public_ref)
    return {"status": "answered", "ask_ref": ask.public_ref, "option": choice,
            "safe_mode_enabled": bool(state.safe_mode_enabled), "action_status": action.status if action else None,
            "action_executed": False}


def create_resume_ask(db: Session) -> models.OpHamiOwnerAsk:
    if not ensure_state(db).safe_mode_enabled:
        raise OwnerControlError("safe_mode_not_active")
    return create_ask(db, decision_ref=RESUME_REF, action_type="widen_permissions",
        question="May Hami leave safe mode? This does not enable customer sending or other flags.",
        options=[{"key": "RESUME", "label": "Clear safe mode only; other gates remain"},
                 {"key": "KEEP_HALTED", "label": "Keep safe mode enabled"}], high_impact=True)


def handle_owner_message(db: Session, *, update_id: int, message: dict[str, Any]) -> str:
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        return "Hami accepts text commands only. Send /help."
    clean = text.strip()
    halt = clean.upper() == "HALT" or re.fullmatch(r"/halt(?:@[A-Za-z0-9_]+)?", clean, re.I) is not None
    _, fresh = record_contact(db, update_id)
    if not fresh:
        return "This Telegram update was already processed."
    if halt:
        set_safe_mode(db, "halt_command", update_id)
        return "HALT confirmed. Persisted safe mode is ON; generic customer email/SMS sends are blocked. Only the owner console can resume."
    quoted = any(k in message and message.get(k) is not None for k in ("reply_to_message", "quote", "forward_origin", "forward_from", "forward_from_chat", "external_reply")) or message.get("is_automatic_forward") is True
    if quoted:
        return "No decision accepted. Send commands as a new message, not a reply, quote or forward."
    command = clean.split(maxsplit=1)[0].split("@", 1)[0].lower()
    if command in {"/start", "/help"}:
        return "Hami owner control\nHALT — persistently block customer sends\n/status — inspect safety state\n/answer ASK-REF CODE OPTION — routine ASKs only\nHigh-impact ASKs require owner console + code. Telegram never executes Actions automatically."
    if command == "/status" or clean.lower() == "status":
        state = ensure_state(db)
        last = normalize_dt(state.last_owner_contact_at)
        sends = bool(settings.FORGE_BOT_LIVE and not state.safe_mode_enabled and last and now() - last < timedelta(days=INACTIVITY_DAYS))
        from app.services import decision_rights
        return f"Hami status: safe_mode={'ON' if state.safe_mode_enabled else 'OFF'}; customer_sending={'ON' if sends else 'OFF'}; stage={decision_rights.ACTIVE_STAGE}; intake={'ON' if settings.FORGE_BOT_INTAKE_ENABLED else 'OFF'}; checkout={'ON' if settings.FORGEOS_PUBLIC_CHECKOUT_ENABLED else 'OFF'}; reason={state.safe_mode_reason or 'none'}."
    if command == "/answer":
        parts = clean.split()
        if len(parts) != 4:
            return "Format: /answer ASK-REF CODE OPTION as a new, unforwarded message."
        try:
            result = answer_ask(db, ask_ref=parts[1], code=parts[2], option=parts[3], channel="telegram")
        except OwnerControlError as exc:
            if exc.reason == "owner_console_required":
                return "High-impact ASK: sign in to Hami owner console and submit the code; Telegram alone cannot approve."
            return "Decision not accepted (invalid, expired, reused or closed). No action executed."
        return f"Recorded {result['option']} for {result['ask_ref']}. No Action was executed automatically."
    if command in {"/resume", "resume", "/unhalt"}:
        return "Resume is owner-console only: request a resume ASK there and submit the code delivered to Telegram."
    return "Unknown command. Send /help. HALT is the only Telegram command that changes send-safety state."


def enqueue_owner_message(db: Session, *, key: str, body: str, kind: str) -> dict[str, Any]:
    if not control_ready():
        return {"status": "skipped", "reason": "telegram_control_not_configured"}
    from app.services import integration_dispatcher, integration_outbox
    row = integration_outbox.enqueue(db, integration_name="telegram_owner", operation="send_telegram_owner",
        idempotency_key=key, request={"chat_id": str(settings.HAMI_TELEGRAM_OWNER_CHAT_ID), "body": body, "message_type": kind})
    if row.status == "SUCCEEDED":
        return {"status": "provider_accepted", "delivery_id": row.id, "idempotent_replay": True}
    if row.status != "QUEUED" or row.attempts > 0:
        return {"status": "ambiguous_not_retried", "delivery_id": row.id}
    result = integration_dispatcher.dispatch_single_delivery(db, row.id)
    return {"status": "provider_accepted" if result.status == "SUCCEEDED" else result.status.lower(),
            "delivery_id": result.id, "delivery_claim": "Telegram API acceptance is not handset-delivery proof."}


def send_daily_owner_digest(db: Session, summary_date: date | None = None) -> dict[str, Any]:
    if not settings.HAMI_TELEGRAM_OWNER_DIGEST_ENABLED:
        return {"status": "skipped", "reason": "owner_telegram_digest_disabled"}
    if not control_ready():
        return {"status": "skipped", "reason": "telegram_control_not_configured"}
    if not durable_database(db):
        return {"status": "skipped", "reason": "durable_postgresql_required"}
    day = summary_date or datetime.now(timezone.utc).date()
    start, end = datetime(day.year, day.month, day.day), datetime(day.year, day.month, day.day) + timedelta(days=1)
    actions = db.query(models.Action).filter(models.Action.proposed_at >= start, models.Action.proposed_at < end).all()
    approvals = sum(1 for x in actions if x.policy_result == "REQUIRE_APPROVAL" or x.status == "APPROVAL_REQUIRED")
    blocked = sum(1 for x in actions if x.policy_result == "BLOCK" or x.status in {"CANCELLED", "FAILED", "BLOCKED"})
    revenues = db.query(models.Outcome).filter(models.Outcome.observed_at >= start, models.Outcome.observed_at < end,
        models.Outcome.outcome_type == "ACTUAL_REVENUE", models.Outcome.unit == "NPR", models.Outcome.actual_value.isnot(None),
        models.Outcome.actual_value > 0, models.Outcome.data_scope == "REAL", models.Outcome.source_kind == "REAL",
        models.Outcome.verification_state == "VERIFIED").all()
    from decimal import Decimal
    total = sum((Decimal(str(x.actual_value)).quantize(Decimal("0.01")) for x in revenues), Decimal("0.00"))
    failures = db.query(models.IntegrationDelivery).filter(models.IntegrationDelivery.updated_at >= start,
        models.IntegrationDelivery.updated_at < end, models.IntegrationDelivery.status == "FAILED").count()
    state = ensure_state(db)
    body = (f"Hami {day.isoformat()} UTC actions{len(actions)} approvals{approvals} blocked{blocked} REALrevNPR{total:.2f} "
        f"n{len(revenues)} fail{failures} intake{'ON' if settings.FORGE_BOT_INTAKE_ENABLED else 'OFF'} "
        f"checkout{'ON' if settings.FORGEOS_PUBLIC_CHECKOUT_ENABLED else 'OFF'} "
        f"sends{'ON' if settings.FORGE_BOT_LIVE and not state.safe_mode_enabled else 'OFF'} "
        f"safe{'ON' if state.safe_mode_enabled else 'OFF'} DB-only-not-REVENUE_LOG")
    if len(body) > 4096 or _EMAIL.search(body) or _PHONE.search(body):
        return {"status": "skipped", "reason": "telegram_digest_invalid"}
    return enqueue_owner_message(db, key=f"hami-owner-daily-telegram:{day.isoformat()}", body=body, kind="daily_digest")
