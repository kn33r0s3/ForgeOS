"""Universal substrate services over a type registry and canonical adapters.

Existing domain tables remain authoritative. ``entities`` holds typed
references for graph composition, while new domains can create first-class
entities from active registry types without introducing a domain table.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import event, inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session

from app import models
from app.services.type_validation import (
    SubstrateError,
    resolve_type as _resolve_type,
    validate_attributes as _validate_attributes,
    validate_schema as validate_json_schema,
)


TYPE_CATEGORIES = frozenset({"entity_type", "relation_type", "event_type", "capability_type"})
TYPE_STATES = frozenset({"proposed", "active", "deprecated"})
ENTITY_STATES = frozenset({"active", "archived", "merged"})
TRUTH_STATES = frozenset({"possible", "hypothesized", "tested", "supported", "refuted", "unknown"})
RELATION_DIRECTIONS = frozenset({"directed", "bidirectional"})
CAPABILITY_STATES = ("proposed", "building", "tested", "active", "deprecated")
_TYPE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
ENTITY_ALIASES = {"post": "domain_record", "knowledge": "claim", "service": "service_listing"}
_CORE_SEED_AUTH_KEY = "forgeos.core_type_seed"
_TYPE_STATUS_AUTH_KEY = "forgeos.type_status_transition"
_TRUTH_TRANSITION_AUTH_KEY = "forgeos.truth_state_transition"
_IDENTITY_TRANSITION_AUTH_KEY = "forgeos.identity_state_transition"
_ENTITY_MERGE_AUTH_KEY = "forgeos.entity_merge"


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
            "capability_test_passed", "capability_test_failed", "type_status_changed",
            "entity_identity_changed", "entity_merged",
        },
        "capability_type": {"tool", "workflow", "integration", "agent", "model"},
    }
    inserted = 0
    db.info[_CORE_SEED_AUTH_KEY] = True
    try:
        for category, names in types.items():
            for name in sorted(names):
                existing = (
                    db.query(models.TypeRegistry)
                    .filter_by(category=category, type_name=name)
                    .first()
                )
                if existing is not None:
                    # Older deterministic core rows predate lifecycle evidence.
                    if existing.owner_agent == "forge_system" and not existing.status_evidence:
                        existing.status_evidence = _dump_json([{
                            "to": existing.status,
                            "actor": "forge_system",
                            "kind": "system_seed",
                            "reference": "forge-system-seed-v1",
                        }], "status_evidence")
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
                    status_evidence=_dump_json([{
                        "to": "active",
                        "actor": "forge_system",
                        "kind": "system_seed",
                        "reference": "forge-system-seed-v1",
                    }], "status_evidence"),
                ))
                inserted += 1
        db.flush()
    finally:
        db.info.pop(_CORE_SEED_AUTH_KEY, None)
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
    if status != "proposed":
        raise SubstrateError("new types must begin proposed; use the recorded lifecycle transition to activate")
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
        status="proposed",
    )
    db.add(record)
    db.flush()
    return record


def set_type_status(
    db: Session,
    record: models.TypeRegistry,
    status: str,
    *,
    actor: str | None = None,
    rationale: str | None = None,
    evidence_ref: str | None = None,
) -> models.TypeRegistry:
    """Canonical, recorded type lifecycle transition path."""
    if status not in TYPE_STATES:
        raise SubstrateError("invalid type registry status")
    allowed = {"proposed": {"active", "deprecated"}, "active": {"deprecated"}, "deprecated": set()}
    if status not in allowed[record.status]:
        raise SubstrateError(f"cannot change type status from {record.status} to {status}")
    owner = (actor or "").strip()
    reason = (rationale or "").strip()
    reference = (evidence_ref or "").strip()
    if not owner or not reason or not _repo_file_exists(reference.split("::", 1)[0]):
        raise SubstrateError("type activation/deprecation requires actor, rationale, and a verifiable repository evidence_ref")
    history = _parse_json(record.status_evidence)
    if not isinstance(history, list):
        history = []
    history.append({
        "from": record.status,
        "to": status,
        "actor": owner,
        "rationale": reason,
        "evidence_ref": reference,
        "recorded_at": models.utcnow().isoformat(),
    })
    previous_authorization = db.info.get(_TYPE_STATUS_AUTH_KEY)
    db.info[_TYPE_STATUS_AUTH_KEY] = (record, record.status, status)
    try:
        record.status = status
        record.status_evidence = _dump_json(history, "status_evidence")
        db.flush()
    finally:
        if previous_authorization is None:
            db.info.pop(_TYPE_STATUS_AUTH_KEY, None)
        else:
            db.info[_TYPE_STATUS_AUTH_KEY] = previous_authorization
    _record_event(
        db,
        event_type="type_status_changed",
        source=owner,
        payload={"category": record.category, "type_name": record.type_name, **history[-1]},
        idempotency_key=f"type-status:{record.category}:{record.type_name}:{len(history)}",
    )
    return record


def create_entity(
    db: Session,
    *,
    entity_type: str,
    display_name: str,
    attributes: Mapping[str, Any],
    created_by: str,
    _adapter_record: bool = False,
    _identity_metadata: Mapping[str, Any] | None = None,
) -> models.SubstrateEntity:
    kind = _require_active_type(db, "entity_type", entity_type)
    _validate_attributes(db, "entity_type", kind, attributes)
    if "canonical_ref" in attributes and not _adapter_record:
        raise SubstrateError("canonical_ref may only be written by a canonical record adapter")
    name = (display_name or "").strip()
    owner = (created_by or "").strip()
    if not name or len(name) > 240:
        raise SubstrateError("display_name must contain 1 to 240 characters")
    if not owner:
        raise SubstrateError("created_by is required")
    identity = dict(_identity_metadata or {})
    identity_key = identity.get("identity_key")
    if identity_key:
        existing = db.query(models.SubstrateEntity).filter_by(identity_key=identity_key).one_or_none()
        if existing is not None:
            if (existing.entity_type, existing.source_system, existing.source_id) == (
                kind, identity.get("source_system"), str(identity.get("source_id"))
            ):
                return existing
            raise SubstrateError("identity key collision; retain separate candidates and investigate")
    entity = models.SubstrateEntity(
        entity_type=kind,
        display_name=name,
        attributes=_dump_json(dict(attributes), "attributes"),
        identity_key=identity_key,
        source_system=identity.get("source_system"),
        source_id=str(identity["source_id"]) if identity.get("source_id") is not None else None,
        canonical_identifier=identity.get("canonical_identifier"),
        normalized_identity=identity.get("normalized_identity") or normalize_identity(name),
        identity_state="candidate",
        identity_uncertainty=identity.get("identity_uncertainty") or "Real-world identity is not independently corroborated.",
        identity_provenance=_dump_json(identity.get("provenance", {}), "identity provenance"),
        created_by=owner,
    )
    db.add(entity)
    db.flush()
    _record_event(
        db, event_type="entity_created", entity_id=entity.id, source=owner,
        payload={"entity_type": kind}, idempotency_key=f"entity-created:{entity.id}",
    )
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
    adapter = CANONICAL_ADAPTERS.get(kind)
    if adapter is None:
        raise SubstrateError(f"no canonical adapter for entity type: {kind}")
    row = db.query(adapter[0]).filter(adapter[0].id == entity_id).first()
    if row is None:
        raise SubstrateError(f"missing canonical record {kind}:{entity_id}")
    existing = find_canonical_entity(db, kind, entity_id)
    display_name = adapter[1](row)
    source_system = adapter[0].__tablename__
    canonical_identifier = _canonical_identifier(
        getattr(row, "canonical_url", None) or getattr(row, "external_id", None)
    )
    source_value = getattr(row, "source", None)
    provenance = getattr(row, "provenance", None)
    metadata = {
        "identity_key": f"source:{source_system}:{entity_id}",
        "source_system": source_system,
        "source_id": entity_id,
        "canonical_identifier": canonical_identifier,
        "normalized_identity": normalize_identity(display_name),
        "identity_uncertainty": "Source row identity is stable; cross-source real-world identity is unconfirmed.",
        "provenance": {
            "adapter": "world_graph.ensure_canonical_entity",
            "source_system": source_system,
            "source_id": entity_id,
            "source_label": source_value,
            "canonical_url": getattr(row, "canonical_url", None),
            "external_id": getattr(row, "external_id", None),
            "source_provenance": provenance,
        },
    }
    if existing is not None:
        if existing.identity_key is None:
            existing.identity_key = metadata["identity_key"]
            existing.source_system = metadata["source_system"]
            existing.source_id = str(metadata["source_id"])
            existing.canonical_identifier = metadata["canonical_identifier"]
            existing.normalized_identity = metadata["normalized_identity"]
            existing.identity_uncertainty = metadata["identity_uncertainty"]
            existing.identity_provenance = _dump_json(metadata["provenance"], "identity provenance")
            db.flush()
        return existing
    return create_entity(
        db,
        entity_type=kind,
        display_name=display_name,
        attributes={"canonical_ref": {"entity_type": kind, "entity_id": entity_id}},
        created_by=created_by,
        _adapter_record=True,
        _identity_metadata=metadata,
    )


def normalize_identity(value: str | None) -> str:
    """Normalize identity text for candidate detection, never for auto-merging."""
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.split()).casefold()


def _canonical_identifier(value: str | None) -> str | None:
    clean = (value or "").strip()
    if not clean:
        return None
    parts = urlsplit(clean)
    if parts.scheme and parts.netloc:
        host = parts.hostname.lower() if parts.hostname else ""
        port = parts.port
        if port and not ((parts.scheme.lower() == "https" and port == 443) or (parts.scheme.lower() == "http" and port == 80)):
            host = f"{host}:{port}"
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))
    return normalize_identity(clean)


def find_identity_candidates(
    db: Session,
    entity_type: str,
    *,
    canonical_identifier: str | None = None,
    normalized_identity: str | None = None,
) -> list[models.SubstrateEntity]:
    """Return possible matches without merging or asserting shared identity."""
    kind = canonical_entity_type(entity_type)
    query = db.query(models.SubstrateEntity).filter_by(entity_type=kind, status="active")
    clauses = []
    if canonical_identifier:
        identifier = _canonical_identifier(canonical_identifier)
        clauses.append(models.SubstrateEntity.canonical_identifier == identifier)
    if normalized_identity:
        clauses.append(models.SubstrateEntity.normalized_identity == normalize_identity(normalized_identity))
    if not clauses:
        return []
    from sqlalchemy import or_
    return query.filter(or_(*clauses)).order_by(models.SubstrateEntity.id.asc()).all()


def transition_entity_identity(
    db: Session,
    entity: models.SubstrateEntity,
    next_state: str,
    *,
    actor: str,
    evidence_id: int,
    rationale: str,
) -> models.SubstrateEntity:
    allowed = {"candidate": {"corroborated"}, "corroborated": {"canonical"}, "canonical": set()}
    if next_state not in allowed.get(entity.identity_state, set()):
        raise SubstrateError(f"cannot change identity state from {entity.identity_state} to {next_state}")
    evidence = db.get(models.Evidence, evidence_id)
    if (
        evidence is None
        or evidence.subject_kind != "entity"
        or evidence.subject_id != entity.id
        or evidence.support_level not in {"tested", "supported"}
        or _is_simulated_source(evidence.source)
        or not _has_test_or_source_provenance(evidence)
    ):
        raise SubstrateError("identity transition requires stored, provenance-backed evidence for the entity")
    owner = (actor or "").strip()
    reason = (rationale or "").strip()
    if not owner or not reason:
        raise SubstrateError("identity transition requires actor and rationale")
    old_state = entity.identity_state
    prior = db.info.get(_IDENTITY_TRANSITION_AUTH_KEY)
    db.info[_IDENTITY_TRANSITION_AUTH_KEY] = (entity, old_state, next_state)
    try:
        entity.identity_state = next_state
        db.flush()
    finally:
        if prior is None:
            db.info.pop(_IDENTITY_TRANSITION_AUTH_KEY, None)
        else:
            db.info[_IDENTITY_TRANSITION_AUTH_KEY] = prior
    _record_event(
        db,
        event_type="entity_identity_changed",
        entity_id=entity.id,
        source=owner,
        payload={"from": old_state, "to": next_state, "evidence_id": evidence.id, "rationale": reason},
        idempotency_key=f"identity:{entity.id}:{old_state}:{next_state}:{evidence.id}",
    )
    return entity


def merge_entities(
    db: Session,
    survivor: models.SubstrateEntity,
    duplicate: models.SubstrateEntity,
    *,
    actor: str,
    rationale: str,
    evidence_id: int,
) -> models.SubstrateEntity:
    """Archive an explicitly corroborated duplicate while preserving both histories."""
    if survivor.id == duplicate.id or survivor.entity_type != duplicate.entity_type:
        raise SubstrateError("merge requires two distinct entities of the same type")
    if survivor.identity_state != "canonical" or duplicate.identity_state != "corroborated":
        raise SubstrateError("merge requires a canonical survivor and a corroborated candidate")
    if not survivor.canonical_identifier or survivor.canonical_identifier != duplicate.canonical_identifier:
        raise SubstrateError("merge requires matching canonical identifiers; similar names are not enough")
    evidence = db.get(models.Evidence, evidence_id)
    if (
        evidence is None
        or evidence.subject_kind != "entity"
        or evidence.subject_id != duplicate.id
        or evidence.support_level not in {"tested", "supported"}
        or _is_simulated_source(evidence.source)
        or not _has_test_or_source_provenance(evidence)
    ):
        raise SubstrateError("merge requires stored provenance-backed evidence for the duplicate")
    owner, reason = (actor or "").strip(), (rationale or "").strip()
    if not owner or not reason:
        raise SubstrateError("merge requires actor and rationale")
    prior = db.info.get(_ENTITY_MERGE_AUTH_KEY)
    db.info[_ENTITY_MERGE_AUTH_KEY] = (duplicate, survivor.id, evidence.id)
    try:
        duplicate.status = "merged"
        duplicate.merged_into_id = survivor.id
        db.flush()
    finally:
        if prior is None:
            db.info.pop(_ENTITY_MERGE_AUTH_KEY, None)
        else:
            db.info[_ENTITY_MERGE_AUTH_KEY] = prior
    _record_event(
        db,
        event_type="entity_merged",
        entity_id=duplicate.id,
        source=owner,
        payload={
            "survivor_entity_id": survivor.id,
            "merged_entity_id": duplicate.id,
            "evidence_id": evidence.id,
            "rationale": reason,
            "source_identity": {"source_system": duplicate.source_system, "source_id": duplicate.source_id},
        },
        idempotency_key=f"entity-merge:{duplicate.id}:{survivor.id}",
    )
    return survivor


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
        existing = db.query(models.WorldRelation).filter_by(idempotency_key=key).one_or_none()
        if existing is None:
            for candidate in db.query(models.WorldRelation).filter_by(
                from_entity_id=from_entity_id, to_entity_id=to_entity_id, relation_type=relation_kind
            ).all():
                existing_system = _parse_json(candidate.attributes).get("_forge", {})
                if isinstance(existing_system, dict) and existing_system.get("idempotency_key") == key:
                    existing = candidate
                    break
        if existing is not None:
            if (existing.from_entity_id, existing.to_entity_id, existing.relation_type) != (
                from_entity_id, to_entity_id, relation_kind
            ):
                raise SubstrateError("relation idempotency key collision; investigate before retrying")
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
        idempotency_key=key if idempotency_key else None,
        valid_from=starts,
        valid_to=ends,
        created_by=owner,
    )
    db.add(relation)
    db.flush()
    _record_event(
        db, event_type="relation_created", relation_id=relation.id, source=owner,
        payload={"relation_type": relation_kind},
        idempotency_key=f"relation-created:{relation.id}",
    )
    return relation


def transition_relation_truth_state(
    db: Session,
    relation: models.WorldRelation,
    next_state: str,
) -> models.WorldRelation:
    if next_state not in TRUTH_STATES:
        raise SubstrateError("invalid relation truth state")
    prior = db.info.get(_TRUTH_TRANSITION_AUTH_KEY)
    db.info[_TRUTH_TRANSITION_AUTH_KEY] = relation
    try:
        relation.truth_state = next_state
        db.flush()
    finally:
        if prior is None:
            db.info.pop(_TRUTH_TRANSITION_AUTH_KEY, None)
        else:
            db.info[_TRUTH_TRANSITION_AUTH_KEY] = prior
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
    idempotency_key: str | None = None,
) -> models.WorldEvent:
    kind = _require_active_type(db, "event_type", event_type)
    clean_payload = dict(payload or {})
    _validate_attributes(db, "event_type", kind, clean_payload)
    if entity_id is not None and relation_id is not None:
        raise SubstrateError("an event may reference an entity or relation, not both")
    if entity_id is not None and db.get(models.SubstrateEntity, entity_id) is None:
        raise SubstrateError("event entity does not exist")
    if relation_id is not None and db.get(models.WorldRelation, relation_id) is None:
        raise SubstrateError("event relation does not exist")
    clean_source = (source or "").strip()
    if not clean_source:
        raise SubstrateError("event source is required")
    if idempotency_key:
        key = idempotency_key.strip()
        if not key:
            raise SubstrateError("event idempotency key cannot be blank")
        existing = db.query(models.WorldEvent).filter_by(idempotency_key=key).one_or_none()
        if existing is not None:
            if (existing.event_type, existing.entity_id, existing.relation_id, existing.payload) != (
                kind, entity_id, relation_id, _dump_json(clean_payload, "payload")
            ):
                raise SubstrateError("event idempotency key collision; investigate before retrying")
            return existing
    event = models.WorldEvent(
        event_type=kind,
        entity_id=entity_id,
        relation_id=relation_id,
        payload=_dump_json(clean_payload, "payload"),
        source=clean_source,
        idempotency_key=key if idempotency_key else None,
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
    attributes: Mapping[str, Any] | None = None,
) -> models.ForgeCapability:
    kind = _require_active_type(db, "capability_type", capability_type)
    payload = dict(attributes or {})
    _validate_attributes(db, "capability_type", kind, payload)
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
        attributes=_dump_json(payload, "attributes"),
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
        create_event(
            db,
            event_type="signal_ingested",
            entity_id=signal_entities[row.id].id,
            source=(row.source or "unknown source"),
            payload={"canonical_ref": {"entity_type": "signal", "entity_id": row.id}},
            occurred_at=row.retrieved_at or row.timestamp,
            idempotency_key=f"signal-ingested:{row.id}",
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
    by_key = db.query(models.WorldRelation).filter_by(idempotency_key=key).one_or_none()
    if by_key is not None:
        if (by_key.from_entity_id, by_key.to_entity_id, by_key.relation_type) != (from_id, to_id, relation_type):
            raise SubstrateError("relation idempotency key collision; investigate before retrying")
        return by_key
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
    return _resolve_type(db, category, type_name).type_name


def _record_event(
    db: Session,
    *,
    event_type: str,
    source: str,
    payload: Mapping[str, Any],
    entity_id: int | None = None,
    relation_id: int | None = None,
    idempotency_key: str | None = None,
) -> models.WorldEvent:
    return create_event(
        db,
        event_type=event_type,
        source=source,
        payload=payload,
        entity_id=entity_id,
        relation_id=relation_id,
        idempotency_key=idempotency_key,
    )


def _relation_evidence(db: Session, relation_id: int, support_level: str) -> models.Evidence | None:
    return (
        db.query(models.Evidence)
        .filter_by(subject_kind="relation", subject_id=relation_id, support_level=support_level)
        .order_by(models.Evidence.id.desc())
        .first()
    )


def _validate_truth_transition(db: Session, relation: models.WorldRelation, old: str, new: str) -> None:
    transitions = {
        "possible": {"hypothesized", "refuted", "unknown"},
        "hypothesized": {"tested", "refuted", "unknown"},
        "tested": {"supported", "refuted", "unknown"},
        "supported": {"tested", "refuted", "unknown"},
        "refuted": {"tested", "unknown"},
        "unknown": {"hypothesized", "tested", "refuted"},
    }
    if new not in transitions.get(old, set()):
        raise SubstrateError(f"cannot move relation from {old} to {new}")
    if new in {"tested", "supported", "refuted"}:
        evidence = _relation_evidence(db, relation.id, new)
        if evidence is None:
            raise SubstrateError(f"transition to {new} requires recorded {new} evidence")
        if _is_simulated_source(evidence.source):
            raise SubstrateError("simulated evidence cannot establish a relation")
        if not _has_test_or_source_provenance(evidence):
            raise SubstrateError("evidence needs source provenance or a passing test reference")
    if new == "supported":
        tested = _relation_evidence(db, relation.id, "tested")
        if tested is None or _is_simulated_source(tested.source) or not _has_test_or_source_provenance(tested):
            raise SubstrateError("transition to supported requires prior tested evidence")


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


def _json_object(raw: str | None, field: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError) as exc:
        raise SubstrateError(f"{field} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise SubstrateError(f"{field} must be a JSON object")
    return value


def _validate_substrate_evidence(db: Session, evidence: models.Evidence) -> None:
    if evidence.subject_kind not in {"entity", "relation"}:
        raise SubstrateError("evidence subject_kind must be entity or relation")
    subject_model = models.SubstrateEntity if evidence.subject_kind == "entity" else models.WorldRelation
    if evidence.subject_id is None or db.get(subject_model, evidence.subject_id) is None:
        raise SubstrateError("evidence subject must resolve to an existing substrate record")
    if evidence.support_level not in TRUTH_STATES:
        raise SubstrateError("invalid evidence support level")
    if not (evidence.claim or "").strip() or not (evidence.source or "").strip():
        raise SubstrateError("evidence source and claim are required")
    if evidence.support_level in {"tested", "supported", "refuted"}:
        if _is_simulated_source(evidence.source):
            raise SubstrateError("simulated evidence cannot be tested, supported, or refuted")
        if not _has_test_or_source_provenance(evidence):
            raise SubstrateError("tested evidence requires provenance")


def _validate_registry_schema_json(raw: str | None) -> None:
    try:
        schema = json.loads(raw or "")
    except (json.JSONDecodeError, TypeError) as exc:
        raise SubstrateError("type_registry.schema_json must contain valid JSON") from exc
    validate_json_schema(schema)


@event.listens_for(Session, "before_flush")
def _enforce_substrate_write_contract(session: Session, flush_context: Any, instances: Any) -> None:
    """Guard application ORM writes so service rules cannot be bypassed by assignment."""
    changed_objects = set(session.new).union(session.dirty)
    for obj in changed_objects:
        state = sqlalchemy_inspect(obj)
        is_new = obj in session.new

        if isinstance(obj, models.TypeRegistry):
            if is_new:
                _validate_registry_schema_json(obj.schema_json)
                if obj.status == "active":
                    evidence = _parse_json(obj.status_evidence)
                    if not (
                        session.info.get(_CORE_SEED_AUTH_KEY)
                        and obj.owner_agent == "forge_system"
                        and isinstance(evidence, list)
                        and evidence
                        and evidence[-1].get("kind") == "system_seed"
                        and evidence[-1].get("reference") == "forge-system-seed-v1"
                    ):
                        raise SubstrateError("new type_registry rows must begin proposed")
                elif obj.status != "proposed":
                    raise SubstrateError("new type_registry rows must begin proposed")
            elif state.attrs.status.history.has_changes():
                authorization = session.info.get(_TYPE_STATUS_AUTH_KEY)
                history = _parse_json(obj.status_evidence)
                record = history[-1] if isinstance(history, list) and history else {}
                old = state.attrs.status.history.deleted
                if not old or authorization != (obj, old[0], obj.status):
                    raise SubstrateError("type status changes must use the recorded lifecycle service")
                if (
                    record.get("from") != old[0]
                    or record.get("to") != obj.status
                    or not record.get("actor")
                    or not record.get("rationale")
                    or not _repo_file_exists((record.get("evidence_ref") or "").split("::", 1)[0])
                ):
                    raise SubstrateError("type status transition lacks its verifiable lifecycle evidence")

        if isinstance(obj, models.SubstrateEntity):
            if is_new:
                if obj.identity_state not in (None, "candidate"):
                    raise SubstrateError("new entities must begin as identity candidates")
                if obj.status not in (None, "active"):
                    raise SubstrateError("new entities must begin active")
                _validate_attributes(session, "entity_type", obj.entity_type, _json_object(obj.attributes, "entity attributes"))
            elif state.attrs.identity_state.history.has_changes():
                authorization = session.info.get(_IDENTITY_TRANSITION_AUTH_KEY)
                previous = state.attrs.identity_state.history.deleted
                if not previous or authorization != (obj, previous[0], obj.identity_state):
                    raise SubstrateError("identity state changes must use the evidence-backed identity service")
            elif state.attrs.attributes.history.has_changes():
                _validate_attributes(session, "entity_type", obj.entity_type, _json_object(obj.attributes, "entity attributes"))
            if state.attrs.merged_into_id.history.has_changes() or (
                not is_new and state.attrs.status.history.has_changes() and obj.status == "merged"
            ):
                authorization = session.info.get(_ENTITY_MERGE_AUTH_KEY)
                evidence_id = authorization[2] if authorization and authorization[0] is obj else None
                evidence = session.get(models.Evidence, evidence_id) if evidence_id else None
                if (
                    not authorization
                    or authorization[0] is not obj
                    or authorization[1] != obj.merged_into_id
                    or evidence is None
                    or evidence.subject_kind != "entity"
                    or evidence.subject_id != obj.id
                ):
                    raise SubstrateError("merged entities require the explicit evidence-backed merge service")

        if isinstance(obj, models.WorldRelation):
            if is_new:
                if obj.truth_state not in (None, "possible", "hypothesized"):
                    raise SubstrateError("new relations must begin possible or hypothesized")
                _validate_attributes(session, "relation_type", obj.relation_type, _json_object(obj.attributes, "relation attributes"))
            elif state.attrs.truth_state.history.has_changes():
                authorization = session.info.get(_TRUTH_TRANSITION_AUTH_KEY)
                previous = state.attrs.truth_state.history.deleted
                if not previous or authorization is not obj:
                    raise SubstrateError("truth-state changes must use the canonical transition service")
                _validate_truth_transition(session, obj, previous[0], obj.truth_state)
            elif state.attrs.attributes.history.has_changes():
                _validate_attributes(session, "relation_type", obj.relation_type, _json_object(obj.attributes, "relation attributes"))

        if isinstance(obj, models.WorldEvent):
            if is_new:
                _validate_attributes(session, "event_type", obj.event_type, _json_object(obj.payload, "event payload"))
            elif state.attrs.payload.history.has_changes():
                _validate_attributes(session, "event_type", obj.event_type, _json_object(obj.payload, "event payload"))
        if isinstance(obj, models.ForgeCapability):
            if is_new:
                _validate_attributes(session, "capability_type", obj.capability_type, _json_object(obj.attributes, "capability attributes"))
            elif state.attrs.attributes.history.has_changes():
                _validate_attributes(session, "capability_type", obj.capability_type, _json_object(obj.attributes, "capability attributes"))
        if isinstance(obj, models.Evidence) and obj.subject_kind is not None:
            _validate_substrate_evidence(session, obj)
