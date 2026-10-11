from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app import models
from app.config import settings
from app.services import payment_intent_engine, product_engine, orchestrator, nepal_payments, world_graph


def _published_product(db):
    world_graph.seed_core_types(db)
    opportunity = models.Opportunity(
        problem="TEST: independent shops lose time on repeated status calls",
        target_customer="TEST: independent repair shops",
        solution="TEST: status visibility service",
        score=70.0,
        status="validated",
    )
    db.add(opportunity)
    db.flush()
    product = models.Product(
        opportunity_id=opportunity.id,
        name="TEST: shop status service",
        offer="TEST: one-time workflow setup",
        target_customer="TEST: independent shops",
        pricing="NPR 5000 one-time",
        mvp_scope="TEST: documented setup session",
        status="launched",
        launch_state="public",
        approval_status="APPROVED",
        approved_at=datetime.now(timezone.utc),
        offer_brief_json=json.dumps({"kind": "test-only", "fixed_price": {"currency": "NPR"}}),
        data_scope="REAL",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_public_checkout_is_disabled_by_default_or_setting(monkeypatch, db):
    monkeypatch.setattr(settings, "FORGEOS_PUBLIC_CHECKOUT_ENABLED", False)
    with pytest.raises(RuntimeError, match="disabled"):
        payment_intent_engine.create_checkout(
            db, product_id=9999, provider="esewa", idempotency_key="checkout-disabled-regression-key"
        )
    assert db.query(models.OpPaymentIntent).count() == 0



def test_legacy_payment_intent_schema_recreates_fulfillment_timestamp_index(db):
    """The owner queue's new timestamp index must be repaired on existing databases."""
    from sqlalchemy import inspect, text
    from app.migrations import run_migrations

    engine = db.get_bind()
    index_name = "ix_op_payment_intents_fulfilled_at"
    with engine.begin() as connection:
        connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))

    before = {item["name"] for item in inspect(engine).get_indexes("op_payment_intents")}
    assert index_name not in before

    applied = run_migrations(engine)
    assert f"CREATE INDEX {index_name} ON op_payment_intents (fulfilled_at)" in applied
    after = {item["name"] for item in inspect(engine).get_indexes("op_payment_intents")}
    assert index_name in after

def test_esewa_checkout_persists_one_intent_and_idempotent_retry_reuses_it(db, monkeypatch):
    product = _published_product(db)
    monkeypatch.setattr(settings, "FORGEOS_PUBLIC_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "TEST-MERCHANT")
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "test-signing-secret")
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-checkout-rate-limit-key")
    monkeypatch.setattr(orchestrator, "validation_counts", lambda *args: (5, 3))
    calls = []

    def checkout(**kwargs):
        calls.append(kwargs)
        return {
            "form_url": "https://epay.esewa.com.np/api/epay/main/v2/form",
            "amount": "5000.00",
            "total_amount": "5000.00",
            "transaction_uuid": kwargs["transaction_uuid"],
            "product_code": "TEST-MERCHANT",
            "success_url": kwargs["success_url"],
            "failure_url": kwargs["failure_url"],
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": "test-signature",
        }

    monkeypatch.setattr(nepal_payments, "esewa_checkout", checkout)
    first = payment_intent_engine.create_checkout(
        db, product_id=product.id, provider="esewa",
        idempotency_key="same-logical-checkout-key-123",
    )
    second = payment_intent_engine.create_checkout(
        db, product_id=product.id, provider="esewa",
        idempotency_key="same-logical-checkout-key-123",
    )
    assert first["intent"] == second["intent"]
    assert second["reused"] is True
    assert first["checkout"]["type"] == "form_post"
    assert first["amount_paisa"] == 500000
    assert db.query(models.OpPaymentIntent).count() == 1
    assert calls[0]["transaction_uuid"] == calls[1]["transaction_uuid"]



