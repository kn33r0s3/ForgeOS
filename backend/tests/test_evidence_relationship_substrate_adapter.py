import json

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import (
    evidence_relationship_substrate_adapter as adapter,
    legacy_evidence_substrate_adapter,
    world_graph,
)


def _evidence_claim_link(db, *, relation_type="derived_from", other_target=False):
    signal = models.Signal(source="reviewed archive", content="A source observation.")
    db.add(signal)
    db.flush()
    evidence = models.Evidence(
        signal_id=signal.id,
        source=signal.source,
        content="The evidence text remains in its legacy row.",
        direction="supports",
        confidence=76.0,
        provenance='{"archive_ref":"source-11"}',
    )
    claim = models.Claim(
        statement="The observed process may have a recurring delay.",
        normalized_statement="the observed process may have a recurring delay",
        epistemic_state="observed",
    )
    db.add_all([evidence, claim])
    db.flush()
    decision = None
    if other_target:
        decision = models.Decision(title="Review the evidence link", rationale="Explicit target fixture")
        db.add(decision)
        db.flush()
    link = models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim.id,
        decision_id=decision.id if decision is not None else None,
        relation_type=relation_type,
        relation_key=f"legacy-link-{evidence.id}-{claim.id}",
    )
    db.add(link)
    db.commit()
    db.refresh(evidence)
    db.refresh(claim)
    db.refresh(link)
    return evidence, claim, link, decision


def test_explicit_legacy_evidence_claim_link_projects_to_one_relation(db):
    evidence, claim, source_link, _decision = _evidence_claim_link(db)
    raw_before = (evidence.source, evidence.content, evidence.direction, evidence.confidence, evidence.provenance)

    legacy_evidence_substrate_adapter.sync_legacy_evidence(db)
    first = adapter.sync_evidence_relationships(db)

    assert first == {
        "records_seen": 1,
        "relations_created": 1,
        "entities_created": 2,
        "unresolved_records": 0,
    }
    edge = db.get(models.WorldRelation, source_link.substrate_relation_id)
    evidence_node = world_graph.find_canonical_entity(db, "evidence_record", evidence.id)
    claim_node = world_graph.find_canonical_entity(db, "claim", claim.id)
    assert evidence_node is not None and evidence_node.source_system == "evidence"
    assert evidence_node.source_id == str(evidence.id)
    assert claim_node is not None
    assert (edge.from_entity_id, edge.to_entity_id) == (evidence_node.id, claim_node.id)
    assert edge.relation_type == "derived_from"
    assert edge.direction == "directed"
    assert edge.truth_state == "hypothesized"
    assert edge.idempotency_key == f"legacy-evidence-relationship:{source_link.id}:substrate-v1"
    assert json.loads(edge.attributes) == {
        "claim_ref": {"id": claim.id, "table": "claims"},
        "evidence_ref": {"id": evidence.id, "table": "evidence"},
        "payload_copied": False,
        "source_ref": {"id": source_link.id, "table": "evidence_relationships"},
    }
    assert source_link.substrate_relation_id == edge.id
    assert claim.epistemic_state == "observed"
    assert (evidence.source, evidence.content, evidence.direction, evidence.confidence, evidence.provenance) == raw_before
    assert db.query(models.Evidence).count() == 1

    repeated = adapter.sync_evidence_relationships(db)
    assert repeated["records_seen"] == 0
    assert repeated["relations_created"] == 0
    assert db.query(models.WorldRelation).count() == 1
    assert db.query(models.SubstrateEntity).filter_by(entity_type="evidence_record").count() == 1


