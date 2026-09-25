"""Project explicit ResearchQuestion source FKs as substrate relations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services import type_validation, world_graph


_SOURCE_FIELDS: tuple[tuple[str, str, type], ...] = (
    ("source_pattern_id", "pattern", models.Pattern),
    ("source_belief_id", "belief", models.Belief),
    ("source_claim_id", "claim", models.Claim),
)


def sync_research_question_sources(db: Session, *, limit: int = 250) -> dict[str, int]:
    """Map only explicit source foreign keys; question text is never searched."""
    world_graph.seed_core_types(db)
    result = {
        "questions_seen": 0,
        "relations_created": 0,
        "entities_created": 0,
        "unresolved_links": 0,
    }
    rows = (
        db.query(models.ResearchQuestion)
        .order_by(models.ResearchQuestion.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    entity_cache: dict[tuple[str, int], models.SubstrateEntity] = {}

    try:
        type_validation.resolve_type(db, "relation_type", "derived_from")
    except type_validation.SubstrateError:
        result["questions_seen"] = len(rows)
        result["unresolved_links"] = sum(
            1 for row in rows
            for field, _entity_type, _model in _SOURCE_FIELDS
            if getattr(row, field, None) is not None
        )
        return result

    for question in rows:
        result["questions_seen"] += 1
        if question.source_rare_signal_id is not None:
            result["unresolved_links"] += 1
        for source_field, entity_type, source_model in _SOURCE_FIELDS:
            source_id = getattr(question, source_field, None)
            if source_id is None:
                continue
            source_row = db.get(source_model, source_id)
            if source_row is None:
                result["unresolved_links"] += 1
                continue
            try:
                question_entity, question_created = _ensure_entity(
                    db, entity_cache, "research_question", question.id
                )
                result["entities_created"] += int(question_created)
                source_entity, source_created = _ensure_entity(
                    db, entity_cache, entity_type, source_id
                )
                result["entities_created"] += int(source_created)
            except type_validation.SubstrateError:
                result["unresolved_links"] += 1
                continue
            idempotency_key = (
                f"legacy-research-question:{question.id}:{source_field}:derived-from-v1"
            )
            existing = db.query(models.WorldRelation).filter_by(
                idempotency_key=idempotency_key
            ).one_or_none()
            try:
                world_graph.create_relation(
                    db,
                    from_entity_id=question_entity.id,
                    to_entity_id=source_entity.id,
                    relation_type="derived_from",
                    attributes={
                        "source_ref": {"table": "research_questions", "id": question.id},
                        "source_field": source_field,
                        "target_ref": {"table": source_model.__tablename__, "id": source_id},
                        "payload_copied": False,
                    },
                    direction="directed",
                    truth_state="hypothesized",
                    created_by="research_question_relation_substrate_adapter",
                    idempotency_key=idempotency_key,
                )
            except (type_validation.SubstrateError, ValueError):
                result["unresolved_links"] += 1
                continue
            result["relations_created"] += int(existing is None)

    return result


def _ensure_entity(
    db: Session,
    cache: dict[tuple[str, int], models.SubstrateEntity],
    entity_type: str,
    source_id: int,
) -> tuple[models.SubstrateEntity, bool]:
    key = (entity_type, source_id)
    cached = cache.get(key)
    if cached is not None:
        return cached, False
    existing = world_graph.find_canonical_entity(db, entity_type, source_id)
    entity = world_graph.ensure_canonical_entity(
        db,
        entity_type,
        source_id,
        created_by="research_question_relation_substrate_adapter",
    )
    cache[key] = entity
    return entity, existing is None