def test_idempotency_key_cannot_start_a_second_provider_for_the_same_product(db, monkeypatch):
    product = _published_product(db)
    monkeypatch.setattr(settings, "FORGEOS_PUBLIC_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "TEST-MERCHANT")
    monkeypatch.setattr(settings, "ESEWA_SECRET_KEY", "test-signing-secret")
    monkeypatch.setattr(settings, "KHALTI_SECRET_KEY", "test-khalti-secret")
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-checkout-rate-limit-key")
    monkeypatch.setattr(orchestrator, "validation_counts", lambda *args: (5, 3))
    monkeypatch.setattr(nepal_payments, "esewa_checkout", lambda **kwargs: {
        "form_url": "https://epay.esewa.com.np/api/epay/main/v2/form",
        "amount": "5000.00",
        "total_amount": "5000.00",
        "transaction_uuid": kwargs["transaction_uuid"],
        "product_code": "TEST-MERCHANT",
        "success_url": kwargs["success_url"],
        "failure_url": kwargs["failure_url"],
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": "test-signature",
    })
    khalti_calls = []
    monkeypatch.setattr(nepal_payments, "khalti_initiate", lambda **kwargs: khalti_calls.append(kwargs) or {
        "pidx": "test-pidx-123456789",
        "payment_url": "https://test-pay.khalti.com/?pidx=test-pidx-123456789",
    })

    key = "cross-provider-idempotency-key-123"
    first = payment_intent_engine.create_checkout(
        db, product_id=product.id, provider="esewa", idempotency_key=key,
    )
    assert first["provider"] == "esewa"
    with pytest.raises(ValueError, match="conflicts"):
        payment_intent_engine.create_checkout(
            db, product_id=product.id, provider="khalti", idempotency_key=key,
        )
    assert khalti_calls == []
    assert db.query(models.OpPaymentIntent).count() == 1

def test_public_app_url_rejects_nested_paths(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://haminp.vercel.app/not-the-origin")
    with pytest.raises(RuntimeError, match="HTTPS origin"):
        payment_intent_engine._public_origin()


def test_provider_checkout_redirects_must_use_approved_hosts(monkeypatch):
    intent = models.OpPaymentIntent(
        public_ref="redirect-guard-test-reference-123456",
        product_id=1,
        provider="esewa",
        status="CREATED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="hami-esewa-redirect-test-123456",
        idempotency_key_hash="e" * 64,
        data_scope="REAL",
    )
    monkeypatch.setattr(nepal_payments, "esewa_checkout", lambda **kwargs: {
        "form_url": "https://epay.esewa.com.np.attacker.example/api/epay/main/v2/form",
    })
    with pytest.raises(RuntimeError, match="approved HTTPS eSewa"):
        payment_intent_engine._checkout_details(intent)
    intent.provider = "khalti"
    intent.checkout_url = "https://khalti.com.attacker.example/pay"
    with pytest.raises(RuntimeError, match="approved HTTPS Khalti"):
        payment_intent_engine._checkout_details(intent)


def test_khalti_minimum_amount_rejected_before_intent_creation(db, monkeypatch):
    product = _published_product(db)
    product.pricing = "NPR 5 one-time"
    db.commit()
    monkeypatch.setattr(settings, "FORGEOS_PUBLIC_CHECKOUT_ENABLED", True)
    monkeypatch.setattr(settings, "KHALTI_SECRET_KEY", "test-khalti-secret")
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-checkout-rate-limit-key")
    monkeypatch.setattr(orchestrator, "validation_counts", lambda *args: (5, 3))
    with pytest.raises(ValueError, match="minimum total of NPR 10"):
        payment_intent_engine.create_checkout(
            db, product_id=product.id, provider="khalti",
            idempotency_key="khalti-minimum-amount-key-123",
        )
    assert db.query(models.OpPaymentIntent).count() == 0


def test_esewa_server_lookup_verifies_payment_then_owner_fulfillment_records_revenue(db, monkeypatch):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="public-test-ref-0123456789ABCDEFG",
        product_id=product.id,
        provider="esewa",
        status="INITIATED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="hami-esewa-test-order-123456",
        idempotency_key_hash="a" * 64,
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "TEST-MERCHANT")
    payload = {
        "status": "COMPLETE",
        "total_amount": "5000.00",
        "transaction_uuid": intent.merchant_order_id,
        "product_code": "TEST-MERCHANT",
        "transaction_code": "TEST-CALLBACK",
    }
    monkeypatch.setattr(nepal_payments, "verify_esewa_response", lambda _: payload)
    monkeypatch.setattr(
        nepal_payments,
        "esewa_lookup",
        lambda **kwargs: {
            "status": "COMPLETE",
            "totalAmount": "5000.00",
            "scd": "TEST-MERCHANT",
            "refId": "TEST-ESewa-Receipt-001",
        },
    )

    result = payment_intent_engine.finalize_esewa_callback(
        db, public_ref=intent.public_ref, encoded_data="test-signed-payload"
    )
    assert result.status == "VERIFIED"
    assert result.outcome_id is None
    assert result.fulfilled_at is None
    assert db.query(models.Outcome).filter_by(
        product_id=product.id, outcome_type="ACTUAL_REVENUE", unit="NPR"
    ).count() == 0
    before = product_engine.product_summary(db, product)
    assert before["actual_revenue_by_currency"] == {"USD": 0.0, "NPR": 0.0}

    retried = payment_intent_engine.finalize_esewa_callback(
        db, public_ref=intent.public_ref, encoded_data="test-signed-payload"
    )
    assert retried.id == intent.id
    assert retried.outcome_id is None

    fulfilled = payment_intent_engine.fulfill_verified_intent(db, intent.id)
    assert fulfilled["fulfilled"] is True
    assert fulfilled["outcome_id"] is not None
    assert fulfilled["customer_event_id"] is not None
    outcome = db.get(models.Outcome, fulfilled["outcome_id"])
    assert outcome.outcome_type == "ACTUAL_REVENUE"
    assert outcome.actual_value == 5000.0
    assert outcome.unit == "NPR"
    assert outcome.source_kind == "REAL"
    assert outcome.verification_state == "VERIFIED"
    customer_event = db.get(models.CustomerEvent, fulfilled["customer_event_id"])
    assert customer_event.stage == "paid_customer"
    assert customer_event.event_type == "purchase"
    assert customer_event.outcome_id == outcome.id
    assert customer_event.contact_identifier is None
    after = product_engine.product_summary(db, product)
    assert after["actual_revenue"] == 0.0
    assert after["actual_revenue_by_currency"] == {"USD": 0.0, "NPR": 5000.0}

    retried_fulfillment = payment_intent_engine.fulfill_verified_intent(db, intent.id)
    assert retried_fulfillment["outcome_id"] == fulfilled["outcome_id"]
    assert db.query(models.Outcome).filter_by(
        product_id=product.id, outcome_type="ACTUAL_REVENUE", unit="NPR"
    ).count() == 1
    assert db.query(models.CustomerEvent).filter_by(outcome_id=fulfilled["outcome_id"]).count() == 1


@pytest.mark.parametrize("terminal_status", ["VERIFIED", "FAILED", "CANCELLED", "DISPUTED", "REFUNDED"])
def test_terminal_payment_intents_cannot_be_reopened(db, terminal_status):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="terminal-test-" + terminal_status.lower() + "-0123456789",
        product_id=product.id,
        provider="esewa",
        status=terminal_status,
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="terminal-order-" + terminal_status.lower() + "-012345",
        idempotency_key_hash=(terminal_status[0].lower() * 64),
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    with pytest.raises(ValueError, match="terminal"):
        payment_intent_engine._transition(db, intent, "PENDING")
    db.refresh(intent)
    assert intent.status == terminal_status


def test_unverified_payment_intent_cannot_be_marked_fulfilled(db):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="pending-test-intent-0123456789ABC",
        product_id=product.id,
        provider="esewa",
        status="INITIATED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="pending-test-order-123456",
        idempotency_key_hash="c" * 64,
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    with pytest.raises(ValueError, match="provider-verified"):
        payment_intent_engine.fulfill_verified_intent(db, intent.id)
    assert db.query(models.Outcome).filter_by(product_id=product.id, outcome_type="ACTUAL_REVENUE").count() == 0


def test_khalti_refunded_flag_does_not_become_pending(db, monkeypatch):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="khalti-refund-test-intent-012345",
        product_id=product.id,
        provider="khalti",
        status="INITIATED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="khalti-refund-order-123456",
        idempotency_key_hash="d" * 64,
        provider_payment_id="khalti-pidx-refund-test-123456",
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    monkeypatch.setattr(nepal_payments, "khalti_lookup", lambda **kwargs: {
        "pidx": intent.provider_payment_id,
        "status": "Completed",
        "total_amount": intent.amount_paisa,
        "transaction_id": "khalti-refunded-tx",
        "refunded": True,
    })
    result = payment_intent_engine.finalize_khalti_callback(
        db, public_ref=intent.public_ref, pidx=intent.provider_payment_id
    )
    assert result.status == "REFUNDED"
    assert result.outcome_id is None
    assert db.query(models.Outcome).filter_by(product_id=product.id, outcome_type="ACTUAL_REVENUE").count() == 0


def test_khalti_refund_after_verified_fulfillment_requires_reconciliation_without_mutation(db, monkeypatch):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="khalti-refund-after-verified-intent-012345",
        product_id=product.id,
        provider="khalti",
        status="VERIFIED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="khalti-refund-after-verified-order-123456",
        idempotency_key_hash="f" * 64,
        provider_payment_id="khalti-pidx-after-verified-123456",
        provider_reference="KHALTI-ORIGINAL-RECEIPT",
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)

    fulfilled = payment_intent_engine.fulfill_verified_intent(db, intent.id)
    original_outcome_id = fulfilled["outcome_id"]
    original_fulfilled_at = fulfilled["fulfilled_at"]
    original_outcome = db.get(models.Outcome, original_outcome_id)
    assert original_outcome.actual_value == 5000.0
    assert original_outcome.unit == "NPR"
    assert original_outcome.verification_state == "VERIFIED"

    monkeypatch.setattr(nepal_payments, "khalti_lookup", lambda **kwargs: {
        "pidx": intent.provider_payment_id,
        "status": "Completed",
        "total_amount": intent.amount_paisa,
        "transaction_id": "KHALTI-REFUND-RECEIPT",
        "refunded": True,
    })
    with pytest.raises(payment_intent_engine.PaymentReconciliationRequired, match="owner reconciliation is required"):
        payment_intent_engine.finalize_khalti_callback(
            db, public_ref=intent.public_ref, pidx=intent.provider_payment_id
        )

    db.refresh(intent)
    db.refresh(original_outcome)
    assert intent.status == "VERIFIED"
    assert intent.outcome_id == original_outcome_id
    assert intent.fulfilled_at.isoformat() == original_fulfilled_at
    assert original_outcome.actual_value == 5000.0
    assert original_outcome.unit == "NPR"
    assert original_outcome.source_kind == "REAL"
    assert original_outcome.verification_state == "VERIFIED"
    assert db.query(models.Outcome).filter_by(
        product_id=product.id, outcome_type="ACTUAL_REVENUE", unit="NPR"
    ).count() == 1

