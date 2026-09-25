from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import world_graph


def _seed(db):
    world_graph.seed_core_types(db)
    db.flush()


def test_type_registry_validates_open_domain_attributes(db):
    _seed(db)
    with pytest.raises(world_graph.SubstrateError, match="unknown entity_type"):
        world_graph.create_entity(
            db, entity_type="not_registered", display_name="Unknown",
            attributes={}, created_by="test",
        )
    registry = world_graph.register_type(
        db,
        category="entity_type",
        type_name="reusable_asset",
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 2},
                "capacity": {"type": "integer", "minimum": 0},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        owner_agent="codex_serial_task",
        status="proposed",
    )
    assert registry.status == "proposed"
    with pytest.raises(world_graph.SubstrateError, match="is proposed"):
        world_graph.create_entity(
            db, entity_type="reusable_asset", display_name="Not active",
            attributes={"name": "Storage"}, created_by="test",
        )
    world_graph.set_type_status(
        db, registry, "active", actor="test_agent",
        rationale="The type schema is covered by the validation suite.",
        evidence_ref="backend/tests/test_world_graph.py::test_type_registry_validates_open_domain_attributes",
    )

    valid = world_graph.create_entity(
        db,
        entity_type="reusable_asset",
        display_name="Available storage",
        attributes={"name": "Storage unit", "capacity": 2},
        created_by="test",
    )
    assert valid.entity_type == "reusable_asset"
    assert '"capacity":2' in valid.attributes

    with pytest.raises(world_graph.SubstrateError, match="required"):
        world_graph.create_entity(
            db,
            entity_type="reusable_asset",
            display_name="Missing name",
            attributes={"capacity": 2},
            created_by="test",
        )
    with pytest.raises(world_graph.SubstrateError, match="additional property"):
        world_graph.create_entity(
            db,
            entity_type="reusable_asset",
            display_name="Unknown property",
            attributes={"name": "Valid", "made_up": True},
            created_by="test",
        )
    with pytest.raises(world_graph.SubstrateError, match="different schema"):
        world_graph.register_type(
            db,
            category="entity_type",
            type_name="reusable_asset",
            schema={"type": "object"},
            owner_agent="other",
        )
    with pytest.raises(world_graph.SubstrateError, match="malformed JSON Schema"):
        world_graph.register_type(
            db,
            category="entity_type",
            type_name="broken_schema",
            schema={"type": "not-a-json-schema-type"},
            owner_agent="test",
        )
    with pytest.raises(world_graph.SubstrateError, match="new types must begin proposed"):
        world_graph.register_type(
            db,
            category="entity_type",
            type_name="unreviewed_type",
            schema={"type": "object"},
            owner_agent="test",
            status="active",
        )
    world_graph.set_type_status(
        db, registry, "deprecated", actor="test_agent",
        rationale="The test exercises deprecated type rejection.",
        evidence_ref="backend/tests/test_world_graph.py::test_type_registry_validates_open_domain_attributes",
    )
    with pytest.raises(world_graph.SubstrateError, match="is deprecated"):
        world_graph.create_entity(
            db, entity_type="reusable_asset", display_name="Deprecated",
            attributes={"name": "Storage"}, created_by="test",
        )


