import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.main import app
from app.services import world_graph
from app import security


@pytest.fixture
def substrate_client(db):
    world_graph.seed_core_types(db)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()
    client.close()


def test_type_entity_and_identity_api_use_canonical_services(substrate_client, db):
    proposed = substrate_client.post("/forge/substrate/types", json={
        "category": "entity_type",
        "type_name": "field_resource",
        "schema": {
            "type": "object",
            "properties": {"region": {"type": "string"}},
            "required": ["region"],
            "additionalProperties": False,
        },
        "owner_agent": "test-agent",
        "description": "A resource with a source region.",
    })
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["status"] == "proposed"

    rejected = substrate_client.post("/forge/substrate/entities", json={
        "entity_type": "field_resource",
        "display_name": "A resource",
        "attributes": {"region": "Koshi"},
        "created_by": "test-agent",
    })
    assert rejected.status_code == 422
    assert db.query(models.SubstrateEntity).filter_by(display_name="A resource").count() == 0

    activated = substrate_client.post(
        "/forge/substrate/types/entity_type/field_resource/status",
        json={
            "status": "active",
            "actor": "test-agent",
            "rationale": "A passing API integration test exercises the schema.",
            "evidence_ref": "backend/tests/test_substrate_api.py",
        },
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    body = {
        "entity_type": "field_resource",
        "display_name": "A resource",
        "attributes": {"region": "Koshi"},
        "created_by": "test-agent",
        "identity": {
            "source_system": "catalogue",
            "source_id": "resource-17",
            "canonical_identifier": "https://example.test/resources/17",
            "provenance": {"source_ref": "catalogue:17"},
        },
    }
    first = substrate_client.post("/forge/substrate/entities", json=body)
    repeated = substrate_client.post("/forge/substrate/entities", json=body)
    assert first.status_code == 201, first.text
    assert repeated.status_code == 201, repeated.text
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["identity_state"] == "candidate"
    assert substrate_client.get(f"/forge/substrate/entities/{first.json()['id']}").json()["source_id"] == "resource-17"
    assert db.query(models.SubstrateEntity).filter_by(identity_key="source:field_resource:catalogue:resource-17").count() == 1

    conflicting_retry = substrate_client.post(
        "/forge/substrate/entities",
        json={**body, "attributes": {"region": "Madhesh"}},
    )
    assert conflicting_retry.status_code == 409
    persisted = substrate_client.get(f"/forge/substrate/entities/{first.json()['id']}")
    assert persisted.json()["attributes"] == {"region": "Koshi"}
    assert db.query(models.SubstrateEntity).filter_by(identity_key="source:field_resource:catalogue:resource-17").count() == 1

    deprecated = substrate_client.post(
        "/forge/substrate/types/entity_type/field_resource/status",
        json={
            "status": "deprecated",
            "actor": "test-agent",
            "rationale": "The test type has served its API lifecycle check.",
            "evidence_ref": "backend/tests/test_substrate_api.py",
        },
    )
    assert deprecated.status_code == 200
    assert deprecated.json()["status"] == "deprecated"


def test_relation_transition_requires_evidence_and_preserves_provenance(substrate_client, db):
    entities = []
    for name in ("origin", "destination"):
        response = substrate_client.post("/forge/substrate/entities", json={
            "entity_type": "resource",
            "display_name": name,
            "attributes": {},
            "created_by": "test-agent",
        })
        assert response.status_code == 201, response.text
        entities.append(response.json())

    relation_body = {
        "from_entity_id": entities[0]["id"],
        "to_entity_id": entities[1]["id"],
        "relation_type": "supports",
        "truth_state": "possible",
        "created_by": "test-agent",
        "idempotency_key": "api-supports-origin-destination",
    }
    created = substrate_client.post("/forge/substrate/relations", json=relation_body)
    repeated = substrate_client.post("/forge/substrate/relations", json=relation_body)
    assert created.status_code == 201, created.text
    assert repeated.json()["id"] == created.json()["id"]
    relation_id = created.json()["id"]
    key_collision = substrate_client.post(
        "/forge/substrate/relations",
        json={**relation_body, "attributes": {"different_intent": True}},
    )
    assert key_collision.status_code == 409

    direct_supported = substrate_client.post(
        f"/forge/substrate/relations/{relation_id}/truth", json={"next_state": "supported"}
    )
    assert direct_supported.status_code == 422
    assert db.get(models.WorldRelation, relation_id).truth_state == "possible"
    state_hypothesized = substrate_client.post(
        f"/forge/substrate/relations/{relation_id}/truth", json={"next_state": "hypothesized"}
    )
    assert state_hypothesized.status_code == 200

    tested = substrate_client.post("/forge/substrate/evidence", json={
        "subject_kind": "relation",
        "subject_id": relation_id,
        "claim": "A source records the relation under test.",
        "support_level": "tested",
        "source": "documented_source",
        "provenance": {"source_url": "https://example.test/source/1"},
        "idempotency_key": "api-evidence-tested-1",
    })
    assert tested.status_code == 201, tested.text
    state_tested = substrate_client.post(
        f"/forge/substrate/relations/{relation_id}/truth", json={"next_state": "tested"}
    )
    assert state_tested.status_code == 200, state_tested.text

    supported = substrate_client.post("/forge/substrate/evidence", json={
        "subject_kind": "relation",
        "subject_id": relation_id,
        "claim": "The tested source supports the relation.",
        "support_level": "supported",
        "source": "documented_source",
        "provenance": {"source_url": "https://example.test/source/2"},
        "idempotency_key": "api-evidence-supported-1",
    })
    assert supported.status_code == 201, supported.text
    state_supported = substrate_client.post(
        f"/forge/substrate/relations/{relation_id}/truth", json={"next_state": "supported"}
    )
    assert state_supported.status_code == 200, state_supported.text
    assert state_supported.json()["truth_state"] == "supported"

    evidence_list = substrate_client.get(
        "/forge/substrate/evidence", params={"subject_kind": "relation", "subject_id": relation_id}
    )
    assert evidence_list.status_code == 200
    assert {row["support_level"] for row in evidence_list.json()} >= {"tested", "supported"}
    assert all(row["provenance"]["source_url"].startswith("https://") for row in evidence_list.json())


def test_event_and_capability_api_enforce_lifecycle_and_idempotency(substrate_client, db):
    entity = substrate_client.post("/forge/substrate/entities", json={
        "entity_type": "tool",
        "display_name": "Event subject",
        "attributes": {},
        "created_by": "test-agent",
    }).json()
    event_body = {
        "event_type": "state_changed",
        "source": "test-agent",
        "entity_id": entity["id"],
        "payload": {"state": "observed"},
        "idempotency_key": "api-state-changed-event-1",
    }
    first_event = substrate_client.post("/forge/substrate/events", json=event_body)
    repeated_event = substrate_client.post("/forge/substrate/events", json=event_body)
    assert first_event.status_code == 201, first_event.text
    assert repeated_event.json()["id"] == first_event.json()["id"]
    conflicting_event = substrate_client.post(
        "/forge/substrate/events",
        json={**event_body, "source": "different-agent"},
    )
    assert conflicting_event.status_code == 409
    assert db.query(models.WorldEvent).filter_by(idempotency_key=event_body["idempotency_key"]).count() == 1
    assert substrate_client.get("/forge/substrate/events", params={"entity_id": entity["id"]}).json()

    capability_body = {
        "capability_type": "tool",
        "name": "api-test-capability",
        "description": "A capability created through the substrate API.",
        "owner_agent": "test-agent",
        "spec_ref": "backend/tests/test_substrate_api.py",
        "attributes": {"purpose": "integration test"},
    }
    created = substrate_client.post("/forge/substrate/capabilities", json=capability_body)
    repeated = substrate_client.post("/forge/substrate/capabilities", json=capability_body)
    assert created.status_code == 201, created.text
    assert repeated.status_code == 201
    assert repeated.json()["id"] == created.json()["id"]
    capability_id = created.json()["id"]

    premature = substrate_client.post(f"/forge/substrate/capabilities/{capability_id}/activate")
    assert premature.status_code == 422
    building = substrate_client.post(f"/forge/substrate/capabilities/{capability_id}/build")
    assert building.status_code == 200
    tested = substrate_client.post(f"/forge/substrate/capabilities/{capability_id}/test", json={
        "test_ref": "backend/tests/test_substrate_api.py",
        "command": "pytest backend/tests/test_substrate_api.py",
        "exit_code": 0,
        "output_excerpt": "passed",
    })
    assert tested.status_code == 200, tested.text
    activated = substrate_client.post(f"/forge/substrate/capabilities/{capability_id}/activate")
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert substrate_client.get("/forge/substrate/capabilities", params={"status": "active"}).json()


def test_bad_attributes_and_idempotency_collisions_return_client_errors(substrate_client, db):
    proposed = substrate_client.post("/forge/substrate/types", json={
        "category": "entity_type",
        "type_name": "schema_bound_resource",
        "schema": {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
            "additionalProperties": False,
        },
        "owner_agent": "test-agent",
    })
    assert proposed.status_code == 201
    activated = substrate_client.post(
        "/forge/substrate/types/entity_type/schema_bound_resource/status",
        json={
            "status": "active", "actor": "test-agent", "rationale": "For validation.",
            "evidence_ref": "backend/tests/test_substrate_api.py",
        },
    )
    assert activated.status_code == 200
    invalid_entity = substrate_client.post("/forge/substrate/entities", json={
        "entity_type": "schema_bound_resource",
        "display_name": "Invalid",
        "attributes": {"count": "one"},
        "created_by": "test-agent",
    })
    assert invalid_entity.status_code == 422

    unknown_entity = substrate_client.post("/forge/substrate/entities", json={
        "entity_type": "not_registered",
        "display_name": "Unknown",
        "attributes": {},
        "created_by": "test-agent",
    })
    assert unknown_entity.status_code == 422

    subject = substrate_client.post("/forge/substrate/entities", json={
        "entity_type": "resource",
        "display_name": "Evidence subject",
        "attributes": {},
        "created_by": "test-agent",
    }).json()

    first = substrate_client.post("/forge/substrate/evidence", json={
        "subject_kind": "entity",
        "subject_id": subject["id"],
        "claim": "First payload.",
        "support_level": "possible",
        "source": "manual",
        "provenance": {"source_ref": "one"},
        "idempotency_key": "api-evidence-conflict",
    })
    conflicting = substrate_client.post("/forge/substrate/evidence", json={
        "subject_kind": "entity",
        "subject_id": subject["id"],
        "claim": "Different payload.",
        "support_level": "possible",
        "source": "manual",
        "provenance": {"source_ref": "one"},
        "idempotency_key": "api-evidence-conflict",
    })
    assert first.status_code == 201, first.text
    assert conflicting.status_code == 409


def test_substrate_reads_and_writes_use_optional_api_key(substrate_client, monkeypatch):
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "substrate-secret")

    hidden = substrate_client.get("/forge/substrate/entities")
    visible = substrate_client.get(
        "/forge/substrate/entities", headers={"X-API-Key": "substrate-secret"}
    )
    denied_write = substrate_client.post("/forge/substrate/entities", json={
        "entity_type": "resource",
        "display_name": "Protected write",
        "attributes": {},
        "created_by": "test-agent",
    })
    authorized_write = substrate_client.post(
        "/forge/substrate/entities",
        headers={"X-API-Key": "substrate-secret"},
        json={
            "entity_type": "resource",
            "display_name": "Protected write",
            "attributes": {},
            "created_by": "test-agent",
        },
    )

    assert hidden.status_code == 401
    assert visible.status_code == 200
    assert denied_write.status_code == 401
    assert authorized_write.status_code == 201, authorized_write.text
