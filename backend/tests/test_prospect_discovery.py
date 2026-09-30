import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app import models
from app.database import Base, get_db
from app.main import app
from app.migrations import run_migrations
from app.services import demand_understanding, economic_validation, prospect_discovery, world_graph



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

def _testable_opportunity(db):
    signal = demand_understanding.record_raw_observation(
        db,
        "Developer fixture: a shop needs reliable weekly delivery of replacement filters.",
        source="developer_test",
        metadata={"test_fixture": True},
    )
    understanding = demand_understanding.understand(
        db,
        [signal.id],
        object_description="replacement filters",
        desired_outcome="receive acceptable filters weekly",
        unresolved_questions=[],
        sufficient=True,
    )
    need_id = understanding.inferred_need_id
    demand_understanding.search_existing_capabilities(
        db,
        understanding,
        requirement_id="scholarly_evidence",
        required_evidence_type="scholarly_metadata",
    )
    evidence_ids = {}
    for assumption in ("capability_fit", "cost", "price"):
        evidence = world_graph.create_evidence(
            db,
            subject_kind="entity",
            subject_id=need_id,
            claim=f"Synthetic fixture reference for {assumption}, not real-world evidence.",
            support_level="possible",
            source="synthetic_test_fixture",
            provenance={"test_fixture": True, "assumption": assumption},
            confidence=0.1,
            idempotency_key=f"prospect-test:{need_id}:{assumption}",
        )
        evidence_ids[assumption] = [evidence.id]
    capability = _activated_test_capability(
        db,
        name="prospect-discovery-test-capability",
        description="Synthetic test fixture; not proof of commercial fulfillment.",
        test_ref="backend/tests/test_prospect_discovery.py",
    )
    db.commit()
    assessment = economic_validation.assess_need_economics(
        db,
        need_id,
        solution_hypothesis="A weekly filter delivery service may help.",
        capability_id=capability.id,
        cost_assumption=10,
        price_assumption=20,
        evidence_by_assumption=evidence_ids,
        experiment_definition="Test a clearly labeled hypothetical price with a consenting participant.",
        experiment_tests_willingness_to_pay=True,
    )
    assert assessment["assessment"]["assessment_state"] == "testable"
    return assessment["opportunity_id"], need_id


def _evaluate(db, opportunity_id, **overrides):
    values = {
        "target_profile": "Independent retailers with evidenced replacement-filter logistics needs",
        "geographic_scope": "Kathmandu Valley",
        "max_candidates": 5,
    }
    values.update(overrides)
    return prospect_discovery.evaluate_prospect_discovery_readiness(
        db, opportunity_id, **values
    )


def test_discovery_requires_a_testable_opportunity_and_need_link(db):
    opportunity_id, need_id = _testable_opportunity(db)

    result = _evaluate(db, opportunity_id)

    assert result["opportunity_id"] == opportunity_id
    assert result["need_id"] == need_id
    assert result["economic_assessment_state"] == "testable"
    relation = db.query(models.WorldRelation).filter_by(
        from_entity_id=result["opportunity_entity_id"],
        to_entity_id=need_id,
        relation_type="derived_from",
    ).one()
    assert relation is not None


def test_discovery_fails_closed_without_economic_context(db):
    with pytest.raises(ValueError, match="Opportunity does not exist"):
        _evaluate(db, 90210)
    assert db.query(models.WorldEvent).filter_by(
        event_type="prospect_discovery_evaluated"
    ).count() == 0

    opportunity_id, need_id = _testable_opportunity(db)
    uncertain = economic_validation.assess_need_economics(
        db,
        need_id,
        solution_hypothesis="A weekly filter delivery service may help.",
        experiment_definition="A later bounded test would require explicit authorization.",
        experiment_tests_willingness_to_pay=False,
    )
    assert uncertain["opportunity_id"] == opportunity_id
    assert uncertain["assessment"]["assessment_state"] == "insufficient_evidence"

    with pytest.raises(ValueError, match="currently testable"):
        _evaluate(db, opportunity_id)
    assert db.query(models.WorldEvent).filter_by(
        event_type="prospect_discovery_evaluated"
    ).count() == 0


