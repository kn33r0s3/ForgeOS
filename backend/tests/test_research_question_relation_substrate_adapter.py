import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import research_question_relation_substrate_adapter as adapter, world_graph


def _research_question_with_sources(db):
    pattern = models.Pattern(title="Repeated coordination delay", description="A recurring pattern.")
    belief = models.Belief(statement="Coordination delay repeats under high demand.")
    claim = models.Claim(
        statement="Operators report coordination delays.",
        normalized_statement="operators report coordination delays",
    )
    db.add_all([pattern, belief, claim])
    db.flush()
    question = models.ResearchQuestion(
        question="What evidence verifies the recurring coordination delay?",
        source_pattern_id=pattern.id,
        source_belief_id=belief.id,
        source_claim_id=claim.id,
    )
    db.add(question)
    db.commit()
    for row in (pattern, belief, claim, question):
        db.refresh(row)
    return pattern, belief, claim, question


def test_explicit_research_question_foreign_keys_become_typed_relations(db):
    pattern, belief, claim, question = _research_question_with_sources(db)

    first = adapter.sync_research_question_sources(db)

    assert first == {
        "questions_seen": 1,
        "relations_created": 3,
        "entities_created": 4,
        "unresolved_links": 0,
    }
    question_entity = world_graph.find_canonical_entity(db, "research_question", question.id)
    source_rows = (
        ("source_pattern_id", "pattern", pattern),
        ("source_belief_id", "belief", belief),
        ("source_claim_id", "claim", claim),
    )
    for field, entity_type, source_row in source_rows:
        key = f"legacy-research-question:{question.id}:{field}:derived-from-v1"
        relation = db.query(models.WorldRelation).filter_by(idempotency_key=key).one()
        target_entity = world_graph.find_canonical_entity(db, entity_type, source_row.id)
        assert relation.from_entity_id == question_entity.id
        assert relation.to_entity_id == target_entity.id
        assert relation.relation_type == "derived_from"
        assert relation.direction == "directed"
        assert relation.truth_state == "hypothesized"
        attrs = json.loads(relation.attributes)
        assert attrs["source_ref"] == {"table": "research_questions", "id": question.id}
        assert attrs["source_field"] == field
        assert attrs["target_ref"] == {"table": source_row.__tablename__, "id": source_row.id}
        assert attrs["payload_copied"] is False

    assert db.query(models.WorldRelation).count() == 3
    repeated = adapter.sync_research_question_sources(db)
    assert repeated["relations_created"] == 0
    assert repeated["entities_created"] == 0
    assert db.query(models.WorldRelation).count() == 3


def test_text_similarity_never_creates_source_relations(db):
    question = models.ResearchQuestion(
        question="Does the phrase Pattern 42 refer to a real source?"
    )
    db.add(question)
    db.commit()

    result = adapter.sync_research_question_sources(db)

    assert result["questions_seen"] == 1
    assert result["relations_created"] == 0
    assert result["unresolved_links"] == 0
    assert db.query(models.WorldRelation).count() == 0


def test_missing_source_stays_unresolved(db, monkeypatch):
    pattern = models.Pattern(title="Source exists", description="A source pattern.")
    db.add(pattern)
    db.flush()
    question = models.ResearchQuestion(
        question="What is the missing source?",
        source_pattern_id=pattern.id,
    )
    db.add(question)
    db.commit()

    original_get = db.get

    def get_with_missing_pattern(model, identity, **kwargs):
        if model is models.Pattern and identity == pattern.id:
            return None
        return original_get(model, identity, **kwargs)

    monkeypatch.setattr(db, "get", get_with_missing_pattern)
    result = adapter.sync_research_question_sources(db)

    assert result["questions_seen"] == 1
    assert result["relations_created"] == 0
    assert result["unresolved_links"] == 1
    assert db.query(models.WorldRelation).count() == 0


def test_deprecated_relation_type_stays_unresolved(db):
    pattern = models.Pattern(title="Source exists", description="A source pattern.")
    db.add(pattern)
    db.flush()
    question = models.ResearchQuestion(
        question="What follows from this pattern?",
        source_pattern_id=pattern.id,
    )
    db.add(question)
    db.commit()
    world_graph.seed_core_types(db)
    relation_type = db.query(models.TypeRegistry).filter_by(
        category="relation_type", type_name="derived_from"
    ).one()
    world_graph.set_type_status(
        db,
        relation_type,
        "deprecated",
        actor="test_agent",
        rationale="Verify adapters respect the existing type lifecycle.",
        evidence_ref="backend/tests/test_research_question_relation_substrate_adapter.py",
    )

    result = adapter.sync_research_question_sources(db)

    assert result["questions_seen"] == 1
    assert result["relations_created"] == 0
    assert result["unresolved_links"] == 1
    assert db.query(models.WorldRelation).count() == 0


def test_research_question_source_relations_survive_restart(tmp_path):
    path = tmp_path / "research_question_relations.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as first_session:
        _pattern, _belief, _claim, question = _research_question_with_sources(first_session)
        question_id = question.id
        first = adapter.sync_research_question_sources(first_session)
        first_session.commit()
        assert first["relations_created"] == 3
    engine.dispose()

    engine = create_engine(f"sqlite:///{path}")
    with sessionmaker(bind=engine)() as restarted:
        repeated = adapter.sync_research_question_sources(restarted)
        restarted.commit()
        assert repeated["relations_created"] == 0
        assert restarted.query(models.WorldRelation).filter(
            models.WorldRelation.idempotency_key.like(
                f"legacy-research-question:{question_id}:%"
            )
        ).count() == 3
    engine.dispose()
