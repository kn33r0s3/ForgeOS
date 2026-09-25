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

    assert result["records_seen"] == 4
    assert result["entities_created"] == 0
    assert result["events_created"] == 0
    assert result["unresolved_records"] == 0
    for entity_type, source_id in zip(
        ("claim", "research_question", "domain_record", "decision"), source_ids
    ):
        assert world_graph.find_canonical_entity(restarted, entity_type, source_id) is not None
    restarted.close()
    engine.dispose()
