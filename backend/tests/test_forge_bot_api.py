import json
import socket
from types import SimpleNamespace
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.main import app
from app.api import forge_bot, forge_bot_owner_notification
from app.services import forge_bot_response, integration_dispatcher, integration_outbox


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


def test_invalid_email_validation_does_not_echo_submitted_value(db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "FORGE_BOT_INTAKE_ENABLED", False)
    submitted_value = "TEST-private-malformed-contact-value"
    client, cleanup = _client(db)
    try:
        response = client.post(
            "/forge-bot/leads",
            json=_payload(email=submitted_value),
        )
    finally:
        client.close()
        cleanup()

    assert response.status_code == 422
    assert submitted_value not in response.text
    assert response.json()["detail"] == "Request validation failed."
    assert response.json()["errors"] == [
        {"field": "email", "message": "Invalid value."}
    ]
    assert db.query(models.ForgeBotLeadContact).count() == 0


def test_live_off_rejects_real_leads_but_allows_test_records(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", False)
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

    assert real_lead.status_code == 403
    assert test_lead.status_code == 202
    assert db.query(models.ForgeBotLeadContact).count() == 1
    assert db.query(models.ForgeBotLeadContact).one().evidence_class == "TEST"


def test_submitted_lead_is_private_consent_scoped_and_not_projected_publicly(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(
        forge_bot_owner_notification,
        "send_owner_summary_notification",
        lambda *args, **kwargs: pytest.fail("TEST inquiry must not notify the owner"),
    )
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


def test_real_lead_notification_failure_does_not_fail_submission(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    notification_calls = []

    def fail_notification(session, reference, lead_data, idempotency_key):
        assert session.query(models.ForgeBotLeadContact).filter_by(
            public_ref=reference
        ).one()
        notification_calls.append((reference, lead_data, idempotency_key))
        raise OSError("simulated SMTP outage")

    monkeypatch.setattr(
        forge_bot_owner_notification,
        "send_owner_summary_notification",
        fail_notification,
    )
    client, cleanup = _client(db)
    try:
        response = client.post(
            "/forge-bot/leads",
            json=_payload(email="real.lead@example.com", phone="+977 9800000012"),
        )
    finally:
        client.close()
        cleanup()

    assert response.status_code == 202
    assert db.query(models.ForgeBotLeadContact).one().evidence_class == "REAL"
    assert len(notification_calls) == 1
    reference, lead_data, idempotency_key = notification_calls[0]
    assert reference == response.json()["reference"]
    assert lead_data["evidence_class"] == "REAL"
    assert lead_data["stage"] == "READY_FOR_OWNER_REVIEW"
    assert idempotency_key == f"forge-bot-lead-owner-notification:{reference}"


def test_owner_test_send_requires_owner_key_and_returns_status_only(db, monkeypatch):
    _enable_intake(monkeypatch)
    calls = []
    monkeypatch.setattr(
        forge_bot_owner_notification,
        "send_owner_test_notification",
        lambda session: calls.append(session) or {"status": "ACCEPTED_BY_SMTP"},
    )
    client, cleanup = _client(db)
    try:
        unauthorized = client.post("/forge-bot/owner-notification/test-send")
        sent = client.post(
            "/forge-bot/owner-notification/test-send",
            headers={"X-API-Key": settings.FORGE_API_KEY},
        )
        monkeypatch.setattr(
            forge_bot_owner_notification,
            "send_owner_test_notification",
            lambda session: {"status": "FAILED", "error": "private provider detail"},
        )
        failed = client.post(
            "/forge-bot/owner-notification/test-send",
            headers={"X-API-Key": settings.FORGE_API_KEY},
        )
    finally:
        client.close()
        cleanup()

    assert unauthorized.status_code == 401
    assert calls == [db]
    assert sent.status_code == failed.status_code == 200
    assert sent.json() == {"status": "sent"}
    assert failed.json() == {"status": "failed"}


def test_response_authorization_is_owner_only_and_defaults_closed(db, monkeypatch):
    _enable_intake(monkeypatch)
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

    assert no_selection.status_code == unauthorized.status_code == 200
    assert readiness.json()["status"] == "BLOCKED"
    assert "channel_not_authorized" in readiness.json()["blocking_reasons"]
    assert readiness.json()["owner_authorized_response_channel"] is None
    assert db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).count() == 2


@pytest.mark.parametrize(
    ("template_ref", "template_authorized", "expected_blocker"),
    [
        (None, True, "approved_template_missing"),
        ("forge-bot.response.inquiry.v1", False, "template_not_authorized"),
    ],
)
def test_response_readiness_blocks_missing_or_unauthorized_template(
    db, monkeypatch, template_ref, template_authorized, expected_blocker
):
    _enable_intake(monkeypatch)
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

    assert config.status_code == readiness.status_code == 200
    assert readiness.json()["status"] == "BLOCKED"
    assert expected_blocker in readiness.json()["blocking_reasons"]
    assert readiness.json()["external_send_enabled"] is False


def test_response_readiness_requires_consent_and_blocks_opted_out_inquiries(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        lead_response = client.post("/forge-bot/leads", json=_payload())
    finally:
        client.close()
        cleanup()

    lead = db.query(models.ForgeBotLeadContact).one()
    authorization = models.OpForgeBotResponseAuthorization(
        id=1,
        **_response_authorization_payload(),
    )
    db.add(authorization)
    db.flush()
    lead.consent_granted = False
    no_consent = forge_bot_response.decide_response_action(
        db,
        inquiry_reference=lead.public_ref,
        action=None,
        requested_channel=authorization.selected_channel,
        requested_template_ref=authorization.template_ref,
    ).as_dict()
    lead.consent_granted = True
    lead.opted_out = True
    lead.erased_at = models.utcnow()
    opted_out = forge_bot_response.decide_response_action(
        db,
        inquiry_reference=lead.public_ref,
        action=None,
        requested_channel=authorization.selected_channel,
        requested_template_ref=authorization.template_ref,
    ).as_dict()

    assert lead_response.status_code == 202
    assert no_consent["decision"] == "BLOCKED"
    assert "consent_missing" in no_consent["reason_codes"]
    assert opted_out["decision"] == "BLOCKED"
    assert "inquiry_opted_out" in opted_out["reason_codes"]
    assert "inquiry_erased" in opted_out["reason_codes"]


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
    result = readiness.json()
    assert lead.status_code == 202
    assert config.status_code == repeated_config.status_code == 200
    assert result["status"] == "BLOCKED"
    assert result["authorization_decision"] == "ALLOWED"
    assert "external_send_disabled" in result["blocking_reasons"]
    assert "sender_unavailable" in result["blocking_reasons"]
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

    assert lead.status_code == 202
    assert owner_config.status_code == 200
    assert readiness.json()["status"] == "BLOCKED"
    assert readiness.json()["observed_submitter_preference"] == "email"
    assert readiness.json()["owner_authorized_response_channel"] == "phone"
    assert (
        "channel_mismatch"
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
        unsafe_template_ref = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(template_ref="12025550123"),
        )
    finally:
        client.close()
        cleanup()

    assert (
        no_consent.status_code
        == unknown_channel.status_code
        == unsafe_template_ref.status_code
        == 422
    )
    assert db.get(models.OpForgeBotResponseAuthorization, 1) is None
    assert db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).count() == 0


def test_response_authorization_change_rolls_back_if_audit_event_fails(db, monkeypatch):
    _enable_intake(monkeypatch)

    def fail_event_write(*args, **kwargs):
        raise RuntimeError("authorization event persistence unavailable")

    monkeypatch.setattr(forge_bot.world_graph, "create_event", fail_event_write)
    client, cleanup = _client(db, raise_server_exceptions=False)
    try:
        response = client.put(
            "/forge-bot/response-authorization",
            headers={"X-API-Key": "test-only-owner-key"},
            json=_response_authorization_payload(),
        )
    finally:
        client.close()
        cleanup()
        db.rollback()

    assert response.status_code == 500
    assert db.get(models.OpForgeBotResponseAuthorization, 1) is None
    assert db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_authorization_changed"
    ).count() == 0


def _response_lead(db, **changes):
    values = {
        "public_ref": "FB-TESTACTION",
        "email": "lead-one@example.test",
        "normalized_email": "lead-one@example.test",
        "phone": "+1 (202) 555-0100",
        "normalized_phone": "12025550100",
        "preferred_channel": "email",
        "evidence_class": "TEST",
        "consent_granted": True,
        "consent_purpose": forge_bot.CONSENT_PURPOSE,
        "consent_provenance": forge_bot.CONSENT_PROVENANCE,
        "opted_out": False,
        "erased_at": None,
    }
    lead = models.ForgeBotLeadContact(**{**values, **changes})
    db.add(lead)
    db.flush()
    return lead


def _install_response_policy(db, **changes):
    values = _response_authorization_payload(external_send_authorized=True)
    authorization = models.OpForgeBotResponseAuthorization(
        id=1,
        **{**values, **changes},
    )
    db.add(authorization)
    db.flush()
    return authorization


def _response_action(db, lead, *, status="APPROVED", **parameter_changes):
    parameters = {
        "inquiry_reference": lead.public_ref,
        "channel": "email",
        "template_ref": "forge-bot.response.inquiry.v1",
        "requires_owner_confirmation": True,
        **parameter_changes,
    }
    action = models.Action(
        action_type="forge_bot_response",
        objective="Review one Forge Bot customer-response action",
        parameters_json=json.dumps(parameters),
        status=status,
        policy_result="REQUIRE_APPROVAL",
        approved_at=models.utcnow() if status == "APPROVED" else None,
        adapter_name="forge_bot_response",
    )
    db.add(action)
    db.flush()
    return action


def test_response_action_decision_reports_policy_approval_but_fails_closed_without_send_gate(
    db, monkeypatch
):
    monkeypatch.setattr(settings, "FORGE_BOT_RESPONSE_SEND_ENABLED", False)
    lead = _response_lead(db)
    _install_response_policy(db)
    action = _response_action(db, lead)

    decision = forge_bot_response.decide_response_action(
        db,
        inquiry_reference=None,
        action=action,
    )
    rendered = json.dumps(decision.as_dict())

    assert decision.authorization_decision == "ALLOWED"
    assert decision.decision == "BLOCKED"
    assert "external_send_disabled" in decision.reason_codes
    assert "sender_unavailable" in decision.reason_codes
    assert settings.FORGE_BOT_RESPONSE_SEND_ENABLED is False
    assert "lead-one@example.test" not in rendered
    assert "+1 (202) 555-0100" not in rendered
    assert "12025550100" not in rendered


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("missing_policy", "owner_authorization_missing"),
        ("missing_channel", "selected_channel_missing"),
        ("unauthorized_channel", "channel_not_authorized"),
        ("unknown_channel", "unknown_channel"),
        ("missing_template", "approved_template_missing"),
        ("unauthorized_template", "template_not_authorized"),
        ("unknown_template", "unknown_template"),
        ("missing_consent", "consent_missing"),
        ("opted_out", "inquiry_opted_out"),
        ("erased", "inquiry_erased"),
        ("contact_unavailable", "contact_unavailable"),
        ("channel_mismatch", "channel_mismatch"),
        ("owner_confirmation_missing", "owner_confirmation_missing"),
        ("send_not_authorized", "external_send_not_authorized"),
        ("send_gate_disabled", "external_send_disabled"),
        ("malformed_policy", "consent_requirement_disabled"),
        ("intake_disabled", "intake_disabled"),
        ("suppression_key_missing", "contact_suppression_key_missing"),
        ("owner_key_missing", "owner_access_configuration_missing"),
        ("live_disabled", "forge_bot_live_disabled"),
        ("test_evidence", "test_evidence_not_real"),
        ("malformed_action", "malformed_action_state"),
        ("no_action", "response_action_missing"),
    ],
)
def test_response_action_decision_fails_closed_for_each_reason(
    db, monkeypatch, mutation, expected_reason
):
    monkeypatch.setattr(settings, "FORGE_BOT_RESPONSE_SEND_ENABLED", False)
    lead = _response_lead(db)
    authorization = _install_response_policy(db)
    action = _response_action(db, lead)
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)

    if mutation == "missing_policy":
        db.delete(authorization)
        db.flush()
    elif mutation == "missing_channel":
        authorization.selected_channel = None
    elif mutation == "unauthorized_channel":
        authorization.channel_authorized = False
    elif mutation == "unknown_channel":
        authorization.selected_channel = "whatsapp"
    elif mutation == "missing_template":
        authorization.template_ref = None
    elif mutation == "unauthorized_template":
        authorization.template_authorized = False
    elif mutation == "unknown_template":
        params = json.loads(action.parameters_json)
        params["template_ref"] = "forge-bot.response.unregistered.v1"
        action.parameters_json = json.dumps(params)
    elif mutation == "malformed_action":
        action.parameters_json = "{malformed"
    elif mutation == "missing_consent":
        lead.consent_granted = False
    elif mutation == "opted_out":
        lead.opted_out = True
    elif mutation == "erased":
        lead.erased_at = models.utcnow()
    elif mutation == "contact_unavailable":
        lead.email = None
    elif mutation == "channel_mismatch":
        lead.preferred_channel = "phone"
    elif mutation == "owner_confirmation_missing":
        action.status = "APPROVAL_REQUIRED"
        action.approved_at = None
    elif mutation == "send_not_authorized":
        authorization.external_send_authorized = False
    elif mutation == "send_gate_disabled":
        pass
    elif mutation == "malformed_policy":
        authorization.consent_required = False
    elif mutation == "intake_disabled":
        monkeypatch.setattr(settings, "FORGE_BOT_INTAKE_ENABLED", False)
    elif mutation == "suppression_key_missing":
        monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "")
    elif mutation == "owner_key_missing":
        monkeypatch.setattr(settings, "FORGE_API_KEY", "")
    elif mutation == "live_disabled":
        monkeypatch.setattr(settings, "FORGE_BOT_LIVE", False)
    elif mutation == "test_evidence":
        pass
    elif mutation == "no_action":
        action = None

    decision = forge_bot_response.decide_response_action(
        db,
        inquiry_reference=lead.public_ref,
        action=action,
        requested_channel="email",
        requested_template_ref="forge-bot.response.inquiry.v1",
    )

    assert decision.decision == "BLOCKED"
    assert expected_reason in decision.reason_codes


