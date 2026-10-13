import json
from datetime import date

from app import models
from app.api import forge_bot_owner_notification
from app.config import settings
from app.services import action_engine, decision_rights


def _configure_owner_sms(monkeypatch):
    monkeypatch.setattr(settings, "HAMI_OWNER_SMS_DIGEST_ENABLED", True)
    monkeypatch.setattr(settings, "HAMI_OWNER_SMS_NUMBER", "+9779800000000")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC" + "1" * 32)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "test-only-auth-token")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15005550006")


def test_decision_rights_registry_is_read_only_and_starts_at_stage_one():
    matrix = decision_rights.describe_registry()
    rights = {row["action_type"]: row for row in matrix["registry"]}

    assert matrix["active_stage"] == 1
    assert matrix["unknown_action_default"] == decision_rights.OWNER_ONLY
    assert matrix["bot_can_promote_itself"] is False
    assert matrix["rights_are_mutable_at_runtime"] is False
    assert rights["research"]["right"] == decision_rights.BOT
    assert rights["draft_customer_reply"]["right"] == decision_rights.BOT_THEN_TELL_OWNER
    assert rights["outreach"]["right"] == decision_rights.OWNER_ONLY
    assert rights["spend_money"]["right"] == decision_rights.OWNER_ONLY
    assert rights["change_price"]["right"] == decision_rights.OWNER_ONLY
    assert rights["change_revenue_share"]["right"] == decision_rights.OWNER_ONLY
    assert rights["legal_tax_company"]["right"] == decision_rights.OWNER_ONLY
    assert rights["new_customer_market"]["right"] == decision_rights.OWNER_ONLY
    assert rights["contact_without_consent"]["right"] == decision_rights.OWNER_ONLY
    assert rights["widen_permissions"]["right"] == decision_rights.OWNER_ONLY


def test_unknown_action_types_fail_closed_to_owner_only():
    result = decision_rights.enforcement_for("unregistered_future_action")

    assert result["right"] == decision_rights.OWNER_ONLY
    assert result["requires_owner_approval"] is True
    assert result["reason_code"] == "decision_rights:owner_only"


def test_external_commitments_remain_owner_only_at_every_stage(monkeypatch):
    monkeypatch.setattr(decision_rights, "ACTIVE_STAGE", 5)
    monkeypatch.setattr(decision_rights, "_owner_sms_ready", lambda: True)

    for action_type in (
        "outreach", "offer", "paid_pilot", "spend_money", "change_price",
        "change_revenue_share", "legal_tax_company", "new_customer_market",
        "contact_without_consent", "widen_permissions", "public_intake_activation",
        "wire_transfer",
    ):
        result = decision_rights.enforcement_for(action_type)
        assert result["right"] == decision_rights.OWNER_ONLY
        assert result["requires_owner_approval"] is True


def test_stage_gated_actions_stay_approval_required_at_stage_one(monkeypatch):
    monkeypatch.setattr(decision_rights, "ACTIVE_STAGE", 1)
    monkeypatch.setattr(decision_rights, "_owner_sms_ready", lambda: True)

    for action_type in ("draft_customer_reply", "schedule_follow_up", "follow_up", "reply_to_inquiry"):
        result = decision_rights.enforcement_for(action_type)
        assert result["requires_owner_approval"] is True
        assert result["reason_code"] == "decision_rights:stage_gate"


def test_final_action_execution_rechecks_owner_only_rights(db, monkeypatch):
    monkeypatch.setattr(decision_rights, "ACTIVE_STAGE", 5)
    monkeypatch.setattr(decision_rights, "_owner_sms_ready", lambda: True)

    action = action_engine.propose_action(
        db,
        objective="TEST: contact a first-time prospect",
        action_type="outreach",
        estimated_cost=0.0,
    )
    action.status = "PROPOSED"
    action.policy_result = "ALLOW"
    action.policy_reason = "TEST: stale prior policy approval"
    db.commit()

    result = action_engine.start_and_execute_action(db, action.id)

    assert result is not None
    assert result.status == "APPROVAL_REQUIRED"
    assert result.policy_result == "REQUIRE_APPROVAL"
    assert "decision_rights:owner_only" in result.policy_reason
    assert result.started_at is None


