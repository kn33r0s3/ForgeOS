"""Project explicit legacy EvidenceRelationship links into WorldRelations.

The legacy link row owns its explicit endpoints and type during migration.
Minimal canonical entity wrappers let the substrate traverse the same link;
the source link points back to the projected relation for restart recovery.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.services import type_validation, world_graph


_EXPLICIT_TARGET_FIELDS = (
    "claim_id",
    "opportunity_id",
    "decision_id",
    "experiment_id",
    "outcome_id",
    "judgment_id",
    "network_connection_id",
)

# These targets already have active canonical adapters. NetworkConnection is
# represented as a WorldRelation by network_substrate_adapter, so it remains
# deliberately unresolved here rather than being duplicated as an entity.
_SUPPORTED_TARGETS: dict[str, tuple[str, type]] = {
    "claim_id": ("claim", models.Claim),
    "opportunity_id": ("opportunity", models.Opportunity),
    "decision_id": ("decision", models.Decision),
    "experiment_id": ("experiment", models.Experiment),
    "outcome_id": ("outcome", models.Outcome),
    "judgment_id": ("judgment", models.Judgment),
}


def sync_evidence_relationships(
    db: Session,
    *,
    limit: int = 250,
    evidence_ids: set[int] | None = None,
) -> dict[str, int]:
    """Map bounded, explicit Evidence → Claim links; never infer from relation_key."""
    world_graph.seed_core_types(db)
    result = {
        "records_seen": 0,
        "relations_created": 0,
        "entities_created": 0,
        "unresolved_records": 0,
    }
    query = db.query(models.EvidenceRelationship).filter(
        models.EvidenceRelationship.substrate_relation_id.is_(None)
    )
    if evidence_ids is not None:
        if not evidence_ids:
            return result
        query = query.filter(models.EvidenceRelationship.evidence_id.in_(evidence_ids))
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 250
    rows = query.order_by(models.EvidenceRelationship.id.asc()).limit(limit).all()
    entity_cache: dict[tuple[str, int], models.SubstrateEntity] = {}

    for source in rows:
        result["records_seen"] += 1
        target_values = [
            (field, getattr(source, field, None))
            for field in _EXPLICIT_TARGET_FIELDS
            if getattr(source, field, None) is not None
        ]
        if len(target_values) != 1 or not source.evidence_id:
            result["unresolved_records"] += 1
            continue
        target_field, target_id = target_values[0]
        target_spec = _SUPPORTED_TARGETS.get(target_field)
        if target_spec is None:
            # Includes NetworkConnection until evidence-to-relation can be
            # expressed without pretending a relation is an entity endpoint.
            result["unresolved_records"] += 1
            continue
        target_type, target_model = target_spec
        if not isinstance(target_id, int) or isinstance(target_id, bool) or target_id < 1:
            result["unresolved_records"] += 1
            continue
        try:
            type_validation.resolve_type(db, "relation_type", source.relation_type)
        except type_validation.SubstrateError:
            result["unresolved_records"] += 1
            continue

        evidence = db.get(models.Evidence, source.evidence_id)
        target = db.get(target_model, target_id)
        if evidence is None or target is None:
            result["unresolved_records"] += 1
            continue

        from_entity, from_created = _ensure_entity(
            db, entity_cache, "evidence_record", evidence.id
        )
        to_entity, to_created = _ensure_entity(
            db, entity_cache, target_type, target_id
        )
        result["entities_created"] += int(from_created) + int(to_created)
        relation_key = f"legacy-evidence-relationship:{source.id}:substrate-v1"
        existing = db.query(models.WorldRelation).filter_by(idempotency_key=relation_key).one_or_none()
        try:
            relation = world_graph.create_relation(
                db,
                from_entity_id=from_entity.id,
                to_entity_id=to_entity.id,
                relation_type=source.relation_type,
                attributes={
                    "source_ref": {"table": "evidence_relationships", "id": source.id},
                    "evidence_ref": {"table": "evidence", "id": evidence.id},
                    f"{target_type}_ref": {"table": target_model.__tablename__, "id": target_id},
                    "payload_copied": False,
                },
                direction="directed",
                truth_state="hypothesized",
                created_by="evidence_relationship_substrate_adapter",
                idempotency_key=relation_key,
            )
        except (type_validation.SubstrateError, ValueError):
            result["unresolved_records"] += 1
            continue
        source.substrate_relation_id = relation.id
        db.flush()
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
        created_by="evidence_relationship_substrate_adapter",
    )
    cache[key] = entity
    return entity, existing is None