def test_canonical_intelligence_path_adapts_without_copying_data_and_is_idempotent(db):
    _seed(db)
    signal = models.Signal(
        source="research_fixture",
        source_type="external",
        title="Source title",
        content="Source content remains in the canonical signals table.",
        canonical_url="https://example.org/source",
    )
    db.add(signal)
    db.flush()
    pattern = models.Pattern(
        title="A recurring theme",
        description="A repeated, still revisable observation.",
        origin_signal_ids=str(signal.id),
    )
    db.add(pattern)
    db.flush()
    belief = models.Belief(
        statement="This relationship remains a hypothesis.",
        pattern_id=pattern.id,
        supporting_signal_ids=str(signal.id),
    )
    db.add(belief)
    db.flush()
    opportunity = models.Opportunity(
        problem="A possible opportunity requiring more research",
        pattern_id=pattern.id,
        identity_key="world-graph-test-opportunity",
        problem_evidence_signal_ids=str(signal.id),
        uncertainty=100,
    )
    db.add(opportunity)
    db.commit()

    first = world_graph.sync_intelligence_path(db, limit=100)
    db.commit()
    second = world_graph.sync_intelligence_path(db, limit=100)
    db.commit()

    assert first["entities_created"] == 4
    assert first["relations_created"] >= 4
    assert second == {"entities_created": 0, "relations_created": 0}
    signal_entity = world_graph.find_canonical_entity(db, "signal", signal.id)
    assert signal_entity is not None
    assert signal_entity.attributes == '{"canonical_ref":{"entity_id":%d,"entity_type":"signal"}}' % signal.id
    assert db.get(models.Signal, signal.id).content.startswith("Source content")
    assert signal_entity.identity_key == f"source:signals:{signal.id}"
    assert signal_entity.source_system == "signals"
    assert signal_entity.source_id == str(signal.id)
    assert signal_entity.identity_state == "candidate"
    assert "research_fixture" in signal_entity.identity_provenance
    assert db.query(models.WorldRelation).filter_by(truth_state="hypothesized").count() >= 4
    assert db.query(models.WorldEvent).filter_by(event_type="signal_ingested", entity_id=signal_entity.id).count() == 1


def test_relations_compose_and_cannot_skip_tested_evidence(db):
    _seed(db)
    left = world_graph.create_entity(
        db, entity_type="resource", display_name="Observed capacity",
        attributes={"provenance": "recorded input"}, created_by="test",
    )
    right = world_graph.create_entity(
        db, entity_type="resource", display_name="Possible use",
        attributes={"description": "A hypothesis only."}, created_by="test",
    )
    relation = world_graph.create_relation(
        db,
        from_entity_id=left.id,
        to_entity_id=right.id,
        relation_type="enables",
        attributes={"context": {"geography": "Nepal"}, "conditions": ["capacity remains available"]},
        truth_state="possible",
        strength=0.4,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_by="test",
        idempotency_key="hypothesis:resource:77",
    )
    assert world_graph.create_relation(
        db,
        from_entity_id=left.id,
        to_entity_id=right.id,
        relation_type="enables",
        attributes={"context": {"geography": "Nepal"}, "conditions": ["capacity remains available"]},
        truth_state="possible",
        strength=0.4,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_by="test",
        idempotency_key="hypothesis:resource:77",
    ).id == relation.id

    db.commit()
    relation.truth_state = "supported"
    with pytest.raises(world_graph.SubstrateError, match="canonical transition service"):
        db.flush()
    db.rollback()
    relation = db.get(models.WorldRelation, relation.id)
    assert relation.truth_state == "possible"

    with pytest.raises(world_graph.SubstrateError, match="cannot move relation from possible to supported"):
        world_graph.transition_relation_truth_state(db, relation, "supported")
    world_graph.transition_relation_truth_state(db, relation, "hypothesized")
    with pytest.raises(world_graph.SubstrateError, match="cannot move relation from hypothesized to supported"):
        world_graph.transition_relation_truth_state(db, relation, "supported")
    tested_evidence = world_graph.create_evidence(
        db,
        subject_kind="relation",
        subject_id=relation.id,
        claim="A test exercised the relationship rule.",
        support_level="tested",
        source="pytest",
        provenance={"test_ref": "backend/tests/test_world_graph.py::test_relations_compose_and_cannot_skip_tested_evidence", "result": "passed"},
    )
    assert tested_evidence.subject_kind == "relation"
    world_graph.transition_relation_truth_state(db, relation, "tested")
    with pytest.raises(world_graph.SubstrateError, match="requires recorded supported evidence"):
        world_graph.transition_relation_truth_state(db, relation, "supported")
    evidence_count = db.query(models.Evidence).filter_by(subject_kind="relation", subject_id=relation.id).count()
    tested_provenance = tested_evidence.provenance
    world_graph.create_evidence(
        db,
        subject_kind="relation",
        subject_id=relation.id,
        claim="The cited test result supports this test-only relation.",
        support_level="supported",
        source="pytest",
        provenance={"test_ref": "backend/tests/test_world_graph.py::test_relations_compose_and_cannot_skip_tested_evidence", "result": "passed"},
    )
    world_graph.transition_relation_truth_state(db, relation, "supported")
    assert relation.truth_state == "supported"
    assert tested_evidence.provenance == tested_provenance
    assert db.query(models.Evidence).filter_by(subject_kind="relation", subject_id=relation.id).count() == evidence_count + 1

    refuted_relation = world_graph.create_relation(
        db, from_entity_id=left.id, to_entity_id=right.id,
        relation_type="enables", truth_state="possible", created_by="test",
    )
    refuted_evidence = world_graph.create_evidence(
        db, subject_kind="relation", subject_id=refuted_relation.id,
        claim="A source disproves this candidate relation.", support_level="refuted",
        source="reviewed_source", provenance={"url": "https://example.org/source", "method": "independent review"},
    )
    world_graph.transition_relation_truth_state(db, refuted_relation, "refuted")
    with pytest.raises(world_graph.SubstrateError, match="cannot move relation from refuted to supported"):
        world_graph.transition_relation_truth_state(db, refuted_relation, "supported")
    assert db.get(models.Evidence, refuted_evidence.id) is not None

    relation_entity = world_graph.ensure_canonical_entity(db, "relation", relation.id)
    outer = world_graph.create_relation(
        db,
        from_entity_id=relation_entity.id,
        to_entity_id=left.id,
        relation_type="informs",
        attributes={"note": "relations can be endpoints via entity adapters"},
        created_by="test",
    )
    assert outer.from_entity_id == relation_entity.id


