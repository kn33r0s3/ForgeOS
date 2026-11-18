import hashlib
import json
import re
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app import models
from app.config import settings
from app.main import app
from app.services import owner_control

def configure(monkeypatch):
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_CONTROL_ENABLED", True)
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_OWNER_DIGEST_ENABLED", False)
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_BOT_TOKEN", "1234567890:" + "A" * 40)
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_WEBHOOK_SECRET", "secret_" + "S" * 40)
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_OWNER_CHAT_ID", "123456789")
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_OWNER_USER_ID", "234567890")
    monkeypatch.setattr(owner_control, "durable_database", lambda _db: True)

def fake_send(monkeypatch):
    sent = []
    from app.services import integration_dispatcher

    monkeypatch.setattr(integration_dispatcher.telegram_transport, "send_owner_message",
        lambda text, message_type="alert": sent.append({"text": text, "kind": message_type}) or {"message_id": 77, "accepted": True})
    return sent


def test_ask_lifecycle_refuses_ephemeral_database(db, monkeypatch):
    configure(monkeypatch)
    sent = fake_send(monkeypatch)
    monkeypatch.setattr(owner_control, "durable_database", lambda _db: False)
    with pytest.raises(owner_control.OwnerControlError, match="durable_database_required"):
        owner_control.create_ask(
            db, decision_ref="review", action_type="prepare_internal_draft",
            question="Choose the next internal draft direction?",
            options=[{"key": "A", "label": "Evidence first"}, {"key": "B", "label": "Compare alternatives"}],
        )
    assert sent == []
    assert db.query(models.OpHamiOwnerAsk).count() == 0

def test_safe_mode_starts_on_and_blocks_sends(db, monkeypatch):
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    monkeypatch.setattr(owner_control, "durable_database", lambda _db: True)
    # The conftest seeds a not-halted row; this test covers the creation
    # default (no row -> ensure_state creates one with safe mode ON).
    row = db.query(models.OpHamiRuntimeControl).first()
    if row is not None:
        db.delete(row)
        db.commit()
    assert owner_control.ensure_state(db).safe_mode_enabled
    assert owner_control.block_customer_delivery(db, integration_name="twilio", operation="send_sms",
        request_data={"to": "+9779812345678", "body": "test"}) == "safe_mode_enabled"


def test_customer_delivery_requires_durable_database_even_if_state_is_open(db, monkeypatch):
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    fresh = owner_control.now()
    # The conftest seeds the row id=1; merge updates it instead of
    # colliding on the primary key.
    db.merge(models.OpHamiRuntimeControl(
        id=1, safe_mode_enabled=False, safe_mode_reason="initial_default_safe",
        last_owner_contact_at=fresh, updated_at=fresh,
    ))
    db.commit()
    monkeypatch.setattr(owner_control, "durable_database", lambda _db: False)
    reason = owner_control.block_customer_delivery(
        db, integration_name="twilio", operation="send_sms",
        request_data={"to": "+9779800000000", "body": "test"},
    )
    assert reason == "durable_database_required"


def test_seven_days_inactive_enables_safe_mode(db, monkeypatch):
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    monkeypatch.setattr(owner_control, "durable_database", lambda _db: True)
    old = owner_control.now() - timedelta(days=8)
    # The conftest seeds the row id=1; merge updates it instead of
    # colliding on the primary key.
    db.merge(models.OpHamiRuntimeControl(id=1, safe_mode_enabled=False, safe_mode_reason="initial_default_safe", last_owner_contact_at=old, updated_at=old))
    db.commit()
    reason = owner_control.block_customer_delivery(db, integration_name="smtp", operation="send_email", request_data={"to": "seller@example.org", "body": "test"})
    assert reason == "owner_inactive"
    assert owner_control.ensure_state(db).safe_mode_enabled

def test_runtime_state_error_fails_closed(db, monkeypatch):
    monkeypatch.setattr(settings, "FORGE_BOT_LIVE", True)
    monkeypatch.setattr(owner_control, "durable_database", lambda _db: True)
    monkeypatch.setattr(owner_control, "ensure_state", lambda _db: (_ for _ in ()).throw(RuntimeError("redacted")))
    assert owner_control.block_customer_delivery(db, integration_name="twilio", operation="send_sms", request_data={"to": "+9779812345678", "body": "test"}) == "runtime_control_unavailable"

