"""Universal substrate services over a type registry and canonical adapters.

Existing domain tables remain authoritative. ``entities`` holds typed
references for graph composition, while new domains can create first-class
entities from active registry types without introducing a domain table.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app import models


TYPE_CATEGORIES = frozenset({"entity_type", "relation_type", "event_type", "capability_type"})
TYPE_STATES = frozenset({"proposed", "active", "deprecated"})
ENTITY_STATES = frozenset({"active", "archived", "merged"})
TRUTH_STATES = frozenset({"possible", "hypothesized", "tested", "supported", "refuted", "unknown"})
RELATION_DIRECTIONS = frozenset({"directed", "bidirectional"})
CAPABILITY_STATES = ("proposed", "building", "tested", "active", "deprecated")
_TYPE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
ENTITY_ALIASES = {"post": "domain_record", "knowledge": "claim", "service": "service_listing"}


class SubstrateError(ValueError):
    """A substrate record violates its registry, provenance, or state contract."""


def _schema_for_canonical_ref() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "canonical_ref": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string"},
                    "entity_id": {"type": "integer", "minimum": 1},
                },
                "required": ["entity_type", "entity_id"],
                "additionalProperties": False,
            }
        },
        "required": ["canonical_ref"],
        "additionalProperties": False,
    }


def seed_core_types(db: Session) -> int:
    """Install the stable substrate vocabulary as registry rows, idempotently."""
    canonical_schema = json.dumps(_schema_for_canonical_ref(), sort_keys=True, separators=(",", ":"))
    open_schema = '{"type":"object"}'
    types = {
        "entity_type": {
            "signal", "pattern", "belief", "claim", "research_question", "opportunity",
            "provider", "service_listing", "domain_record", "outcome", "customer", "person",
            "organization", "resource", "capability", "tool", "agent", "project", "market", "relation",
        },
        "relation_type": {
            "derived_from", "supports", "possible_match", "co_occurs_with", "informs", "informed_by",
            "offered_by", "owned_by", "part_of", "enables", "observed_with",
        },
        "event_type": {
            "entity_created", "relation_created", "signal_ingested", "state_changed",
            "capability_test_passed", "capability_test_failed",
        },
        "capability_type": {"tool", "workflow", "integration", "agent", "model"},
    }
    inserted = 0
    for category, names in types.items():
        for name in sorted(names):
            existing = (
                db.query(models.TypeRegistry)
                .filter_by(category=category, type_name=name)
                .first()
            )
            if existing is not None:
                continue
            schema_json = canonical_schema if category == "entity_type" and name in {
                "signal", "pattern", "belief", "claim", "research_question", "opportunity",
                "provider", "service_listing", "domain_record", "outcome", "customer",
                "relation",
            } else open_schema
            db.add(models.TypeRegistry(
                category=category,
                type_name=name,
                schema_json=schema_json,
                description=f"Core ForgeOS {category.replace('_', ' ')} type.",
                owner_agent="forge_system",
                status="active",
            ))
            inserted += 1
    if inserted:
        db.flush()
    return inserted


def register_type(
    db: Session,
    *,
    category: str,
    type_name: str,
    schema: Mapping[str, Any],
    owner_agent: str,
    description: str | None = None,
    status: str = "proposed",
) -> models.TypeRegistry:
    category = (category or "").strip().lower()
    name = (type_name or "").strip().lower()
    owner = (owner_agent or "").strip()
    if category not in TYPE_CATEGORIES:
        raise SubstrateError("unsupported type category")
    if not _TYPE_NAME.fullmatch(name):
        raise SubstrateError("type name must be lowercase snake case")
    if not owner:
        raise SubstrateError("owner_agent is required")
    if status not in TYPE_STATES:
        raise SubstrateError("invalid type registry status")
    validate_json_schema(schema)
    schema_json = _dump_json(dict(schema), "schema")
    existing = db.query(models.TypeRegistry).filter_by(category=category, type_name=name).first()
    if existing is not None:
        if existing.schema_json != schema_json:
            raise SubstrateError("type already exists with a different schema")
        return existing
    record = models.TypeRegistry(
        category=category,
        type_name=name,
        schema_json=schema_json,
        description=description,
        owner_agent=owner,
        status=status,
    )
    db.add(record)
    db.flush()
    return record


def set_type_status(db: Session, record: models.TypeRegistry, status: str) -> models.TypeRegistry:
    if status not in TYPE_STATES:
        raise SubstrateError("invalid type registry status")
    allowed = {"proposed": {"active", "deprecated"}, "active": {"deprecated"}, "deprecated": set()}
    if status not in allowed[record.status]:
        raise SubstrateError(f"cannot change type status from {record.status} to {status}")
    record.status = status
    db.flush()
    return record


def create_entity(
    db: Session,
    *,
    entity_type: str,
    display_name: str,
    attributes: Mapping[str, Any],
    created_by: str,
    _adapter_record: bool = False,
) -> models.SubstrateEntity:
    kind = _require_active_type(db, "entity_type", entity_type)
    if "canonical_ref" in attributes and not _adapter_record:
        raise SubstrateError("canonical_ref may only be written by a canonical record adapter")
    _validate_attributes(db, "entity_type", kind, attributes)
    name = (display_name or "").strip()
    owner = (created_by or "").strip()
    if not name or len(name) > 240:
        raise SubstrateError("display_name must contain 1 to 240 characters")
    if not owner:
        raise SubstrateError("created_by is required")
    entity = models.SubstrateEntity(
        entity_type=kind,
        display_name=name,
        attributes=_dump_json(dict(attributes), "attributes"),
        created_by=owner,
    )
    db.add(entity)
    db.flush()
    _record_event(db, event_type="entity_created", entity_id=entity.id, source=owner, payload={"entity_type": kind})
    return entity


def find_canonical_entity(db: Session, entity_type: str, entity_id: int) -> models.SubstrateEntity | None:
    kind = canonical_entity_type(entity_type)
    attrs = _dump_json({"canonical_ref": {"entity_type": kind, "entity_id": int(entity_id)}}, "attributes")
    return (
        db.query(models.SubstrateEntity)
        .filter_by(entity_type=kind, attributes=attrs)
        .order_by(models.SubstrateEntity.id.asc())
        .first()
    )


def ensure_canonical_entity(
    db: Session,
    entity_type: str,
    entity_id: int,
    *,
    created_by: str = "canonical_adapter",
) -> models.SubstrateEntity:
    """Create a minimal wrapper for an existing record, never copy its payload."""
    kind = canonical_entity_type(entity_type)
    if isinstance(entity_id, bool) or not isinstance(entity_id, int) or entity_id < 1:
        raise SubstrateError("canonical entity id must be a positive integer")
    existing = find_canonical_entity(db, kind, entity_id)
    if existing is not None:
        return existing
    adapter = CANONICAL_ADAPTERS.get(kind)
    if adapter is None:
        raise SubstrateError(f"no canonical adapter for entity type: {kind}")
    row = db.query(adapter[0]).filter(adapter[0].id == entity_id).first()
    if row is None:
        raise SubstrateError(f"missing canonical record {kind}:{entity_id}")
    return create_entity(
        db,
        entity_type=kind,
        display_name=adapter[1](row),
        attributes={"canonical_ref": {"entity_type": kind, "entity_id": entity_id}},
        created_by=created_by,
        _adapter_record=True,
    )


def create_relation(
    db: Session,
    *,
    from_entity_id: int,
    to_entity_id: int,
    relation_type: str,
    attributes: Mapping[str, Any] | None = None,
    direction: str = "directed",
    strength: float | None = None,
    truth_state: str = "hypothesized",
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    created_by: str,
    idempotency_key: str | None = None,
) -> models.WorldRelation:
    relation_kind = _require_active_type(db, "relation_type", relation_type)
    attrs = dict(attributes or {})
    _validate_attributes(db, "relation_type", relation_kind, attrs)
    if direction not in RELATION_DIRECTIONS:
        raise SubstrateError("direction must be directed or bidirectional")
    if truth_state not in {"possible", "hypothesized"}:
        raise SubstrateError("new relations must begin possible or hypothesized")
    if strength is not None and (not math.isfinite(float(strength)) or not 0 <= float(strength) <= 1):
        raise SubstrateError("strength must be between 0 and 1")
    starts = _utc_naive(valid_from)
    ends = _utc_naive(valid_to)
    if starts is not None and ends is not None and ends <= starts:
        raise SubstrateError("valid_to must be later than valid_from")
    if db.get(models.SubstrateEntity, from_entity_id) is None or db.get(models.SubstrateEntity, to_entity_id) is None:
        raise SubstrateError("relation endpoints must resolve to existing entities")
    owner = (created_by or "").strip()
    if not owner:
        raise SubstrateError("created_by is required")
    if idempotency_key:
        key = idempotency_key.strip()
        if not key:
            raise SubstrateError("idempotency key cannot be blank")
        for existing in (
            db.query(models.WorldRelation)
            .filter_by(from_entity_id=from_entity_id, to_entity_id=to_entity_id, relation_type=relation_kind)
            .all()
        ):
            existing_system = _parse_json(existing.attributes).get("_forge", {})
            if isinstance(existing_system, dict) and existing_system.get("idempotency_key") == key:
                return existing
        system_attrs = attrs.get("_forge") or {}
        if not isinstance(system_attrs, dict):
            raise SubstrateError("_forge relation metadata must be an object")
        attrs["_forge"] = {**system_attrs, "idempotency_key": key}
    relation = models.WorldRelation(
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type=relation_kind,
        attributes=_dump_json(attrs, "attributes"),
        direction=direction,
        strength=float(strength) if strength is not None else None,
        truth_state=truth_state,
        valid_from=starts,
        valid_to=ends,
        created_by=owner,
    )
    db.add(relation)
    db.flush()
    _record_event(db, event_type="relation_created", relation_id=relation.id, source=owner, payload={"relation_type": relation_kind})
    return relation


def transition_relation_truth_state(
    db: Session,
    relation: models.WorldRelation,
    next_state: str,
) -> models.WorldRelation:
    if next_state not in TRUTH_STATES:
        raise SubstrateError("invalid relation truth state")
    transitions = {
        "possible": {"hypothesized", "unknown"},
        "hypothesized": {"tested", "unknown"},
        "tested": {"supported", "refuted", "unknown"},
        "supported": {"tested", "refuted", "unknown"},
        "refuted": {"tested", "unknown"},
        "unknown": {"hypothesized", "tested"},
    }
    if next_state not in transitions[relation.truth_state]:
        raise SubstrateError(f"cannot move relation from {relation.truth_state} to {next_state}")
    if next_state in {"tested", "supported", "refuted"}:
        required_level = "tested" if next_state == "tested" else next_state
        evidence = _relation_evidence(db, relation.id, required_level)
        if evidence is None:
            raise SubstrateError(f"transition to {next_state} requires recorded {required_level} evidence")
        if _is_simulated_source(evidence.source):
            raise SubstrateError("simulated evidence cannot establish a relation")
        if not _has_test_or_source_provenance(evidence):
            raise SubstrateError("evidence needs source provenance or a passing test reference")
    relation.truth_state = next_state
    db.flush()
    return relation


def create_evidence(
    db: Session,
    *,
    subject_kind: str,
    subject_id: int,
    claim: str,
    support_level: str,
    source: str,
    provenance: Mapping[str, Any] | str,
    confidence: float | None = None,
) -> models.Evidence:
    kind = (subject_kind or "").strip().lower()
    if kind not in {"entity", "relation"}:
        raise SubstrateError("evidence subject_kind must be entity or relation")
    table = models.SubstrateEntity if kind == "entity" else models.WorldRelation
    if db.get(table, subject_id) is None:
        raise SubstrateError(f"missing {kind} subject")
    state = (support_level or "").strip().lower()
    if state not in TRUTH_STATES:
        raise SubstrateError("invalid evidence support level")
    clean_source = (source or "").strip()
    clean_claim = (claim or "").strip()
    if not clean_source or not clean_claim:
        raise SubstrateError("evidence source and claim are required")
    if confidence is not None and (not math.isfinite(float(confidence)) or not 0 <= float(confidence) <= 1):
        raise SubstrateError("evidence confidence must be between 0 and 1")
    provenance_json = provenance if isinstance(provenance, str) else _dump_json(dict(provenance), "provenance")
    if state in {"tested", "supported", "refuted"} and _is_simulated_source(clean_source):
        raise SubstrateError("simulated evidence cannot be tested, supported, or refuted")
    if state in {"tested", "supported", "refuted"} and not provenance_json.strip():
        raise SubstrateError("tested evidence requires provenance")
    if clean_source.lower() == "pytest":
        test_meta = _parse_json(provenance_json)
        if test_meta.get("result") != "passed" or not test_meta.get("test_ref"):
            raise SubstrateError("test evidence must cite a passing test reference")
    evidence = models.Evidence(
        subject_kind=kind,
        subject_id=subject_id,
        claim=clean_claim,
        support_level=state,
        confidence=confidence if confidence is not None else 0.0,
        source=clean_source,
        provenance=provenance_json,
        recorded_at=models.utcnow(),
    )
    db.add(evidence)
    db.flush()
    return evidence


def create_event(
    db: Session,
    *,
    event_type: str,
    source: str,
    payload: Mapping[str, Any] | None = None,
    entity_id: int | None = None,
    relation_id: int | None = None,
    occurred_at: datetime | None = None,
) -> models.WorldEvent:
    kind = _require_active_type(db, "event_type", event_type)
    if entity_id is not None and relation_id is not None:
        raise SubstrateError("an event may reference an entity or relation, not both")
    if entity_id is not None and db.get(models.SubstrateEntity, entity_id) is None:
        raise SubstrateError("event entity does not exist")
    if relation_id is not None and db.get(models.WorldRelation, relation_id) is None:
        raise SubstrateError("event relation does not exist")
    clean_source = (source or "").strip()
    if not clean_source:
        raise SubstrateError("event source is required")
    event = models.WorldEvent(
        event_type=kind,
        entity_id=entity_id,
        relation_id=relation_id,
        payload=_dump_json(dict(payload or {}), "payload"),
        source=clean_source,
        occurred_at=_utc_naive(occurred_at) or models.utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def create_capability(
    db: Session,
    *,
    capability_type: str,
    name: str,
    description: str,
    owner_agent: str,
    spec_ref: str | None = None,
) -> models.ForgeCapability:
    kind = _require_active_type(db, "capability_type", capability_type)
    clean_name = (name or "").strip()
    clean_description = (description or "").strip()
    owner = (owner_agent or "").strip()
    if not clean_name or not clean_description or not owner:
        raise SubstrateError("capability name, description, and owner_agent are required")
    capability = models.ForgeCapability(
        capability_type=kind,
        name=clean_name,
        description=clean_description,
        owner_agent=owner,
        spec_ref=spec_ref,
        status="proposed",
    )
    db.add(capability)
    db.flush()
    return capability


def mark_capability_tested(
    db: Session,
    capability: models.ForgeCapability,
    *,
    test_ref: str,
    command: str,
    exit_code: int,
    output_excerpt: str,
) -> models.ForgeCapability:
    if capability.status != "building":
        raise SubstrateError("only a building capability can be tested")
    if not _repo_file_exists(test_ref):
        raise SubstrateError("test_ref must resolve to a file inside the ForgeOS repository")
    if not command.strip():
        raise SubstrateError("test command is required")
    event_type = "capability_test_passed" if exit_code == 0 else "capability_test_failed"
    _record_event(
        db,
        event_type=event_type,
        source="pytest",
        payload={
            "capability_id": capability.id,
            "test_ref": test_ref,
            "command": command,
            "exit_code": int(exit_code),
            "output_excerpt": output_excerpt[-2000:],
        },
    )
    if exit_code == 0:
        capability.test_ref = test_ref
        capability.status = "tested"
        db.flush()
    return capability


def begin_capability_build(db: Session, capability: models.ForgeCapability) -> models.ForgeCapability:
    if capability.status != "proposed":
        raise SubstrateError(f"cannot begin build from {capability.status}")
    capability.status = "building"
    db.flush()
    return capability


def activate_capability(db: Session, capability: models.ForgeCapability) -> models.ForgeCapability:
    if capability.status != "tested" or not capability.test_ref:
        raise SubstrateError("capability must pass a recorded test before activation")
    passed = False
    for event in (
        db.query(models.WorldEvent)
        .filter_by(event_type="capability_test_passed", source="pytest")
        .order_by(models.WorldEvent.id.desc())
        .all()
    ):
        payload = _parse_json(event.payload)
        if payload.get("capability_id") == capability.id and payload.get("test_ref") == capability.test_ref and payload.get("exit_code") == 0:
            passed = True
            break
    if not passed or not _repo_file_exists(capability.test_ref):
        raise SubstrateError("a passing test event and existing test_ref are required")
    capability.status = "active"
    db.flush()
    return capability


def sync_intelligence_path(db: Session, *, limit: int = 100) -> dict[str, int]:
    """Mirror a bounded canonical Signal→Pattern→Belief→Opportunity slice.

    The substrate stores references and typed relations, not copies of the
    canonical domain payload. Repeated cycle runs are idempotent.
    """
    seed_core_types(db)
    signals = db.query(models.Signal).order_by(models.Signal.id.desc()).limit(limit).all()
    patterns = db.query(models.Pattern).order_by(models.Pattern.id.desc()).limit(limit).all()
    beliefs = db.query(models.Belief).order_by(models.Belief.id.desc()).limit(limit).all()
    opportunities = db.query(models.Opportunity).order_by(models.Opportunity.id.desc()).limit(limit).all()
    entities_added = 0
    relations_added = 0
    signal_entities: dict[int, models.SubstrateEntity] = {}
    pattern_entities: dict[int, models.SubstrateEntity] = {}
    belief_entities: dict[int, models.SubstrateEntity] = {}
    opportunity_entities: dict[int, models.SubstrateEntity] = {}

    def ensure(kind: str, row: Any) -> models.SubstrateEntity:
        nonlocal entities_added
        before = find_canonical_entity(db, kind, row.id)
        entity = ensure_canonical_entity(db, kind, row.id)
        if before is None:
            entities_added += 1
        return entity

    for row in signals:
        signal_entities[row.id] = ensure("signal", row)
        if not db.query(models.WorldEvent).filter_by(
            event_type="signal_ingested", entity_id=signal_entities[row.id].id
        ).first():
            create_event(
                db,
                event_type="signal_ingested",
                entity_id=signal_entities[row.id].id,
                source=(row.source or "unknown source"),
                payload={"canonical_ref": {"entity_type": "signal", "entity_id": row.id}},
                occurred_at=row.retrieved_at or row.timestamp,
            )

    for row in patterns:
        pattern_entities[row.id] = ensure("pattern", row)
        for signal_id in _csv_ids(row.origin_signal_ids):
            signal = db.get(models.Signal, signal_id)
            if signal is None:
                continue
            signal_entity = signal_entities.get(signal.id) or ensure("signal", signal)
            if _ensure_relation(
                db, pattern_entities[row.id], signal_entity,
                relation_type="derived_from",
                key=f"pattern:{row.id}:derived_from:signal:{signal.id}",
                created_by="world_graph_adapter",
            ):
                relations_added += 1

    for row in beliefs:
        belief_entities[row.id] = ensure("belief", row)
        if row.pattern_id:
            pattern = db.get(models.Pattern, row.pattern_id)
            if pattern is not None:
                pattern_entity = pattern_entities.get(pattern.id) or ensure("pattern", pattern)
                if _ensure_relation(
                    db, belief_entities[row.id], pattern_entity,
                    relation_type="derived_from",
                    key=f"belief:{row.id}:derived_from:pattern:{pattern.id}",
                    created_by="world_graph_adapter",
                ):
                    relations_added += 1
        for signal_id in _csv_ids(row.supporting_signal_ids):
            signal = db.get(models.Signal, signal_id)
            if signal is None:
                continue
            signal_entity = signal_entities.get(signal.id) or ensure("signal", signal)
            if _ensure_relation(
                db, belief_entities[row.id], signal_entity,
                relation_type="informed_by",
                key=f"belief:{row.id}:informed_by:signal:{signal.id}",
                created_by="world_graph_adapter",
            ):
                relations_added += 1

    for row in opportunities:
        opportunity_entities[row.id] = ensure("opportunity", row)
        if row.pattern_id:
            pattern = db.get(models.Pattern, row.pattern_id)
            if pattern is not None:
                pattern_entity = pattern_entities.get(pattern.id) or ensure("pattern", pattern)
                if _ensure_relation(
                    db, opportunity_entities[row.id], pattern_entity,
                    relation_type="derived_from",
                    key=f"opportunity:{row.id}:derived_from:pattern:{pattern.id}",
                    created_by="world_graph_adapter",
                ):
                    relations_added += 1
        for signal_id in _csv_ids(row.problem_evidence_signal_ids):
            signal = db.get(models.Signal, signal_id)
            if signal is None:
                continue
            signal_entity = signal_entities.get(signal.id) or ensure("signal", signal)
            if _ensure_relation(
                db, opportunity_entities[row.id], signal_entity,
                relation_type="informed_by",
                key=f"opportunity:{row.id}:informed_by:signal:{signal.id}",
                created_by="world_graph_adapter",
            ):
                relations_added += 1
    db.flush()
    return {"entities_created": entities_added, "relations_created": relations_added}


def _ensure_relation(
    db: Session,
    subject: models.SubstrateEntity,
    object_: models.SubstrateEntity,
    *,
    relation_type: str,
    key: str,
    created_by: str,
) -> bool:
    before = _find_idempotent_relation(db, subject.id, object_.id, relation_type, key)
    if before is not None:
        return False
    create_relation(
        db,
        from_entity_id=subject.id,
        to_entity_id=object_.id,
        relation_type=relation_type,
        attributes={"adapter": "canonical_record_provenance"},
        truth_state="hypothesized",
        created_by=created_by,
        idempotency_key=key,
    )
    return True


def _find_idempotent_relation(
    db: Session, from_id: int, to_id: int, relation_type: str, key: str
) -> models.WorldRelation | None:
    rows = (
        db.query(models.WorldRelation)
        .filter_by(from_entity_id=from_id, to_entity_id=to_id, relation_type=relation_type)
        .all()
    )
    for row in rows:
        system = _parse_json(row.attributes).get("_forge", {})
        if isinstance(system, dict) and system.get("idempotency_key") == key:
            return row
    return None


def _csv_ids(value: str | None) -> list[int]:
    found: list[int] = []
    for part in (value or "").split(","):
        try:
            number = int(part.strip())
        except (TypeError, ValueError):
            continue
        if number > 0:
            found.append(number)
    return sorted(set(found))


def canonical_entity_type(value: str, *, strict: bool = True) -> str | None:
    kind = (value or "").strip().lower()
    kind = ENTITY_ALIASES.get(kind, kind)
    if not _TYPE_NAME.fullmatch(kind):
        if strict:
            raise SubstrateError("entity type must be lowercase snake case")
        return None
    return kind


def find_match_workflow(
    db: Session,
    left_kind: str,
    left_id: int,
    right_kind: str,
    right_id: int,
) -> models.NetworkConnection | None:
    left = canonical_entity_type(left_kind)
    right = canonical_entity_type(right_kind)
    legacy_rights = [right, *(alias for alias, target in ENTITY_ALIASES.items() if target == right)]
    return (
        db.query(models.NetworkConnection)
        .filter_by(left_kind=left, left_id=left_id, right_id=right_id)
        .filter(models.NetworkConnection.right_kind.in_(legacy_rights))
        .order_by(models.NetworkConnection.id.desc())
        .first()
    )


def _require_active_type(db: Session, category: str, type_name: str) -> str:
    name = (type_name or "").strip().lower()
    row = db.query(models.TypeRegistry).filter_by(category=category, type_name=name, status="active").first()
    if row is None:
        raise SubstrateError(f"{category} {name!r} is not active in type_registry")
    return name


def _validate_attributes(db: Session, category: str, type_name: str, value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise SubstrateError("attributes must be a JSON object")
    row = db.query(models.TypeRegistry).filter_by(category=category, type_name=type_name, status="active").first()
    if row is None:
        raise SubstrateError(f"{category} {type_name!r} is not active in type_registry")
    schema = _parse_json(row.schema_json)
    errors = _validate_schema_value(dict(value), schema, "$", schema_position=True)
    if errors:
        raise SubstrateError("; ".join(errors[:5]))


_SCHEMA_KEYS = {
    "type", "properties", "required", "additionalProperties", "enum", "const",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength",
    "maxLength", "minItems", "maxItems", "items", "pattern", "description",
    "title", "default", "examples", "$schema", "$id",
}


def validate_json_schema(schema: Mapping[str, Any]) -> None:
    if not isinstance(schema, Mapping) or schema.get("type") not in ("object", None):
        raise SubstrateError("schema_json must be an object schema")
    _validate_schema_value({}, dict(schema), "$", schema_position=True)


def _validate_schema_value(value: Any, schema: Mapping[str, Any], path: str, *, schema_position: bool = False) -> list[str]:
    errors: list[str] = []
    unknown = set(schema) - _SCHEMA_KEYS
    if unknown:
        return [f"{path}: unsupported schema keywords {', '.join(sorted(unknown))}"]
    if schema_position:
        schema_type = schema.get("type")
        allowed_types = {"object", "array", "string", "integer", "number", "boolean", "null"}
        type_invalid = (
            schema_type not in allowed_types
            if isinstance(schema_type, str)
            else (not isinstance(schema_type, list) or not schema_type or not set(schema_type) <= allowed_types)
        ) if schema_type is not None else False
        if type_invalid:
            errors.append(f"{path}: invalid JSON Schema type")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            errors.append(f"{path}: properties must be an object")
            properties = {}
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(name, str) for name in required):
            errors.append(f"{path}: required must be a string array")
        additional = schema.get("additionalProperties", True)
        if not isinstance(additional, (bool, dict)):
            errors.append(f"{path}: additionalProperties must be boolean or a schema")
        if isinstance(additional, dict):
            errors.extend(_validate_schema_value({}, additional, path + ".additionalProperties", schema_position=True))
        for key, child in properties.items():
            if not isinstance(key, str) or not isinstance(child, dict):
                errors.append(f"{path}: property schemas must map names to objects")
            else:
                errors.extend(_validate_schema_value({}, child, f"{path}.properties.{key}", schema_position=True))
        items = schema.get("items")
        if items is not None:
            if not isinstance(items, dict):
                errors.append(f"{path}: items schema must be an object")
            else:
                errors.extend(_validate_schema_value({}, items, path + ".items", schema_position=True))
        for key in ("minLength", "maxLength", "minItems", "maxItems"):
            if key in schema and (isinstance(schema[key], bool) or not isinstance(schema[key], int) or schema[key] < 0):
                errors.append(f"{path}: {key} must be a non-negative integer")
        return errors
    expected = schema.get("type")
    if expected is not None and not _matches_type(value, expected):
        return [f"{path}: expected {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: value does not match const")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return [f"{path}: properties must be an object"]
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"{path}.{required}: required")
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors.extend(_validate_schema_value(item, properties[key], f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}.{key}: additional property is not allowed")
            elif isinstance(additional, dict):
                errors.extend(_validate_schema_value(item, additional, f"{path}.{key}"))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than minLength")
        if len(value) > schema.get("maxLength", math.inf):
            errors.append(f"{path}: longer than maxLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        for key, predicate in (("minimum", lambda a, b: a < b), ("maximum", lambda a, b: a > b),
                               ("exclusiveMinimum", lambda a, b: a <= b), ("exclusiveMaximum", lambda a, b: a >= b)):
            if key in schema and predicate(value, schema[key]):
                errors.append(f"{path}: outside {key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than minItems")
        if len(value) > schema.get("maxItems", math.inf):
            errors.append(f"{path}: more than maxItems")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(_validate_schema_value(item, schema["items"], f"{path}[{index}]"))
    return errors


def _matches_type(value: Any, expected: Any) -> bool:
    choices = expected if isinstance(expected, list) else [expected]
    for choice in choices:
        if choice == "object" and isinstance(value, dict): return True
        if choice == "array" and isinstance(value, list): return True
        if choice == "string" and isinstance(value, str): return True
        if choice == "integer" and isinstance(value, int) and not isinstance(value, bool): return True
        if choice == "number" and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)): return True
        if choice == "boolean" and isinstance(value, bool): return True
        if choice == "null" and value is None: return True
    return False


def _record_event(
    db: Session,
    *,
    event_type: str,
    source: str,
    payload: Mapping[str, Any],
    entity_id: int | None = None,
    relation_id: int | None = None,
) -> models.WorldEvent:
    kind = _require_active_type(db, "event_type", event_type)
    event = models.WorldEvent(
        event_type=kind,
        entity_id=entity_id,
        relation_id=relation_id,
        payload=_dump_json(dict(payload), "payload"),
        source=source,
        occurred_at=models.utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def _relation_evidence(db: Session, relation_id: int, support_level: str) -> models.Evidence | None:
    return (
        db.query(models.Evidence)
        .filter_by(subject_kind="relation", subject_id=relation_id, support_level=support_level)
        .order_by(models.Evidence.id.desc())
        .first()
    )


def _has_test_or_source_provenance(evidence: models.Evidence) -> bool:
    provenance = evidence.provenance or ""
    if evidence.source and evidence.source.lower() == "pytest":
        data = _parse_json(provenance)
        return data.get("result") == "passed" and bool(data.get("test_ref"))
    return bool(provenance.strip())


def _is_simulated_source(source: str | None) -> bool:
    value = (source or "").strip().lower()
    return value == "simulated" or value.startswith(("simulated_", "fixture", "mock", "seed", "test-data"))


def _repo_file_exists(reference: str) -> bool:
    root = Path(__file__).resolve().parents[3]
    path = Path(reference)
    if path.is_absolute():
        return False
    resolved = (root / path).resolve()
    return resolved.is_relative_to(root) and resolved.is_file()


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _dump_json(value: Any, field: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SubstrateError(f"{field} must contain JSON-safe values") from exc


def _parse_json(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def _canonical_display(row: Any, *fields: str) -> str:
    for field in fields:
        value = getattr(row, field, None)
        if value is not None and str(value).strip():
            return " ".join(str(value).split())[:240]
    return f"{row.__class__.__name__} #{row.id}"


CANONICAL_ADAPTERS: dict[str, tuple[type, Any]] = {
    "signal": (models.Signal, lambda row: _canonical_display(row, "title", "content")),
    "pattern": (models.Pattern, lambda row: _canonical_display(row, "title")),
    "belief": (models.Belief, lambda row: _canonical_display(row, "statement")),
    "claim": (models.Claim, lambda row: _canonical_display(row, "statement")),
    "research_question": (models.ResearchQuestion, lambda row: _canonical_display(row, "question")),
    "opportunity": (models.Opportunity, lambda row: _canonical_display(row, "problem")),
    "provider": (models.Provider, lambda row: _canonical_display(row, "business_name", "name")),
    "service_listing": (models.ServiceListing, lambda row: _canonical_display(row, "title")),
    "domain_record": (models.DomainRecord, lambda row: _canonical_display(row, "title")),
    "outcome": (models.Outcome, lambda row: _canonical_display(row, "qualitative_result")),
    "customer": (models.Customer, lambda row: _canonical_display(row, "name")),
    "network_connection": (models.NetworkConnection, lambda row: f"Connection #{row.id}"),
    "relation": (models.WorldRelation, lambda row: f"{row.relation_type} relation #{row.id}"),
}