def test_registry_evidence_and_relation_validations_fail_closed(db):
    _seed(db)
    entity = world_graph.create_entity(
        db, entity_type="resource", display_name="Temporary concept",
        attributes={}, created_by="test",
    )
    with pytest.raises(world_graph.SubstrateError, match="not active in type_registry"):
        world_graph.create_relation(
            db,
            from_entity_id=entity.id,
            to_entity_id=entity.id,
            relation_type="unregistered_relation",
            created_by="test",
        )
    with pytest.raises(world_graph.SubstrateError, match="cannot be tested, supported, or refuted"):
        world_graph.create_evidence(
            db,
            subject_kind="entity",
            subject_id=entity.id,
            claim="An invented claim",
            support_level="supported",
            source="simulated fixture",
            provenance={"url": "https://example.org/not-real"},
        )
    with pytest.raises(world_graph.SubstrateError, match="event may reference"):
        world_graph.create_event(
            db,
            event_type="state_changed",
            entity_id=entity.id,
            relation_id=1,
            source="test",
        )


def test_capability_lifecycle_requires_a_passing_test_reference(db):
    _seed(db)
    capability = world_graph.create_capability(
        db,
        capability_type="workflow",
        name="test workflow",
        description="A tested capability lifecycle fixture.",
        owner_agent="test",
    )
    world_graph.begin_capability_build(db, capability)
    failed = world_graph.mark_capability_tested(
        db, capability,
        test_ref="backend/tests/test_world_graph.py",
        command="pytest backend/tests/test_world_graph.py",
        exit_code=1,
        output_excerpt="1 failed",
    )
    assert failed.status == "building"
    with pytest.raises(world_graph.SubstrateError, match="pass a recorded test"):
        world_graph.activate_capability(db, capability)

    world_graph.mark_capability_tested(
        db, capability,
        test_ref="backend/tests/test_world_graph.py",
        command="pytest backend/tests/test_world_graph.py",
        exit_code=0,
        output_excerpt="all tests passed",
    )
    activated = world_graph.activate_capability(db, capability)
    assert activated.status == "active"


def test_canonical_endpoint_aliases_keep_one_canonical_type(db):
    _seed(db)
    record = models.DomainRecord(
        kind="job", title="A real needs record", detail="Recorded for a test.", close_token_hash="test"
    )
    db.add(record)
    db.flush()
    first = world_graph.ensure_canonical_entity(db, "post", record.id)
    second = world_graph.ensure_canonical_entity(db, "domain_record", record.id)
    assert first.id == second.id
    assert first.entity_type == "domain_record"
    assert first.attributes == '{"canonical_ref":{"entity_id":%d,"entity_type":"domain_record"}}' % record.id