def test_halt_persists_and_emits_event(db):
    state = owner_control.set_safe_mode(db, "halt_command", 71)
    assert state.safe_mode_enabled and state.safe_mode_reason == "halt_command" and state.last_telegram_update_id == 71
    assert db.query(models.WorldEvent).filter_by(event_type="state_changed", source="hami_owner_control").first() is not None

def test_high_impact_ask_code_is_hashed_and_console_only(db, monkeypatch):
    configure(monkeypatch); sent = fake_send(monkeypatch)
    ask = owner_control.create_ask(db, decision_ref="fee", action_type="change_price", question="Keep the proposed fee unchanged?",
        options=[{"key": "KEEP", "label": "Keep fee"}, {"key": "REVIEW", "label": "Prepare another proposal"}])
    code = re.search(r"(?m)^Code: ([A-Za-z0-9_-]+)$", sent[0]["text"]).group(1)
    assert ask.high_impact and ask.code_hash == hashlib.sha256(code.encode()).hexdigest()
    with pytest.raises(owner_control.OwnerControlError, match="owner_console_required"):
        owner_control.answer_ask(db, ask_ref=ask.public_ref, code=code, option="KEEP", channel="telegram")
    result = owner_control.answer_ask(db, ask_ref=ask.public_ref, code=code, option="KEEP", channel="owner_console")
    assert not result["action_executed"]
    db.refresh(ask)
    assert ask.status == "ANSWERED" and ask.code_hash is None
    with pytest.raises(owner_control.OwnerControlError, match="ask_not_open"):
        owner_control.answer_ask(db, ask_ref=ask.public_ref, code=code, option="KEEP", channel="owner_console")

def test_routine_ask_is_single_use_and_does_not_execute(db, monkeypatch):
    configure(monkeypatch); sent = fake_send(monkeypatch)
    ask = owner_control.create_ask(db, decision_ref="copy", action_type="prepare_internal_draft", question="Which draft direction?",
        options=[{"key": "A", "label": "Evidence-led"}, {"key": "B", "label": "Alternative"}])
    code = re.search(r"(?m)^Code: ([A-Za-z0-9_-]+)$", sent[0]["text"]).group(1)
    result = owner_control.answer_ask(db, ask_ref=ask.public_ref, code=code, option="A", channel="telegram")
    assert not result["action_executed"]
    with pytest.raises(owner_control.OwnerControlError, match="ask_not_open"):
        owner_control.answer_ask(db, ask_ref=ask.public_ref, code=code, option="A", channel="telegram")


def test_ask_resend_uses_a_new_gated_outbox_delivery(db, monkeypatch):
    configure(monkeypatch)
    sent = fake_send(monkeypatch)
    ask = owner_control.create_ask(
        db,
        decision_ref="review",
        action_type="prepare_internal_draft",
        question="Which internal review should come first?",
        options=[{"key": "A", "label": "Evidence"}, {"key": "B", "label": "Alternatives"}],
    )
    initial_code = re.search(r"(?m)^Code: ([A-Za-z0-9_-]+)$", sent[0]["text"]).group(1)

    resent = owner_control.resend_ask(db, ask.public_ref)
    resent_code = re.search(r"(?m)^Code: ([A-Za-z0-9_-]+)$", sent[1]["text"]).group(1)

    assert initial_code != resent_code
    assert resent.code_resend_count == 1
    assert resent.notification_status == "SENT"
    deliveries = db.query(models.IntegrationDelivery).filter_by(
        integration_name="telegram_owner",
        operation="send_telegram_owner",
    ).order_by(models.IntegrationDelivery.id).all()
    assert len(deliveries) == 2
    assert all(row.status == "SUCCEEDED" for row in deliveries)
    assert all(row.response_json and '"accepted": true' in row.response_json for row in deliveries)
    assert all(
        json.loads(row.request_json)["body"] == "[redacted after dispatch]"
        for row in deliveries
    )


