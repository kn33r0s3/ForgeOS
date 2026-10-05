import json
import urllib.error
from unittest.mock import patch, MagicMock

import pytest

from app.config import settings
from app.services import integration_outbox, integration_dispatcher
from app.models import IntegrationDelivery


def test_twilio_fails_closed_without_credentials(db, monkeypatch):
    # Ensure credentials are empty
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    
    delivery = integration_outbox.enqueue(
        db,
        integration_name="twilio",
        operation="send_sms",
        idempotency_key="test_twilio_1",
        request={"to": "+1234567890", "body": "Test message"}
    )
    
    # Process the queue
    attempted = integration_dispatcher.dispatch_pending_deliveries(db, limit=1)
    assert attempted == 1
    
    # Check the result
    db.refresh(delivery)
    assert delivery.status == "FAILED"  # Permanent errors fail closed immediately
    assert delivery.attempts == 1
    assert "credentials are not configured" in delivery.last_error


def test_twilio_success_persists_sid(db, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_FAKE")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "FAKE_TOKEN")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+19999999999")
    
    delivery = integration_outbox.enqueue(
        db,
        integration_name="twilio",
        operation="send_sms",
        idempotency_key="test_twilio_2",
        request={"to": "+1234567890", "body": "Test message"}
    )
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"sid": "SM123456", "status": "queued"}'
        attempted = integration_dispatcher.dispatch_pending_deliveries(db, limit=1)
        assert attempted == 1
        
        # Verify API request
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "https://api.twilio.com/2010-04-01/Accounts/AC_FAKE/Messages.json"
        
    db.refresh(delivery)
    assert delivery.status == "SUCCEEDED"
    assert delivery.attempts == 0
    assert delivery.last_error is None
    
    resp_json = json.loads(delivery.response_json)
    assert resp_json["sid"] == "SM123456"


def test_twilio_http_error(db, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_FAKE")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "FAKE_TOKEN")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+19999999999")
    
    delivery = integration_outbox.enqueue(
        db,
        integration_name="twilio",
        operation="send_sms",
        idempotency_key="test_twilio_3",
        request={"to": "+1234567890", "body": "Test message"}
    )
    
    mock_error = urllib.error.HTTPError(
        url="", code=400, msg="Bad Request", hdrs={}, fp=None
    )
    mock_error.read = MagicMock(return_value=b'{"message": "Invalid phone number"}')
    
    with patch("urllib.request.urlopen", side_effect=mock_error):
        integration_dispatcher.dispatch_pending_deliveries(db, limit=1)
        
    db.refresh(delivery)
    assert delivery.status == "FAILED"
    assert delivery.attempts == 1
    assert "HTTP 400" in delivery.last_error
    assert "Invalid phone number" in delivery.last_error


def test_malformed_response_marks_failure(db, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_FAKE")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "FAKE_TOKEN")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+19999999999")
    
    delivery = integration_outbox.enqueue(
        db,
        integration_name="twilio",
        operation="send_sms",
        idempotency_key="test_twilio_4",
        request={"to": "+1234567890", "body": "Test message"}
    )
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"ok": true}'  # missing 'sid'
        integration_dispatcher.dispatch_pending_deliveries(db, limit=1)
        
    db.refresh(delivery)
    assert delivery.status == "FAILED"
    assert "missing message SID" in delivery.last_error


def test_smtp_email_action_uses_real_outbox(db):
    from app.services import action_engine

    action = action_engine.propose_action(
        db,
        objective="Notify a participant about the approved workflow",
        action_type="smtp_email",
        parameters={
            "to": "ops@example.com",
            "subject": "Approved workflow",
            "body": "The workflow has been authorized and this is a real outbound email.",
        },
    )
    action_engine.approve_action(db, action.id)

    def fake_dispatch(db_session, delivery_id):
        row = db_session.get(IntegrationDelivery, delivery_id)
        row.status = "ACCEPTED_BY_SMTP"
        row.response_json = json.dumps({"message_id": "msg-123", "status": "ACCEPTED_BY_SMTP"})
        db_session.commit()
        db_session.refresh(row)
        return row

    with patch("app.services.integration_dispatcher.dispatch_single_delivery", side_effect=fake_dispatch):
        executed = action_engine.start_and_execute_action(db, action.id)

    assert executed.status == "SUCCEEDED"
    assert executed.verification_state == "VERIFIED_SUCCESS"
    assert "adapter execution only" in executed.execution_result
    assert executed.external_ref is not None

    delivery_rows = db.query(IntegrationDelivery).filter_by(integration_name="smtp").all()
    assert len(delivery_rows) == 1
    assert delivery_rows[0].status == "ACCEPTED_BY_SMTP"
    assert "msg-123" in (delivery_rows[0].response_json or "")


def test_twilio_429_rate_limit_retries(db, monkeypatch):
    """HTTP 429 from Twilio is transient (retried), not a permanent failure."""
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_FAKE")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "FAKE_TOKEN")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+19999999999")

    delivery = integration_outbox.enqueue(
        db,
        integration_name="twilio",
        operation="send_sms",
        idempotency_key="test_twilio_429",
        request={"to": "+1234567890", "body": "Test message"}
    )

    mock_error = urllib.error.HTTPError(
        url="", code=429, msg="Too Many Requests", hdrs={}, fp=None
    )
    mock_error.read = MagicMock(return_value=b'{"message": "Rate limit exceeded"}')

    with patch("urllib.request.urlopen", side_effect=mock_error):
        integration_dispatcher.dispatch_pending_deliveries(db, limit=1)

    db.refresh(delivery)
    assert delivery.status == "QUEUED"  # retried, not FAILED
    assert delivery.attempts == 1
    assert delivery.next_attempt_at is not None
    assert "HTTP 429" in delivery.last_error


def test_corrupt_request_json_fails_permanent(db, monkeypatch):
    """Corrupt request_json can never succeed; fail closed on attempt 1."""
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_FAKE")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "FAKE_TOKEN")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+19999999999")

    delivery = IntegrationDelivery(
        integration_name="twilio",
        operation="send_sms",
        idempotency_key="test_twilio_corrupt_json",
        request_json="{not valid json",
        status="QUEUED",
        attempts=0,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    integration_dispatcher.dispatch_pending_deliveries(db, limit=1)

    db.refresh(delivery)
    assert delivery.status == "FAILED"  # permanent, no pointless retries
    assert delivery.attempts == 1
    assert "not valid JSON" in delivery.last_error