def test_owner_sms_digest_is_closed_by_default_and_creates_no_delivery(db, monkeypatch):
    _configure_owner_sms(monkeypatch)
    # Apply the condition under test AFTER the fixture helper has set defaults.
    monkeypatch.setattr(settings, "HAMI_OWNER_SMS_DIGEST_ENABLED", False)
    monkeypatch.setattr(forge_bot_owner_notification, "_owner_sms_database_ready", lambda _: True)

    result = forge_bot_owner_notification.send_daily_owner_status_sms(db, date(2026, 10, 14))

    assert result == {"status": "skipped", "reason": "owner_sms_digest_disabled"}
    assert db.query(models.IntegrationDelivery).filter_by(
        integration_name="twilio_owner", operation="send_owner_sms"
    ).count() == 0


def test_owner_sms_digest_requires_an_exact_configured_owner_number(db, monkeypatch):
    _configure_owner_sms(monkeypatch)
    monkeypatch.setattr(settings, "HAMI_OWNER_SMS_NUMBER", "")
    monkeypatch.setattr(forge_bot_owner_notification, "_owner_sms_database_ready", lambda _: True)

    result = forge_bot_owner_notification.send_daily_owner_status_sms(db, date(2026, 10, 14))

    assert result["status"] == "skipped"
    assert result["reason"] == "owner_sms_number_missing_or_invalid"
    assert db.query(models.IntegrationDelivery).filter_by(
        integration_name="twilio_owner", operation="send_owner_sms"
    ).count() == 0


def test_owner_sms_digest_requires_durable_postgresql(db, monkeypatch):
    _configure_owner_sms(monkeypatch)
    monkeypatch.setattr(
        forge_bot_owner_notification,
        "_owner_sms_database_ready",
        lambda session: session.get_bind().dialect.name == "postgresql",
    )

    result = forge_bot_owner_notification.send_daily_owner_status_sms(db, date(2026, 10, 14))

    assert result["status"] == "skipped"
    assert result["reason"] == "durable_postgresql_required"
    assert db.query(models.IntegrationDelivery).filter_by(
        integration_name="twilio_owner", operation="send_owner_sms"
    ).count() == 0


def test_owner_sms_digest_is_one_segment_and_idempotent_without_real_provider_calls(
    db, monkeypatch
):
    _configure_owner_sms(monkeypatch)
    monkeypatch.setattr(forge_bot_owner_notification, "_owner_sms_database_ready", lambda _: True)
    dispatched_ids = []

    def fake_dispatch(session, delivery_id):
        delivery = session.get(models.IntegrationDelivery, delivery_id)
        assert delivery.integration_name == "twilio_owner"
        assert delivery.operation == "send_owner_sms"
        payload = json.loads(delivery.request_json)
        assert set(payload) == {"to", "body", "message_type"}
        assert payload["to"] == settings.HAMI_OWNER_SMS_NUMBER
        assert payload["message_type"] == "daily_digest"
        assert payload["body"].isascii()
        assert 1 <= len(payload["body"]) <= 160
        dispatched_ids.append(delivery_id)
        delivery.status = "SUCCEEDED"
        delivery.response_json = json.dumps({"sid": "SM-TEST-ACCEPTED"})
        delivery.attempts = 1
        db.commit()
        db.refresh(delivery)
        return delivery

    monkeypatch.setattr(
        forge_bot_owner_notification.integration_dispatcher,
        "dispatch_single_delivery",
        fake_dispatch,
    )

    first = forge_bot_owner_notification.send_daily_owner_status_sms(db, date(2026, 10, 14))
    second = forge_bot_owner_notification.send_daily_owner_status_sms(db, date(2026, 10, 14))

    assert first["status"] == "provider_accepted"
    assert first["idempotent_replay"] is False
    assert second["status"] == "provider_accepted"
    assert second["idempotent_replay"] is True
    assert len(dispatched_ids) == 1
    assert db.query(models.IntegrationDelivery).filter_by(
        idempotency_key="hami-owner-daily-sms:2026-10-14"
    ).count() == 1
