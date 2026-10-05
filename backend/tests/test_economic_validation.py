import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.migrations import run_migrations
from app.services import demand_understanding, economic_validation, product_engine, world_graph
from app.services import source_manager



def _activated_test_capability(db, *, name, description, test_ref):
    """Reach ``active`` only through the substrate lifecycle (test fixture)."""
    capability = world_graph.create_capability(
        db,
        capability_type="workflow",
        name=name,
        description=description,
        owner_agent="test",
    )
    world_graph.begin_capability_build(db, capability)
    world_graph.mark_capability_tested(
        db,
        capability,
        test_ref=test_ref,
        command=f"pytest {test_ref}",
        exit_code=0,
        output_excerpt="test fixture",
        provenance={"actor": "test", "revision": "bf8546ed26f9179e8522726e966a984fc1dd83c6"},
    )
    return world_graph.activate_capability(db, capability)

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
        requirement_id="scholarly_evidence",
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
    world_graph.seed_core_types(db)
    need = world_graph.create_entity(
        db,
        entity_type="need",
        display_name="Need with unresolved test dimensions",
        attributes={
            "desired_outcome": "receive acceptable filters weekly",
            "epistemic_state": "hypothesized",
            "unresolved_questions": ["quantity"],
        },
        created_by="test",
    )

    assessment = _assessment(db, need.id)

    assert assessment["assessment"]["assessment_state"] == "insufficient_evidence"
    assert assessment["opportunity_id"] is None
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.Experiment).count() == 0
    assert db.query(models.Outcome).count() == 0


def test_possible_demand_cannot_enter_economics_without_a_need(db):
    signal = demand_understanding.record_raw_observation(
        db,
        "A vague developer test request with no stated outcome.",
        source="developer_test",
        metadata={"test_fixture": True},
    )
    understanding = demand_understanding.understand(db, [signal.id])
    assert understanding.state == "possible_demand"
    assert understanding.inferred_need_id is None
    with pytest.raises(ValueError, match="existing Need entity"):
        _assessment(db, signal.id)
    assert db.query(models.Opportunity).count() == 0


def test_sufficient_need_keeps_missing_economics_explicit(db):
    result = _need(db)
    _search(db, result)
    fit = _evidence(db, result.inferred_need_id, "capability fit")
    capability = _activated_test_capability(
        db,
        name="economic-uncertain-test-capability",
        description="Synthetic capability fixture; not evidence of commercial fulfillment.",
        test_ref="backend/tests/test_economic_validation.py",
    )
    db.commit()

    assessment = _assessment(
        db,
        result.inferred_need_id,
        capability_id=capability.id,
        evidence_by_assumption={"capability_fit": [fit.id]},
    )

    assert assessment["opportunity_id"] is not None
    assert assessment["assessment"]["assessment_state"] == "economically_uncertain"
    assert assessment["assessment"]["willingness_to_pay"]["status"] == "unknown"
    assert any("cost assumption is unknown" == item for item in assessment["assessment"]["unresolved_uncertainties"])
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
    capability = _activated_test_capability(
        db,
        name="economic-validation-test-capability",
        description="Synthetic capability fixture; not evidence of commercial fulfillment.",
        test_ref="backend/tests/test_economic_validation.py",
    )
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


def test_refuted_or_unprovenanced_records_cannot_back_an_economic_assumption(db):
    result = _need(db)
    _search(db, result)
    evidence = models.Evidence(
        source="synthetic_test_fixture",
        provenance=json.dumps({"test_fixture": True}),
        support_level="refuted",
    )
    db.add(evidence)
    db.commit()

    with pytest.raises(ValueError, match="classifiable non-refuted support"):
        _assessment(
            db,
            result.inferred_need_id,
            cost_assumption=10.0,
            evidence_by_assumption={"cost": [evidence.id]},
        )


def test_need_assessment_api_uses_existing_opportunity_surface(db):
    understanding = _need(db)
    _search(db, understanding)
    from app import security
    security.settings.FORGE_API_KEY = ""

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post(
            f"/needs/{understanding.inferred_need_id}/economic-validation",
            json={
                "solution_hypothesis": "A bounded weekly delivery coordination service may help.",
                "experiment_definition": "Present an explicitly hypothetical price to one consenting participant.",
                "experiment_tests_willingness_to_pay": True,
            },
            # POST /needs/{id}/economic-validation is owner-guarded (it
            # writes Opportunity + world-graph rows); the module key is
            # set at import below the imports above.
            headers={"X-API-Key": security.settings.FORGE_API_KEY},
        )
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assessment"]["assessment_state"] == "insufficient_evidence"
    assert body["assessment"]["willingness_to_pay"]["status"] == "unknown"
    assert body["assessment"]["authorization_required_before_external_action"] is True
    assert db.query(models.Action).count() == 0
    assert db.query(models.Experiment).count() == 0


