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



def test_payment_status_is_owner_protected_configuration_only_and_never_contacts_providers(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "private-merchant-code")
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "private-esewa-signing-secret")
    monkeypatch.setattr(settings, "KHALTI_SECRET_KEY", "private-khalti-secret")

    def unexpected_provider_call(*args, **kwargs):
        raise AssertionError("configuration status must not contact a payment provider")

    monkeypatch.setattr(payments.nepal_payments, "esewa_checkout", unexpected_provider_call)
    monkeypatch.setattr(payments.nepal_payments, "esewa_lookup", unexpected_provider_call)
    monkeypatch.setattr(payments.nepal_payments, "khalti_initiate", unexpected_provider_call)
    monkeypatch.setattr(payments.nepal_payments, "khalti_lookup", unexpected_provider_call)

    denied = client.get("/api/payments/status")
    assert denied.status_code == 401

    response = client.get("/api/payments/status", headers={"X-API-Key": "test-owner-key"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "configuration_only"
    assert body["provider_connectivity_checked"] is False
    assert body["transaction_state_checked"] is False
    assert body["providers"]["esewa"] == {
        "merchant_code_configured": True,
        "signing_secret_configured": True,
        "required_credentials_present": True,
    }
    assert body["providers"]["khalti"] == {
        "secret_key_configured": True,
        "required_credentials_present": True,
    }
    assert all(secret not in response.text for secret in (
        "private-merchant-code", "private-esewa-signing-secret", "private-khalti-secret"
    ))

    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "")
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "")
    monkeypatch.setattr(settings, "KHALTI_SECRET_KEY", "")
    incomplete = client.get("/api/payments/status", headers={"X-API-Key": "test-owner-key"})
    assert incomplete.status_code == 200
    flags = incomplete.json()["providers"]
    assert flags["esewa"]["required_credentials_present"] is False
    assert flags["khalti"]["required_credentials_present"] is False



def test_public_intent_reconciliation_endpoint_is_no_store_and_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-public-reconciliation-key")
    monkeypatch.setattr(
        payments.forge_bot_privacy, "consume_rate_limited_request", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        payments.payment_intent_engine,
        "reconcile_public_intent",
        lambda _db, public_ref: {
            "intent": public_ref,
            "offer_id": 5,
            "provider": "khalti",
            "status": "CANCELLED",
            "retry_allowed": True,
            "recovery": {
                "checked": True,
                "retry_allowed": True,
                "provider_status": "Expired",
                "message": "Provider confirmed a terminal attempt.",
            },
        },
    )
    response = client.post("/api/payments/intent/public-recovery-ref-0123456789/reconcile")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["retry_allowed"] is True


def test_public_intent_reconciliation_conflicts_require_owner_review(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-public-reconciliation-key")
    monkeypatch.setattr(
        payments.forge_bot_privacy, "consume_rate_limited_request", lambda *args, **kwargs: True
    )
    def conflict(_db, public_ref):
        raise payments.payment_intent_engine.PaymentReconciliationRequired(
            "Provider conflicts with this terminal state; owner reconciliation is required."
        )
    monkeypatch.setattr(payments.payment_intent_engine, "reconcile_public_intent", conflict)
    response = client.post("/api/payments/intent/public-recovery-ref-0123456789/reconcile")
    assert response.status_code == 409
    assert "owner reconciliation is required" in response.json()["detail"]


def test_public_checkout_reconciliation_by_key_uses_existing_key_and_no_store(monkeypatch):
    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-public-reconciliation-key")
    monkeypatch.setattr(
        payments.forge_bot_privacy, "consume_rate_limited_request", lambda *args, **kwargs: True
    )
    observed = {}
    def reconcile(_db, *, product_id, idempotency_key):
        observed.update(product_id=product_id, idempotency_key=idempotency_key)
        return {
            "intent": None,
            "offer_id": product_id,
            "provider": None,
            "status": "NO_ATTEMPT",
            "retry_allowed": True,
            "recovery": {
                "checked": False,
                "retry_allowed": True,
                "provider_status": None,
                "message": "No attempt was persisted.",
            },
        }
    monkeypatch.setattr(payments.payment_intent_engine, "reconcile_checkout_by_key", reconcile)
    key = "public-recovery-idempotency-key-123456"
    response = client.post(
        "/api/payments/products/5/checkout/reconcile",
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert observed == {"product_id": 5, "idempotency_key": key}
    assert response.json()["retry_allowed"] is True


def test_khalti_callback_reports_owner_reconciliation_for_refund_conflict(monkeypatch):
    def reconciliation_required(_db, **kwargs):
        raise payments.payment_intent_engine.PaymentReconciliationRequired(
            "Khalti reports a refund for a previously verified payment; owner reconciliation is required."
        )

    monkeypatch.setattr(payments.payment_intent_engine, "finalize_khalti_callback", reconciliation_required)
    response = client.get(
        "/api/payments/khalti/callback",
        params={
            "intent": "khalti-refund-callback-intent-123456",
            "pidx": "khalti-refund-pidx-123456",
        },
    )
    assert response.status_code == 409
    assert "Owner reconciliation is required" in response.json()["detail"]
    assert "existing revenue record has not been changed" in response.json()["detail"]




def test_esewa_callback_reports_owner_reconciliation_for_verified_refund(monkeypatch):
    def reconciliation_required(_db, **kwargs):
        raise payments.payment_intent_engine.PaymentReconciliationRequired(
            "eSewa reports a refund for a previously verified payment; owner reconciliation is required."
        )

    monkeypatch.setattr(
        payments.payment_intent_engine, "finalize_esewa_callback", reconciliation_required
    )
    response = client.get(
        "/api/payments/esewa/callback",
        params={
            "data": "signed-esewa-refund-callback-payload-123456",
            "intent": "esewa-refund-callback-intent-123456789",
        },
    )
    assert response.status_code == 409
    assert "eSewa reports a refund" in response.json()["detail"]
    assert "Owner reconciliation is required" in response.json()["detail"]
    assert "existing revenue record has not been changed" in response.json()["detail"]
