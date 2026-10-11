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
            db, product_id=9999, provider="esewa", idempotency_key="test-key-0123456789"
        )
    assert db.query(models.OpPaymentIntent).count() == 0


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
            "form_url": "https://pay.example.test/esewa",
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


def test_esewa_server_lookup_creates_one_npr_verified_outcome(db, monkeypatch):
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
    assert result.outcome_id is not None
    outcome = db.get(models.Outcome, result.outcome_id)
    assert outcome.outcome_type == "ACTUAL_REVENUE"
    assert outcome.actual_value == 5000.0
    assert outcome.unit == "NPR"
    assert outcome.source_kind == "REAL"
    assert outcome.verification_state == "VERIFIED"

    retried = payment_intent_engine.finalize_esewa_callback(
        db, public_ref=intent.public_ref, encoded_data="test-signed-payload"
    )
    assert retried.id == intent.id
    assert db.query(models.Outcome).filter_by(
        product_id=product.id, outcome_type="ACTUAL_REVENUE", unit="NPR"
    ).count() == 1
    summary = product_engine.product_summary(db, product)
    assert summary["actual_revenue"] == 0.0
    assert summary["actual_revenue_by_currency"] == {"USD": 0.0, "NPR": 5000.0}


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
    result = payment_intent_engine.finalize_esewa_callback(
        db, public_ref=intent.public_ref, encoded_data="test-signed-payload"
    ) if False else None
    with pytest.raises(ValueError, match="does not match"):
        payment_intent_engine.finalize_esewa_callback(
            db, public_ref=intent.public_ref, encoded_data="test-signed-payload"
        )
    db.refresh(intent)
    assert intent.status == "DISPUTED"
    assert db.query(models.Outcome).filter_by(product_id=product.id, outcome_type="ACTUAL_REVENUE").count() == 0