def test_response_action_decision_blocks_malformed_authorization_state(db, monkeypatch):
    lead = _response_lead(db)
    action = _response_action(db, lead)
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    malformed = SimpleNamespace(
        id=1,
        selected_channel="email",
        channel_authorized=True,
        template_ref="forge-bot.response.inquiry.v1",
        template_authorized=True,
        consent_required=True,
        opt_out_boundary="unexpected",
        escalation_boundary="owner_confirmation_required_for_exceptions",
        external_send_authorized=True,
    )

    class MalformedPolicySession:
        def get(self, model, identifier):
            if model is models.OpForgeBotResponseAuthorization:
                return malformed
            return db.get(model, identifier)

        def query(self, model):
            return db.query(model)

    decision = forge_bot_response.decide_response_action(
        MalformedPolicySession(),
        inquiry_reference=None,
        action=action,
    )

    assert decision.decision == "BLOCKED"
    assert "malformed_authorization_state" in decision.reason_codes


def test_action_audit_failure_fails_closed_before_delivery_or_provider_call(db, monkeypatch):
    lead = _response_lead(db)
    _install_response_policy(db)
    action = _response_action(db, lead)

    def fail_event(*args, **kwargs):
        raise RuntimeError("event persistence unavailable")

    monkeypatch.setattr(forge_bot_response.world_graph, "create_event", fail_event)
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_smtp_email",
        lambda *args, **kwargs: pytest.fail("audit failure reached SMTP"),
    )
    from app.services import action_engine

    executed = action_engine.start_and_execute_action(db, action.id)

    assert executed.status == "FAILED"
    assert "event persistence unavailable" in executed.execution_error
    assert db.query(models.IntegrationDelivery).count() == 0


