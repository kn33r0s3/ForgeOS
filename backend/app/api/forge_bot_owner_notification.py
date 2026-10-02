"""Forge Bot owner internal notification service.

Sends internal owner summaries only. Not customer-facing. Does NOT require
FORGE_BOT_LIVE; internal notifications are allowed for testing and review
while external customer messaging remains gated.

This service uses the existing integration_outbox/integration_dispatcher
infrastructure for durable, truthful SMTP delivery.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import integration_outbox, integration_dispatcher


def send_owner_summary_notification(
    db: Session,
    lead_reference: str,
    lead_data: dict,
    idempotency_key: str,
) -> Optional[dict]:
    """Queue an internal owner notification for a Forge Bot lead.

    Args:
        db: Database session
        lead_reference: Lead public reference (e.g., "FB-ABC123")
        lead_data: Dictionary of lead fields to include in summary
        idempotency_key: Unique key to prevent duplicate notifications

    Returns:
        Dictionary with notification status if attempted, None if SMTP
        not configured (capability gap, not an error).

    The notification is queued durably but requires SMTP configuration
    to actually send. Absence of SMTP credentials fails closed and is
    reported as a missing capability.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        # SMTP not configured. This is a capability gap, not an error.
        return None

    owner_email = settings.FORGE_BOT_CONTACT_EMAIL
    if not owner_email or "@" not in owner_email:
        return None

    subject = f"Forge Bot lead: {lead_reference}"
    body = _format_owner_notification_body(lead_reference, lead_data)

    return _queue_owner_email(
        db,
        recipient=owner_email,
        subject=subject,
        body=body,
        idempotency_key=idempotency_key,
    )


def send_daily_owner_summary_notification(
    db: Session,
    summary_date_utc: date | None = None,
) -> Optional[dict]:
    """Queue one privacy-minimized daily status digest for the owner."""
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        return None

    owner_email = settings.FORGE_BOT_CONTACT_EMAIL
    if not owner_email or "@" not in owner_email:
        return None

    day = summary_date_utc or datetime.now(timezone.utc).date()
    leads = (
        db.query(models.ForgeBotLeadContact)
        .filter(
            models.ForgeBotLeadContact.opted_out.is_(False),
            models.ForgeBotLeadContact.erased_at.is_(None),
        )
        .order_by(models.ForgeBotLeadContact.created_at.desc())
        .limit(100)
        .all()
    )
    return _queue_owner_email(
        db,
        recipient=owner_email,
        subject=f"Forge Bot daily lead status - {day.isoformat()} UTC",
        body=_format_daily_owner_summary_body(day, leads),
        idempotency_key=f"forge-bot-daily-owner-summary:{day.isoformat()}",
    )


def _queue_owner_email(
    db: Session,
    *,
    recipient: str,
    subject: str,
    body: str,
    idempotency_key: str,
) -> dict:
    try:
        delivery = integration_outbox.enqueue(
            db,
            integration_name="smtp",
            operation="send_email",
            idempotency_key=idempotency_key,
            request={"to": recipient, "subject": subject, "body": body},
        )
        if delivery.status in {"ACCEPTED_BY_SMTP", "SUCCEEDED", "FAILED"}:
            dispatched = delivery
        else:
            try:
                dispatched = integration_dispatcher.dispatch_single_delivery(
                    db, delivery.id
                )
            except Exception:
                dispatched = db.get(models.IntegrationDelivery, delivery.id)
                if dispatched is None:
                    raise

        return {
            "status": dispatched.status,
            "delivery_id": delivery.id,
            "recipient": recipient,
            "message_id": dispatched.response_json,
            "error": dispatched.last_error,
        }
    except Exception as exc:
        return {"status": "FAILED", "error": str(exc), "delivery_id": None}


def _format_owner_notification_body(reference: str, lead_data: dict) -> str:
    """Format a plaintext owner notification body.

    Includes all lead fields in a readable format. No HTML, no links,
    no customer-to-owner integration triggers.
    """
    lines = [
        "Forge Bot Lead Summary",
        "=" * 60,
        f"Reference: {reference}",
        f"Evidence Class: {lead_data.get('evidence_class', 'UNKNOWN')}",
        f"Stage: {lead_data.get('stage', 'UNKNOWN')}",
        "",
        "Contact Information",
        "-" * 60,
        f"Preferred Channel: {lead_data.get('preferred_channel', 'N/A')}",
        f"Email: {lead_data.get('email', '(not provided)')}",
        f"Phone: {lead_data.get('phone', '(not provided)')}",
        "",
        "Qualification",
        "-" * 60,
        f"Destination: {lead_data.get('destination', 'N/A')}",
        f"Course/Service: {lead_data.get('course', 'N/A')}",
        f"Timeline: {lead_data.get('timeline', 'N/A')}",
        f"Budget Range: {lead_data.get('budget_minimum', 0)} - {lead_data.get('budget_maximum', 0)}",
        "",
        "Consent & Provenance",
        "-" * 60,
        f"Consent Granted: {lead_data.get('consent_granted', False)}",
        f"Consent At: {lead_data.get('consent_at', 'N/A')}",
        f"Purpose: {lead_data.get('consent_purpose', 'N/A')}",
        f"Provenance: {lead_data.get('consent_provenance', 'N/A')}",
        "",
        "Next Steps",
        "-" * 60,
        "Review in Forge Bot owner summary endpoint.",
        "No automated action, booking, or outreach has been sent.",
        f"Booking link available: {settings.FORGE_BOT_BOOKING_URL}",
        "Owner approval required before any external response.",
    ]
    return "\n".join(lines)


def _format_daily_owner_summary_body(summary_date_utc: date, leads: list) -> str:
    lines = [
        "Forge Bot daily lead status",
        f"Date (UTC): {summary_date_utc.isoformat()}",
        f"Active inquiries shown: {len(leads)}",
        "",
        "Reference | Evidence | Stage | Created (UTC)",
        "-" * 76,
    ]
    if leads:
        lines.extend(
            f"{lead.public_ref} | {lead.evidence_class} | {lead.stage} | "
            f"{lead.created_at.isoformat()}"
            for lead in leads
        )
    else:
        lines.append("No active inquiries are on record.")
    lines.extend(
        [
            "",
            "No customer reply, booking, or external contact was sent.",
            f"Booking link available: {settings.FORGE_BOT_BOOKING_URL}",
            "Use the authenticated Forge Bot owner summary for contact details.",
        ]
    )
    return "\n".join(lines)
