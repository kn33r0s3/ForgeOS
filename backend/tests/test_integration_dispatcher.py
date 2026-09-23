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