def test_owner_response_action_routes_emit_events_and_never_send(db, monkeypatch):
    _enable_intake(monkeypatch)
    lead = _response_lead(db)
    client, cleanup = _client(db)
    headers = {"X-API-Key": "test-only-owner-key"}
    try:
        no_key = client.post(
            "/forge-bot/response-actions",
            json={
                "inquiry_reference": lead.public_ref,
                "channel": "email",
                "template_ref": "forge-bot.response.inquiry.v1",
            },
        )
        created = client.post(
            "/forge-bot/response-actions",
            headers=headers,
            json={
                "inquiry_reference": lead.public_ref,
                "channel": "email",
                "template_ref": "forge-bot.response.inquiry.v1",
            },
        )
        action_id = created.json()["action_id"]
        approved = client.post(
            f"/forge-bot/response-actions/{action_id}/approve",
            headers=headers,
        )
        executed = client.post(
            f"/forge-bot/response-actions/{action_id}/execute",
            headers=headers,
        )
    finally:
        client.close()
        cleanup()

    assert no_key.status_code == 401
    assert created.status_code == 202
    assert created.json()["status"] == "APPROVAL_REQUIRED"
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert executed.status_code == 200
    assert executed.json()["status"] == "FAILED"
    assert executed.json()["external_message_sent"] is False
    assert db.query(models.IntegrationDelivery).count() == 0
    assert db.query(models.WorldEvent).filter(
        models.WorldEvent.event_type.in_(
            [
                "forge_bot_response_action_proposed",
                "forge_bot_response_action_owner_approved",
                "forge_bot_response_action_authorization_decided",
            ]
        )
    ).count() == 3


