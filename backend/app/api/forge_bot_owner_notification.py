"""Forge Bot owner internal notification service.

Sends internal owner summaries only. Not customer-facing. Does NOT require
FORGE_BOT_LIVE; internal notifications are allowed for testing and review
while external customer messaging remains gated.

This service uses the existing integration_outbox/integration_dispatcher
infrastructure for durable, truthful SMTP delivery.
"""

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

    try:
        delivery = integration_outbox.enqueue(
            db,
            integration_name="smtp",
            operation="send_email",
            idempotency_key=idempotency_key,
            request={
                "to": owner_email,
                "subject": subject,
                "body": body,
            },
        )

        # Attempt immediate dispatch
        try:
            dispatched = integration_dispatcher.dispatch_single_delivery(db, delivery.id)
        except Exception:
            # Even if dispatch fails, the delivery is queued and can be
            # retried later. We don't raise here; the queued state is success.
            dispatched = db.get(models.IntegrationDelivery, delivery.id)

        return {
            "status": dispatched.status if dispatched else "QUEUED",
            "delivery_id": delivery.id,
            "recipient": owner_email,
            "message_id": (
                dispatched.response_json
                if dispatched and dispatched.response_json
                else None
            ),
            "error": dispatched.last_error if dispatched else None,
        }

    except Exception as exc:
        return {
            "status": "FAILED",
            "error": str(exc),
            "delivery_id": None,
        }


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
        "Owner approval required before any external response.",
    ]
    return "\n".join(lines)
