import socket
from datetime import date

from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.main import app
from app.api import forge_bot
from app.api import forge_bot_owner_notification
from app.services import integration_dispatcher


def _client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), lambda: app.dependency_overrides.clear()


def _payload(**changes):
    values = {
        "email": "lead-one@example.test",
        "phone": "+1 (202) 555-0100",
        "preferred_channel": "email",
        "destination": "Japan",
        "course": "Agriculture",
        "timeline": "Next year",
        "budget_minimum": 100000,
        "budget_maximum": 250000,
        "consent_granted": True,
    }
    return {**values, **changes}


def _enable_intake(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_BOT_INTAKE_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "FORGE_BOT_CONTACT_HMAC_KEY",
        "test-only-hmac-key-that-is-long-enough-for-tests",
    )
    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-only-owner-key")


def test_intake_is_disabled_without_explicit_enablement_and_suppression_key(db, monkeypatch):
    monkeypatch.setattr(settings, "FORGE_BOT_INTAKE_ENABLED", False)
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-hmac-key")
    client, cleanup = _client(db)
    try:
        response = client.post("/forge-bot/leads", json=_payload())
    finally:
        client.close()
        cleanup()

    assert response.status_code == 503
    assert db.query(models.ForgeBotLeadContact).count() == 0

    monkeypatch.setattr(settings, "FORGE_BOT_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "")
    assert forge_bot._enabled() is False


def test_public_config_exposes_booking_without_publishing_owner_email(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        response = client.get("/forge-bot/config")
    finally:
        client.close()
        cleanup()

    assert response.status_code == 200
    assert response.json() == {
        "intake_enabled": True,
        "booking_url": "https://cal.com/hami-forge-m9agd6/build-hami",
        "consent_version": "forge_bot_web_form_v1",
    }
    assert "contact_email" not in response.json()


def test_explicit_consent_and_channel_contact_are_server_enforced(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        no_consent = client.post("/forge-bot/leads", json=_payload(consent_granted=False))
        missing_email = client.post(
            "/forge-bot/leads",
            json=_payload(email=None, preferred_channel="email"),
        )
        invalid_budget = client.post(
            "/forge-bot/leads",
            json=_payload(budget_minimum=300000, budget_maximum=250000),
        )
    finally:
        client.close()
        cleanup()

    assert no_consent.status_code == 422
    assert missing_email.status_code == 422
    assert invalid_budget.status_code == 422
    assert db.query(models.ForgeBotLeadContact).count() == 0


def test_live_off_rejects_real_leads_but_allows_test_records(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", False)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        real_lead = client.post(
            "/forge-bot/leads",
            json=_payload(
                email="owner@example.com",
                phone="+977 9800000012",
            ),
        )
        test_lead = client.post("/forge-bot/leads", json=_payload())
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    assert real_lead.status_code == 403
    assert test_lead.status_code == 202
    assert db.query(models.ForgeBotLeadContact).count() == 1
    assert db.query(models.ForgeBotLeadContact).one().evidence_class == "TEST"


def test_submitted_lead_is_private_consent_scoped_and_not_projected_publicly(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        response = client.post("/forge-bot/leads", json=_payload())
        public = client.get("/public/feed")
    finally:
        client.close()
        cleanup()

    assert response.status_code == 202
    assert response.json()["status"] == "received"
    assert "email" not in response.json()
    assert "lead-one@example.test" not in response.text
    lead = db.query(models.ForgeBotLeadContact).one()
    assert lead.email == "lead-one@example.test"
    assert lead.consent_granted is True
    assert lead.consent_purpose == "respond_to_forge_bot_inquiry"
    assert lead.consent_provenance == "forge_bot_web_form_v1"
    assert lead.stage == "READY_FOR_OWNER_REVIEW"
    assert lead.evidence_class == "TEST"
    assert db.query(models.Signal).count() == 0
    assert db.query(models.SubstrateEntity).count() == 0
    assert response.json()["reference"] == lead.public_ref
    assert public.status_code == 200
    assert "lead-one@example.test" not in public.text
    assert "Agriculture" not in public.text


def test_test_lead_flow_is_offline_with_legacy_intelligence_disabled(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", False)
    monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_USER", "owner@example.test")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "test-only-password")
    forge_bot._submissions_by_ip.clear()
    sent = []

    def reject_socket(*args, **kwargs):
        raise AssertionError("The TEST lead flow attempted an outbound network connection.")

    def mock_email_sender(to_email, subject, body):
        sent.append((to_email, subject, body))
        return {"status": "ACCEPTED_BY_MOCK", "message_id": "test-message"}

    monkeypatch.setattr(socket, "create_connection", reject_socket)
    monkeypatch.setattr(socket.socket, "connect", reject_socket)
    monkeypatch.setattr(integration_dispatcher, "_send_smtp_email", mock_email_sender)
    client, cleanup = _client(db)
    try:
        config = client.get("/forge-bot/config")
        receipt_response = client.post("/forge-bot/leads", json=_payload())
        owner_summary = client.get(
            "/forge-bot/leads/summary",
            headers={"X-API-Key": "test-only-owner-key"},
        )
        email_result = forge_bot_owner_notification.send_daily_owner_summary_notification(
            db, date(2026, 10, 2)
        )
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    lead = db.query(models.ForgeBotLeadContact).one()
    assert config.status_code == 200
    assert config.json()["booking_url"] == "https://cal.com/hami-forge-m9agd6/build-hami"
    assert receipt_response.status_code == 202
    assert receipt_response.json()["status"] == "received"
    assert "No automated reply or booking was sent" in receipt_response.json()["message"]
    assert owner_summary.status_code == 200
    assert owner_summary.json()[0]["evidence_class"] == "TEST"
    assert owner_summary.json()[0]["stage"] == "READY_FOR_OWNER_REVIEW"
    assert lead.destination == "Japan"
    assert lead.course == "Agriculture"
    assert lead.timeline == "Next year"
    assert lead.consent_provenance == "forge_bot_web_form_v1"
    assert lead.consent_at is not None
    assert email_result["status"] == "ACCEPTED_BY_SMTP"
    assert len(sent) == 1
    assert "Booking link available: https://cal.com/hami-forge-m9agd6/build-hami" in sent[0][2]
    assert "TEST" in sent[0][2]
    assert "BOOKED" not in sent[0][2]


def test_duplicates_by_either_contact_are_deduplicated_without_existence_leak(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        first = client.post("/forge-bot/leads", json=_payload())
        duplicate_email = client.post(
            "/forge-bot/leads",
            json=_payload(
                email=" LEAD-ONE@EXAMPLE.TEST ",
                phone="+1 (202) 555-0199",
            ),
        )
        duplicate_phone = client.post(
            "/forge-bot/leads",
            json=_payload(
                email="different@example.test",
                phone="12025550100",
            ),
        )
    finally:
        client.close()
        cleanup()

    assert first.status_code == duplicate_email.status_code == duplicate_phone.status_code == 202
    assert first.json()["status"] == duplicate_email.json()["status"] == "received"
    assert first.json()["reference"] != duplicate_email.json()["reference"]
    assert first.json()["manage_token"] != duplicate_email.json()["manage_token"]
    assert db.query(models.ForgeBotLeadContact).count() == 1


def test_honeypot_is_acknowledged_without_storing_contact_data(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        response = client.post("/forge-bot/leads", json=_payload(website="spam.example.test"))
    finally:
        client.close()
        cleanup()

    assert response.status_code == 202
    assert db.query(models.ForgeBotLeadContact).count() == 0


def test_rate_limiter_returns_429_without_storing_the_over_limit_request(db, monkeypatch):
    _enable_intake(monkeypatch)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        responses = [
            client.post(
                "/forge-bot/leads",
                json=_payload(
                    email=f"lead-{index}@example.test",
                    phone=f"120255501{index:02d}",
                ),
            )
            for index in range(forge_bot.RATE_LIMIT + 1)
        ]
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    assert [response.status_code for response in responses[:-1]] == [202] * forge_bot.RATE_LIMIT
    assert responses[-1].status_code == 429
    assert db.query(models.ForgeBotLeadContact).count() == forge_bot.RATE_LIMIT


def test_opt_out_erases_contact_and_answers_and_permanently_suppresses_resubmission(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        first = client.post("/forge-bot/leads", json=_payload())
        opt_out = client.post(
            "/forge-bot/leads/opt-out",
            json={"manage_token": first.json()["manage_token"]},
        )
        rejected_reentry = client.post("/forge-bot/leads", json=_payload())
        repeat_opt_out = client.post(
            "/forge-bot/leads/opt-out",
            json={"manage_token": first.json()["manage_token"]},
        )
    finally:
        client.close()
        cleanup()

    assert opt_out.status_code == 202
    assert rejected_reentry.status_code == 202
    assert repeat_opt_out.status_code == 404
    lead = db.query(models.ForgeBotLeadContact).one()
    assert lead.opted_out is True
    assert lead.opted_out_at is not None
    assert lead.erased_at is not None
    assert lead.email is None and lead.phone is None
    assert lead.destination is None and lead.course is None
    assert lead.email_suppression_hmac is not None


def test_control_token_deletion_removes_record_and_is_single_use(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        first = client.post("/forge-bot/leads", json=_payload())
        token = first.json()["manage_token"]
        deleted = client.post("/forge-bot/leads/delete", json={"manage_token": token})
        repeated = client.post("/forge-bot/leads/delete", json={"manage_token": token})
    finally:
        client.close()
        cleanup()

    assert deleted.status_code == 204
    assert repeated.status_code == 404
    assert db.query(models.ForgeBotLeadContact).count() == 0


def test_owner_summary_requires_configured_header_api_key(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        monkeypatch.setattr(settings, "FORGE_API_KEY", "")
        no_key_config = client.get("/forge-bot/leads/summary")
        monkeypatch.setattr(settings, "FORGE_API_KEY", "owner-test-key")
        no_key = client.get("/forge-bot/leads/summary")
        query_key = client.get("/forge-bot/leads/summary?api_key=owner-test-key")
        with_key = client.get(
            "/forge-bot/leads/summary",
            headers={"X-API-Key": "owner-test-key"},
        )
    finally:
        client.close()
        cleanup()

    assert no_key_config.status_code == 503
    assert no_key.status_code == 401
    assert query_key.status_code == 401
    assert with_key.status_code == 200
    assert with_key.json() == []
