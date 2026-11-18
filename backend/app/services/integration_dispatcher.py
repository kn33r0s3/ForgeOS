"""Outbound integration dispatcher for durable queue delivery.

Reads queued IntegrationDelivery rows and dispatches them to real external providers.
Never fabricates success; relies strictly on real provider responses.
Supports real standard-library SMTP over TLS and Twilio SMS.
"""

from __future__ import annotations

import base64
import email.message
import email.utils
import json
import logging
import re
import smtplib
import socket
import urllib.parse
import urllib.request
import urllib.error
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import forge_bot_response, integration_outbox, owner_control, telegram_transport
from app.services.execution_boundary import Action as BoundaryAction
from app.services.execution_boundary import ExecutionResult, Operation, Outcome, Refusal, RefusalReason

logger = logging.getLogger(__name__)
_SMTP_TIMEOUT_OVERRIDE: ContextVar[int | None] = ContextVar("smtp_timeout_override", default=None)


class PermanentIntegrationError(RuntimeError):
    """Non-retryable error (e.g. auth failed, recipient rejected, missing credentials)."""
    pass


class TransientIntegrationError(RuntimeError):
    """Retryable error (e.g. network timeout, temporary server busy)."""
    pass


def _send_twilio_sms(to_number: str, body: str) -> dict[str, Any]:
    """Make a real HTTP request to Twilio API.
    
    Returns parsed JSON on success containing a 'sid'.
    Raises RuntimeError on missing credentials, network errors, or API errors.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_FROM_NUMBER:
        raise PermanentIntegrationError("Twilio credentials are not configured")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    
    data = urllib.parse.urlencode({
        "To": to_number,
        "From": settings.TWILIO_FROM_NUMBER,
        "Body": body
    }).encode("utf-8")

    auth_str = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
    auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {auth_b64}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_body = response.read().decode("utf-8")
            resp_data = json.loads(resp_body)
            if "sid" not in resp_data:
                raise PermanentIntegrationError("Provider response missing message SID")
            return resp_data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        if e.code == 429:
            # Rate limited: retryable, never a permanent failure.
            raise TransientIntegrationError(f"HTTP 429 (rate limited): {err_body}")
        if 400 <= e.code < 500:
            raise PermanentIntegrationError(f"HTTP {e.code}: {err_body}")
        raise TransientIntegrationError(f"HTTP {e.code}: {err_body}")
    except (TimeoutError, socket.error, OSError) as e:
        raise TransientIntegrationError(str(e))
    except Exception as e:
        if isinstance(e, (PermanentIntegrationError, TransientIntegrationError)):
            raise
        raise TransientIntegrationError(str(e))


def _send_smtp_email(
    to_email: str,
    subject: str,
    body: str,
    *,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Send a real outbound email via standard-library SMTP over TLS/STARTTLS.
    
    Returns parsed metadata on SMTP acceptance containing message_id and status.
    Fails closed if credentials are unset or invalid. Never logs credentials.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise PermanentIntegrationError("SMTP credentials are not configured")

    if not to_email or "@" not in to_email:
        raise PermanentIntegrationError(f"Invalid recipient email: {to_email}")

    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER

    domain = None
    if "." in settings.SMTP_HOST:
        domain = ".".join(settings.SMTP_HOST.split(".")[-2:])
    msg_id = email.utils.make_msgid(domain=domain)

    msg = email.message.EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Message-ID"] = msg_id
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.set_content(body)

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=timeout_seconds or settings.SMTP_TIMEOUT_SECONDS,
            )
        else:
            server = smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=timeout_seconds or settings.SMTP_TIMEOUT_SECONDS,
            )
            if settings.SMTP_USE_TLS:
                server.ehlo()
                server.starttls()
                server.ehlo()

        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        refused = server.send_message(msg)
        server.quit()

        if refused:
            raise PermanentIntegrationError(f"Recipient refused by SMTP server: {refused}")

        return {
            "message_id": msg_id,
            "recipient": to_email,
            "status": "ACCEPTED_BY_SMTP",
            "smtp_host": settings.SMTP_HOST,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except smtplib.SMTPAuthenticationError as e:
        raise PermanentIntegrationError(f"SMTP authentication failed (code {e.smtp_code}): {e.smtp_error}") from e
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused) as e:
        raise PermanentIntegrationError(f"SMTP address refused: {e}") from e
    except smtplib.SMTPResponseException as e:
        if 500 <= e.smtp_code < 600:
            raise PermanentIntegrationError(f"SMTP permanent rejection (code {e.smtp_code}): {e.smtp_error}") from e
        raise TransientIntegrationError(f"SMTP temporary error (code {e.smtp_code}): {e.smtp_error}") from e
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, socket.error, OSError) as e:
        raise TransientIntegrationError(f"SMTP connection error: {e}") from e
    except Exception as e:
        if isinstance(e, (PermanentIntegrationError, TransientIntegrationError)):
            raise
        raise TransientIntegrationError(f"Unexpected SMTP failure: {e}") from e


_SEND_OPERATIONS = {
    Operation.SEND_EMAIL: {("smtp", "send_email")},
    Operation.SEND_SMS: {
        ("twilio", "send_sms"),
        ("twilio_owner", "send_owner_sms"),
    },
    Operation.SEND_TELEGRAM: {("telegram_owner", "send_telegram_owner")},
}


def _send_operation(integration_name: str, operation: str) -> Operation | None:
    identity = (integration_name, operation)
    return next(
        (gate_operation for gate_operation, identities in _SEND_OPERATIONS.items() if identity in identities),
        None,
    )


def execute_gated_delivery(db: Session, action: BoundaryAction) -> dict[str, Any]:
    """Validate and send one outbox row as the decision-gate adapter."""
    payload = action.payload or {}
    delivery_id = payload.get("delivery_id")
    if set(payload) != {"delivery_id"} or type(delivery_id) is not int or delivery_id < 1:
        return {"error": "send operation requires one positive delivery_id", "permanent": True}
    delivery = db.get(models.IntegrationDelivery, delivery_id)
    if delivery is None:
        return {"error": "integration delivery not found", "permanent": True}
    if _send_operation(delivery.integration_name, delivery.operation) != action.operation:
        return {"error": "delivery does not match the registered send operation", "permanent": True}
    if delivery.status != "QUEUED":
        return {"error": "delivery is not queued; prior outcome is ambiguous or terminal", "permanent": True}

    try:
        request_data = json.loads(delivery.request_json)
    except (TypeError, ValueError):
        return {"error": "integration request is not valid JSON", "permanent": True}
    if not isinstance(request_data, dict):
        return {"error": "integration request must be an object", "permanent": True}
    try:
        marked_decision = forge_bot_response.decision_for_marked_delivery(db, request_data)
        forge_bot_response.enforce_delivery_boundary(
            db,
            integration_name=delivery.integration_name,
            operation=delivery.operation,
            request=request_data,
            action_decision=marked_decision,
        )
    except forge_bot_response.ForgeBotResponseBlocked as exc:
        return {"error": str(exc), "permanent": True}

    if (delivery.integration_name, delivery.operation) in {("twilio", "send_sms"), ("smtp", "send_email")}:
        block_reason = owner_control.block_customer_delivery(
            db,
            integration_name=delivery.integration_name,
            operation=delivery.operation,
            request_data=request_data,
        )
        if block_reason:
            return {"error": f"customer delivery blocked: {block_reason}", "permanent": True}

    if delivery.integration_name == "twilio_owner":
        owner_number = (settings.HAMI_OWNER_SMS_NUMBER or "").strip()
        body = request_data.get("body")
        if delivery.attempts > 0:
            return {"error": "owner SMS will not be retried after an ambiguous attempt", "permanent": True}
        if not settings.HAMI_OWNER_SMS_DIGEST_ENABLED:
            return {"error": "owner SMS digest is disabled", "permanent": True}
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", owner_number):
            return {"error": "owner SMS destination is missing or invalid", "permanent": True}
        if (
            set(request_data) != {"to", "body", "message_type"}
            or request_data.get("message_type") != "daily_digest"
            or not isinstance(body, str)
            or not body.isascii()
            or not body.strip()
            or len(body) > 160
        ):
            return {"error": "owner SMS request failed destination or content validation", "permanent": True}
        if request_data.get("to") != owner_number:
            return {"error": "owner SMS recipient does not match the configured owner number", "permanent": True}
    elif delivery.integration_name == "twilio":
        to_number, body = request_data.get("to"), request_data.get("body")
        if not isinstance(to_number, str) or not to_number or not isinstance(body, str) or not body:
            return {"error": "SMS request requires a recipient and body", "permanent": True}
    elif delivery.integration_name == "smtp":
        to_email = request_data.get("to") or request_data.get("recipient")
        body = request_data.get("body", "")
        if not isinstance(to_email, str) or not to_email or not isinstance(body, str) or not body:
            return {"error": "email request requires a recipient and body", "permanent": True}
    elif delivery.integration_name == "telegram_owner":
        if delivery.attempts > 0:
            return {"error": "Telegram owner delivery will not be retried after an ambiguous attempt", "permanent": True}
        if not owner_control.valid_owner_delivery(delivery.integration_name, delivery.operation, request_data):
            return {"error": "Telegram owner delivery failed destination/configuration validation", "permanent": True}
        if request_data.get("message_type") == "daily_digest" and not settings.HAMI_TELEGRAM_OWNER_DIGEST_ENABLED:
            return {"error": "Telegram owner digest is disabled", "permanent": True}

    delivery.status = "SENDING"
    delivery.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(delivery)
    except Exception as exc:
        db.rollback()
        return {"error": f"delivery could not be marked SENDING: {type(exc).__name__}", "permanent": False}

    try:
        if action.operation == Operation.SEND_EMAIL:
            recipient = request_data.get("to") or request_data.get("recipient")
            response = _send_smtp_email(
                recipient,
                request_data.get("subject", ""),
                request_data.get("body", ""),
                timeout_seconds=_SMTP_TIMEOUT_OVERRIDE.get(),
            )
        elif action.operation == Operation.SEND_SMS:
            recipient = settings.HAMI_OWNER_SMS_NUMBER if delivery.integration_name == "twilio_owner" else request_data.get("to")
            response = _send_twilio_sms(recipient, request_data["body"])
        else:
            response = telegram_transport.send_owner_message(
                request_data["body"],
                message_type=request_data["message_type"],
            )
    except PermanentIntegrationError as exc:
        return {"error": str(exc), "permanent": True}
    except TransientIntegrationError as exc:
        return {
            "error": str(exc),
            "permanent": action.operation == Operation.SEND_TELEGRAM,
        }
    except Exception as exc:
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "permanent": action.operation == Operation.SEND_TELEGRAM,
        }

    if action.operation == Operation.SEND_EMAIL:
        accepted = response.get("status") == "ACCEPTED_BY_SMTP" and bool(response.get("message_id"))
    elif action.operation == Operation.SEND_SMS:
        accepted = bool(response.get("sid"))
    else:
        accepted = response.get("accepted") is True and type(response.get("message_id")) is int
    if not accepted:
        return {"error": "provider response did not prove acceptance", "permanent": True}

    if action.operation == Operation.SEND_EMAIL:
        receipt = {"message_id": response["message_id"], "status": "ACCEPTED_BY_SMTP"}
    elif action.operation == Operation.SEND_SMS:
        receipt = {"sid": response["sid"], "status": response.get("status")}
    else:
        receipt = {"message_id": response["message_id"], "accepted": True}
    delivery.response_json = json.dumps(receipt, sort_keys=True, default=str)
    delivery.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(delivery)
    except Exception as exc:
        db.rollback()
        return {"error": f"provider response could not be persisted: {type(exc).__name__}", "permanent": True}
    return {"delivery_id": delivery.id, "provider_response": receipt}


def dispatch_single_delivery(
    db: Session,
    delivery_id: int,
    *,
    smtp_timeout_seconds: int | None = None,
) -> models.IntegrationDelivery:
    """Process a single integration delivery through the decision service."""
    delivery = db.get(models.IntegrationDelivery, delivery_id)
    if not delivery:
        raise ValueError(f"Integration delivery {delivery_id} not found")
    if delivery.status in {"SUCCEEDED", "ACCEPTED_BY_SMTP", "FAILED"}:
        return delivery

    logger.info("Dispatching delivery %s (%s/%s)", delivery.id, delivery.integration_name, delivery.operation)
    operation = _send_operation(delivery.integration_name, delivery.operation)
    if operation is None:
        return integration_outbox.mark_failed(
            db,
            delivery.id,
            f"Unsupported integration: {delivery.integration_name}/{delivery.operation}",
            permanent=True,
        )

    from app.services.execution_engine import execute_through_gate

    timeout_token = _SMTP_TIMEOUT_OVERRIDE.set(smtp_timeout_seconds)
    try:
        try:
            result = execute_through_gate(
                db,
                BoundaryAction(
                    operation=operation,
                    principal="integration_dispatcher",
                    scope=delivery.integration_name,
                    payload={"delivery_id": delivery.id},
                ),
            )
        except Exception as exc:
            db.rollback()
            logger.exception("Decision service failed for delivery %s", delivery.id)
            return integration_outbox.mark_failed(
                db,
                delivery.id,
                f"Decision service failed: {type(exc).__name__}",
                permanent=False,
            )
    finally:
        _SMTP_TIMEOUT_OVERRIDE.reset(timeout_token)
    if isinstance(result, Refusal):
        if result.reason == RefusalReason.ALREADY_IN_PROGRESS:
            return delivery
        return integration_outbox.mark_failed(
            db,
            delivery.id,
            f"Decision service refused {operation.value}: {result.reason.value}",
            permanent=True,
        )
    if not isinstance(result, ExecutionResult):
        return integration_outbox.mark_failed(db, delivery.id, "Decision service returned an invalid result", permanent=True)
    if result.outcome != Outcome.VERIFIED:
        result_data = result.result or {}
        error = result_data.get("error") or f"Decision service did not verify {operation.value}"
        permanent = bool(result_data.get("permanent")) or result.replayed or "provider_response" in result_data
        return integration_outbox.mark_failed(db, delivery.id, str(error), permanent=permanent)

    response = (result.result or {}).get("provider_response")
    if not isinstance(response, dict):
        return integration_outbox.mark_failed(db, delivery.id, "Verified send had no provider response", permanent=True)
    status = "ACCEPTED_BY_SMTP" if operation == Operation.SEND_EMAIL else "SUCCEEDED"
    try:
        delivery = integration_outbox.mark_succeeded(db, delivery.id, response, status=status)
    except Exception:
        db.rollback()
        logger.exception("Could not finalize gated delivery %s; the gate result remains replayable", delivery.id)
        delivery = db.get(models.IntegrationDelivery, delivery_id)
    logger.info("Provider accepted gated delivery %s", delivery_id)
    return delivery


def dispatch_pending_deliveries(db: Session, limit: int = 10) -> int:
    """Process pending integration deliveries from the outbox.
    
    Returns the number of deliveries attempted.
    """
    pending = integration_outbox.pending(db, limit=limit)
    attempted = 0
    for delivery in pending:
        attempted += 1
        dispatch_single_delivery(db, delivery.id)
    return attempted
