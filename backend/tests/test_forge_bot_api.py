import json
import socket
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.main import app
from app.api import forge_bot, forge_bot_owner_notification
from app.services import integration_dispatcher


def _client(db, *, raise_server_exceptions=True):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return (
        TestClient(app, raise_server_exceptions=raise_server_exceptions),
        lambda: app.dependency_overrides.clear(),
    )


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


def _response_authorization_payload(**changes):
    values = {
        "selected_channel": "email",
        "channel_authorized": True,
        "template_ref": "forge-bot.response.inquiry.v1",
        "template_authorized": True,
        "consent_required": True,
        "opt_out_boundary": "permanent_suppression",
        "escalation_boundary": "owner_confirmation_required_for_exceptions",
        "external_send_authorized": False,
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


def test_response_authorization_is_owner_only_and_defaults_closed(db, monkeypatch):
    _enable_intake(monkeypatch)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        lead_response = client.post("/forge-bot/leads", json=_payload())
        reference = lead_response.json()["reference"]
        no_key = client.get("/forge-bot/response-authorization")
        state = client.get(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
        )
        readiness = client.get(
            f"/forge-bot/leads/{reference}/response-readiness",
            headers={"X-API-Key": "test-only-owner-key"},
        )
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    assert lead_response.status_code == 202
    assert no_key.status_code == 401
    assert state.status_code == readiness.status_code == 200
    assert state.json()["configured"] is False
    assert state.json()["selected_channel"] is None
    assert state.json()["channel_authorized"] is False
    assert state.json()["template_ref"] is None
    assert state.json()["external_send_authorized"] is False
    assert readiness.json()["status"] == "BLOCKED"
    assert "owner_authorization_missing" in readiness.json()["blocking_reasons"]
    assert "selected_channel_missing" in readiness.json()["blocking_reasons"]
    assert readiness.json()["observed_submitter_preference"] == "email"
    assert readiness.json()["owner_authorized_response_channel"] is None
    assert readiness.json()["external_send_enabled"] is False
    assert db.query(models.IntegrationDelivery).count() == 0


def test_response_readiness_blocks_unselected_or_unauthorized_channel(db, monkeypatch):
    _enable_intake(monkeypatch)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        lead = client.post("/forge-bot/leads", json=_payload())
        reference = lead.json()["reference"]
        no_selection = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(selected_channel=None),
        )
        unauthorized = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(channel_authorized=False),
        )
        readiness = client.get(
            f"/forge-bot/leads/{reference}/response-readiness",
            headers={"X-API-Key": "test-only-owner-key"},
        )
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    assert no_selection.status_code == unauthorized.status_code == 200
    assert readiness.json()["status"] == "BLOCKED"
    assert "selected_channel_not_authorized" in readiness.json()["blocking_reasons"]
    assert readiness.json()["owner_authorized_response_channel"] is None
    assert db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).count() == 2


@pytest.mark.parametrize(
    ("template_ref", "template_authorized", "expected_blocker"),
    [
        (None, True, "permitted_template_reference_missing"),
        ("forge-bot.response.inquiry.v1", False, "permitted_template_not_authorized"),
    ],
)
def test_response_readiness_blocks_missing_or_unauthorized_template(
    db, monkeypatch, template_ref, template_authorized, expected_blocker
):
    _enable_intake(monkeypatch)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        lead = client.post("/forge-bot/leads", json=_payload())
        reference = lead.json()["reference"]
        config = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(
                template_ref=template_ref,
                template_authorized=template_authorized,
            ),
        )
        readiness = client.get(
            f"/forge-bot/leads/{reference}/response-readiness",
            headers={"X-API-Key": "test-only-owner-key"},
        )
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    assert config.status_code == readiness.status_code == 200
    assert readiness.json()["status"] == "BLOCKED"
    assert expected_blocker in readiness.json()["blocking_reasons"]
    assert readiness.json()["external_send_enabled"] is False