def test_webhook_secret_and_chat_allowlist(db, monkeypatch):
    configure(monkeypatch); sent = fake_send(monkeypatch); client = TestClient(app)
    update = {"update_id": 8, "message": {"from": {"id": 999, "is_bot": False}, "chat": {"id": 999, "type": "private"}, "text": "HALT"}}
    bad = client.post("/owner-control/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}, json=update)
    assert bad.status_code == 401
    ignored = client.post("/owner-control/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": settings.HAMI_TELEGRAM_WEBHOOK_SECRET}, json=update)
    assert ignored.status_code == 200 and sent == []
    assert owner_control.ensure_state(db).last_owner_contact_at is None


def test_webhook_reply_uses_gated_outbox(db, monkeypatch):
    configure(monkeypatch)
    sent = fake_send(monkeypatch)
    state = owner_control.ensure_state(db)
    state.safe_mode_enabled = False
    state.safe_mode_reason = "owner_resumed"
    state.last_owner_contact_at = owner_control.now()
    state.last_telegram_update_id = 777
    db.commit()
    client = TestClient(app)
    update = {
        "update_id": 778,
        "message": {
            "from": {"id": 234567890, "is_bot": False},
            "chat": {"id": 123456789, "type": "private"},
            "text": "/help",
        },
    }

    response = client.post(
        "/owner-control/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.HAMI_TELEGRAM_WEBHOOK_SECRET},
        json=update,
    )

    assert response.status_code == 200
    assert sent and sent[0]["kind"] == "status"
    delivery = db.query(models.IntegrationDelivery).filter_by(
        integration_name="telegram_owner",
        operation="send_telegram_owner",
    ).one()
    assert delivery.status == "SUCCEEDED"
    assert db.query(models.WorldEvent).filter_by(
        event_type="gate_execution",
        source="execution_boundary",
    ).count() == 1


def test_halt_webhook_persists_before_acknowledgement(db, monkeypatch):
    configure(monkeypatch); sent = fake_send(monkeypatch); client = TestClient(app)
    update = {"update_id": 777, "message": {"from": {"id": 234567890, "is_bot": False}, "chat": {"id": 123456789, "type": "private"}, "text": "HALT"}}
    response = client.post("/owner-control/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": settings.HAMI_TELEGRAM_WEBHOOK_SECRET}, json=update)
    assert response.status_code == 200
    state = owner_control.ensure_state(db)
    assert state.safe_mode_enabled and state.safe_mode_reason == "halt_command" and state.last_telegram_update_id == 777
    assert sent == []
    delivery = db.query(models.IntegrationDelivery).filter_by(
        integration_name="telegram_owner",
        operation="send_telegram_owner",
    ).one()
    assert delivery.status == "FAILED"
    assert db.query(models.WorldEvent).filter_by(event_type="gate_refusal").count() == 1

def test_digest_defaults_off(db, monkeypatch):
    monkeypatch.setattr(settings, "HAMI_TELEGRAM_OWNER_DIGEST_ENABLED", False)
    result = owner_control.send_daily_owner_digest(db)
    assert result["status"] == "skipped" and result["reason"] == "owner_telegram_digest_disabled"
    assert db.query(models.IntegrationDelivery).filter_by(integration_name="telegram_owner").count() == 0

def test_resume_ask_fails_closed_while_halted(db, monkeypatch):
    configure(monkeypatch); sent = fake_send(monkeypatch)
    state = owner_control.set_safe_mode(db, "halt_command"); was_live = settings.FORGE_BOT_LIVE
    with pytest.raises(owner_control.OwnerControlError, match="telegram_ask_delivery_failed"):
        owner_control.create_resume_ask(db)
    db.refresh(state)
    ask = db.query(models.OpHamiOwnerAsk).one()
    assert ask.status == "NOTIFIED_FAILED" and ask.code_hash is None
    assert sent == []
    assert state.safe_mode_enabled is True
    assert settings.FORGE_BOT_LIVE is was_live
