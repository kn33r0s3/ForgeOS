from datetime import datetime, timezone

import pytest

from app import models
from app.services import execution_engine, repair_shop



def make_real_item(db, *, suffix="one"):
    item = repair_shop.create_work_item(
        db,
        customer_name="TEST: repair shop",
        contact_identifier=None,
        consent_state="NOT_REQUIRED",
        asset_label=f"TEST-device-{suffix}",
        reported_problem="TEST: device does not boot",
        data_scope="REAL",
        actor="test",
        idempotency_key=f"repair-item-{suffix}-real",
    )
    repair_shop.create_triage(
        db, item.id,
        rationale="TEST: link a verified payment to the matching Opportunity",
        expected_outcome="TEST: payment and service outcome remain distinct",
        confidence=50,
        actor="test",
        idempotency_key=f"repair-triage-{suffix}",
    )
    return item


def make_payment_intent_for_item(db, item, *, suffix="one", status="VERIFIED"):
    product = models.Product(
        opportunity_id=item.opportunity_id,
        name=f"TEST: repair offer {suffix}",
        offer="TEST: repair-shop workflow",
        target_customer="TEST: independent repair shop",
        pricing="NPR 5000 one-time",
        mvp_scope="TEST-only provider-fulfillment regression",
        status="launched",
        launch_state="public",
        approval_status="APPROVED",
        approved_at=datetime.now(timezone.utc),
        data_scope="REAL",
    )
    db.add(product)
    db.flush()
    intent = models.OpPaymentIntent(
        public_ref=f"repair-{item.id}-{suffix}-public-reference",
        product_id=product.id,
        provider="esewa",
        status=status,
        amount_paisa=500000,
        currency="NPR",
        merchant_order_id=f"repair-{item.id}-{suffix}-merchant-order",
        idempotency_key_hash=("a" if suffix == "one" else "b") * 64,
        provider_reference=f"TEST-provider-reference-{suffix}" if status == "VERIFIED" else None,
        data_scope="REAL",
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    db.refresh(product)
    return product, intent


def test_repair_shop_tables_exist(db):
    assert db.query(models.Customer).count() == 0
    assert db.query(models.RepairWorkItem).count() == 0
    assert db.query(models.WorkItemEvent).count() == 0
    assert db.query(models.CustomerCommunication).count() == 0


def make_item(db, scope="SANDBOX"):
    return repair_shop.create_work_item(
        db,
        customer_name="Test Repair Shop",
        contact_identifier="sandbox-contact",
        consent_state="GRANTED",
        asset_label="Device-1",
        reported_problem="Does not start",
        data_scope=scope,
        actor="tester",
        idempotency_key="create-item-1" if scope == "SANDBOX" else "create-item-real",
    )


def test_work_item_and_evidence_are_audited(db):
    item = make_item(db)
    evidence = repair_shop.attach_evidence(
        db, item.id, content="Operator observed no power", source="manual", data_scope="SANDBOX", actor="tester",
        idempotency_key="evidence-1",
    )
    detail = repair_shop.get_work_item_detail(db, item.id)
    assert item.status == "EVIDENCE_CAPTURED"
    assert evidence.id in [entry.id for entry in detail["evidence"]]
    assert detail["events"][-1].previous_state == "INTAKE"
    assert detail["events"][-1].next_state == "EVIDENCE_CAPTURED"


def test_triage_reuses_existing_experiment_action_and_requires_approval(db):
    item = make_item(db)
    result = repair_shop.create_triage(
        db, item.id, rationale="Power failure needs human inspection", expected_outcome="Technician confirms fault", confidence=60, actor="tester",
    )
    action = result["experiment"]
    assert item.decision_id == result["decision"].id
    assert item.experiment_id == action.id
    assert action.requires_owner_approval is True
    assert action.approved_at is None
    assert execution_engine.start_action(db, action.id) is None


def test_customer_acceptance_is_not_payment(db):
    item = make_item(db)
    repair_shop.create_triage(db, item.id, rationale="Inspect", expected_outcome="Inspection complete", confidence=50)
    communication = repair_shop.propose_customer_status(db, item.id, body="We recommend an inspection.")
    repair_shop.approve_customer_status(db, communication.id)
    response = repair_shop.record_customer_response(db, communication.id, accepted=True, response="Approved inspection")
    assert response.status == "CUSTOMER_RESPONDED"
    assert db.query(models.Outcome).count() == 0


def test_failed_or_unverified_payment_cannot_be_actual_revenue(db):
    item = make_item(db)
    repair_shop.create_triage(db, item.id, rationale="Inspect", expected_outcome="Inspection complete", confidence=50)
    try:
        repair_shop.record_verified_payment(db, item.id, amount=100, unit="NPR", provider="", provider_reference="", data_scope="SANDBOX")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid payment evidence must fail")
    assert db.query(models.Outcome).count() == 0


def test_real_payment_cannot_be_verified_from_manual_provider_reference(db):
    item = make_item(db, scope="REAL")
    repair_shop.create_triage(
        db, item.id, rationale="Inspect", expected_outcome="Inspection complete", confidence=50
    )
    try:
        repair_shop.record_verified_payment(
            db,
            item.id,
            amount=100,
            unit="NPR",
            provider="esewa",
            provider_reference="caller-supplied-reference",
            data_scope="REAL",
        )
    except ValueError as exc:
        assert "provider-verified payment-intent" in str(exc)
    else:
        raise AssertionError("a caller-supplied reference must not create verified REAL revenue")
    assert db.query(models.Outcome).filter_by(data_scope="REAL").count() == 0


def test_verified_payment_is_not_successful_outcome(db):
    item = make_item(db)
    repair_shop.create_triage(db, item.id, rationale="Inspect", expected_outcome="Inspection complete", confidence=50)
    payment = repair_shop.record_verified_payment(
        db, item.id, amount=100, unit="NPR", provider="sandbox-provider", provider_reference="sandbox-ref", data_scope="SANDBOX", idempotency_key="payment-1",
    )
    assert payment.outcome_type == "ACTUAL_REVENUE"
    assert payment.verification_state == "VERIFIED"
    assert payment.success is None
    assert db.query(models.LearningEvent).count() == 0


def test_outcome_creates_learning_but_no_payment(db):
    item = make_item(db)
    repair_shop.create_triage(db, item.id, rationale="Inspect", expected_outcome="Inspection complete", confidence=50)
    outcome, learning = repair_shop.record_work_outcome(db, item.id, actual="Inspection completed", success=True, source="manual")
    assert outcome.outcome_type == "QUALITATIVE"
    assert learning.experiment_id == item.experiment_id
    assert db.query(models.Outcome).filter_by(outcome_type="ACTUAL_REVENUE").count() == 0


def test_duplicate_work_item_submission_is_idempotent(db):
    first = make_item(db)
    second = make_item(db)
    assert first.id == second.id
    assert db.query(models.Customer).count() == 1
    assert db.query(models.WorkItemEvent).count() == 1


def test_sandbox_payment_does_not_roll_into_real_product(db):
    item = make_item(db)
    repair_shop.create_triage(db, item.id, rationale="Inspect", expected_outcome="Inspection complete", confidence=50)
    repair_shop.record_verified_payment(
        db, item.id, amount=100, unit="NPR", provider="sandbox-provider", provider_reference="sandbox-ref-2", data_scope="SANDBOX",
    )
    assert db.query(models.Product).filter(models.Product.data_scope == "REAL").count() == 0





def test_verified_payment_intent_links_to_work_item_idempotently(db):
    item = make_real_item(db)
    product, intent = make_payment_intent_for_item(db, item)

    first = repair_shop.link_verified_payment_intent(db, item.id, intent.id)
    second = repair_shop.link_verified_payment_intent(db, item.id, intent.id)

    db.refresh(item)
    assert first["link_event_id"] == second["link_event_id"]
    assert first["payment_intent"]["id"] == intent.id
    assert item.product_id == product.id
    assert item.status == "PAYMENT_PENDING"
    assert db.query(models.WorkItemEvent).filter_by(
        work_item_id=item.id, event_type="PAYMENT_INTENT_LINKED"
    ).count() == 1

    detail = repair_shop.get_work_item_detail(db, item.id)
    assert [row["id"] for row in detail["payment_intents"]] == [intent.id]
    assert detail["outcomes"] == []  # VERIFIED alone is not fulfilled revenue.


def test_repair_work_item_link_rejects_unverified_intent_and_wrong_opportunity(db):
    item = make_real_item(db, suffix="left")
    _product, intent = make_payment_intent_for_item(db, item, suffix="left", status="INITIATED")

    with pytest.raises(ValueError, match="provider-verified"):
        repair_shop.link_verified_payment_intent(db, item.id, intent.id)
    db.refresh(item)
    assert item.product_id is None
    assert db.query(models.WorkItemEvent).filter_by(event_type="PAYMENT_INTENT_LINKED").count() == 0

    other_item = make_real_item(db, suffix="right")
    intent.status = "VERIFIED"
    intent.provider_reference = "TEST-provider-reference-left"
    db.commit()
    with pytest.raises(ValueError, match="canonical opportunity"):
        repair_shop.link_verified_payment_intent(db, other_item.id, intent.id)
    db.refresh(other_item)
    assert other_item.product_id is None
    assert db.query(models.WorkItemEvent).filter_by(
        work_item_id=other_item.id, event_type="PAYMENT_INTENT_LINKED"
    ).count() == 0