def test_response_readiness_requires_consent_and_blocks_opted_out_inquiries(db, monkeypatch):
    _enable_intake(monkeypatch)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        lead_response = client.post("/forge-bot/leads", json=_payload())
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    lead = db.query(models.ForgeBotLeadContact).one()
    authorization = models.OpForgeBotResponseAuthorization(
        id=1,
        **_response_authorization_payload(),
    )
    db.add(authorization)
    db.flush()
    lead.consent_granted = False
    no_consent = forge_bot._evaluate_response_readiness(lead, authorization)
    lead.consent_granted = True
    lead.opted_out = True
    opted_out = forge_bot._evaluate_response_readiness(lead, authorization)

    assert lead_response.status_code == 202
    assert no_consent["status"] == "BLOCKED"
    assert "inquiry_response_consent_missing" in no_consent["blocking_reasons"]
    assert opted_out["status"] == "BLOCKED"
    assert "inquiry_opted_out_or_erased" in opted_out["blocking_reasons"]
    assert opted_out["external_send_enabled"] is False


def test_owner_authorized_response_is_internal_only_until_final_send_gate_opens(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_RESPONSE_SEND_ENABLED", False)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_smtp_email",
        lambda *args, **kwargs: pytest.fail("response readiness attempted an SMTP send"),
    )
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_twilio_sms",
        lambda *args, **kwargs: pytest.fail("response readiness attempted an SMS send"),
    )
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        lead = client.post("/forge-bot/leads", json=_payload())
        reference = lead.json()["reference"]
        config = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(external_send_authorized=True),
        )
        readiness = client.get(
            f"/forge-bot/leads/{reference}/response-readiness",
            headers={"X-API-Key": "test-only-owner-key"},
        )
        repeated_config = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(external_send_authorized=True),
        )
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()
    result = readiness.json()
    result = readiness.json()
    assert lead.status_code == 202
    assert config.status_code == repeated_config.status_code == 200
    assert result["status"] == "INTERNAL_RESPONSE_READY"
    assert result["blocking_reasons"] == []
    assert result["observed_submitter_preference"] == "email"
    assert result["owner_authorized_response_channel"] == "email"
    assert result["permitted_template_ref"] == "forge-bot.response.inquiry.v1"
    assert result["consent_required"] is True
    assert result["opt_out_boundary"] == "permanent_suppression"
    assert result["escalation_boundary"] == "owner_confirmation_required_for_exceptions"
    assert result["external_send_authorized"] is True
    assert result["external_send_gate_open"] is False
    assert result["external_sender_available"] is False
    assert result["external_send_enabled"] is False
    assert result["external_message_sent"] is False
    assert db.query(models.IntegrationDelivery).count() == 0
    assert db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).count() == 1
    authorization_event = db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).one()
    assert authorization_event.source == "forge_bot_owner_response_authorization"
    authorization_payload = json.loads(authorization_event.payload)
    assert authorization_payload["current"] == _response_authorization_payload(
        external_send_authorized=True
    )
    assert db.query(models.TypeRegistry).filter_by(
        category="event_type",
        type_name="forge_bot_response_authorization_changed",
        status="active",
    ).one_or_none() is not None
    assert "lead-one@example.test" not in authorization_event.payload
    assert db.query(models.IntegrationDelivery).count() == 0


def test_submitter_preference_cannot_silently_select_or_authorize_response_channel(
    db, monkeypatch
):
    _enable_intake(monkeypatch)
    forge_bot._submissions_by_ip.clear()
    client, cleanup = _client(db)
    try:
        lead = client.post("/forge-bot/leads", json=_payload(preferred_channel="email"))
        reference = lead.json()["reference"]
        owner_config = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(
                selected_channel="phone",
                channel_authorized=True,
            ),
        )
        readiness = client.get(
            f"/forge-bot/leads/{reference}/response-readiness",
            headers={"X-API-Key": "test-only-owner-key"},
        )
    finally:
        client.close()
        cleanup()
        forge_bot._submissions_by_ip.clear()

    assert lead.status_code == 202
    assert owner_config.status_code == 200
    assert readiness.json()["status"] == "BLOCKED"
    assert readiness.json()["observed_submitter_preference"] == "email"
    assert readiness.json()["owner_authorized_response_channel"] == "phone"
    assert (
        "submitter_preference_does_not_match_authorized_channel"
        in readiness.json()["blocking_reasons"]
    )
    assert readiness.json()["external_send_enabled"] is False
    assert db.query(models.IntegrationDelivery).count() == 0


