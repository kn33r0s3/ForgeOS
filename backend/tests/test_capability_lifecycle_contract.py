"""CAPABILITY primitive write contract.

An ``active`` capability is a claim that Hami can reliably do something. It
must therefore only be reachable through the lifecycle services, and only with
an attributable passing run of a repository test file: who ran it, against
which revision, with a command that actually invokes that file. Before this
contract, any ORM write could insert or assign ``status="active"`` directly and
downstream gates (for example economic validation) trusted it.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import models
from app.database import get_db
from app.main import app
from app.services import world_graph

TEST_REF = "backend/tests/test_capability_lifecycle_contract.py"
PROVENANCE = {"actor": "test", "revision": "bf8546ed26f9179e8522726e966a984fc1dd83c6"}


def _proposed(db, name="lifecycle-contract-capability"):
    world_graph.seed_core_types(db)
    return world_graph.create_capability(
        db,
        capability_type="workflow",
        name=name,
        description="Capability lifecycle contract fixture.",
        owner_agent="test",
    )


def _non_starved(db):
    """Establish recent real-world contact so STARVED does not block builds.
    Lifecycle tests verify mechanics, not operating discipline."""
    world_graph.seed_core_types(db)
    world_graph.create_event(
        db,
        event_type="outreach.sent",
        source="test",
        payload={"note": "lifecycle test contact"},
    )
    db.commit()


def test_capabilities_cannot_be_born_active_or_pre_tested(db):
    world_graph.seed_core_types(db)
    db.add(models.ForgeCapability(
        capability_type="workflow", name="born-active", description="x",
        owner_agent="test", status="active", test_ref=TEST_REF,
    ))
    with pytest.raises(world_graph.SubstrateError, match="must begin proposed"):
        db.flush()
    db.rollback()
    db.add(models.ForgeCapability(
        capability_type="workflow", name="born-with-test-ref", description="x",
        owner_agent="test", test_ref=TEST_REF,
    ))
    with pytest.raises(world_graph.SubstrateError, match="must begin proposed"):
        db.flush()


def test_status_and_test_ref_assignment_cannot_bypass_the_lifecycle(db):
    capability = _proposed(db)
    db.commit()
    capability.test_ref = TEST_REF
    capability.status = "active"
    with pytest.raises(world_graph.SubstrateError, match="lifecycle services"):
        db.flush()
    db.rollback()

    capability = db.query(models.ForgeCapability).filter_by(name="lifecycle-contract-capability").one()
    assert capability.status == "proposed"
    capability.test_ref = TEST_REF
    with pytest.raises(world_graph.SubstrateError, match="lifecycle services"):
        db.flush()
    db.rollback()
    _non_starved(db)
    world_graph.begin_capability_build(db, capability)
    capability.status = "tested"
    with pytest.raises(world_graph.SubstrateError, match="lifecycle services"):
        db.flush()


def test_a_pass_requires_actor_revision_and_a_command_that_runs_the_test(db):
    capability = _proposed(db)
    _non_starved(db)
    world_graph.begin_capability_build(db, capability)
    for provenance, command, message in (
        ({}, f"pytest {TEST_REF}", "provenance.actor"),
        ({"actor": "test"}, f"pytest {TEST_REF}", "provenance.revision"),
        ({"actor": "test", "revision": "main"}, f"pytest {TEST_REF}", "provenance.revision"),
        (PROVENANCE, "echo ok", "must invoke the referenced test_ref"),
    ):
        with pytest.raises(world_graph.SubstrateError, match=message):
            world_graph.mark_capability_tested(
                db, capability, test_ref=TEST_REF, command=command,
                exit_code=0, output_excerpt="passed", provenance=provenance,
            )
        assert capability.status == "building"
    assert db.query(models.WorldEvent).filter_by(event_type="capability_test_passed").count() == 0

    # Failures are never erased, even without provenance.
    world_graph.mark_capability_tested(
        db, capability, test_ref=TEST_REF, command=f"pytest {TEST_REF}",
        exit_code=1, output_excerpt="1 failed",
    )
    assert capability.status == "building"
    assert db.query(models.WorldEvent).filter_by(event_type="capability_test_failed").count() == 1


def test_attributable_pass_activates_and_is_reported_as_the_activation_record(db):
    capability = _proposed(db)
    assert world_graph.capability_activation_record(db, capability) is None
    _non_starved(db)
    world_graph.begin_capability_build(db, capability)
    world_graph.mark_capability_tested(
        db, capability, test_ref=TEST_REF, command=f"python -m pytest {TEST_REF} -q",
        exit_code=0, output_excerpt="5 passed", provenance=PROVENANCE,
    )
    world_graph.activate_capability(db, capability)
    db.commit()

    assert capability.status == "active"
    record = world_graph.capability_activation_record(db, capability)
    event = db.get(models.WorldEvent, record["test_event_id"])
    assert event.event_type == "capability_test_passed"
    assert json.loads(event.payload)["provenance"] == PROVENANCE
    assert (record["actor"], record["revision"], record["test_ref"]) == (
        "test", PROVENANCE["revision"], TEST_REF,
    )


def test_legacy_active_rows_without_attributable_pass_are_not_verified(db):
    """Rows written before this contract keep their status but are not trusted."""
    capability = _proposed(db, name="legacy-active-capability")
    db.commit()
    db.execute(
        text("UPDATE capabilities SET status='active', test_ref=:ref WHERE id=:id"),
        {"ref": TEST_REF, "id": capability.id},
    )
    world_graph.create_event(
        db, event_type="capability_test_passed", source="pytest",
        payload={"capability_id": capability.id, "test_ref": TEST_REF, "command": "echo ok", "exit_code": 0},
    )
    db.commit()
    db.refresh(capability)
    assert capability.status == "active"
    assert world_graph.capability_activation_record(db, capability) is None


def test_substrate_api_rejects_unattributed_passes_and_reports_verification(db, monkeypatch):
    from app import security
    # Substrate writes are owner-keyed (Step 1).
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "capability-test-key")

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, headers={"X-API-Key": "capability-test-key"})
        world_graph.seed_core_types(db)
        db.commit()
        _non_starved(db)
        created = client.post("/forge/substrate/capabilities", json={
            "capability_type": "workflow",
            "name": "api-lifecycle-contract",
            "description": "API lifecycle contract fixture.",
            "owner_agent": "test",
        })
        assert created.status_code == 201, created.text
        assert created.json()["activation"] == {"verified": False, "record": None}
        capability_id = created.json()["id"]
        assert client.post(f"/forge/substrate/capabilities/{capability_id}/build").status_code == 200

        body = {"test_ref": TEST_REF, "command": f"pytest {TEST_REF}", "exit_code": 0, "output_excerpt": "passed"}
        unattributed = client.post(f"/forge/substrate/capabilities/{capability_id}/test", json=body)
        assert unattributed.status_code == 422
        assert unattributed.json() == {"detail": "Invalid request value."}

        tested = client.post(
            f"/forge/substrate/capabilities/{capability_id}/test",
            json={**body, **PROVENANCE},
        )
        assert tested.status_code == 200, tested.text
        activated = client.post(f"/forge/substrate/capabilities/{capability_id}/activate")
        assert activated.status_code == 200, activated.text
        payload = activated.json()
        assert payload["status"] == "active"
        assert payload["activation"]["verified"] is True
        assert payload["activation"]["record"]["revision"] == PROVENANCE["revision"]
        listed = client.get("/forge/substrate/capabilities", params={"status": "active"}).json()
        assert [row["activation"]["verified"] for row in listed] == [True]
    finally:
        app.dependency_overrides.clear()


def test_starved_blocks_capability_build(db):
    """STARVED freeze is authoritative over begin_capability_build."""
    from app.services import operating_v4

    capability = _proposed(db)
    assert operating_v4.is_starved(db) is True
    with pytest.raises(world_graph.SubstrateError, match="STARVED"):
        world_graph.begin_capability_build(db, capability)
    db.rollback()
    assert capability.status == "proposed"


def test_system_obligation_bypasses_starved(db):
    """System Obligations are exempt from the STARVED freeze."""
    capability = _proposed(db)
    world_graph.begin_capability_build(db, capability, is_system_obligation=True)
    assert capability.status == "building"


def test_non_starved_allows_build(db):
    """Recent contact lifts the STARVED freeze."""
    from app.services import operating_v4

    capability = _proposed(db)
    _non_starved(db)
    assert operating_v4.is_starved(db) is False
    world_graph.begin_capability_build(db, capability)
    assert capability.status == "building"
