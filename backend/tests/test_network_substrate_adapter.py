import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import network_substrate_adapter, world_graph


def _endpoints(db):
    need = models.DomainRecord(
        kind="job",
        title="Local repair support needed",
        detail="A source record for a possible relationship.",
        close_token_hash="test",
    )
    provider = models.Provider(
        name="North workshop",
        business_name="North workshop",
        category="repair",
        summary="Repair provider serving local households.",
        city="Pokhara",
        country="Nepal",
    )
    db.add_all([need, provider])
    db.flush()
    return need, provider


def _connection(need, provider, **overrides):
    values = {
        "left_kind": "domain_record",
        "left_id": need.id,
        "right_kind": "provider",
        "right_id": provider.id,
        "relation_type": "offered_by",
        "direction": "directed",
        "epistemic_state": "hypothesized",
        "state": "candidate",
        "reason": "The provider may be able to meet this need.",
        "context": {"place": "Pokhara"},
        "uncertainty": {"relationship": "not yet verified"},
        "provenance": {"created_by": "reviewed_source"},
        "agreement_gap": "No agreement is implied.",
    }
    values.update(overrides)
    return models.NetworkConnection(**values)


def test_network_connection_projects_to_relation_with_evidence_and_source_history(db):
    need, provider = _endpoints(db)
    evidence = models.Evidence(
        source="reviewed_source",
        content="The source lists the workshop as offering repairs.",
        provenance='{"record":"catalogue-17"}',
    )
    db.add(evidence)
    db.flush()
    connection = _connection(need, provider)
    db.add(connection)
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=evidence.id,
        network_connection_id=connection.id,
        relation_type="derived_from",
        relation_key="source-evidence-to-connection-1",
    ))
    db.commit()

    first = network_substrate_adapter.sync_network_connections(db)
    assert first["entities_created"] == 2
    assert first["relations_created"] == 1
    assert first["projected_connections"] == 1
    assert first["unresolved_connections"] == 0
    assert connection.relation_id is not None
    relation = db.get(models.WorldRelation, connection.relation_id)
    left = world_graph.find_canonical_entity(db, "domain_record", need.id)
    right = world_graph.find_canonical_entity(db, "provider", provider.id)
    assert (relation.from_entity_id, relation.to_entity_id, relation.relation_type) == (
        left.id,
        right.id,
        "offered_by",
    )
    assert relation.truth_state == "hypothesized"

    projection = db.query(models.WorldEvent).filter_by(
        event_type="network_relation_projected", relation_id=relation.id
    ).one()
    payload = json.loads(projection.payload)
    assert payload["source_ref"] == {"entity_type": "network_connection", "entity_id": connection.id}
    assert payload["evidence_refs"] == [{
        "evidence_id": evidence.id,
        "relationship": "derived_from",
        "relation_key": "source-evidence-to-connection-1",
    }]
    assert payload["provenance"] == {"created_by": "reviewed_source"}

    second = network_substrate_adapter.sync_network_connections(db)
    assert second["entities_created"] == 0
    assert second["relations_created"] == 0
    assert second["events_created"] == 0
    assert db.query(models.WorldRelation).filter_by(idempotency_key=f"network-connection:{connection.id}:substrate-relation-v1").count() == 1

    connection.state = "proposed"
    connection.epistemic_state = "supported"
    db.commit()
    refreshed = network_substrate_adapter.sync_network_connections(db)
    assert refreshed["events_created"] == 1
    assert refreshed["epistemic_state_pending_evidence"] == 1
    assert relation.truth_state == "hypothesized"
    latest = (
        db.query(models.WorldEvent)
        .filter_by(event_type="network_relation_projected", relation_id=relation.id)
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert json.loads(latest.payload)["epistemic_state"] == "supported"
    assert json.loads(latest.payload)["workflow_state"] == "proposed"


def test_network_adapter_does_not_activate_unregistered_relation_types_or_guess_endpoints(db):
    need, provider = _endpoints(db)
    custom = world_graph.register_type(
        db,
        category="relation_type",
        type_name="custom_exchange",
        schema={"type": "object"},
        owner_agent="test-agent",
    )
    known_type_connection = _connection(need, provider, relation_type=custom.type_name)
    dangling_connection = _connection(
        need,
        provider,
        left_kind="network_connection",
        left_id=98765,
    )
    db.add_all([known_type_connection, dangling_connection])
    db.commit()

    result = network_substrate_adapter.sync_network_connections(db)
    assert result["unactivated_relation_types"] == 1
    assert result["unresolved_connections"] == 2
    assert known_type_connection.relation_id is None
    assert dangling_connection.relation_id is None
    db.refresh(custom)
    assert custom.status == "proposed"
    assert db.query(models.WorldRelation).count() == 0
    assert db.query(models.WorldEvent).filter_by(event_type="network_relation_unresolved").count() == 2


def test_inactive_endpoint_entity_type_does_not_starve_valid_network_connections(db):
    need, provider = _endpoints(db)
    opportunity = models.Opportunity(problem="This endpoint type becomes inactive.")
    db.add(opportunity)
    db.flush()
    blocked = _connection(
        need, provider, left_kind="opportunity", left_id=opportunity.id
    )
    db.add(blocked)
    db.commit()

    valid_need, valid_provider = _endpoints(db)
    valid = _connection(valid_need, valid_provider)
    db.add(valid)
    db.commit()

    opportunity_type = db.query(models.TypeRegistry).filter_by(
        category="entity_type", type_name="opportunity"
    ).one()
    world_graph.set_type_status(
        db, opportunity_type, "deprecated",
        actor="test_agent",
        rationale="Inactive endpoint types cannot starve valid links.",
        evidence_ref="backend/tests/test_network_substrate_adapter.py",
    )

    result = network_substrate_adapter.sync_network_connections(db, limit=1)

    assert result["projected_connections"] == 1
    assert result["unresolved_connections"] == 1
    assert db.get(models.NetworkConnection, valid.id).relation_id is not None
    assert db.get(models.NetworkConnection, blocked.id).relation_id is None


def test_old_unregistered_connection_does_not_starve_new_valid_connection(db):
    need, provider = _endpoints(db)
    invalid = _connection(need, provider, relation_type="not_registered")
    db.add(invalid)
    db.commit()

    valid_need, valid_provider = _endpoints(db)
    valid = _connection(valid_need, valid_provider)
    db.add(valid)
    db.commit()

    result = network_substrate_adapter.sync_network_connections(db, limit=1)

    assert result["projected_connections"] == 1
    assert result["unresolved_connections"] == 1
    assert result["unactivated_relation_types"] == 1
    assert db.get(models.NetworkConnection, valid.id).relation_id is not None
    assert db.get(models.NetworkConnection, invalid.id).relation_id is None
    assert db.query(models.WorldEvent).filter_by(
        event_type="network_relation_unresolved"
    ).count() == 1
    assert db.query(models.WorldEvent).filter_by(
        event_type="network_relation_projected"
    ).count() == 1


def test_small_network_batch_projects_parent_before_nested_child(db):
    need, provider = _endpoints(db)
    outcome = models.Outcome(
        source="human_report",
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="A response was recorded.",
    )
    db.add(outcome)
    db.flush()
    parent = _connection(need, provider)
    db.add(parent)
    db.flush()
    child = models.NetworkConnection(
        left_kind="network_connection",
        left_id=parent.id,
        right_kind="outcome",
        right_id=outcome.id,
        relation_type="derived_from",
        direction="directed",
        epistemic_state="hypothesized",
        state="candidate",
        reason="The outcome is related to the parent connection.",
        agreement_gap="The causal link is still unverified.",
    )
    db.add(child)
    db.commit()

    first = network_substrate_adapter.sync_network_connections(db, limit=1)
    assert first["projected_connections"] == 1
    assert db.get(models.NetworkConnection, parent.id).relation_id is not None
    assert db.get(models.NetworkConnection, child.id).relation_id is None

    second = network_substrate_adapter.sync_network_connections(db, limit=1)
    assert second["projected_connections"] == 1
    assert db.get(models.NetworkConnection, child.id).relation_id is not None
    parent_relation_entity = world_graph.find_canonical_entity(
        db, "relation", parent.relation_id
    )
    child_relation = db.get(models.WorldRelation, child.relation_id)
    assert child_relation.from_entity_id == parent_relation_entity.id


def test_nested_network_connection_uses_its_substrate_relation_as_endpoint(db):
    need, provider = _endpoints(db)
    outcome = models.Outcome(
        source="human_report",
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="A response was recorded.",
    )
    db.add(outcome)
    db.flush()
    first = _connection(need, provider)
    db.add(first)
    db.flush()
    second = models.NetworkConnection(
        left_kind="network_connection",
        left_id=first.id,
        right_kind="outcome",
        right_id=outcome.id,
        relation_type="derived_from",
        direction="directed",
        epistemic_state="hypothesized",
        state="candidate",
        reason="The response is linked to the earlier connection record.",
        agreement_gap="No agreement is implied.",
    )
    db.add(second)
    db.commit()

    result = network_substrate_adapter.sync_network_connections(db)
    assert result["projected_connections"] == 2
    assert result["unresolved_connections"] == 0
    first_relation_entity = world_graph.find_canonical_entity(db, "relation", first.relation_id)
    second_relation = db.get(models.WorldRelation, second.relation_id)
    assert second_relation.from_entity_id == first_relation_entity.id
    assert second_relation.to_entity_id == world_graph.find_canonical_entity(db, "outcome", outcome.id).id


def test_network_relation_transition_still_uses_constitutional_evidence_path(db):
    need, provider = _endpoints(db)
    connection = _connection(need, provider, epistemic_state="supported")
    db.add(connection)
    db.commit()

    network_substrate_adapter.sync_network_connections(db)
    relation = db.get(models.WorldRelation, connection.relation_id)
    assert relation.truth_state == "hypothesized"
    assert not db.query(models.Evidence).filter_by(subject_kind="relation", subject_id=relation.id).first()


def test_network_projection_survives_database_restart_and_remains_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'substrate-restart.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as first_session:
        need, provider = _endpoints(first_session)
        connection = _connection(need, provider)
        first_session.add(connection)
        first_session.commit()
        connection_id = connection.id
        initial = network_substrate_adapter.sync_network_connections(first_session)
        first_session.commit()
        relation_id = first_session.get(models.NetworkConnection, connection_id).relation_id
        assert initial["relations_created"] == 1

    # A fresh ORM session against the persisted database models a process restart.
    with Session() as restarted_session:
        repeated = network_substrate_adapter.sync_network_connections(restarted_session)
        restarted_session.commit()
        connection = restarted_session.get(models.NetworkConnection, connection_id)
        assert connection.relation_id == relation_id
        assert repeated["relations_created"] == 0
        assert repeated["events_created"] == 0
        assert restarted_session.query(models.WorldRelation).count() == 1
        assert restarted_session.query(models.WorldEvent).filter_by(
            event_type="network_relation_projected"
        ).count() == 1
    engine.dispose()


def test_network_dependency_cycle_is_reported_not_left_silent(db):
    _need, provider = _endpoints(db)
    first = models.NetworkConnection(
        left_kind="network_connection",
        left_id=1,
        right_kind="provider",
        right_id=provider.id,
        relation_type="offered_by",
        direction="directed",
        epistemic_state="hypothesized",
        state="candidate",
        reason="First side of a deliberately cyclic dependency.",
        agreement_gap="Neither connection has a projectable root.",
    )
    second = models.NetworkConnection(
        left_kind="network_connection",
        left_id=1,
        right_kind="provider",
        right_id=provider.id,
        relation_type="offered_by",
        direction="directed",
        epistemic_state="hypothesized",
        state="candidate",
        reason="Second side of a deliberately cyclic dependency.",
        agreement_gap="Neither connection has a projectable root.",
    )
    db.add_all([first, second])
    db.flush()
    first.left_id = second.id
    second.left_id = first.id
    db.commit()

    result = network_substrate_adapter.sync_network_connections(db, limit=2)

    assert result["projected_connections"] == 0
    assert result["unresolved_connections"] == 2
    unresolved = db.query(models.WorldEvent).filter_by(
        event_type="network_relation_unresolved",
    ).all()
    assert len(unresolved) == 2
    assert all(
        "possible cycle" in json.loads(event.payload)["reason"]
        for event in unresolved
    )


def test_canonical_cycle_projects_existing_network_connections(db):
    from app.services import forge_loop

    need, provider = _endpoints(db)
    connection = _connection(need, provider)
    db.add(connection)
    db.commit()

    summary = forge_loop.run_cycle(db)

    assert "substrate_adapters" not in summary["stage_errors"]
    assert summary["substrate_network_connections_projected"] == 1
    assert summary["substrate_relations_created"] >= 1
    assert db.get(models.NetworkConnection, connection.id).relation_id is not None
