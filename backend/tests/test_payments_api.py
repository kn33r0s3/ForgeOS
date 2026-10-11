from decimal import Decimal

from fastapi.testclient import TestClient

from app.api import payments
from app.config import settings
from app.main import app


client = TestClient(app)


def _callback_payload():
    return {
        "status": "COMPLETE",
        "total_amount": "100.00",
        "transaction_uuid": "order-123",
        "product_code": "MERCHANT",
        "transaction_code": "TX-123",
    }


def test_esewa_browser_callback_needs_no_owner_key_and_checks_provider_status(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "")
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "MERCHANT")
    monkeypatch.setattr(payments.nepal_payments, "verify_esewa_response", lambda data: _callback_payload())
    seen = {}

    def lookup(**kwargs):
        seen.update(kwargs)
        return {
            "status": "COMPLETE",
            "totalAmount": 100,
            "scd": "MERCHANT",
            "refId": "PROVIDER-REF",
        }

    monkeypatch.setattr(payments.nepal_payments, "esewa_lookup", lookup)
    response = client.get("/api/payments/esewa/callback", params={"data": "signed-return-payload-12345"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "esewa"
    assert body["verified"] is True
    assert body["response"]["transaction_uuid"] == "order-123"
    assert body["response"]["total_amount"] == "100.00"
    assert body["response"]["provider_reference"] == "PROVIDER-REF"
    assert seen == {"amount_npr": Decimal("100.00"), "transaction_uuid": "order-123"}


def test_esewa_browser_callback_does_not_verify_wrong_amount_or_merchant(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "")
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "MERCHANT")
    monkeypatch.setattr(payments.nepal_payments, "verify_esewa_response", lambda data: _callback_payload())
    monkeypatch.setattr(
        payments.nepal_payments,
        "esewa_lookup",
        lambda **kwargs: {"status": "COMPLETE", "totalAmount": 99, "scd": "MERCHANT"},
    )
    response = client.get("/api/payments/esewa/callback", params={"data": "signed-return-payload-12345"})
    assert response.status_code == 200
    assert response.json()["verified"] is False


def test_esewa_browser_callback_does_not_call_lookup_for_non_complete_status(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "")
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "MERCHANT")
    payload = {**_callback_payload(), "status": "PENDING"}
    monkeypatch.setattr(payments.nepal_payments, "verify_esewa_response", lambda data: payload)

    def unexpected_lookup(**kwargs):
        raise AssertionError("non-complete callback must not be presented as a successful payment")

    monkeypatch.setattr(payments.nepal_payments, "esewa_lookup", unexpected_lookup)
    response = client.get("/api/payments/esewa/callback", params={"data": "signed-return-payload-12345"})
    assert response.status_code == 200
    assert response.json()["verified"] is False
