import json
from datetime import date

from app import models
from app.api import forge_bot_owner_notification
from app.config import settings


def test_daily_owner_summary_is_idempotent_and_omits_contact_data(db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "sender@example.test")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "test-only-password")
    lead = models.ForgeBotLeadContact(
        public_ref="FB-TESTSUMMARY",
        email="private-lead@example.test",
        normalized_email="private-lead@example.test",
        phone="+12025550123",
        normalized_phone="12025550123",
        preferred_channel="email",
        destination="Japan",
        course="Agriculture",
        timeline="Next year",
        budget_minimum=100,
        budget_maximum=200,
        stage="READY_FOR_OWNER_REVIEW",
        evidence_class="TEST",
        consent_granted=True,
    )
    db.add(lead)
    db.commit()
    dispatches = []

    def accept_by_smtp(session, delivery_id):
        delivery = session.get(models.IntegrationDelivery, delivery_id)
        delivery.status = "ACCEPTED_BY_SMTP"
        delivery.response_json = '{"status":"accepted"}'
        session.commit()
        dispatches.append(delivery_id)
        return delivery

    monkeypatch.setattr(
        forge_bot_owner_notification.integration_dispatcher,
        "dispatch_single_delivery",
        accept_by_smtp,
    )
    summary_date = date(2026, 10, 2)

    first = forge_bot_owner_notification.send_daily_owner_summary_notification(
        db, summary_date
    )
    second = forge_bot_owner_notification.send_daily_owner_summary_notification(
        db, summary_date
    )

    delivery = db.query(models.IntegrationDelivery).one()
    request = json.loads(delivery.request_json)
    assert first["status"] == second["status"] == "ACCEPTED_BY_SMTP"
    assert len(dispatches) == 1
    assert delivery.idempotency_key == "forge-bot-daily-owner-summary:2026-10-02"
    assert request["to"] == settings.FORGE_BOT_CONTACT_EMAIL
    assert "FB-TESTSUMMARY" in request["body"]
    assert "TEST" in request["body"]
    assert "READY_FOR_OWNER_REVIEW" in request["body"]
    assert "Booking link available: https://cal.com/hami-forge-m9agd6/build-hami" in request["body"]
    assert "BOOKED" not in request["body"]
    assert "private-lead@example.test" not in request["body"]
    assert "+12025550123" not in request["body"]
    assert "No customer reply, booking, or external contact was sent." in request["body"]


def test_daily_owner_summary_skips_without_smtp_credentials(db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    result = forge_bot_owner_notification.send_daily_owner_summary_notification(
        db, date(2026, 10, 2)
    )

    assert result is None
    assert db.query(models.IntegrationDelivery).count() == 0