def test_no_authorized_source_means_no_candidates_or_prospect_promotion(db):
    opportunity_id, _ = _testable_opportunity(db)

    result = _evaluate(db, opportunity_id)

    assert result["discovery_state"] == "blocked_no_authorized_source"
    assert result["bounded_search"]["eligible_sources"] == []
    assert result["bounded_search"]["source_data_queried"] is False
    assert result["bounded_search"]["external_requests_made"] == 0
    assert result["candidate_count"] == result["potential_prospect_count"] == 0
    assert result["candidate_entity_ids"] == []
    assert result["qualification_handoff"]["state"] == "blocked_before_candidate"
    assert result["qualification_handoff"]["qualification_started"] is False
    assert result["qualification_handoff"]["outreach_eligible"] is False
    assert result["qualification_handoff"]["outreach_authorized"] is False
    assert result["qualification_handoff"]["action_created"] is False
    assert result["qualification_handoff"]["interested_party_created"] is False
    assert result["qualification_handoff"]["customer_created"] is False
    assert db.query(models.SubstrateEntity).filter(
        models.SubstrateEntity.entity_type.in_(("organization", "person", "customer"))
    ).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.Experiment).count() == 0
    assert db.query(models.Outcome).count() == 0
    assert db.query(models.CustomerEvent).count() == 0
    assert db.query(models.Customer).count() == 0


def test_requested_uncleared_source_fails_closed_without_records(db):
    opportunity_id, _ = _testable_opportunity(db)

    with pytest.raises(PermissionError, match="not currently cleared"):
        _evaluate(
            db,
            opportunity_id,
            requested_source_registry_ids=["gdelt-doc-api-v2"],
        )
    assert db.query(models.WorldEvent).filter_by(
        event_type="prospect_discovery_evaluated"
    ).count() == 0
    assert db.query(models.Evidence).filter(
        models.Evidence.idempotency_key.like("prospect-discovery-evaluation:%")
    ).count() == 0


def test_readiness_route_records_audit_and_rejects_uncleared_source(db):
    opportunity_id, _ = _testable_opportunity(db)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, raise_server_exceptions=False)
    try:
        path = f"/opportunities/{opportunity_id}/prospect-discovery/readiness"
        body = {
            "target_profile": "Independent retailers with replacement-filter needs",
            "geographic_scope": "Kathmandu Valley",
            "max_candidates": 5,
        }
        response = client.post(path, json=body)
        denied = client.post(
            path,
            json={**body, "requested_source_registry_ids": ["gdelt-doc-api-v2"]},
        )
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    assert response.json()["discovery_state"] == "blocked_no_authorized_source"
    assert denied.status_code == 403, denied.text


def test_bounded_source_audit_is_idempotent_and_criteria_scoped(db):
    opportunity_id, _ = _testable_opportunity(db)

    with pytest.raises(ValueError, match="max_candidates must be between"):
        _evaluate(db, opportunity_id, max_candidates=11)
    assert db.query(models.WorldEvent).filter_by(
        event_type="prospect_discovery_evaluated"
    ).count() == 0

    first = _evaluate(db, opportunity_id, max_candidates=3)
    replay = _evaluate(db, opportunity_id, max_candidates=3)
    independent = _evaluate(db, opportunity_id, max_candidates=4)

    assert first["bounded_search"]["maximum_candidates"] == 3
    assert first["event_id"] == replay["event_id"]
    assert first["evidence_id"] == replay["evidence_id"]
    assert independent["event_id"] != first["event_id"]
    assert independent["evidence_id"] != first["evidence_id"]
    assert db.query(models.WorldEvent).filter_by(
        event_type="prospect_discovery_evaluated"
    ).count() == 2
    assert db.query(models.Evidence).filter(
        models.Evidence.idempotency_key.like("prospect-discovery-evaluation:%")
    ).count() == 2


def test_event_evidence_and_opportunity_provenance_survive_sqlite_reopen(tmp_path):
    database_path = tmp_path / "prospect-discovery.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        opportunity_id, need_id = _testable_opportunity(db)
        result = _evaluate(db, opportunity_id)
        event_id = result["event_id"]
        evidence_id = result["evidence_id"]
        opportunity_entity_id = result["opportunity_entity_id"]
    engine.dispose()

    reopened_engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
    )
    with sessionmaker(bind=reopened_engine, expire_on_commit=False)() as reopened:
        event = reopened.get(models.WorldEvent, event_id)
        evidence = reopened.get(models.Evidence, evidence_id)
        relation = reopened.query(models.WorldRelation).filter_by(
            from_entity_id=opportunity_entity_id,
            to_entity_id=need_id,
            relation_type="derived_from",
        ).one()

        assert event is not None and evidence is not None and relation is not None
        payload = json.loads(event.payload)
        provenance = json.loads(evidence.provenance)
        assert payload["candidate_count"] == 0
        assert payload["need_id"] == need_id
        assert payload["bounded_search"]["source_data_queried"] is False
        assert provenance["need_id"] == need_id
        assert provenance["opportunity_entity_id"] == opportunity_entity_id
        assert provenance["source_registry_id"] == "runtime_source_clearances"
        assert provenance["source_data_queried"] is False
        assert provenance["external_requests_made"] == 0
        assert provenance["eligible_source_registry_ids"] == []
        assert provenance["reviewed_source_registry_ids"]
        assert event.occurred_at is not None
    reopened_engine.dispose()
