import json

from app import models
from app.services import content_loop, world_graph


def test_content_loop_creates_bilingual_grounded_draft_in_substrate(db):
    question = models.ResearchQuestion(
        question="Where does coordination fail between a real need and a capable provider?",
        priority_score=92.0,
        status="open",
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    result = content_loop.run_content_draft_cycle(db, max_new_drafts=1)
    db.commit()

    assert result["status"] == "ok"
    assert result["drafts_generated"] == 1
    assert result["published"] == 0
    assert result["publish_status"] == "blocked"

    asset = (
        db.query(models.SubstrateEntity)
        .filter_by(entity_type="content_asset", source_system="hami_content_loop")
        .one()
    )
    attrs = json.loads(asset.attributes)
    assert attrs["status"] == "draft"
    assert attrs["content_type"] == "question_invitation"
    assert attrs["language_codes"] == ["en", "ne"]
    assert "not a claim" in attrs["content_en"]
    assert "दाबी होइन" in attrs["content_ne"]
    assert attrs["source_record"] == {"table": "research_questions", "id": question.id}
    assert attrs["source_kind"] == "HYPOTHESIS"
    assert attrs["publish_blockers"]

    source_entity = world_graph.find_canonical_entity(db, "research_question", question.id)
    assert source_entity is not None
    relation = (
        db.query(models.WorldRelation)
        .filter_by(
            from_entity_id=asset.id,
            to_entity_id=source_entity.id,
            relation_type="derived_from",
        )
        .one()
    )
    assert relation.truth_state == "hypothesized"

    event = (
        db.query(models.WorldEvent)
        .filter_by(
            event_type="content_draft_created",
            entity_id=asset.id,
            idempotency_key=f"content-draft-created:{attrs['source_fingerprint']}",
        )
        .one()
    )
    event_payload = json.loads(event.payload)
    assert event_payload["source_record_id"] == question.id
    assert event_payload["publication_attempted"] is False


def test_content_loop_is_idempotent_and_does_not_duplicate_lineage(db):
    question = models.ResearchQuestion(
        question="What stops people from accessing a service they need?",
        priority_score=88.0,
        status="open",
    )
    db.add(question)
    db.commit()

    first = content_loop.run_content_draft_cycle(db, max_new_drafts=1)
    db.commit()
    second = content_loop.run_content_draft_cycle(db, max_new_drafts=1)
    db.commit()

    assert first["drafts_generated"] == 1
    assert second["drafts_generated"] == 0
    assert second["existing_drafts"] == 1
    assert db.query(models.SubstrateEntity).filter_by(entity_type="content_asset").count() == 1
    assert db.query(models.WorldRelation).filter_by(relation_type="derived_from").count() == 1
    assert db.query(models.WorldEvent).filter_by(event_type="content_draft_created").count() == 1


def test_content_loop_does_not_copy_private_contact_details_to_public_draft(db):
    question = models.ResearchQuestion(
        question="Ask user at niroj@example.com or call +977 9801234567 about this private case.",
        priority_score=99.0,
        status="open",
    )
    db.add(question)
    db.commit()

    result = content_loop.run_content_draft_cycle(db, max_new_drafts=1)
    db.commit()

    assert result["drafts_generated"] == 0
    assert result["skipped_private_or_sensitive"] == 1
    assert db.query(models.SubstrateEntity).filter_by(entity_type="content_asset").count() == 0
