"""Adapter from workflow NetworkConnection rows to typed substrate relations.

NetworkConnection remains the source for the migration-stage workflow state.
The substrate relation is the composable graph edge; its immutable projection
events retain source state, evidence-link ids, provenance, and endpoint refs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import network_endpoints, world_graph
from app.services.type_validation import SubstrateError, resolve_type


class _DeferredEndpoint(ValueError):
    """A relation endpoint depends on another legacy connection projection."""


def sync_network_connections(db: Session, *, limit: int = 100) -> dict[str, int]:
    """Project registered endpoint pairs into idempotent WorldRelation rows."""
    world_graph.seed_core_types(db)
    rows = (
        db.query(models.NetworkConnection)
        .order_by(models.NetworkConnection.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    result = {
        "entities_created": 0,
        "relations_created": 0,
        "events_created": 0,
        "projected_connections": 0,
        "unresolved_connections": 0,
        "unactivated_relation_types": 0,
        "epistemic_state_pending_evidence": 0,
    }
    relation_by_connection: dict[int, int] = {}
    pending = list(rows)

    while pending:
        deferred: list[models.NetworkConnection] = []
        progressed = False
        for connection in pending:
            relation_type = (connection.relation_type or "possible_match").strip().lower()
            try:
                resolve_type(db, "relation_type", relation_type)
            except SubstrateError as exc:
                if "unknown relation_type" in str(exc) or "not active" in str(exc):
                    result["unactivated_relation_types"] += 1
                result["unresolved_connections"] += 1
                result["events_created"] += _record_unresolved(db, connection, str(exc))
                progressed = True
                continue

            try:
                left_entity = _resolve_substrate_endpoint(
                    db, connection.left_kind, connection.left_id, relation_by_connection, result
                )
                right_entity = _resolve_substrate_endpoint(
                    db, connection.right_kind, connection.right_id, relation_by_connection, result
                )
            except _DeferredEndpoint:
                deferred.append(connection)
                continue
            except (ValueError, SubstrateError) as exc:
                result["unresolved_connections"] += 1
                result["events_created"] += _record_unresolved(db, connection, str(exc))
                progressed = True
                continue

            source_truth = (connection.epistemic_state or "hypothesized").strip().lower()
            initial_truth = source_truth if source_truth in {"possible", "hypothesized"} else "hypothesized"
            key = f"network-connection:{connection.id}:substrate-relation-v1"
            existing = (
                db.get(models.WorldRelation, connection.relation_id)
                if connection.relation_id
                else db.query(models.WorldRelation).filter_by(idempotency_key=key).one_or_none()
            )
            try:
                relation = _resolve_relation(
                    db,
                    connection,
                    left_entity,
                    right_entity,
                    relation_type=relation_type,
                    direction=connection.direction or "directed",
                    initial_truth=initial_truth,
                    idempotency_key=key,
                )
            except SubstrateError as exc:
                result["unresolved_connections"] += 1
                result["events_created"] += _record_unresolved(db, connection, str(exc))
                progressed = True
                continue
            if relation is None:
                result["unresolved_connections"] += 1
                result["events_created"] += _record_unresolved(
                    db, connection, "existing relation_id does not match the source endpoints/type"
                )
                progressed = True
                continue

            if existing is None:
                result["relations_created"] += 1

            if connection.relation_id != relation.id:
                connection.relation_id = relation.id
                db.flush()
            relation_by_connection[connection.id] = relation.id
            result["projected_connections"] += 1
            result["events_created"] += _record_projection_event(db, connection, relation)
            if source_truth not in {"possible", "hypothesized"} and relation.truth_state != source_truth:
                # A legacy state is retained in the event and served through
                # its registered adapter until substrate evidence satisfies
                # the canonical transition path.
                result["epistemic_state_pending_evidence"] += 1
            progressed = True

        if not deferred:
            break
        if not progressed:
            for connection in deferred:
                result["unresolved_connections"] += 1
                result["events_created"] += _record_unresolved(
                    db,
                    connection,
                    "endpoint references another NetworkConnection without a resolved substrate relation",
                )
            break
        pending = deferred

    db.flush()
    return result


def _resolve_substrate_endpoint(
    db: Session,
    kind: str,
    entity_id: int,
    relation_by_connection: dict[int, int],
    result: dict[str, int],
) -> models.SubstrateEntity:
    canonical_kind, source = network_endpoints.resolve_endpoint(db, kind, entity_id)
    if canonical_kind == "network_connection":
        relation_id = relation_by_connection.get(source.id) or source.relation_id
        if relation_id is None:
            raise _DeferredEndpoint(f"NetworkConnection #{source.id} relation is not projected yet")
        canonical_kind, canonical_id = "relation", relation_id
    else:
        canonical_id = entity_id

    if canonical_kind not in world_graph.CANONICAL_ADAPTERS:
        raise ValueError(f"endpoint kind {canonical_kind!r} has no registered substrate adapter")
    before = world_graph.find_canonical_entity(db, canonical_kind, canonical_id)
    entity = world_graph.ensure_canonical_entity(
        db,
        canonical_kind,
        canonical_id,
        created_by="network_connection_adapter",
    )
    if before is None:
        result["entities_created"] += 1
    return entity


def _resolve_relation(
    db: Session,
    connection: models.NetworkConnection,
    left: models.SubstrateEntity,
    right: models.SubstrateEntity,
    *,
    relation_type: str,
    direction: str,
    initial_truth: str,
    idempotency_key: str,
) -> models.WorldRelation | None:
    relation = db.get(models.WorldRelation, connection.relation_id) if connection.relation_id else None
    if relation is None:
        relation = db.query(models.WorldRelation).filter_by(idempotency_key=idempotency_key).one_or_none()
    if relation is not None:
        if (relation.from_entity_id, relation.to_entity_id, relation.relation_type) != (
            left.id,
            right.id,
            relation_type,
        ):
            return None
        return relation
    return world_graph.create_relation(
        db,
        from_entity_id=left.id,
        to_entity_id=right.id,
        relation_type=relation_type,
        attributes={},
        direction=direction,
        truth_state=initial_truth,
        valid_from=connection.valid_from,
        valid_to=connection.valid_until,
        created_by="network_connection_adapter",
        idempotency_key=idempotency_key,
    )


def _evidence_refs(db: Session, connection_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(models.EvidenceRelationship)
        .filter_by(network_connection_id=connection_id)
        .order_by(models.EvidenceRelationship.id.asc())
        .all()
    )
    return [
        {
            "evidence_id": row.evidence_id,
            "relationship": row.relation_type,
            "relation_key": row.relation_key,
        }
        for row in rows
        if db.get(models.Evidence, row.evidence_id) is not None
    ]


def _snapshot(connection: models.NetworkConnection, relation: models.WorldRelation) -> dict[str, Any]:
    return {
        "source_system": "network_connections",
        "source_id": connection.id,
        "source_ref": {"entity_type": "network_connection", "entity_id": connection.id},
        "substrate_relation_id": relation.id,
        "left_ref": {"entity_type": connection.left_kind, "entity_id": connection.left_id},
        "right_ref": {"entity_type": connection.right_kind, "entity_id": connection.right_id},
        "relation_type": connection.relation_type or "possible_match",
        "direction": connection.direction,
        "epistemic_state": connection.epistemic_state or "hypothesized",
        "workflow_state": connection.state,
        "reason": connection.reason,
        "context": connection.context,
        "uncertainty": connection.uncertainty,
        "provenance": connection.provenance,
        "evidence_refs": [],
        "valid_from": _iso(connection.valid_from),
        "valid_until": _iso(connection.valid_until),
        "public_visible": connection.public_visible,
        "observed_at": _iso(connection.observed_at),
    }


def _record_projection_event(
    db: Session, connection: models.NetworkConnection, relation: models.WorldRelation
) -> int:
    payload = _snapshot(connection, relation)
    payload["evidence_refs"] = _evidence_refs(db, connection.id)
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    key = f"network-connection-projection:{connection.id}:{fingerprint}"
    if db.query(models.WorldEvent).filter_by(idempotency_key=key).first() is not None:
        return 0
    world_graph.create_event(
        db,
        event_type="network_relation_projected",
        source="network_connection_adapter",
        relation_id=relation.id,
        payload=payload,
        # The adapter's own relation_id write advances updated_at. Use the
        # source observation time so a restart won't invent another projection
        # event for that bookkeeping-only update.
        occurred_at=connection.observed_at or connection.created_at,
        idempotency_key=key,
    )
    return 1


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _record_unresolved(db: Session, connection: models.NetworkConnection, reason: str) -> int:
    payload = {
        "source_system": "network_connections",
        "source_id": connection.id,
        "source_ref": {"entity_type": "network_connection", "entity_id": connection.id},
        "left_ref": {"entity_type": connection.left_kind, "entity_id": connection.left_id},
        "right_ref": {"entity_type": connection.right_kind, "entity_id": connection.right_id},
        "relation_type": connection.relation_type or "possible_match",
        "reason": reason,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    key = f"network-connection-unresolved:{connection.id}:{fingerprint}"
    if db.query(models.WorldEvent).filter_by(idempotency_key=key).first() is not None:
        return 0
    world_graph.create_event(
        db,
        event_type="network_relation_unresolved",
        source="network_connection_adapter",
        payload=payload,
        occurred_at=connection.updated_at or connection.created_at,
        idempotency_key=key,
    )
    return 1
