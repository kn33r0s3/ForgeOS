"""Read-only public Network traversal over substrate rows and legacy adapters."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import models, schemas
from app.services.public_feed import build_public_feed


def build_public_network(db: Session, *, limit: int = 100) -> schemas.PublicNetworkSnapshot:
    """Return public graph nodes/edges without persisting a Network copy.

    Feed visibility is the public gate. Substrate relations are returned when
    both endpoint entities are visible. NetworkConnection rows are an explicit
    migration adapter: projected rows become substrate edges; visible but
    unprojected rows remain source-reference edges.
    """
    bounded_limit = max(1, min(int(limit), 100))
    feed_items = build_public_feed(db, limit=bounded_limit)

    visible_entity_ids: set[int] = set()
    visible_evidence: dict[int, schemas.PublicFeedRelation] = {}
    visible_events: dict[int, schemas.PublicFeedRelation] = {}
    connection_items: list[schemas.PublicFeedItem] = []
    relation_sources: dict[int, schemas.PublicFeedItem] = {}
    relation_evidence: dict[int, dict[int, schemas.PublicFeedRelation]] = {}
    relation_events: dict[int, dict[int, schemas.PublicFeedRelation]] = {}

    for item in feed_items:
        if item.kind == "connection":
            connection_items.append(item)
        visible_entity_ids.update(
            ref.entity_id for ref in item.relations if ref.entity_type == "entity"
        )
        item_evidence = {
            ref.entity_id: ref for ref in item.relations if ref.entity_type == "evidence"
        }
        item_events = {
            ref.entity_id: ref for ref in item.relations if ref.entity_type == "event"
        }
        visible_evidence.update(item_evidence)
        visible_events.update(item_events)
        if item.kind == "connection":
            substrate_relation_ids = {
                ref.entity_id for ref in item.relations
                if ref.entity_type == "relation" and ref.relation == "substrate_relation"
            }
            for relation_id in substrate_relation_ids:
                relation_sources[relation_id] = item
                relation_evidence.setdefault(relation_id, {}).update(item_evidence)
                relation_events.setdefault(relation_id, {}).update(item_events)

    source_rows = (
        db.query(models.NetworkConnection.relation_id)
        .filter(models.NetworkConnection.relation_id.isnot(None))
        .all()
    )
    registered_network_relation_ids = {row.relation_id for row in source_rows}

    entity_rows = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.id.in_(visible_entity_ids))
        .order_by(models.SubstrateEntity.id.asc())
        .all()
        if visible_entity_ids else []
    )
    nodes = [_public_node(entity) for entity in entity_rows]
    visible_entity_ids = {node.id for node in nodes}

    edge_limit = min(max(bounded_limit * 10, bounded_limit), 1000)
    relation_rows = (
        db.query(models.WorldRelation)
        .filter(models.WorldRelation.from_entity_id.in_(visible_entity_ids))
        .filter(models.WorldRelation.to_entity_id.in_(visible_entity_ids))
        .order_by(models.WorldRelation.id.desc())
        .limit(edge_limit)
        .all()
        if visible_entity_ids else []
    )

    edges: list[schemas.PublicNetworkEdge] = []
    for relation in relation_rows:
        if (
            relation.id in registered_network_relation_ids
            and relation.id not in relation_sources
        ):
            # A private/dangling legacy connection may not be made public just
            # because both generic endpoint wrappers happen to be visible.
            continue
        source_item = relation_sources.get(relation.id)
        edges.append(schemas.PublicNetworkEdge(
            id=f"relation:{relation.id}",
            relation_type=relation.relation_type,
            direction=relation.direction,
            epistemic_state=relation.truth_state,
            graph_source="substrate",
            from_entity_id=relation.from_entity_id,
            to_entity_id=relation.to_entity_id,
            source_ref=(
                schemas.PublicFeedRelation(
                    entity_type="network_connection",
                    entity_id=source_item.entity_id,
                    relation="adapter_source",
                ) if source_item is not None else None
            ),
            evidence_refs=list(relation_evidence.get(relation.id, {}).values()),
            event_refs=list(relation_events.get(relation.id, {}).values()),
        ))
    for item in connection_items:
        source_relation_ids = {
            ref.entity_id for ref in item.relations
            if ref.entity_type == "relation" and ref.relation == "substrate_relation"
        }
        if source_relation_ids:
            # The substrate relation above is the sole graph edge after
            # projection; preserve its legacy source ref there.
            continue
        left = next((ref for ref in item.relations if ref.relation == "left_side"), None)
        right = next((ref for ref in item.relations if ref.relation == "right_side"), None)
        if left is None or right is None:
            continue
        edges.append(schemas.PublicNetworkEdge(
            id=f"network_connection:{item.entity_id}",
            relation_type=item.relation_type or "possible_match",
            direction=item.direction or "directed",
            epistemic_state=item.epistemic_state,
            graph_source="legacy_adapter",
            from_ref=left,
            to_ref=right,
            source_ref=schemas.PublicFeedRelation(
                entity_type="network_connection",
                entity_id=item.entity_id,
                relation="adapter_source",
            ),
            evidence_refs=[
                ref for ref in item.relations if ref.entity_type == "evidence"
            ],
            event_refs=[
                ref for ref in item.relations if ref.entity_type == "event"
            ],
        ))

    edges.sort(key=lambda edge: edge.id, reverse=True)
    edges = edges[:edge_limit]
    return schemas.PublicNetworkSnapshot(
        nodes=nodes,
        edges=edges,
        evidence_refs=list(visible_evidence.values()),
        event_refs=list(visible_events.values()),
    )


def _public_node(entity: models.SubstrateEntity) -> schemas.PublicNetworkNode:
    source_ref = None
    if entity.source_system and entity.source_id:
        try:
            source_id = int(entity.source_id)
        except (TypeError, ValueError):
            source_id = None
        if source_id is not None and source_id > 0:
            source_ref = schemas.PublicFeedRelation(
                entity_type=entity.entity_type,
                entity_id=source_id,
                relation="source_record",
            )
    if source_ref is None:
        try:
            canonical_ref = json.loads(entity.attributes or "{}").get("canonical_ref", {})
            source_type = canonical_ref.get("entity_type")
            source_id = canonical_ref.get("entity_id")
        except (json.JSONDecodeError, AttributeError, TypeError):
            source_type, source_id = None, None
        if isinstance(source_type, str) and isinstance(source_id, int) and source_id > 0:
            source_ref = schemas.PublicFeedRelation(
                entity_type=source_type,
                entity_id=source_id,
                relation="source_record",
            )
    return schemas.PublicNetworkNode(
        id=entity.id,
        entity_type=entity.entity_type,
        source_ref=source_ref,
        identity_state=entity.identity_state,
    )