def test_identity_candidates_do_not_silently_merge_and_merge_history_is_retained(db):
    _seed(db)
    one = models.Signal(
        source="registry_a", source_type="external", title="Same named organization",
        content="First source record.", canonical_url="https://example.org/org/1/",
        provenance='{"review":"source A"}',
    )
    two = models.Signal(
        source="registry_b", source_type="external", title="Same named organization",
        content="Second source record.", canonical_url="https://example.org/org/1",
        provenance='{"review":"source B"}',
    )
    db.add_all([one, two])
    db.flush()
    first = world_graph.ensure_canonical_entity(db, "signal", one.id)
    second = world_graph.ensure_canonical_entity(db, "signal", two.id)
    assert world_graph.ensure_canonical_entity(db, "signal", one.id).id == first.id
    assert first.id != second.id
    assert first.identity_state == second.identity_state == "candidate"
    candidates = world_graph.find_identity_candidates(
        db, "signal", canonical_identifier="https://example.org/org/1"
    )
    assert {item.id for item in candidates} == {first.id, second.id}
    assert first.status == second.status == "active"

    with pytest.raises(world_graph.SubstrateError, match="evidence-backed identity service"):
        first.identity_state = "canonical"
        db.flush()
    db.rollback()
    first = db.get(models.SubstrateEntity, first.id)
    second = db.get(models.SubstrateEntity, second.id)

    first_evidence = world_graph.create_evidence(
        db, subject_kind="entity", subject_id=first.id,
        claim="Registry A and registry B identify the same organization.",
        support_level="supported", source="reviewed_registry",
        provenance={"url": "https://example.org/org/1", "review_ref": "identity-review-42"},
    )
    second_evidence = world_graph.create_evidence(
        db, subject_kind="entity", subject_id=second.id,
        claim="This candidate has the same canonical registry identifier.",
        support_level="supported", source="reviewed_registry",
        provenance={"url": "https://example.org/org/1", "review_ref": "identity-review-42"},
    )
    world_graph.transition_entity_identity(
        db, first, "corroborated", actor="reviewer", evidence_id=first_evidence.id,
        rationale="Independent provenance confirms the canonical identifier.",
    )
    world_graph.transition_entity_identity(
        db, first, "canonical", actor="reviewer", evidence_id=first_evidence.id,
        rationale="The reviewed identifier is the canonical identity.",
    )
    world_graph.transition_entity_identity(
        db, second, "corroborated", actor="reviewer", evidence_id=second_evidence.id,
        rationale="Independent provenance confirms the same canonical identifier.",
    )
    world_graph.merge_entities(
        db, first, second, actor="reviewer", rationale="Reviewed exact canonical identifier match.",
        evidence_id=second_evidence.id,
    )
    assert second.status == "merged"
    assert second.merged_into_id == first.id
    assert db.get(models.Evidence, second_evidence.id) is not None
    history = db.query(models.WorldEvent).filter_by(
        event_type="entity_merged", entity_id=second.id
    ).one()
    assert '"survivor_entity_id":%d' % first.id in history.payload


def test_restart_and_additive_migration_keep_adapter_idempotent(tmp_path):
    database_path = tmp_path / "substrate-restart.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)
    with TestSession() as before_restart:
        world_graph.seed_core_types(before_restart)
        signal = models.Signal(
            source="persistent_registry", source_type="external", title="Restart source",
            content="The legacy row remains authoritative.", canonical_url="https://example.org/restart",
        )
        before_restart.add(signal)
        before_restart.commit()
        first = world_graph.sync_intelligence_path(before_restart)
        before_restart.commit()
        assert first["entities_created"] == 1
    engine.dispose()

    engine = create_engine(f"sqlite:///{database_path}")
    assert run_migrations(engine) == []
    with sessionmaker(bind=engine, autoflush=False)() as after_restart:
        world_graph.seed_core_types(after_restart)
        second = world_graph.sync_intelligence_path(after_restart)
        after_restart.commit()
        assert second == {"entities_created": 0, "relations_created": 0}
        signal = after_restart.query(models.Signal).filter_by(title="Restart source").one()
        entity = world_graph.find_canonical_entity(after_restart, "signal", signal.id)
        assert entity is not None and entity.source_id == str(signal.id)
        assert entity.identity_provenance and "persistent_registry" in entity.identity_provenance
    indexes = inspect(engine).get_indexes("entities")
    assert any(index["unique"] and index["column_names"] == ["identity_key"] for index in indexes)
    engine.dispose()
