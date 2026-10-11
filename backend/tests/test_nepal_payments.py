def test_esewa_v2_status_default_matches_the_official_v2_endpoint():
    assert DEFAULT_ESEWA_V2_STATUS_URL == "https://epay.esewa.com.np/api/epay/transaction/status/"
    assert Settings.model_fields["ESEWA_STATUS_URL"].default == DEFAULT_ESEWA_V2_STATUS_URL


import base64
import json
import hashlib
import hmac
from decimal import Decimal
import pytest

from app.config import DEFAULT_ESEWA_V2_STATUS_URL, Settings, settings
from app.services import nepal_payments


def test_esewa_checkout_uses_official_hmac_fields(monkeypatch):
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "MERCHANT")
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "secret")
    result = nepal_payments.esewa_checkout(
        amount_npr=Decimal("100.00"), transaction_uuid="order-123",
        success_url="https://example.com/success", failure_url="https://example.com/failure",
    )
    signed = "total_amount=100.00,transaction_uuid=order-123,product_code=MERCHANT"
    expected = base64.b64encode(hmac.new(b"secret", signed.encode(), hashlib.sha256).digest()).decode()
    assert result["signature"] == expected
    assert result["signed_field_names"] == "total_amount,transaction_uuid,product_code"
    assert result["total_amount"] == "100.00"


def test_missing_provider_credentials_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "")
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="ESEWA_MERCHANT_CODE"):
        nepal_payments.esewa_checkout(
            amount_npr=10, transaction_uuid="order-123",
            success_url="https://example.com/success", failure_url="https://example.com/failure",
        )


def test_khalti_amount_is_npr_to_paisa(monkeypatch):
    monkeypatch.setattr(settings, "KHALTI_SECRET_KEY", "secret")
    monkeypatch.setattr(nepal_payments, "_post_json", lambda url, payload, headers: {"url": url, "payload": payload, "headers": headers})
    result = nepal_payments.khalti_initiate(
        amount_npr=Decimal("125.50"), purchase_order_id="order-123", purchase_order_name="Test offer",
        return_url="https://example.com/return", website_url="https://example.com/",
    )
    assert result["payload"]["amount"] == 12550
    assert result["headers"]["Authorization"] == "Key secret"


def test_esewa_callback_rejects_tampering(monkeypatch):
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "secret")
    payload = {"status": "COMPLETE", "total_amount": "100.00", "transaction_uuid": "order-123", "product_code": "MERCHANT", "signed_field_names": "status,total_amount,transaction_uuid,product_code,signed_field_names", "signature": "bad"}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    with pytest.raises(ValueError, match="signature mismatch"):
        nepal_payments.verify_esewa_response(encoded)



def test_esewa_callback_requires_signing_the_transaction_identity(monkeypatch):
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "secret")
    payload = {
        "status": "COMPLETE",
        "total_amount": "100.00",
        "transaction_uuid": "order-123",
        "product_code": "MERCHANT",
        "signed_field_names": "status,total_amount,product_code,signed_field_names",
        "signature": "unused",
    }
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    with pytest.raises(ValueError, match="invalid eSewa callback payload"):
        nepal_payments.verify_esewa_response(encoded)


def test_esewa_callback_verifies_official_signed_fields(monkeypatch):
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "secret")
    fields = "transaction_code,status,total_amount,transaction_uuid,product_code,signed_field_names"
    payload = {
        "transaction_code": "TX-123",
        "status": "COMPLETE",
        "total_amount": "100.00",
        "transaction_uuid": "order-123",
        "product_code": "MERCHANT",
        "signed_field_names": fields,
    }
    signed = ",".join(f"{field}={payload[field]}" for field in fields.split(","))
    payload["signature"] = base64.b64encode(
        hmac.new(b"secret", signed.encode(), hashlib.sha256).digest()
    ).decode()
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    assert nepal_payments.verify_esewa_response(encoded) == payload
