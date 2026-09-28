import json

import pytest

from app import models
from app.services import demand_understanding, economic_validation, product_engine, world_graph


def _need(db, *, sufficient=True):
    signal = demand_understanding.record_raw_observation(
        db,
        "Developer test request: a shop needs reliable weekly delivery of replacement filters.",
        source="developer_test",
        metadata={"test_fixture": True},
    )
    return demand_understanding.understand(
        db,
        [signal.id],
        object_description="replacement filters",
        desired_outcome="receive acceptable filters weekly",
        unresolved_questions=[] if sufficient else ["quantity"],
        sufficient=sufficient,
    )


def _search(db, understanding):
    return demand_understanding.search_existing_capabilities(
        db,
        understanding,
        requirement_id=f"economic-test-{understanding.inferred_need_id}",
        required_evidence_type="scholarly_metadata",
    )


def _evidence(db, need_id, kind):
    return world_graph.create_evidence(
        db,
        subject_kind="entity",
        subject_id=need_id,
        claim=f"Synthetic test reference for {kind} assumption; not market evidence.",
        support_level="possible",
        source="synthetic_test_fixture",
        provenance={"test_fixture": True, "assumption": kind},
        confidence=0.1,
        idempotency_key=f"economic-test-evidence:{need_id}:{kind}",
    )


def _assessment(db, need_id, **overrides):
    values = {
        "solution_hypothesis": "A weekly delivery coordination service may help.",
        "experiment_definition": "Ask one consenting test participant to assess a clearly labeled price proposal.",
        "experiment_tests_willingness_to_pay": True,
    }
    values.update(overrides)
    return economic_validation.assess_need_economics(db, need_id, **values)


def test_unresolved_demand_cannot_create_commercial_opportunity(db):
    result = _need(db, sufficient=False)
    need = db.get(models.SubstrateEntity, result.inferred_need_id)

    assessment = _assessment(db, need.id)

    assert assessment["assessment"]["assessment_state"] == "insufficient_evidence"
    assert assessment["opportunity_id"] is None
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.Experiment).count() == 0
    assert db.query(models.Outcome).count() == 0


def test_sufficient_need_with_bounded_search_stays_economically_uncertain_without_evidence(db):
    result = _need(db)
    _search(db, result)

    assessment = _assessment(db, result.inferred_need_id)

    assert assessment["opportunity_id"] is not None
    assert assessment["assessment"]["assessment_state"] == "economically_uncertain"
    assert assessment["assessment"]["willingness_to_pay"]["status"] == "unknown"
    assert any("cost assumption" in item for item in assessment["assessment"]["unresolved_uncertainties"])
    assert assessment["assessment"]["authorization_required_before_external_action"] is True
    assert assessment["assessment"]["external_action_authorized"] is False
    assert assessment["assessment"]["action_created"] is False
    assert db.query(models.Action).count() == 0
    assert db.query(models.Experiment).count() == 0


def test_referenced_assumptions_make_only_a_bounded_test_proposal(db):
    result = _need(db)
    _search(db, result)
    fit = _evidence(db, result.inferred_need_id, "capability fit")
    cost = _evidence(db, result.inferred_need_id, "cost")
    price = _evidence(db, result.inferred_need_id, "price")
    capability = models.ForgeCapability(
        capability_type="workflow",
        name="economic-validation-test-capability",
        description="Synthetic capability fixture; not evidence of commercial fulfillment.",
        status="active",
        test_ref="backend/tests/test_economic_validation.py",
        owner_agent="test",
    )
    db.add(capability)
    db.commit()

    assessment = _assessment(
        db,
        result.inferred_need_id,
        capability_id=capability.id,
        cost_assumption=10.0,
        price_assumption=20.0,
        evidence_by_assumption={
            "capability_fit": [fit.id],
            "cost": [cost.id],
            "price": [price.id],
        },
    )

    assert assessment["assessment"]["assessment_state"] == "testable"
    assert assessment["assessment"]["willingness_to_pay"]["status"] == "unknown"
    assert assessment["assessment"]["authorization_required_before_external_action"] is True
    assert assessment["assessment"]["external_action_authorized"] is False
    assert db.query(models.Experiment).count() == 0
    assert db.query(models.Action).count() == 0

    replay = _assessment(
        db,
        result.inferred_need_id,
        capability_id=capability.id,
        cost_assumption=10.0,
        price_assumption=20.0,
        evidence_by_assumption={
            "capability_fit": [fit.id],
            "cost": [cost.id],
            "price": [price.id],
        },
    )
    assert replay["opportunity_id"] == assessment["opportunity_id"]
    assert db.query(models.OpportunityEvent).filter_by(
        event_type="economic_validation_assessed"
    ).count() == 1
    substrate_events = db.query(models.WorldEvent).filter_by(
        event_type="economic_validation_assessed"
    ).all()
    assert len(substrate_events) == 1
    payload = json.loads(substrate_events[0].payload)
    assert payload["authorization_required_before_external_action"] is True
    assert payload["willingness_to_pay"]["status"] == "unknown"


def test_customer_progression_requires_linked_outcome_evidence(db):
    product = product_engine.create_product(db, name="Test offer", offer="Test offer", data_scope="SANDBOX")

    with pytest.raises(ValueError, match="authorized action or response outcome"):
        product_engine.create_customer_event(
            db, product_id=product.id, stage="contacted", data_scope="SANDBOX"
        )
    with pytest.raises(ValueError, match="actual response outcome"):
        product_engine.create_customer_event(
            db, product_id=product.id, stage="interested", data_scope="SANDBOX"
        )
    with pytest.raises(ValueError, match="verified positive revenue"):
        product_engine.create_customer_event(
            db, product_id=product.id, stage="paid_customer", data_scope="SANDBOX"
        )

    reported_payment = models.Outcome(
        product_id=product.id,
        outcome_type="ACTUAL_REVENUE",
        actual_value=1.0,
        unit="USD",
        verification_state="REPORTED",
        data_scope="SANDBOX",
        source="synthetic test fixture",
    )
    db.add(reported_payment)
    db.commit()
    with pytest.raises(ValueError, match="verified positive revenue"):
        product_engine.create_customer_event(
            db,
            product_id=product.id,
            stage="paid_customer",
            outcome_id=reported_payment.id,
            data_scope="SANDBOX",
        )
