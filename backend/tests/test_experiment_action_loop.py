from app import models
from app.services import experiment_action_service


def _authorized_experiment(db):
    experiment = models.Experiment(
        opportunity_id=None,
        action="Contact the research participants",
        action_type="research",
        hypothesis="Participants will confirm the problem.",
        expected_result="A response is recorded from the participants.",
        authorization_status="allowed",
        authorized_at=models.utcnow(),
        approved_at=models.utcnow(),
        execution_status="authorized",
        response_received="none",
        revenue_amount=0.0,
        revenue_currency="USD",
        status="planned",
        requires_owner_approval=True,
        execution_allowed=True,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def test_adapter_success_is_separate_from_business_outcome_and_learning(db):
    experiment = _authorized_experiment(db)

    proposed = experiment_action_service.propose_action(db, experiment.id)
    executed = experiment_action_service.execute_action(db, experiment.id)

    assert proposed["experiment_id"] == experiment.id
    assert executed["status"] == "SUCCEEDED"
    assert executed["verification_state"] == "UNVERIFIED"
    assert db.query(models.Outcome).count() == 0
    assert db.query(models.LearningEvent).count() == 0
    assert db.query(models.Lesson).count() == 0

    result = experiment_action_service.record_actual_response(
        db,
        experiment.id,
        actual="Participants rejected the proposed workflow.",
        success=False,
        source="human_interview",
    )

    outcome = result["outcome"]
    learning = result["learning"]
    refreshed_action = db.get(models.Action, proposed["id"])
    refreshed_experiment = db.get(models.Experiment, experiment.id)

    assert outcome.action_id == refreshed_action.id
    assert outcome.experiment_id == experiment.id
    assert outcome.actual_value is None
    assert outcome.verification_state == "REPORTED"
    assert learning.experiment_id == experiment.id
    assert refreshed_action.status == "VERIFIED"
    assert refreshed_action.verification_state == "VERIFIED_FAILURE"
    assert refreshed_experiment.status == "completed"
    assert refreshed_experiment.execution_status == "completed"
    assert refreshed_experiment.revenue_amount == 0.0
    assert refreshed_experiment.revenue is None
    assert db.query(models.Lesson).count() == 1

def test_product_learning_changes_only_after_verified_real_outcome(db):
    from app import evidence_source
    from app.services import action_engine

    opportunity = models.Opportunity(
        problem="Outcome learning gate fixture",
        target_customer="TEST-only customer",
        solution="A verified result may be noted against its linked product",
    )
    db.add(opportunity)
    db.flush()
    reported_product = models.Product(
        opportunity_id=opportunity.id,
        name="Reported fixture",
        offer="Reported outcomes must not update shared learning",
        data_scope="REAL",
    )
    verified_product = models.Product(
        opportunity_id=opportunity.id,
        name="Verified fixture",
        offer="Only verified REAL outcomes may update matching learning state",
        data_scope="REAL",
    )
    db.add_all([reported_product, verified_product])
    db.commit()
    db.refresh(opportunity)
    db.refresh(reported_product)
    db.refresh(verified_product)

    action_engine.record_outcome(
        db,
        outcome_type="ACTUAL_RESPONSE",
        product_id=reported_product.id,
        actual_value=2.0,
        unit="count",
        qualitative_result="Unverified TEST fixture.",
        source="manual-test-fixture",
        success=False,
        data_scope="REAL",
        source_kind=evidence_source.MOCK,
        verification_state="REPORTED",
        idempotency_key="test-mock-must-not-learn",
    )
    db.refresh(opportunity)
    assert "[LEARNING " not in (opportunity.validation_plan or "")

    params = {
        "outcome_type": "ACTUAL_RESPONSE",
        "product_id": verified_product.id,
        "actual_value": 3.0,
        "unit": "count",
        "qualitative_result": "Verified TEST-database fixture.",
        "source": "verified-real-test-fixture",
        "success": True,
        "data_scope": "REAL",
        "source_kind": evidence_source.REAL,
        "verification_state": "VERIFIED",
        "idempotency_key": "test-verified-real-must-learn-once",
    }
    outcome = action_engine.record_outcome(db, **params)
    event = db.query(models.LearningEvent).filter_by(
        product_id=verified_product.id,
        outcome_id=outcome.id,
    ).one()
    db.refresh(opportunity)

    assert event.data_scope == "REAL"
    assert event.source_kind == evidence_source.REAL
    assert "REAL/REAL/VERIFIED" in event.lesson
    note = f"[LEARNING {event.created_at}] {event.lesson}"
    assert (opportunity.validation_plan or "").count(note) == 1

    replay = action_engine.record_outcome(db, **params)
    db.refresh(opportunity)
    assert replay.id == outcome.id
    assert (opportunity.validation_plan or "").count(note) == 1
    assert db.query(models.LearningEvent).filter_by(outcome_id=outcome.id).count() == 1
