import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import legacy_record_substrate_adapter as adapter, world_graph


def _legacy_rows(db):
    decision = models.Decision(
        title="Investigate the observed need",
        rationale="The evidence warrants more research before acting.",
        status="proposed",
    )
    db.add(decision)
    db.flush()
    claim = models.Claim(
        statement="Some local operators report recurring coordination delays.",
        normalized_statement="some local operators report recurring coordination delays",
        epistemic_state="observed",
        decision_id=decision.id,
        provenance='{"source":"reviewed report"}',
    )
    db.add(claim)
    db.flush()
    question = models.ResearchQuestion(
        question="What evidence would verify the reported coordination delays?",
        status="open",
        source_claim_id=claim.id,
    )
    record = models.DomainRecord(
        kind="job",
        title="Repair coordination request",
        detail="A local repair job record.",
        city="Biratnagar",
        close_token_hash="opaque-token-hash",
    )
    db.add_all([question, record])
    db.commit()
    for row in (claim, question, record, decision):
        db.refresh(row)
    return claim, question, record, decision


def test_remaining_canonical_legacy_rows_project_without_copy_or_guessed_edges(db):
    claim, question, record, decision = _legacy_rows(db)

    first = adapter.sync_legacy_records(db)

    assert first["records_seen"] == 4
    assert first["entities_created"] == 4
    assert first["events_created"] == 8
    assert first["unresolved_records"] == 0
    for entity_type, row in (
        ("claim", claim),
        ("research_question", question),
        ("domain_record", record),
        ("decision", decision),
    ):
        entity = world_graph.find_canonical_entity(db, entity_type, row.id)
        assert entity is not None
        assert entity.identity_key == f"source:{entity_type}:{row.__tablename__}:{row.id}"
        assert json.loads(entity.attributes) == {
            "canonical_ref": {"entity_type": entity_type, "entity_id": row.id}
        }

    assert db.query(models.WorldRelation).count() == 0
    assert db.query(models.Decision).count() == 1
    assert db.query(models.Action).count() == 0
    assert record.close_token_hash == "opaque-token-hash"
    snapshots = db.query(models.WorldEvent).filter_by(
        event_type="entity_source_refreshed"
    ).all()
    assert len(snapshots) == 4
    assert all("snapshot_sha256" in json.loads(event.payload) for event in snapshots)
    assert all("payload_copied" in json.loads(event.payload) for event in snapshots)
    assert all(claim.statement not in event.payload for event in snapshots)
    assert all(record.detail not in event.payload for event in snapshots)

    repeated = adapter.sync_legacy_records(db)
    assert repeated["entities_created"] == 0
    assert repeated["events_created"] == 0
    assert repeated["unresolved_records"] == 0

    claim.statement = "Operators still report recurring coordination delays."
    question.status = "closed"
    record.status = "closed"
    decision.status = "accepted"
    db.commit()
    refreshed = adapter.sync_legacy_records(db)
    assert refreshed["entities_created"] == 0
    assert refreshed["events_created"] == 4
    assert world_graph.find_canonical_entity(db, "claim", claim.id).display_name == claim.statement
    assert db.query(models.Claim).count() == 1
    assert db.query(models.ResearchQuestion).count() == 1
    assert db.query(models.DomainRecord).count() == 1
    assert db.query(models.Decision).count() == 1