def test_supported_explicit_targets_project_by_reference(db):
    evidence, claim, claim_link, _decision = _evidence_claim_link(db)

    opportunity = models.Opportunity(problem="Opportunity source target")
    decision = models.Decision(title="Decision source target", rationale="A linked decision")
    experiment = models.Experiment(action="Run a bounded test")
    outcome = models.Outcome(
        outcome_type="QUALITATIVE",
        source="owner_report",
        qualitative_result="An observed outcome",
    )
    judgment = models.Judgment(
        judge_name="fixture-judge",
        provider="test",
        model="deterministic",
        question="Does the evidence support the question?",
        evidence_ids=str(evidence.id),
        judgment_key="target-projector-test-judgment",
        status="completed",
    )
    db.add_all([opportunity, decision, experiment, outcome, judgment])
    db.flush()

    targets = [
        ("opportunity_id", "opportunity", opportunity, "supports"),
        ("decision_id", "decision", decision, "informs"),
        ("experiment_id", "experiment", experiment, "derived_from"),
        ("outcome_id", "outcome", outcome, "supports"),
        ("judgment_id", "judgment", judgment, "supports"),
    ]
    rows = []
    for index, (field, _entity_type, target, relation_type) in enumerate(targets, start=1):
        row = models.EvidenceRelationship(
            evidence_id=evidence.id,
            **{field: target.id},
            relation_type=relation_type,
            relation_key=f"explicit-target-{index}-{target.id}",
        )
        db.add(row)
        rows.append(row)
    db.commit()

    legacy_evidence_substrate_adapter.sync_legacy_evidence(db)
    first = adapter.sync_evidence_relationships(db, limit=20)

    assert first == {
        "records_seen": 6,
        "relations_created": 6,
        "entities_created": 7,
        "unresolved_records": 0,
    }

    expected_by_row = [(claim_link, "claim", claim.id, "claims")]
    expected_by_row.extend(
        (row, entity_type, target.id, target.__tablename__)
        for row, (_field, entity_type, target, _relation_type) in zip(rows, targets)
    )
    for row, expected_type, expected_id, target_table in expected_by_row:
        relation = db.get(models.WorldRelation, row.substrate_relation_id)
        assert relation is not None
        target_entity = db.get(models.SubstrateEntity, relation.to_entity_id)
        assert target_entity is not None
        assert target_entity.entity_type == expected_type
        attrs = json.loads(relation.attributes)
        assert attrs["payload_copied"] is False
        assert attrs["evidence_ref"] == {"table": "evidence", "id": evidence.id}
        assert attrs["source_ref"] == {"table": "evidence_relationships", "id": row.id}
        assert attrs[f"{expected_type}_ref"] == {
            "table": target_table,
            "id": expected_id,
        }

    repeated = adapter.sync_evidence_relationships(db, limit=20)
    assert repeated["records_seen"] == 0
    assert repeated["relations_created"] == 0
    assert db.query(models.WorldRelation).count() == 6


def test_evidence_to_network_connection_uses_existing_projected_relation(db):
    from app.services import network_substrate_adapter

    evidence, claim, _claim_link, _decision = _evidence_claim_link(db)
    opportunity = models.Opportunity(problem="Network relation target")
    db.add(opportunity)
    db.flush()
    connection = models.NetworkConnection(
        left_kind="claim",
        left_id=claim.id,
        right_kind="opportunity",
        right_id=opportunity.id,
        relation_type="supports",
        reason="The relationship is recorded but not independently verified.",
        agreement_gap="No independent confirmation recorded.",
    )
    db.add(connection)
    db.commit()

    projection = network_substrate_adapter.sync_network_connections(db)
    assert projection["projected_connections"] == 1
    db.refresh(connection)
    assert connection.relation_id is not None

    source_link = models.EvidenceRelationship(
        evidence_id=evidence.id,
        network_connection_id=connection.id,
        relation_type="supports",
        relation_key="evidence-to-network-connection",
    )
    db.add(source_link)
    db.commit()

    first = adapter.sync_evidence_relationships(db)

    assert first == {
        "records_seen": 1,
        "relations_created": 1,
        "entities_created": 2,
        "unresolved_records": 0,
    }
    edge = db.get(models.WorldRelation, source_link.substrate_relation_id)
    assert edge is not None
    relation_entity = world_graph.find_canonical_entity(
        db, "relation", connection.relation_id
    )
    assert relation_entity is not None
    assert edge.to_entity_id == relation_entity.id
    attrs = json.loads(edge.attributes)
    assert attrs["relation_ref"] == {
        "table": "relations",
        "id": connection.relation_id,
    }
    assert attrs["network_connection_ref"] == {
        "table": "network_connections",
        "id": connection.id,
    }
    assert attrs["payload_copied"] is False

    again = adapter.sync_evidence_relationships(db)
    assert again["records_seen"] == 0
    assert again["relations_created"] == 0
    assert db.query(models.WorldRelation).count() == 2


def test_unregistered_or_ambiguous_evidence_links_remain_unprojected(db):
    evidence, claim, unregistered, _decision = _evidence_claim_link(
        db, relation_type="unreviewed_link_type"
    )
    _evidence2, _claim2, ambiguous, decision = _evidence_claim_link(
        db, relation_type="derived_from", other_target=True
    )
    # Without an existing substrate relation pointer, the evidence projector
    # must leave the target unresolved instead of guessing its endpoint.
    connection = models.NetworkConnection(
        left_kind="claim",
        left_id=claim.id,
        right_kind="opportunity",
        right_id=1,
        reason="Potential connection only",
        agreement_gap="Independent confirmation is absent",
    )
    db.add(connection)
    db.flush()
    network_link = models.EvidenceRelationship(
        evidence_id=evidence.id,
        network_connection_id=connection.id,
        relation_type="supports",
        relation_key="evidence-network-connection-remains-explicit",
    )
    db.add(network_link)
    db.commit()

    result = adapter.sync_evidence_relationships(db, limit=20)

    assert result["records_seen"] == 3
    assert result["relations_created"] == 0
    assert result["unresolved_records"] == 3
    assert unregistered.substrate_relation_id is None
    assert ambiguous.substrate_relation_id is None
    assert network_link.substrate_relation_id is None
    assert decision is not None
    assert db.query(models.TypeRegistry).filter_by(
        category="relation_type", type_name="unreviewed_link_type"
    ).count() == 0
    assert db.query(models.WorldRelation).count() == 0



