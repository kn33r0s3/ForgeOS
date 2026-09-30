from app import models
from app.services import execution_engine, repair_shop


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