def test_response_action_stub_cannot_create_outbox_or_call_provider_when_blocked(
    db, monkeypatch
):
    lead = _response_lead(db)
    _install_response_policy(db)
    action = _response_action(db, lead)
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_smtp_email",
        lambda *args, **kwargs: pytest.fail("Forge Bot response invoked SMTP"),
    )
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_twilio_sms",
        lambda *args, **kwargs: pytest.fail("Forge Bot response invoked Twilio"),
    )

    from app.services import action_engine

    executed = action_engine.start_and_execute_action(db, action.id)

    assert executed.status == "FAILED"
    assert "external_send_disabled" in executed.execution_error
    assert db.query(models.IntegrationDelivery).count() == 0
    events = db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_response_action_authorization_decided"
    ).all()
    assert len(events) == 1
    event_payload = json.loads(events[0].payload)
    assert event_payload["decision"] == "BLOCKED"
    assert event_payload["inquiry_reference"] == lead.public_ref
    assert "lead-one@example.test" not in events[0].payload


@pytest.mark.parametrize(
    ("integration_name", "operation", "request_data"),
    [
        (
            "smtp",
            "send_email",
            {
                "to": "lead-one@example.test",
                "subject": "Unapproved",
                "body": "Must not be sent",
            },
        ),
        (
            "twilio",
            "send_sms",
            {"to": "+1 (202) 555-0100", "body": "Must not be sent"},
        ),
    ],
)
def test_generic_provider_outbox_cannot_target_forge_bot_contacts(
    db, monkeypatch, integration_name, operation, request_data
):
    _response_lead(db)
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_smtp_email",
        lambda *args, **kwargs: pytest.fail("generic SMTP bypassed Forge Bot boundary"),
    )
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_twilio_sms",
        lambda *args, **kwargs: pytest.fail("generic Twilio bypassed Forge Bot boundary"),
    )

    with pytest.raises(forge_bot_response.ForgeBotResponseBlocked):
        integration_outbox.enqueue(
            db,
            integration_name=integration_name,
            operation=operation,
            idempotency_key=f"forge-bot-generic-bypass:{integration_name}",
            request=request_data,
        )
    assert db.query(models.IntegrationDelivery).count() == 0