def test_unresolved_old_links_do_not_starve_later_valid_links(db):
    _evidence1, _claim1, invalid_type, _decision1 = _evidence_claim_link(
        db, relation_type="unreviewed_link_type"
    )
    _evidence2, _claim2, ambiguous, _decision2 = _evidence_claim_link(
        db, relation_type="derived_from", other_target=True
    )
    evidence3, claim3, _link3, _decision3 = _evidence_claim_link(db)
    connection = models.NetworkConnection(
        left_kind="claim",
        left_id=claim3.id,
        right_kind="opportunity",
        right_id=1,
        reason="Not yet projected",
        agreement_gap="Endpoint relation is not available yet.",
    )
    db.add(connection)
    db.flush()
    waiting_network_link = models.EvidenceRelationship(
        evidence_id=evidence3.id,
        network_connection_id=connection.id,
        relation_type="supports",
        relation_key="old-network-link-waits-for-projection",
    )
    db.add(waiting_network_link)
    db.commit()

    _evidence4, _claim4, valid, _decision4 = _evidence_claim_link(db)

    result = adapter.sync_evidence_relationships(db, limit=1)

    assert result["records_seen"] == 4
    assert result["relations_created"] == 1
    assert result["unresolved_records"] == 3
    assert valid.substrate_relation_id is not None
    assert invalid_type.substrate_relation_id is None
    assert ambiguous.substrate_relation_id is None
    assert waiting_network_link.substrate_relation_id is None


def test_evidence_id_scope_projects_only_selected_relationships(db):
    _evidence, _claim, selected, _decision = _evidence_claim_link(db)
    _other_evidence, _other_claim, other, _other_decision = _evidence_claim_link(db)

    result = adapter.sync_evidence_relationships(db, evidence_ids={selected.evidence_id})

    assert result["records_seen"] == result["relations_created"] == 1
    assert result["unresolved_records"] == 0
    assert selected.substrate_relation_id is not None
    assert other.substrate_relation_id is None


def test_evidence_relationship_projection_survives_restart(tmp_path):
    path = tmp_path / "evidence_relationship.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as first_session:
        evidence, claim, link, _decision = _evidence_claim_link(first_session)
        legacy_evidence_substrate_adapter.sync_legacy_evidence(first_session)
        first = adapter.sync_evidence_relationships(first_session)
        first_session.commit()
        run_migrations(engine)
        assert first["relations_created"] == 1
        link_id, relation_id, evidence_id, claim_id = link.id, link.substrate_relation_id, evidence.id, claim.id
    engine.dispose()

    engine = create_engine(f"sqlite:///{path}")
    with sessionmaker(bind=engine)() as restarted:
        assert run_migrations(engine) == []
        again = adapter.sync_evidence_relationships(restarted)
        assert again["records_seen"] == 0
        link = restarted.get(models.EvidenceRelationship, link_id)
        assert link.substrate_relation_id == relation_id
        assert restarted.query(models.WorldRelation).filter_by(
            idempotency_key=f"legacy-evidence-relationship:{link_id}:substrate-v1"
        ).count() == 1
        assert restarted.get(models.Evidence, evidence_id) is not None
        assert world_graph.find_canonical_entity(restarted, "claim", claim_id) is not None
    engine.dispose()


def test_additive_migration_adds_relation_back_reference_without_rewriting_links():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE evidence_relationships (id INTEGER PRIMARY KEY, evidence_id INTEGER NOT NULL, "
            "claim_id INTEGER, relation_type TEXT NOT NULL, relation_key TEXT NOT NULL, created_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO evidence_relationships (id, evidence_id, claim_id, relation_type, relation_key) "
            "VALUES (1, 8, 13, 'derived_from', 'old-key')"
        )

    applied = run_migrations(engine)

    assert any(
        statement.startswith("ALTER TABLE evidence_relationships ADD COLUMN substrate_relation_id")
        for statement in applied
    )
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT id, evidence_id, claim_id, relation_type, relation_key, substrate_relation_id "
            "FROM evidence_relationships WHERE id = 1"
        ).one()
    assert tuple(row) == (1, 8, 13, "derived_from", "old-key", None)
    assert any(
        index["unique"] and index["column_names"] == ["substrate_relation_id"]
        for index in inspect(engine).get_indexes("evidence_relationships")
    )
    assert run_migrations(engine) == []
    engine.dispose()
