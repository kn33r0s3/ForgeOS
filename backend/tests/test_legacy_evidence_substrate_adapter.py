import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import legacy_evidence_substrate_adapter as adapter, world_graph


def _legacy_evidence_rows(db):
    signal = models.Signal(source="reviewed archive", content="A source observation.")
    db.add(signal)
    db.flush()
    belief = models.Belief(statement="The process has a recurring delay.")
    opportunity = models.Opportunity(problem="Reduce recurring process delays.")
    prediction = models.ScenarioPrediction(claim="The process will remain delayed.")
    db.add_all([belief, opportunity, prediction])
    db.flush()

    rows = [
        models.Evidence(
            belief_id=belief.id,
            signal_id=signal.id,
            source="independent archive",
            content="The first raw observation.",
            direction="supports",
            confidence=82.5,
            provenance='{"raw":"belief evidence"}',
            provenance_hash="legacy-belief-hash",
        ),
        models.Evidence(
            scenario_prediction_id=prediction.id,
            signal_id=signal.id,
            source=None,
            content="The second raw observation.",
            direction="contradicts",
            confidence=100.0,
            provenance=None,
            provenance_hash="legacy-prediction-hash",
        ),
        models.Evidence(
            opportunity_id=opportunity.id,
            signal_id=signal.id,
            source="field interview",
            content="The third raw observation.",
            direction="supports",
            confidence=64.0,
            provenance='{"raw":"opportunity evidence"}',
            provenance_hash="legacy-opportunity-hash",
        ),
        models.Evidence(
            signal_id=signal.id,
            source="field notebook",
            content="The fourth raw observation.",
            direction="unknown",
            confidence=5.0,
            provenance='{"raw":"signal-only evidence"}',
            provenance_hash="legacy-signal-hash",
        ),
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return signal, belief, prediction, opportunity, rows


def test_historical_evidence_maps_in_bounded_batches_without_changing_raw_rows(db):
    signal, belief, prediction, opportunity, rows = _legacy_evidence_rows(db)
    raw_before = {
        row.id: (
            row.belief_id, row.scenario_prediction_id, row.opportunity_id, row.signal_id,
            row.source, row.content, row.direction, row.confidence, row.provenance,
            row.provenance_hash, row.created_at,
        )
        for row in rows
    }

    first = adapter.sync_legacy_evidence(db, limit=2)
    assert first == {
        "records_seen": 2,
        "records_mapped": 2,
        "entities_created": 2,
        "unresolved_records": 0,
        "events_created": 0,
    }
    second = adapter.sync_legacy_evidence(db, limit=2)
    assert second["records_seen"] == second["records_mapped"] == 2
    assert second["unresolved_records"] == 0
    assert db.query(models.Evidence).count() == 4
    assert db.query(models.WorldRelation).count() == 0

    expected_subjects = [
        ("belief", belief.id),
        ("scenario_prediction", prediction.id),
        ("opportunity", opportunity.id),
        ("signal", signal.id),
    ]
    for evidence, (entity_type, source_id) in zip(rows, expected_subjects):
        entity = world_graph.find_canonical_entity(db, entity_type, source_id)
        assert entity is not None
        assert evidence.subject_kind == "entity"
        assert evidence.subject_id == entity.id
        assert evidence.support_level == "unknown"
        assert evidence.recorded_at == evidence.created_at
        assert evidence.substrate_confidence is None
        assert evidence.claim is None  # raw content is referenced, not copied
        substrate_source = evidence.substrate_source
        if evidence.id == rows[1].id:
            assert substrate_source == signal.source  # source fallback did not rewrite the raw NULL
            assert evidence.source is None
        metadata = json.loads(evidence.substrate_provenance)
        assert metadata["adapter"] == "legacy_evidence_substrate_adapter"
        assert metadata["source_ref"] == {"table": "evidence", "id": evidence.id}
        assert metadata["subject_ref"]["entity_type"] == entity_type
        assert metadata["subject_ref"]["source_id"] == source_id
        assert metadata["raw_confidence_scale"] == "legacy_0_to_100"
        assert evidence.substrate_source
        assert (
            evidence.belief_id, evidence.scenario_prediction_id, evidence.opportunity_id,
            evidence.signal_id, evidence.source, evidence.content, evidence.direction,
            evidence.confidence, evidence.provenance, evidence.provenance_hash, evidence.created_at,
        ) == raw_before[evidence.id]

    repeated = adapter.sync_legacy_evidence(db, limit=2)
    assert repeated["records_seen"] == 0
    assert repeated["records_mapped"] == 0
    assert db.query(models.Evidence).count() == 4


def test_ambiguous_or_incomplete_legacy_evidence_stays_unmapped(db):
    signal, belief, _prediction, opportunity, _rows = _legacy_evidence_rows(db)
    ambiguous = models.Evidence(
        belief_id=belief.id,
        opportunity_id=opportunity.id,
        signal_id=signal.id,
        source="archive",
        content="Two target fields disagree.",
    )
    no_target = models.Evidence(source="archive", content="No linked source or target.")
    no_content = models.Evidence(signal_id=signal.id, source="archive", content="  ")
    db.add_all([ambiguous, no_target, no_content])
    db.commit()

    result = adapter.sync_legacy_evidence(db, limit=20)

    assert result["records_seen"] == 7
    assert result["records_mapped"] == 4
    assert result["unresolved_records"] == 3
    assert all(row.subject_kind is None for row in (ambiguous, no_target, no_content))
    assert all(row.subject_id is None for row in (ambiguous, no_target, no_content))


def test_legacy_evidence_mapping_survives_restart_without_duplicate_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_evidence.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as before_restart:
        signal, belief, _prediction, _opportunity, rows = _legacy_evidence_rows(before_restart)
        result = adapter.sync_legacy_evidence(before_restart, limit=20)
        before_restart.commit()
        assert result["records_mapped"] == 4
        source_id, belief_source_id = signal.id, belief.id
        evidence_ids = [row.id for row in rows]
    engine.dispose()

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_evidence.sqlite'}")
    with sessions_for_engine(engine)() as after_restart:
        result = adapter.sync_legacy_evidence(after_restart, limit=20)
        after_restart.commit()
        assert result["records_seen"] == 0
        assert after_restart.query(models.Evidence).count() == 4
        assert all(after_restart.get(models.Evidence, row_id).subject_kind == "entity" for row_id in evidence_ids)
        assert world_graph.find_canonical_entity(after_restart, "belief", belief_source_id) is not None
        assert world_graph.find_canonical_entity(after_restart, "signal", source_id) is not None
    engine.dispose()


def sessions_for_engine(engine):
    return sessionmaker(bind=engine)


def test_additive_evidence_migration_preserves_legacy_confidence_and_payload():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE evidence (id INTEGER PRIMARY KEY, source TEXT, content TEXT, direction TEXT, "
            "confidence FLOAT, provenance TEXT, provenance_hash TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO evidence (id, source, content, direction, confidence, provenance, provenance_hash) "
            "VALUES (1, NULL, 'raw historical content', 'contradicts', 87.5, '{\"origin\":\"archive\"}', 'dup-hash')"
        )

    applied = run_migrations(engine)

    assert any(statement.startswith("ALTER TABLE evidence ADD COLUMN substrate_source") for statement in applied)
    assert any(statement.startswith("ALTER TABLE evidence ADD COLUMN substrate_confidence") for statement in applied)
    assert any(statement.startswith("ALTER TABLE evidence ADD COLUMN substrate_provenance") for statement in applied)
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT source, content, direction, confidence, provenance, provenance_hash, "
            "subject_kind, substrate_source, substrate_confidence, substrate_provenance FROM evidence WHERE id = 1"
        ).one()
    assert tuple(row) == (
        None, "raw historical content", "contradicts", 87.5, '{"origin":"archive"}', "dup-hash",
        None, None, None, None,
    )
    assert run_migrations(engine) == []
    engine.dispose()