def test_generic_provider_outbox_respects_persistent_forge_bot_opt_out(db, monkeypatch):
    _enable_intake(monkeypatch)
    lead = _response_lead(db)
    lead.email = None
    lead.normalized_email = None
    lead.phone = None
    lead.normalized_phone = None
    lead.email_suppression_hmac = forge_bot_response._contact_hmac(
        "email", "lead-one@example.test"
    )
    lead.opted_out = True
    lead.erased_at = models.utcnow()
    lead.public_ref = "FB-SUPP-TESTACTION"
    db.flush()

    with pytest.raises(forge_bot_response.ForgeBotResponseBlocked) as blocked:
        integration_outbox.enqueue(
            db,
            integration_name="smtp",
            operation="send_email",
            idempotency_key="forge-bot-suppression-bypass",
            request={
                "to": "lead-one@example.test",
                "subject": "Unapproved",
                "body": "Must not be sent",
            },
        )

    assert "inquiry_opted_out" in blocked.value.reason_codes
    assert "inquiry_erased" in blocked.value.reason_codes
    assert db.query(models.IntegrationDelivery).count() == 0


def test_forge_bot_outbox_marker_cannot_bypass_canonical_decision(db):
    lead = _response_lead(db)
    action = _response_action(db, lead)
    marker = forge_bot_response.response_action_marker(
        action,
        json.loads(action.parameters_json),
    )

    with pytest.raises(forge_bot_response.ForgeBotResponseBlocked):
        integration_outbox.enqueue(
            db,
            integration_name="smtp",
            operation="send_email",
            idempotency_key="forge-bot-marker-without-decision",
            request={
                **marker,
                "to": lead.email,
                "subject": "Not sent",
                "body": "Not sent",
            },
        )
    assert db.query(models.IntegrationDelivery).count() == 0