def test_rare_signal_assessment_projects_safe_lifecycle_snapshots(db):
    assessment = models.RareSignalAssessment(
        cluster_key="rare-coordination-shift",
        label="Unusual coordination shift",
        signal_ids="12,19,22",
        frequency=3,
        prior_frequency=1,
        recent_frequency=2,
        velocity=1.5,
        acceleration=0.5,
        source_diversity=2.0,
        novelty=0.8,
        specificity=0.7,
        pain_intensity=0.4,
        solution_scarcity=0.6,
        economic_relevance=0.9,
        freshness=0.8,
        recurrence=0.7,
        geographic_spread=0.2,
        language_spread=0.3,
        score=67.0,
        status="DETECTED",
        explanation={"sensitive_detail": "must remain in the source record"},
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    first = adapter.sync_legacy_records(db)
    entity = world_graph.find_canonical_entity(
        db, "rare_signal_assessment", assessment.id
    )
    assert first["records_seen"] == 1
    assert first["entities_created"] == 1
    assert first["events_created"] == 2
    assert first["unresolved_records"] == 0
    assert entity is not None
    assert entity.identity_key == (
        f"source:rare_signal_assessment:rare_signal_assessments:{assessment.id}"
    )
    assert json.loads(entity.attributes) == {
        "canonical_ref": {
            "entity_type": "rare_signal_assessment",
            "entity_id": assessment.id,
        }
    }

    snapshots = db.query(models.WorldEvent).filter_by(
        event_type="entity_source_refreshed",
        entity_id=entity.id,
    ).all()
    assert len(snapshots) == 1
    payload = json.loads(snapshots[0].payload)
    assert payload["source_ref"] == {
        "table": "rare_signal_assessments",
        "id": assessment.id,
    }
    assert payload["payload_copied"] is False
    assert "score" in payload["source_fields"]
    assert "explanation" not in payload["source_fields"]
    assert "sensitive_detail" not in snapshots[0].payload

    repeated = adapter.sync_legacy_records(db)
    # Unchanged rows with a current digest are not work for the next bounded
    # pass, so they cannot monopolize the projection budget.
    assert repeated["records_seen"] == 0
    assert repeated["entities_created"] == 0
    assert repeated["events_created"] == 0
    assert repeated["unresolved_records"] == 0

    assessment.score = 72.0
    assessment.status = "REVIEWED"
    db.commit()
    refreshed = adapter.sync_legacy_records(db)
    assert refreshed["entities_created"] == 0
    assert refreshed["events_created"] == 1
    snapshots = db.query(models.WorldEvent).filter_by(
        event_type="entity_source_refreshed",
        entity_id=entity.id,
    ).all()
    assert len(snapshots) == 2


def test_unprojected_rare_signals_are_not_starved_by_old_snapshots(db):
    older = models.RareSignalAssessment(
        cluster_key="older-rare-signal",
        label="Older assessment",
        signal_ids="1",
        frequency=1,
        score=10.0,
        status="DETECTED",
    )
    db.add(older)
    db.commit()
    db.refresh(older)

    first = adapter.sync_legacy_records(db, limit=1)
    assert first["entities_created"] == 1
    assert world_graph.find_canonical_entity(
        db, "rare_signal_assessment", older.id
    ) is not None

    newer = [
        models.RareSignalAssessment(
            cluster_key=f"new-rare-signal-{index}",
            label=f"New assessment {index}",
            signal_ids=str(index + 2),
            frequency=1,
            score=20.0 + index,
            status="DETECTED",
        )
        for index in range(2)
    ]
    db.add_all(newer)
    db.commit()

    one = adapter.sync_legacy_records(db, limit=1)
    assert one["entities_created"] == 1
    assert world_graph.find_canonical_entity(
        db, "rare_signal_assessment", newer[0].id
    ) is not None
    assert world_graph.find_canonical_entity(
        db, "rare_signal_assessment", newer[1].id
    ) is None

    two = adapter.sync_legacy_records(db, limit=1)
    assert two["entities_created"] == 1
    assert world_graph.find_canonical_entity(
        db, "rare_signal_assessment", newer[1].id
    ) is not None


def test_legacy_record_projection_survives_restart(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_records.sqlite'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    first_session = SessionLocal()
    claim, question, record, decision = _legacy_rows(first_session)
    adapter.sync_legacy_records(first_session)
    first_session.commit()
    source_ids = (claim.id, question.id, record.id, decision.id)
    first_session.close()

    restarted = SessionLocal()
    result = adapter.sync_legacy_records(restarted)
    restarted.commit()

    assert result["records_seen"] == 0
    assert result["entities_created"] == 0
    assert result["events_created"] == 0
    assert result["unresolved_records"] == 0
    for entity_type, source_id in zip(
        ("claim", "research_question", "domain_record", "decision"), source_ids
    ):
        assert world_graph.find_canonical_entity(restarted, entity_type, source_id) is not None
    restarted.close()
    engine.dispose()