def test_esewa_amount_mismatch_is_disputed_without_revenue(db, monkeypatch):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="public-test-ref-amount-0123456789",
        product_id=product.id,
        provider="esewa",
        status="INITIATED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="hami-esewa-test-order-mismatch",
        idempotency_key_hash="b" * 64,
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "TEST-MERCHANT")
    monkeypatch.setattr(nepal_payments, "verify_esewa_response", lambda _: {
        "status": "COMPLETE",
        "total_amount": "4999.00",
        "transaction_uuid": intent.merchant_order_id,
        "product_code": "TEST-MERCHANT",
    })
    with pytest.raises(ValueError, match="does not match"):
        payment_intent_engine.finalize_esewa_callback(
            db, public_ref=intent.public_ref, encoded_data="test-signed-payload"
        )
    db.refresh(intent)
    assert intent.status == "DISPUTED"
    assert db.query(models.Outcome).filter_by(product_id=product.id, outcome_type="ACTUAL_REVENUE").count() == 0



def _fulfilled_esewa_intent_for_refund_test(db):
    product = _published_product(db)
    intent = models.OpPaymentIntent(
        public_ref="esewa-refund-test-intent-0123456789",
        product_id=product.id,
        provider="esewa",
        status="VERIFIED",
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id="hami-esewa-refund-test-order-123456",
        idempotency_key_hash="9" * 64,
        provider_reference="ESEWA-ORIGINAL-RECEIPT",
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    result = payment_intent_engine.fulfill_verified_intent(db, intent.id)
    assert result["fulfilled"] is True
    return product, intent, result


def test_esewa_signed_refund_after_verified_fulfillment_requires_owner_reconciliation(db, monkeypatch):
    product, intent, fulfilled = _fulfilled_esewa_intent_for_refund_test(db)
    outcome_id = fulfilled["outcome_id"]
    original_fulfilled_at = fulfilled["fulfilled_at"]
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "TEST-MERCHANT")
    monkeypatch.setattr(nepal_payments, "verify_esewa_response", lambda _: {
        "status": "FULL_REFUND",
        "total_amount": "5000.00",
        "transaction_uuid": intent.merchant_order_id,
        "product_code": "TEST-MERCHANT",
        "transaction_code": "ESEWA-REFUND-CALLBACK",
    })

    with pytest.raises(
        payment_intent_engine.PaymentReconciliationRequired,
        match="eSewa reports a refund",
    ):
        payment_intent_engine.finalize_esewa_callback(
            db, public_ref=intent.public_ref, encoded_data="test-signed-refund-payload"
        )

    db.refresh(intent)
    outcome = db.get(models.Outcome, outcome_id)
    assert intent.status == "VERIFIED"
    assert intent.outcome_id == outcome_id
    assert intent.fulfilled_at.isoformat() == original_fulfilled_at
    assert outcome.actual_value == 5000.0
    assert outcome.unit == "NPR"
    assert outcome.source_kind == "REAL"
    assert outcome.verification_state == "VERIFIED"
    assert db.query(models.Outcome).filter_by(
        product_id=product.id, outcome_type="ACTUAL_REVENUE", unit="NPR"
    ).count() == 1