def test_need_assessment_and_provenance_survive_sqlite_reopen(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'economic-assessment.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        source_manager.seed_default_sources(session)
        understanding = _need(session)
        search = _search(session, understanding)
        assert search["matched_sources"]
        assert search["capability_gap_id"] is None
        assert session.query(models.ResearchQuestion).count() == 0
        assessed = _assessment(session, understanding.inferred_need_id)
        assert assessed["opportunity_id"] is not None
        need_id = understanding.inferred_need_id
        opportunity_id = assessed["opportunity_id"]
        gate_state = assessed["assessment"]["assessment_state"]
    engine.dispose()

    reopened_engine = create_engine(
        f"sqlite:///{tmp_path / 'economic-assessment.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    reopened_factory = sessionmaker(bind=reopened_engine, expire_on_commit=False)
    with reopened_factory() as reopened:
        opportunity = reopened.get(models.Opportunity, opportunity_id)
        need = reopened.get(models.SubstrateEntity, need_id)
        history = (
            reopened.query(models.OpportunityEvent)
            .filter_by(opportunity_id=opportunity_id, event_type="economic_validation_assessed")
            .one()
        )
        event = (
            reopened.query(models.WorldEvent)
            .filter_by(event_type="economic_validation_assessed")
            .one()
        )
        assert opportunity is not None and need is not None
        assert json.loads(history.details)["need_id"] == need_id
        payload = json.loads(event.payload)
        assert payload["assessment_state"] == gate_state
        assert payload["authorization_required_before_external_action"] is True
        assert payload["external_action_authorized"] is False
        search_event = reopened.query(models.WorldEvent).filter_by(
            entity_id=need_id, event_type="capability_search_performed"
        ).one()
        search_payload = json.loads(search_event.payload)
        assert search_payload["need_id"] == need_id
        search_evidence = reopened.query(models.Evidence).filter_by(
            subject_kind="entity", subject_id=need_id, source="demand_understanding"
        ).filter(
            models.Evidence.idempotency_key.like(
                f"need-capability-search-evidence:{need_id}:%"
            )
        ).one()
        assert json.loads(search_evidence.provenance)["requirement_id"] == "scholarly_evidence"
        opportunity_entity = reopened.query(models.SubstrateEntity).filter_by(
            entity_type="opportunity",
            source_system="opportunities",
            source_id=str(opportunity_id),
        ).one()
        relation = reopened.query(models.WorldRelation).filter_by(
            from_entity_id=opportunity_entity.id,
            to_entity_id=need_id,
            relation_type="derived_from",
        ).one()
        assert relation.truth_state == "hypothesized"
        assert reopened.query(models.Action).count() == 0
        assert reopened.query(models.Experiment).count() == 0
        assert reopened.query(models.Outcome).count() == 0
        assert reopened.query(models.CustomerEvent).count() == 0
    reopened_engine.dispose()


def test_customer_progression_requires_linked_outcome_evidence(db):
    product = product_engine.create_product(db, name="Test offer", offer="Test offer", data_scope="SANDBOX")

    with pytest.raises(ValueError, match="authorized action or response outcome"):
        product_engine.create_customer_event(
            db, product_id=product.id, stage="contacted", data_scope="SANDBOX"
        )
    unapproved_action = models.Action(
        action_type="outreach",
        objective="Synthetic unapproved test action",
        policy_result="REQUIRE_APPROVAL",
        started_at=datetime.now(timezone.utc),
    )
    db.add(unapproved_action)
    db.commit()
    with pytest.raises(ValueError, match="authorized action or response outcome"):
        product_engine.create_customer_event(
            db,
            product_id=product.id,
            stage="contacted",
            action_id=unapproved_action.id,
            data_scope="SANDBOX",
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
    verified_payment = models.Outcome(
        product_id=product.id,
        outcome_type="ACTUAL_REVENUE",
        actual_value=1.0,
        unit="USD",
        verification_state="VERIFIED",
        data_scope="SANDBOX",
        source="synthetic test fixture",
    )
    db.add(verified_payment)
    db.commit()
    paid = product_engine.create_customer_event(
        db,
        product_id=product.id,
        stage="paid_customer",
        outcome_id=verified_payment.id,
        data_scope="SANDBOX",
    )
    assert paid.stage == "paid_customer"
