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
import smtplib
import socket
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import integration_outbox

logger = logging.getLogger(__name__)


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
        if 400 <= e.code < 500:
            raise PermanentIntegrationError(f"HTTP {e.code}: {err_body}")
        raise TransientIntegrationError(f"HTTP {e.code}: {err_body}")
    except (TimeoutError, socket.error, OSError) as e:
        raise TransientIntegrationError(str(e))
    except Exception as e:
        if isinstance(e, (PermanentIntegrationError, TransientIntegrationError)):
            raise
        raise TransientIntegrationError(str(e))


def _send_smtp_email(to_email: str, subject: str, body: str) -> dict[str, Any]:
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
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS)
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


def dispatch_single_delivery(db: Session, delivery_id: int) -> models.IntegrationDelivery:
    """Process a single integration delivery by ID and return updated record."""
    delivery = db.get(models.IntegrationDelivery, delivery_id)
    if not delivery:
        raise ValueError(f"Integration delivery {delivery_id} not found")

    logger.info(f"Dispatching delivery {delivery.id} ({delivery.integration_name}/{delivery.operation})")
    try:
        if delivery.integration_name == "twilio" and delivery.operation == "send_sms":
            req_data = json.loads(delivery.request_json)
            to_number = req_data.get("to")
            body = req_data.get("body")
            if not to_number or not body:
                raise PermanentIntegrationError("Missing 'to' or 'body' in request payload")
            resp = _send_twilio_sms(to_number, body)
            delivery = integration_outbox.mark_succeeded(db, delivery.id, resp, status="SUCCEEDED")
            logger.info(f"Delivery {delivery.id} succeeded. Provider ID: {resp.get('sid')}")

        elif delivery.integration_name == "smtp" and delivery.operation == "send_email":
            req_data = json.loads(delivery.request_json)
            to_email = req_data.get("to") or req_data.get("recipient")
            subject = req_data.get("subject", "")
            body = req_data.get("body", "")
            if not to_email or not body:
                raise PermanentIntegrationError("Missing 'to' or 'body' in email request payload")
            resp = _send_smtp_email(to_email, subject, body)
            # Explicit truthful state: ACCEPTED_BY_SMTP, never claimed as DELIVERED
            delivery = integration_outbox.mark_succeeded(db, delivery.id, resp, status="ACCEPTED_BY_SMTP")
            logger.info(f"Delivery {delivery.id} accepted by SMTP. Message-ID: {resp.get('message_id')}")

        else:
            raise PermanentIntegrationError(f"Unsupported integration: {delivery.integration_name}/{delivery.operation}")

    except PermanentIntegrationError as exc:
        err_msg = str(exc)
        logger.error(f"Delivery {delivery.id} permanent failure: {err_msg}")
        delivery = integration_outbox.mark_failed(db, delivery.id, err_msg, permanent=True)
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Delivery {delivery.id} transient failure: {err_msg}")
        delivery = integration_outbox.mark_failed(db, delivery.id, err_msg, permanent=False)

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