def test_esewa_lookup_refund_after_verified_fulfillment_requires_owner_reconciliation(db, monkeypatch):
    product, intent, fulfilled = _fulfilled_esewa_intent_for_refund_test(db)
    outcome_id = fulfilled["outcome_id"]
    original_fulfilled_at = fulfilled["fulfilled_at"]
    monkeypatch.setattr(settings, "ESEWA_MERCHANT_CODE", "TEST-MERCHANT")
    monkeypatch.setattr(nepal_payments, "verify_esewa_response", lambda _: {
        "status": "COMPLETE",
        "total_amount": "5000.00",
        "transaction_uuid": intent.merchant_order_id,
        "product_code": "TEST-MERCHANT",
        "transaction_code": "ESEWA-ORIGINAL-CALLBACK",
    })
    monkeypatch.setattr(nepal_payments, "esewa_lookup", lambda **kwargs: {
        "status": "PARTIAL_REFUND",
        "totalAmount": "5000.00",
        "scd": "TEST-MERCHANT",
        "refId": "ESEWA-ORIGINAL-RECEIPT",
    })

    with pytest.raises(
        payment_intent_engine.PaymentReconciliationRequired,
        match="eSewa reports a refund",
    ):
        payment_intent_engine.finalize_esewa_callback(
            db, public_ref=intent.public_ref, encoded_data="test-signed-complete-payload"
        )

    db.refresh(intent)
    outcome = db.get(models.Outcome, outcome_id)
    assert intent.status == "VERIFIED"
    assert intent.outcome_id == outcome_id
    assert intent.fulfilled_at.isoformat() == original_fulfilled_at
    assert outcome.actual_value == 5000.0
    assert outcome.unit == "NPR"
    assert outcome.source_kind == "REAL"
    assert outcome.verification_state == "VERIFIED"
    assert db.query(models.Outcome).filter_by(
        product_id=product.id, outcome_type="ACTUAL_REVENUE", unit="NPR"
    ).count() == 1