@pytest.mark.parametrize(
    ("integration_name", "operation", "delivery_request"),
    [
        (
            "smtp",
            "send_email",
            {
                "to": "lead-one@example.test",
                "subject": "Unapproved",
                "body": "Must not be sent",
            },
        ),
        (
            "twilio",
            "send_sms",
            {"to": "+1 (202) 555-0100", "body": "Must not be sent"},
        ),
    ],
)
def test_generic_provider_dispatch_blocks_preexisting_forge_bot_delivery(
    db, monkeypatch, integration_name, operation, delivery_request
):
    _response_lead(db)
    delivery = models.IntegrationDelivery(
        integration_name=integration_name,
        operation=operation,
        idempotency_key="legacy-forge-bot-recipient",
        request_json=json.dumps(delivery_request),
        status="QUEUED",
        attempts=0,
    )
    db.add(delivery)
    db.flush()
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_smtp_email",
        lambda *args, **kwargs: pytest.fail("dispatcher bypassed Forge Bot boundary"),
    )
    monkeypatch.setattr(
        integration_dispatcher,
        "_send_twilio_sms",
        lambda *args, **kwargs: pytest.fail("dispatcher bypassed Forge Bot boundary"),
    )

    dispatched = integration_dispatcher.dispatch_single_delivery(db, delivery.id)

    assert dispatched.status == "FAILED"
    assert "forge bot response action blocked" in dispatched.last_error.lower()