def test_response_authorization_rejects_unsafe_consent_and_unknown_channel(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        no_consent = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(consent_required=False),
        )
        unknown_channel = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(selected_channel="whatsapp"),
        )
    finally:
        client.close()
        cleanup()

    assert no_consent.status_code == unknown_channel.status_code == 422
    assert db.get(models.OpForgeBotResponseAuthorization, 1) is None
    assert db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).count() == 0


def test_inquiry_lifecycle_events_are_registered_minimized_and_survive_erasure(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        created = client.post("/forge-bot/leads", json=_payload())
        received_event = db.query(models.WorldEvent).one()
        first_control = created.json()["manage_token"]
        opted_out = client.post(
            "/forge-bot/leads/opt-out",
            json={"manage_token": first_control},
        )

        second = client.post(
            "/forge-bot/leads",
            json=_payload(
                email="another-lead@example.test",
                phone="12025550101",
            ),
        )
        erased = client.post(
            "/forge-bot/leads/delete",
            json={"manage_token": second.json()["manage_token"]},
        )
    finally:
        client.close()
        cleanup()

    assert created.status_code == opted_out.status_code == second.status_code == 202
    assert erased.status_code == 204
    events = db.query(models.WorldEvent).order_by(models.WorldEvent.id).all()
    assert [event.event_type for event in events] == [
        "forge_bot_inquiry_received",
        "forge_bot_inquiry_opted_out",
        "forge_bot_inquiry_received",
        "forge_bot_inquiry_erased",
    ]
    assert received_event.source == "forge_bot_web_form"
    registered = {
        row.type_name: row.status
        for row in db.query(models.TypeRegistry)
        .filter_by(category="event_type")
        .all()
    }
    assert all(registered[event.event_type] == "active" for event in events)
    assert db.query(models.ForgeBotLeadContact).count() == 1
    opted_out_lead = db.query(models.ForgeBotLeadContact).one()
    assert opted_out_lead.opted_out is True
    assert opted_out_lead.email is None and opted_out_lead.phone is None

    payloads = [json.loads(event.payload) for event in events]
    assert payloads[0] == {
        "reference": created.json()["reference"],
        "evidence_class": "TEST",
        "state": "READY_FOR_OWNER_REVIEW",
    }
    assert payloads[1] == {
        "reference": created.json()["reference"],
        "evidence_class": "TEST",
        "state": "OPTED_OUT",
        "previous_state": "READY_FOR_OWNER_REVIEW",
    }
    assert payloads[3] == {
        "reference": second.json()["reference"],
        "evidence_class": "TEST",
        "state": "ERASED",
        "previous_state": "READY_FOR_OWNER_REVIEW",
    }
    for event, payload in zip(events, payloads):
        assert event.idempotency_key
        assert not {"email", "phone", "destination", "course", "timeline"} & payload.keys()
        assert "example.test" not in event.payload
        assert "+1" not in event.payload


def test_inquiry_event_failure_does_not_persist_the_lead(db, monkeypatch):
    _enable_intake(monkeypatch)

    def fail_event_write(*args, **kwargs):
        raise RuntimeError("event persistence unavailable")

    monkeypatch.setattr(forge_bot.world_graph, "create_event", fail_event_write)
    client, cleanup = _client(db, raise_server_exceptions=False)
    try:
        response = client.post("/forge-bot/leads", json=_payload())
    finally:
        client.close()
        cleanup()
        db.rollback()

    assert response.status_code == 500
    assert db.query(models.ForgeBotLeadContact).count() == 0
    assert db.query(models.WorldEvent).filter(
        models.WorldEvent.event_type.like("forge_bot_inquiry_%")
    ).count() == 0


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
    assert "No reply was sent through your selected contact channel" in receipt_response.json()["message"]
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