def test_generic_action_api_cannot_create_forge_bot_response_actions(db, monkeypatch):
    _enable_intake(monkeypatch)
    client, cleanup = _client(db)
    try:
        response = client.post(
            "/forge/actions",
            headers={"X-API-Key": "test-only-owner-key"},
            params={
                "objective": "Reply to a Forge Bot lead",
                "action_type": "forge_bot_response",
            },
        )
    finally:
        client.close()
        cleanup()
    assert response.status_code == 403


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
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_EMAIL", "owner@example.test")
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

    assert [response.status_code for response in responses[:-1]] == [202] * forge_bot.RATE_LIMIT
    assert responses[-1].status_code == 429
    assert responses[-1].json()["detail"] == (
        "Hourly submission limit reached: no more than 5 inquiries per visitor per hour."
    )
    assert db.query(models.ForgeBotLeadContact).count() == forge_bot.RATE_LIMIT
    rate_bucket = db.query(models.ForgeBotIntakeRateLimit).one()
    assert rate_bucket.request_count == forge_bot.RATE_LIMIT + 1
    assert len(rate_bucket.visitor_hash) == 64
    assert "testclient" not in rate_bucket.visitor_hash


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


def test_owner_console_readiness_is_keyed_and_aggregate_only(db, monkeypatch):
    _enable_intake(monkeypatch)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    deployed_sha = "a" * 40
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", deployed_sha)
    client, cleanup = _client(db)
    try:
        lead = client.post("/forge-bot/leads", json=_payload())
        unauthorized = client.get("/api/forge-bot/owner/readiness")
        response = client.get(
            "/api/forge-bot/owner/readiness",
            headers={"X-API-Key": settings.FORGE_API_KEY},
        )
    finally:
        client.close()
        cleanup()

    assert lead.status_code == 202
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"detail": "Owner authentication failed."}
    readiness = response.json()
    assert response.status_code == 200
    assert readiness["database_ok"] is True
    assert readiness["migrations_ok"] is True
    assert readiness["smtp_configured"] is False
    assert readiness["hmac_key_configured"] is True
    assert readiness["deployed_commit"] == deployed_sha
    assert readiness["intake_enabled"] is True
    assert readiness["live_enabled"] is False
    assert readiness["lead_counts_by_stage"] == {
        "REQUESTED": 1,
        "REPLIED": 0,
        "BOOKED": 0,
        "COMPLETED": 0,
    }
    assert readiness["lead_counts_by_evidence_class"] == {"REAL": 0, "TEST": 1}
    assert readiness["new_leads_last_24h"] == 1
    assert settings.FORGE_API_KEY not in response.text
    assert "lead-one@example.test" not in response.text


def test_owner_console_enforces_lifecycle_and_erases_only_contact_record(db, monkeypatch):
    _enable_intake(monkeypatch)
    owner_headers = {"X-API-Key": settings.FORGE_API_KEY}
    html_course = "<img src=x onerror=alert(1)>"
    html_destination = "<script>alert('text')</script>"
    client, cleanup = _client(db)
    try:
        submitted = client.post(
            "/forge-bot/leads",
            json=_payload(
                email="script-payload@example.test",
                destination=html_destination,
                course=html_course,
            ),
        )
        reference = submitted.json()["reference"]
        public_list = client.get("/forge-bot/owner/leads", headers=owner_headers)
        detail = client.get(
            f"/forge-bot/owner/leads/{reference}",
            headers=owner_headers,
        )
        early_booking = client.post(
            f"/forge-bot/owner/leads/{reference}/booked",
            headers=owner_headers,
            json={"evidence_reference": "booking-001"},
        )
        replied = client.post(
            f"/forge-bot/owner/leads/{reference}/replied",
            headers=owner_headers,
        )
        invalid_booking = client.post(
            f"/forge-bot/owner/leads/{reference}/booked",
            headers=owner_headers,
            json={"evidence_reference": "x"},
        )
        booked = client.post(
            f"/forge-bot/owner/leads/{reference}/booked",
            headers=owner_headers,
            json={"evidence_reference": "local-booking-001"},
        )
        completed = client.post(
            f"/forge-bot/owner/leads/{reference}/completed",
            headers=owner_headers,
            json={"outcome_note": "TEST consultation delivered; no payment recorded"},
        )
        erased = client.delete(
            f"/forge-bot/owner/leads/{reference}",
            headers=owner_headers,
        )
    finally:
        client.close()
        cleanup()

    assert submitted.status_code == 202
    assert public_list.status_code == 200
    assert public_list.json()[0]["stage"] == "REQUESTED"
    assert "script-payload@example.test" not in public_list.text
    assert "email" not in public_list.json()[0]
    assert detail.status_code == 200
    assert detail.json()["email"] == "script-payload@example.test"
    assert detail.json()["course"] == html_course
    assert detail.json()["destination"] == html_destination
    assert early_booking.status_code == 409
    assert replied.json()["stage"] == "REPLIED"
    assert invalid_booking.status_code == 422
    assert "x" not in invalid_booking.text
    assert booked.json()["stage"] == "BOOKED"
    assert completed.json()["stage"] == "COMPLETED"
    assert erased.status_code == 200
    assert erased.json()["status"] == "erased"
    assert db.query(models.ForgeBotLeadContact).count() == 0
    transitions = (
        db.query(models.WorldEvent)
        .filter(
            models.WorldEvent.payload.contains(reference),
            models.WorldEvent.source == "forge_bot_owner_console",
        )
        .order_by(models.WorldEvent.id)
        .all()
    )
    assert [json.loads(event.payload)["transition"] for event in transitions[:-1]] == [
        "REPLIED",
        "BOOKED",
        "COMPLETED",
    ]
    assert transitions[-1].event_type == "forge_bot_inquiry_erased"
    assert all(json.loads(event.payload)["evidence_class"] == "TEST" for event in transitions)
    erased_payload = json.loads(transitions[-1].payload)
    assert erased_payload == {
        "evidence_class": "TEST",
        "previous_state": "COMPLETED",
        "reference": reference,
        "state": "ERASED",
    }
    assert "script-payload@example.test" not in transitions[-1].payload
    assert html_course not in transitions[-1].payload


def test_owner_console_failed_authentication_is_rate_limited(db, monkeypatch):
    _enable_intake(monkeypatch)
    owner_headers = {"X-API-Key": settings.FORGE_API_KEY}
    client, cleanup = _client(db)
    try:
        submitted = client.post("/forge-bot/leads", json=_payload())
        reference = submitted.json()["reference"]
        failures = [
            client.post(f"/forge-bot/owner/leads/{reference}/replied")
            for _ in range(forge_bot.OWNER_AUTH_FAILURE_LIMIT)
        ]
        limited = client.post(f"/forge-bot/owner/leads/{reference}/replied")
        authorized = client.post(
            f"/forge-bot/owner/leads/{reference}/replied",
            headers=owner_headers,
        )
    finally:
        client.close()
        cleanup()

    assert submitted.status_code == 202
    assert [response.status_code for response in failures] == [401] * forge_bot.OWNER_AUTH_FAILURE_LIMIT
    assert all(response.json() == {"detail": "Owner authentication failed."} for response in failures)
    assert limited.status_code == 429
    assert "test-only-owner-key" not in limited.text
    assert authorized.status_code == 200
    buckets = (
        db.query(models.ForgeBotIntakeRateLimit)
        .filter_by(request_count=forge_bot.OWNER_AUTH_FAILURE_LIMIT + 1)
        .all()
    )
    assert len(buckets) == 1
    assert "127.0.0.1" not in buckets[0].visitor_hash
