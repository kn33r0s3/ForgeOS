"""Universal substrate services over a type registry and canonical adapters.

Existing domain tables remain authoritative. ``entities`` holds typed
references for graph composition, while new domains can create first-class
entities from active registry types without introducing a domain table.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import event, inspect as sqlalchemy_inspect
from sqlalchemy.exc import IntegrityError
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
_ENTITY_ARCHIVE_AUTH_KEY = "forgeos.entity_archive"
_ENTITY_SOURCE_REFRESH_AUTH_KEY = "forgeos.entity_source_refresh"
_CAPABILITY_LIFECYCLE_AUTH_KEY = "forgeos.capability_lifecycle_transition"
_CAPABILITY_TRANSITIONS = {"proposed": {"building"}, "building": {"tested"}, "tested": {"active"}}
_REVISION = re.compile(r"^[0-9a-f]{7,40}$")


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


def _schema_for_assumption() -> dict[str, Any]:
    """Attribute schema for the assumption projection (entity_type=assumption).
    Recovered from v2's Assumption fields; enforced by the substrate write
    contract on every assumption write."""
    return {
        "type": "object",
        "properties": {
            "statement": {"type": "string", "minLength": 1},
            "status": {
                "type": "string",
                "enum": ["untested", "supported", "contradicted"],
            },
            "deal_killer": {"type": "boolean"},
            "cost_to_test": {"type": "string"},
            "cheapest_test": {"type": "string"},
            "milestone": {"type": "string"},
            "source_note": {"type": "string"},
            "evidence_links": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "statement",
            "status",
            "deal_killer",
            "cost_to_test",
            "cheapest_test",
            "milestone",
            "source_note",
            "evidence_links",
        ],
        "additionalProperties": False,
    }


def _schema_for_orientation() -> dict[str, Any]:
    """Attribute schema for the orientation projection (entity_type=orientation).
    Recovered from v2's Orientation + OrientationBelief; beliefs are embedded
    as structured attributes, not a separate table."""
    return {
        "type": "object",
        "properties": {
            "version": {"type": "integer", "minimum": 1},
            "observer_who": {"type": "string", "minLength": 1},
            "observer_from_where": {"type": "string", "minLength": 1},
            "means": {"type": "string", "minLength": 1},
            "local_knowledge": {"type": "string"},
            "beliefs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "belief_text": {"type": "string", "minLength": 1},
                        "assumption_id": {"type": ["integer", "null"], "minimum": 1},
                    },
                    "required": ["belief_text", "assumption_id"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "version",
            "observer_who",
            "observer_from_where",
            "means",
            "local_knowledge",
            "beliefs",
        ],
        "additionalProperties": False,
    }


def _schema_for_constraint_diagnosis() -> dict[str, Any]:
    """Attribute schema for the constraint-diagnosis projection
    (entity_type=constraint_diagnosis). Recovered from v2's ConstraintDiagnosis
    + DiagnosisNode; nodes are embedded as structured attributes. The
    most_binding_hypothesis is a hypothesis, not an established fact."""
    return {
        "type": "object",
        "properties": {
            "situation": {"type": "string", "minLength": 1},
            "nodes": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "node_text": {"type": "string", "minLength": 1},
                        "evidence": {"type": "string"},
                        "binding_status": {
                            "type": "string",
                            "enum": [
                                "most_binding_hypothesis",
                                "not_binding_now",
                                "may_bind_later",
                            ],
                        },
                    },
                    "required": ["node_text", "evidence", "binding_status"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["situation", "nodes"],
        "additionalProperties": False,
    }


def seed_core_types(db: Session) -> int:
    """Install the stable substrate vocabulary as registry rows, idempotently."""
    canonical_schema = json.dumps(_schema_for_canonical_ref(), sort_keys=True, separators=(",", ":"))
    assumption_schema = json.dumps(_schema_for_assumption(), sort_keys=True, separators=(",", ":"))
    orientation_schema = json.dumps(_schema_for_orientation(), sort_keys=True, separators=(",", ":"))
    diagnosis_schema = json.dumps(_schema_for_constraint_diagnosis(), sort_keys=True, separators=(",", ":"))
    open_schema = '{"type":"object"}'
    types = {
        "entity_type": {
            "signal", "pattern", "belief", "claim", "research_question", "opportunity",
            "provider", "service_listing", "domain_record", "outcome", "customer", "person",
            "organization", "resource", "capability", "tool", "agent", "project", "market",
            "market_signal", "market_segment", "relation", "action", "learning_event",
            "booking_request", "decision", "experiment", "scenario_prediction",
            "evidence_record", "product",
            "repair_work_item", "need",
            "bet", "scout_candidate",
            "probe", "assumption",
            "orientation", "constraint_diagnosis",
        },
        "relation_type": {
            "derived_from", "supports", "possible_match", "co_occurs_with", "informs", "informed_by",
            "offered_by", "owned_by", "part_of", "enables", "observed_with",
            "signals", "tracks", "responds_to",
        },
        "event_type": {
            "entity_created", "relation_created", "signal_ingested", "state_changed",
            "capability_test_passed", "capability_test_failed", "type_status_changed",
            "entity_identity_changed", "entity_merged", "entity_archived",
            "entity_source_refreshed", "action_attempt_started", "action_attempt_status_changed",
            "outcome_recorded", "learning_recorded", "network_relation_projected",
            "network_relation_unresolved", "capability_source_refreshed",
            "market_signal_observed", "market_signal_aggregated", "market_signal_related",
            "demand_observed", "demand_understood", "capability_search_performed",
            "capability_gap_recorded", "capability_gap_candidates_discovered",
            "economic_validation_assessed",
            "prospect_discovery_evaluated",
            "cognitive_proposals_generated",
            "forge_bot_inquiry_received",
            "forge_bot_inquiry_opted_out",
            "forge_bot_inquiry_erased",
            "forge_bot_response_authorization_changed",
            "forge_bot_response_action_proposed",
            "forge_bot_response_action_owner_approved",
            "forge_bot_response_action_authorization_decided",
            "outreach.sent",
            "outreach.reply",
        },
        "capability_type": {"tool", "workflow", "integration", "agent", "model", "market_signal_analysis"},
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
                if category == "entity_type" and name == "assumption":
                    schema_json = assumption_schema
                elif category == "entity_type" and name == "orientation":
                    schema_json = orientation_schema
                elif category == "entity_type" and name == "constraint_diagnosis":
                    schema_json = diagnosis_schema
                elif category == "entity_type" and name in {
                    "signal", "pattern", "belief", "claim", "research_question", "opportunity",
                    "provider", "service_listing", "domain_record", "outcome", "customer",
                    "relation", "action", "learning_event", "booking_request", "decision",
                    "experiment", "scenario_prediction", "evidence_record", "product", "repair_work_item",
                }:
                    schema_json = canonical_schema
                else:
                    schema_json = open_schema
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
    allowed = {"proposed": {"active"}, "active": {"deprecated"}, "deprecated": set()}
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
    identity: Mapping[str, Any] | None = None,
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
    identity = dict(identity or {})
    source_system = (identity.get("source_system") or "").strip().casefold() or None
    source_id = str(identity["source_id"]).strip() if identity.get("source_id") is not None else None
    if bool(source_system) != bool(source_id):
        raise SubstrateError("source identity requires both source_system and source_id")
    if source_system and not identity.get("provenance"):
        raise SubstrateError("source identity requires recorded provenance")
    identity_key = f"source:{kind}:{source_system}:{source_id}" if source_system and source_id else None
    attributes_json = _dump_json(dict(attributes), "attributes")
    canonical_identifier = _canonical_identifier(identity.get("canonical_identifier"))
    normalized_identity = identity.get("normalized_identity") or normalize_identity(name)
    identity_uncertainty = (
        identity.get("identity_uncertainty")
        or "Real-world identity is not independently corroborated."
    )
    identity_provenance = _dump_json(identity.get("provenance", {}), "identity provenance")
    if identity_key:
        existing = db.query(models.SubstrateEntity).filter_by(identity_key=identity_key).one_or_none()
        if existing is not None:
            expected = (
                name,
                attributes_json,
                canonical_identifier,
                normalized_identity,
                identity_uncertainty,
                identity_provenance,
            )
            actual = (
                existing.display_name,
                existing.attributes,
                existing.canonical_identifier,
                existing.normalized_identity,
                existing.identity_uncertainty,
                existing.identity_provenance,
            )
            if (existing.entity_type, existing.source_system, existing.source_id) != (
                kind, source_system, source_id
            ) or actual != expected:
                raise SubstrateError(
                    "source identity already exists with a different payload; "
                    "use its registered adapter to refresh it"
                )
            return existing
    entity = models.SubstrateEntity(
        entity_type=kind,
        display_name=name,
        attributes=attributes_json,
        identity_key=identity_key,
        source_system=source_system,
        source_id=source_id,
        canonical_identifier=canonical_identifier,
        normalized_identity=normalized_identity,
        identity_state="candidate",
        identity_uncertainty=identity_uncertainty,
        identity_provenance=identity_provenance,
        created_by=owner,
    )
    db.add(entity)
    db.flush()
    _record_event(
        db, event_type="entity_created", entity_id=entity.id, source=owner,
        payload={"entity_type": kind}, idempotency_key=f"entity-created:{entity.id}",
    )
    return entity


def find_canonical_entity(
    db: Session,
    entity_type: str,
    entity_id: int,
    *,
    source_system: str | None = None,
) -> models.SubstrateEntity | None:
    kind = canonical_entity_type(entity_type)
    explicit_source = source_system is not None
    if source_system is None:
        adapter = CANONICAL_ADAPTERS.get(kind)
        source_system = adapter[0].__tablename__ if adapter is not None else None
    if source_system is not None:
        entity = (
            db.query(models.SubstrateEntity)
            .filter_by(entity_type=kind, source_system=source_system, source_id=str(entity_id))
            .order_by(models.SubstrateEntity.id.asc())
            .first()
        )
        if entity is not None:
            return entity
        if explicit_source:
            legacy_attrs = _dump_json(
                {"canonical_ref": {"entity_type": kind, "entity_id": int(entity_id)}},
                "attributes",
            )
            legacy = (
                db.query(models.SubstrateEntity)
                .filter_by(entity_type=kind, attributes=legacy_attrs)
                .order_by(models.SubstrateEntity.id.asc())
                .first()
            )
            return legacy if legacy is not None and legacy.source_system is None and legacy.identity_key is None else None
    attrs = _dump_json({"canonical_ref": {"entity_type": kind, "entity_id": int(entity_id)}}, "attributes")
    query = db.query(models.SubstrateEntity).filter_by(entity_type=kind, attributes=attrs)
    if source_system is not None:
        query = query.filter(
            models.SubstrateEntity.source_system.is_(None),
            models.SubstrateEntity.identity_key.is_(None),
        )
    return query.order_by(models.SubstrateEntity.id.asc()).first()


def ensure_canonical_entity(
    db: Session,
    entity_type: str,
    entity_id: int,
    *,
    created_by: str = "canonical_adapter",
    source_system: str | None = None,
) -> models.SubstrateEntity:
    """Create a minimal wrapper for an existing record, never copy its payload."""
    kind = canonical_entity_type(entity_type)
    if isinstance(entity_id, bool) or not isinstance(entity_id, int) or entity_id < 1:
        raise SubstrateError("canonical entity id must be a positive integer")
    adapter = CANONICAL_ADAPTERS.get(kind)
    if kind == "action" and source_system == "experiments":
        adapter = (models.Experiment, lambda row: f"{row.action_type or 'Experiment'} attempt #{row.id}")
    if adapter is None:
        raise SubstrateError(f"no canonical adapter for entity type: {kind}")
    if source_system is not None and adapter[0].__tablename__ != source_system:
        raise SubstrateError("source_system is not registered for this canonical entity type")
    source_system = adapter[0].__tablename__
    row = db.query(adapter[0]).filter(adapter[0].id == entity_id).first()
    if row is None:
        raise SubstrateError(f"missing canonical record {kind}:{entity_id}")
    action_eligible = True
    if kind == "action":
        action_eligible = (
            _is_authorized_experiment_attempt(row) if source_system == "experiments"
            else _is_authorized_action_attempt(row)
        )
    if kind == "action" and not action_eligible:
        raise SubstrateError(
            "operational action is not a substrate Action attempt until an allowed, authorized execution has started"
        )
    existing = find_canonical_entity(db, kind, entity_id, source_system=source_system)
    display_name = adapter[1](row)
    source_identifier = (
        getattr(row, "canonical_url", None)
        or getattr(row, "website", None)
        or getattr(row, "external_id", None)
    )
    canonical_identifier = _canonical_identifier(source_identifier)
    source_value = getattr(row, "source", None)
    provenance = getattr(row, "provenance", None)
    metadata = {
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
            "canonical_url": source_identifier,
            "external_id": getattr(row, "external_id", None),
            "source_provenance": provenance,
        },
    }
    if existing is not None:
        expected_key = f"source:{kind}:{metadata['source_system']}:{metadata['source_id']}"
        if existing.identity_key not in (None, expected_key):
            raise SubstrateError("canonical source identity changed; retain the candidate and review the conflict")
        old_values = {
            "display_name": existing.display_name,
            "identity_key": existing.identity_key,
            "source_system": existing.source_system,
            "source_id": existing.source_id,
            "canonical_identifier": existing.canonical_identifier,
            "normalized_identity": existing.normalized_identity,
            "identity_uncertainty": existing.identity_uncertainty,
            "identity_provenance": existing.identity_provenance,
        }
        next_values = {
            "display_name": display_name,
            "identity_key": expected_key,
            "source_system": source_system,
            "source_id": str(entity_id),
            "canonical_identifier": canonical_identifier,
            "normalized_identity": metadata["normalized_identity"],
            "identity_uncertainty": metadata["identity_uncertainty"],
            "identity_provenance": _dump_json(metadata["provenance"], "identity provenance"),
        }
        changed = [key for key, value in next_values.items() if old_values[key] != value]
        if changed:
            prior = db.info.get(_ENTITY_SOURCE_REFRESH_AUTH_KEY)
            db.info[_ENTITY_SOURCE_REFRESH_AUTH_KEY] = existing
            try:
                for key, value in next_values.items():
                    setattr(existing, key, value)
                db.flush()
            finally:
                if prior is None:
                    db.info.pop(_ENTITY_SOURCE_REFRESH_AUTH_KEY, None)
                else:
                    db.info[_ENTITY_SOURCE_REFRESH_AUTH_KEY] = prior
            fingerprint = hashlib.sha256(_dump_json(next_values, "identity refresh").encode("utf-8")).hexdigest()
            _record_event(
                db,
                event_type="entity_source_refreshed",
                entity_id=existing.id,
                source=created_by,
                payload={
                    "entity_type": kind,
                    "source_system": source_system,
                    "source_id": str(entity_id),
                    "changed_fields": changed,
                    "canonical_identifier": canonical_identifier,
                    "source_provenance": metadata["provenance"],
                },
                idempotency_key=f"entity-source-refresh:{existing.id}:{fingerprint}",
            )
        return existing
    return create_entity(
        db,
        entity_type=kind,
        display_name=display_name,
        attributes={"canonical_ref": {"entity_type": kind, "entity_id": entity_id}},
        created_by=created_by,
        _adapter_record=True,
        identity=metadata,
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
        or _is_simulated_source(evidence_source(evidence))
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
        or _is_simulated_source(evidence_source(evidence))
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


def archive_entity(
    db: Session,
    entity: models.SubstrateEntity,
    *,
    actor: str,
    rationale: str,
) -> models.SubstrateEntity:
    """Archive an entity without deleting its identity, relations, or evidence."""
    if entity.status != "active":
        raise SubstrateError(f"cannot archive entity from {entity.status}")
    owner, reason = (actor or "").strip(), (rationale or "").strip()
    if not owner or not reason:
        raise SubstrateError("archiving an entity requires actor and rationale")
    prior = db.info.get(_ENTITY_ARCHIVE_AUTH_KEY)
    db.info[_ENTITY_ARCHIVE_AUTH_KEY] = entity
    try:
        entity.status = "archived"
        db.flush()
    finally:
        if prior is None:
            db.info.pop(_ENTITY_ARCHIVE_AUTH_KEY, None)
        else:
            db.info[_ENTITY_ARCHIVE_AUTH_KEY] = prior
    _record_event(
        db,
        event_type="entity_archived",
        entity_id=entity.id,
        source=owner,
        payload={"entity_id": entity.id, "rationale": reason},
        idempotency_key=f"entity-archive:{entity.id}",
    )
    return entity


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
            expected = (
                from_entity_id,
                to_entity_id,
                relation_kind,
                attrs,
                direction,
                float(strength) if strength is not None else None,
                truth_state,
                starts,
                ends,
                owner,
            )
            actual = (
                existing.from_entity_id,
                existing.to_entity_id,
                existing.relation_type,
                _parse_json(existing.attributes),
                existing.direction,
                existing.strength,
                existing.truth_state,
                existing.valid_from,
                existing.valid_to,
                existing.created_by,
            )
            if actual != expected:
                raise SubstrateError("relation idempotency key collision; investigate before retrying")
            return existing
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
    _validate_truth_transition(db, relation, relation.truth_state, next_state)
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
    idempotency_key: str | None = None,
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
        test_ref = (test_meta.get("test_ref") or "").split("::", 1)[0]
        if test_meta.get("result") != "passed" or not _repo_file_exists(test_ref):
            raise SubstrateError("test evidence must cite an existing passing test reference")
    key = None
    if idempotency_key is not None:
        key = idempotency_key.strip()
        if not key:
            raise SubstrateError("evidence idempotency key cannot be blank")
        existing = db.query(models.Evidence).filter_by(idempotency_key=key).one_or_none()
        if existing is not None:
            expected = (kind, subject_id, clean_claim, state, clean_source, provenance_json,
                        confidence if confidence is not None else 0.0)
            actual = (existing.subject_kind, existing.subject_id, existing.claim,
                      existing.support_level, evidence_source(existing), evidence_provenance(existing),
                      existing.substrate_confidence if existing.substrate_confidence is not None else existing.confidence)
            if actual != expected:
                raise SubstrateError("evidence idempotency key collision; investigate before retrying")
            return existing
    evidence = models.Evidence(
        subject_kind=kind,
        subject_id=subject_id,
        claim=clean_claim,
        support_level=state,
        confidence=confidence if confidence is not None else 0.0,
        source=clean_source,
        provenance=provenance_json,
        substrate_source=clean_source,
        substrate_confidence=confidence if confidence is not None else 0.0,
        substrate_provenance=provenance_json,
        recorded_at=models.utcnow(),
        idempotency_key=key,
    )
    if key is None:
        db.add(evidence)
        db.flush()
    else:
        try:
            with db.begin_nested():
                db.add(evidence)
                db.flush()
        except IntegrityError as exc:
            # Another writer may have committed this key after our lookup.
            # The savepoint keeps the caller's outer transaction recoverable.
            db.expire_all()
            existing = db.query(models.Evidence).filter_by(idempotency_key=key).one_or_none()
            if existing is None:
                raise SubstrateError(
                    "evidence idempotency collision; retry after rolling back the outer transaction"
                ) from exc
            expected = (kind, subject_id, clean_claim, state, clean_source, provenance_json,
                        confidence if confidence is not None else 0.0)
            actual = (existing.subject_kind, existing.subject_id, existing.claim,
                      existing.support_level, evidence_source(existing), evidence_provenance(existing),
                      existing.substrate_confidence if existing.substrate_confidence is not None else existing.confidence)
            if actual != expected:
                raise SubstrateError("evidence idempotency key collision; investigate before retrying") from exc
            return existing
    return evidence


def attach_legacy_evidence(
    db: Session,
    evidence: models.Evidence,
    *,
    subject_id: int,
    source: str,
    substrate_provenance: Mapping[str, Any],
    recorded_at: datetime,
) -> models.Evidence:
    """Attach one existing raw Evidence row through the canonical validator.

    Legacy source, content, direction, confidence, provenance, identifiers,
    and timestamps remain byte-for-byte source authority. Historical truth is
    represented as ``unknown`` until a separate evidence-backed transition.
    """
    if evidence.id is None or db.get(models.Evidence, evidence.id) is None:
        raise SubstrateError("legacy evidence must already be persisted")
    subject = db.get(models.SubstrateEntity, subject_id)
    if subject is None:
        raise SubstrateError("legacy evidence subject does not exist")
    clean_source = (source or "").strip()
    provenance_json = _dump_json(dict(substrate_provenance), "substrate provenance")
    if not clean_source or not (evidence.content or "").strip():
        raise SubstrateError("legacy evidence requires its raw content and a resolvable source")

    if evidence.subject_kind is not None:
        if (
            evidence.subject_kind == "entity"
            and evidence.subject_id == subject_id
            and evidence.substrate_source == clean_source
            and evidence.substrate_provenance == provenance_json
            and evidence.support_level == "unknown"
        ):
            return evidence
        raise SubstrateError("legacy evidence is already mapped; investigate before changing its subject")
    if evidence.subject_id is not None:
        raise SubstrateError("legacy evidence has a dangling substrate subject id")

    evidence.subject_kind = "entity"
    evidence.subject_id = subject_id
    evidence.support_level = "unknown"
    evidence.substrate_source = clean_source
    evidence.substrate_confidence = None
    evidence.substrate_provenance = provenance_json
    evidence.recorded_at = recorded_at
    _validate_substrate_evidence(db, evidence)
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
    normalized_occurred_at = _utc_naive(occurred_at)
    if idempotency_key:
        key = idempotency_key.strip()
        if not key:
            raise SubstrateError("event idempotency key cannot be blank")
        existing = db.query(models.WorldEvent).filter_by(idempotency_key=key).one_or_none()
        if existing is not None:
            if (existing.event_type, existing.entity_id, existing.relation_id, existing.payload) != (
                kind, entity_id, relation_id, _dump_json(clean_payload, "payload")
            ) or existing.source != clean_source or (
                normalized_occurred_at is not None and existing.occurred_at != normalized_occurred_at
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
        occurred_at=normalized_occurred_at or models.utcnow(),
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
    provenance: Mapping[str, Any] | None = None,
) -> models.ForgeCapability:
    """Record one test run; only an attributable pass of ``test_ref`` advances it.

    A pass must name who ran it (``provenance.actor``), the repository revision
    it ran against (``provenance.revision``), and a command that actually
    invokes the referenced test file. A failing run is still recorded as a
    ``capability_test_failed`` event so failures are never erased.
    """
    if capability.status != "building":
        raise SubstrateError("only a building capability can be tested")
    if not _repo_file_exists(test_ref):
        raise SubstrateError("test_ref must resolve to a file inside the ForgeOS repository")
    if not command.strip():
        raise SubstrateError("test command is required")
    clean_provenance = dict(provenance or {})
    if exit_code == 0:
        _require_capability_test_provenance(test_ref, command, clean_provenance)
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
            "provenance": clean_provenance,
        },
    )
    if exit_code == 0:
        _set_capability_lifecycle(db, capability, "tested", test_ref=test_ref)
    return capability


def begin_capability_build(db: Session, capability: models.ForgeCapability) -> models.ForgeCapability:
    if capability.status != "proposed":
        raise SubstrateError(f"cannot begin build from {capability.status}")
    _set_capability_lifecycle(db, capability, "building")
    return capability


def activate_capability(db: Session, capability: models.ForgeCapability) -> models.ForgeCapability:
    if capability.status != "tested" or not capability.test_ref:
        raise SubstrateError("capability must pass a recorded test before activation")
    if capability_activation_record(db, capability) is None:
        raise SubstrateError(
            "a passing, provenance-backed test event and existing test_ref are required"
        )
    _set_capability_lifecycle(db, capability, "active")
    return capability


def capability_activation_record(
    db: Session, capability: models.ForgeCapability
) -> dict[str, Any] | None:
    """Return the passing test event that justifies ``capability.test_ref``.

    ``None`` means no stored, attributable passing run of the current test_ref
    exists: such a capability must not be treated as verified, whatever its
    stored status says (older rows may predate this rule).
    """
    if not capability.id or not capability.test_ref or not _repo_file_exists(capability.test_ref):
        return None
    events = (
        db.query(models.WorldEvent)
        .filter_by(event_type="capability_test_passed", source="pytest")
        .order_by(models.WorldEvent.id.desc())
        .all()
    )
    for event in events:
        payload = _parse_json(event.payload)
        if (
            payload.get("capability_id") != capability.id
            or payload.get("test_ref") != capability.test_ref
            or payload.get("exit_code") != 0
        ):
            continue
        provenance = payload.get("provenance")
        try:
            _require_capability_test_provenance(
                capability.test_ref, str(payload.get("command") or ""),
                provenance if isinstance(provenance, dict) else {},
            )
        except SubstrateError:
            continue
        return {
            "test_event_id": event.id,
            "test_ref": capability.test_ref,
            "command": payload["command"],
            "actor": provenance["actor"],
            "revision": provenance["revision"],
            "occurred_at": event.occurred_at,
        }
    return None


def _require_capability_test_provenance(
    test_ref: str, command: str, provenance: Mapping[str, Any]
) -> None:
    actor = provenance.get("actor")
    revision = provenance.get("revision")
    if not isinstance(actor, str) or not actor.strip():
        raise SubstrateError("a passing capability test requires provenance.actor")
    if not isinstance(revision, str) or not _REVISION.match(revision.strip().lower()):
        raise SubstrateError("a passing capability test requires provenance.revision (a git commit SHA)")
    if Path(test_ref).name not in command:
        raise SubstrateError("the test command must invoke the referenced test_ref file")


def _set_capability_lifecycle(
    db: Session,
    capability: models.ForgeCapability,
    next_status: str,
    *,
    test_ref: str | None = None,
) -> None:
    old_status = capability.status
    if next_status not in _CAPABILITY_TRANSITIONS.get(old_status, set()):
        raise SubstrateError(f"cannot move capability from {old_status} to {next_status}")
    prior = db.info.get(_CAPABILITY_LIFECYCLE_AUTH_KEY)
    db.info[_CAPABILITY_LIFECYCLE_AUTH_KEY] = (capability, old_status, next_status)
    try:
        if test_ref is not None:
            capability.test_ref = test_ref
        capability.status = next_status
        db.flush()
    finally:
        if prior is None:
            db.info.pop(_CAPABILITY_LIFECYCLE_AUTH_KEY, None)
        else:
            db.info[_CAPABILITY_LIFECYCLE_AUTH_KEY] = prior


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
        event_key = f"signal-ingested:{row.id}"
        if not db.query(models.WorldEvent).filter_by(idempotency_key=event_key).first() and not db.query(
            models.WorldEvent
        ).filter_by(event_type="signal_ingested", entity_id=signal_entities[row.id].id).first():
            create_event(
                db,
                event_type="signal_ingested",
                entity_id=signal_entities[row.id].id,
                source=(row.source or "unknown source"),
                payload={
                    "canonical_ref": {"entity_type": "signal", "entity_id": row.id},
                    "source_provenance": _parse_json(signal_entities[row.id].identity_provenance),
                },
                occurred_at=row.retrieved_at or row.timestamp,
                idempotency_key=event_key,
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


def sync_action_outcome_learning_path(db: Session, *, limit: int = 100) -> dict[str, int]:
    """Project existing authorized attempts and their measured learning path.

    The operational tables remain write authority. Proposals, blocked actions,
    and actions without a recorded start are not logical Action attempts. A
    learning/outcome edge is added only when a unique experiment and matching
    data scope identify it; ambiguous legacy links remain unconnected.
    """
    seed_core_types(db)
    source_limit = max(1, int(limit))
    action_rows = (
        db.query(models.Action)
        .filter(models.Action.started_at.isnot(None))
        .order_by(models.Action.started_at.desc(), models.Action.id.desc())
        .limit(source_limit)
        .all()
    )
    actions = {row.id: row for row in action_rows if _is_authorized_action_attempt(row)}
    experiment_rows = (
        db.query(models.Experiment)
        .filter(models.Experiment.started_at.isnot(None))
        .order_by(models.Experiment.started_at.desc(), models.Experiment.id.desc())
        .limit(source_limit)
        .all()
    )
    experiment_ids = [row.id for row in experiment_rows]
    existing_action_experiment_ids = {
        experiment_id
        for (experiment_id,) in db.query(models.Action.experiment_id)
        .filter(models.Action.experiment_id.in_(experiment_ids or [-1]))
        .all()
        if experiment_id is not None
    }
    experiments = {
        row.id: row
        for row in experiment_rows
        if row.id not in existing_action_experiment_ids and _is_authorized_experiment_attempt(row)
    }
    outcomes = (
        db.query(models.Outcome)
        .order_by(models.Outcome.observed_at.desc(), models.Outcome.id.desc())
        .limit(source_limit)
        .all()
    )
    learning_events = (
        db.query(models.LearningEvent)
        .order_by(models.LearningEvent.created_at.desc(), models.LearningEvent.id.desc())
        .limit(source_limit)
        .all()
    )

    created = {"entities_created": 0, "relations_created": 0, "events_created": 0}
    action_entities: dict[int, models.SubstrateEntity] = {}
    experiment_entities: dict[int, models.SubstrateEntity] = {}
    actions_by_experiment: dict[int, list[models.SubstrateEntity]] = {}
    outcome_entities: dict[int, models.SubstrateEntity] = {}
    learning_entities: dict[int, models.SubstrateEntity] = {}

    def ensure(kind: str, row: Any) -> models.SubstrateEntity:
        before = find_canonical_entity(db, kind, row.id)
        entity = ensure_canonical_entity(db, kind, row.id)
        if before is None:
            created["entities_created"] += 1
        return entity

    def record_event(
        *,
        kind: str,
        source_row: Any,
        entity: models.SubstrateEntity,
        key: str,
        payload: dict[str, Any],
        occurred_at: datetime | None,
    ) -> bool:
        if db.query(models.WorldEvent).filter_by(idempotency_key=key).first() is not None:
            return False
        create_event(
            db,
            event_type=kind,
            source="legacy_action_outcome_learning_adapter",
            entity_id=entity.id,
        payload={
                **payload,
                "source_system": source_row.__tablename__,
                "source_id": source_row.id,
                "source_ref": {
                    "entity_type": entity.entity_type,
                    "entity_id": source_row.id,
                    "source_system": source_row.__tablename__,
                },
                "source_provenance": {
                    "adapter": "legacy_action_outcome_learning_adapter",
                    "source_system": source_row.__tablename__,
                    "source_id": source_row.id,
                },
                "entity_identity_provenance": _parse_json(entity.identity_provenance),
            },
            occurred_at=occurred_at,
            idempotency_key=key,
        )
        created["events_created"] += 1
        return True

    def record_attempt(row: Any, entity: models.SubstrateEntity, *, source_system: str, source_id: int) -> None:
        if source_system == "actions":
            start_key = f"action-attempt-started:actions:{source_id}"
            status_key_prefix = f"action-attempt-status:actions:{source_id}"
            policy = row.policy_result
            ongoing = {"RUNNING", "PROPOSED", "APPROVAL_REQUIRED"}
            adapter_name = row.adapter_name
        else:
            start_key = f"action-attempt-started:experiments:{source_id}"
            status_key_prefix = f"action-attempt-status:experiments:{source_id}"
            policy = row.policy_decision or row.authorization_status
            ongoing = {"in_progress", "planned", "ready"}
            adapter_name = None
        record_event(
            kind="action_attempt_started",
            source_row=row,
            entity=entity,
            key=start_key,
            payload={
                "status": row.status,
                "policy_result": policy,
                "approved_at": _datetime_iso(row.approved_at),
                "started_at": _datetime_iso(row.started_at),
                "adapter_name": adapter_name,
            },
            occurred_at=row.started_at,
        )
        if row.status not in ongoing:
            previous_state_events = (
                db.query(models.WorldEvent)
                .filter_by(event_type="action_attempt_status_changed", entity_id=entity.id)
                .order_by(models.WorldEvent.id.desc())
                .all()
            )
            previous_status = next((
                prior_payload.get("status")
                for prior_payload in (_parse_json(event.payload) for event in previous_state_events)
                if prior_payload.get("source_system") == source_system
            ), None)
            record_event(
                kind="action_attempt_status_changed",
                source_row=row,
                entity=entity,
                key=f"{status_key_prefix}:{row.status}",
                payload={
                    "from_status": previous_status,
                    "status": row.status,
                    "verification_state": getattr(row, "verification_state", None),
                    "completed_at": _datetime_iso(row.completed_at),
                },
                occurred_at=row.completed_at or row.started_at,
            )

    for row in actions.values():
        experiment_entity = (
            find_canonical_entity(db, "action", row.experiment_id, source_system="experiments")
            if row.experiment_id is not None else None
        )
        entity = experiment_entity or ensure("action", row)
        action_entities[row.id] = entity
        if row.experiment_id is not None:
            actions_by_experiment.setdefault(row.experiment_id, []).append(entity)
        record_attempt(row, entity, source_system="actions", source_id=row.id)

    for row in experiments.values():
        before = find_canonical_entity(db, "action", row.id, source_system="experiments")
        entity = ensure_canonical_entity(
            db, "action", row.id, created_by="legacy_action_outcome_learning_adapter",
            source_system="experiments",
        )
        if before is None:
            created["entities_created"] += 1
        experiment_entities[row.id] = entity
        actions_by_experiment.setdefault(row.id, []).append(entity)
        record_attempt(row, entity, source_system="experiments", source_id=row.id)

    for row in outcomes:
        entity = outcome_entities[row.id] = ensure("outcome", row)
        record_event(
            kind="outcome_recorded",
            source_row=row,
            entity=entity,
            key=f"outcome-recorded:{row.id}",
            payload={
                "outcome_type": row.outcome_type,
                "verification_state": row.verification_state,
                "data_scope": row.data_scope,
                "observed_at": _datetime_iso(row.observed_at),
            },
            occurred_at=row.observed_at,
        )

    for row in learning_events:
        entity = learning_entities[row.id] = ensure("learning_event", row)
        record_event(
            kind="learning_recorded",
            source_row=row,
            entity=entity,
            key=f"learning-recorded:{row.id}",
            payload={
                "experiment_id": row.experiment_id,
                "data_scope": row.data_scope,
                "created_at": _datetime_iso(row.created_at),
            },
            occurred_at=row.created_at,
        )

    outcomes_by_experiment_scope: dict[tuple[int, str], list[models.Outcome]] = {}
    for row in outcomes:
        if row.experiment_id is not None:
            outcomes_by_experiment_scope.setdefault(
                (row.experiment_id, (row.data_scope or "").upper()), []
            ).append(row)

    ambiguous_links = 0
    for outcome in outcomes:
        linked_entity: models.SubstrateEntity | None = None
        link_basis: str | None = None
        if outcome.action_id is not None:
            linked_entity = action_entities.get(outcome.action_id)
            if linked_entity is not None:
                link_basis = "outcome.action_id"
        elif outcome.experiment_id is not None:
            candidates = actions_by_experiment.get(outcome.experiment_id, [])
            if len(candidates) == 1:
                linked_entity, link_basis = candidates[0], "shared_experiment_id"
            elif len(candidates) > 1:
                ambiguous_links += 1
            elif outcome.experiment_id in existing_action_experiment_ids:
                ambiguous_links += 1
        if linked_entity is None:
            continue
        if _ensure_operational_relation(
            db,
            outcome_entities[outcome.id],
            linked_entity,
            key=f"outcome:{outcome.id}:derived_from:action-entity:{linked_entity.id}",
            adapter="action_outcome_learning",
            source_ref={"entity_type": "outcome", "entity_id": outcome.id, "source_system": "outcomes"},
            related_ref=_source_identity_ref(linked_entity),
            link_basis=link_basis,
        ):
            created["relations_created"] += 1

    for learning in learning_events:
        if learning.experiment_id is None:
            continue
        scope = (learning.data_scope or "").upper()
        candidates = outcomes_by_experiment_scope.get((learning.experiment_id, scope), [])
        if len(candidates) != 1:
            if len(candidates) > 1:
                ambiguous_links += 1
            continue
        outcome = candidates[0]
        if _ensure_operational_relation(
            db,
            learning_entities[learning.id],
            outcome_entities[outcome.id],
            key=f"learning:{learning.id}:derived_from:outcome:{outcome.id}",
            adapter="action_outcome_learning",
            source_ref={"entity_type": "learning_event", "entity_id": learning.id, "source_system": "learning_events"},
            related_ref={"entity_type": "outcome", "entity_id": outcome.id, "source_system": "outcomes"},
            link_basis="shared_experiment_id_and_data_scope",
        ):
            created["relations_created"] += 1

    db.flush()
    return {**created, "ambiguous_links": ambiguous_links}


def _is_authorized_action_attempt(row: models.Action) -> bool:
    if row.started_at is None:
        return False
    if row.policy_result == "ALLOW":
        return True
    return row.policy_result == "REQUIRE_APPROVAL" and row.approved_at is not None


def _is_authorized_experiment_attempt(row: models.Experiment) -> bool:
    if row.started_at is None or row.status in {"blocked", "abandoned"}:
        return False
    if row.policy_decision == "block":
        return False
    if row.requires_owner_approval and row.approved_at is None:
        return False
    if row.authorization_status == "allowed" and row.authorized_at is not None:
        return True
    if row.requires_owner_approval and row.approved_at is not None:
        return True
    return row.policy_decision == "allow" and bool(row.execution_allowed)


def _datetime_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _source_identity_ref(entity: models.SubstrateEntity) -> dict[str, Any]:
    source_id: Any = entity.source_id
    if isinstance(source_id, str) and source_id.isdigit():
        source_id = int(source_id)
    return {
        "entity_type": entity.entity_type,
        "entity_id": source_id,
        "source_system": entity.source_system,
    }


def _ensure_operational_relation(
    db: Session,
    source: models.SubstrateEntity,
    related: models.SubstrateEntity,
    *,
    key: str,
    adapter: str,
    source_ref: dict[str, Any],
    related_ref: dict[str, Any],
    link_basis: str,
) -> bool:
    before = _find_idempotent_relation(db, source.id, related.id, "derived_from", key)
    if before is not None:
        return False
    create_relation(
        db,
        from_entity_id=source.id,
        to_entity_id=related.id,
        relation_type="derived_from",
        attributes={
            "adapter": adapter,
            "source_ref": source_ref,
            "related_ref": related_ref,
            "link_basis": link_basis,
            "source_identity": {"source_system": source.source_system, "source_id": source.source_id},
            "related_identity": {"source_system": related.source_system, "source_id": related.source_id},
        },
        truth_state="hypothesized",
        created_by="legacy_action_outcome_learning_adapter",
        idempotency_key=key,
    )
    return True


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
        attributes={
            "adapter": "signal_pattern_belief_opportunity",
            "source_ref": _parse_json(subject.attributes).get("canonical_ref"),
            "related_ref": _parse_json(object_.attributes).get("canonical_ref"),
            "source_identity": {
                "source_system": subject.source_system,
                "source_id": subject.source_id,
            },
            "related_identity": {
                "source_system": object_.source_system,
                "source_id": object_.source_id,
            },
        },
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
        if _is_simulated_source(evidence_source(evidence)):
            raise SubstrateError("simulated evidence cannot establish a relation")
        if not _has_test_or_source_provenance(evidence):
            raise SubstrateError("evidence needs source provenance or a passing test reference")
    if new == "supported":
        tested = _relation_evidence(db, relation.id, "tested")
        if tested is None or _is_simulated_source(evidence_source(tested)) or not _has_test_or_source_provenance(tested):
            raise SubstrateError("transition to supported requires prior tested evidence")


def _has_test_or_source_provenance(evidence: models.Evidence) -> bool:
    provenance = evidence_provenance(evidence)
    source = evidence_source(evidence)
    if source and source.lower() == "pytest":
        data = _parse_json(provenance)
        test_ref = (data.get("test_ref") or "").split("::", 1)[0]
        return data.get("result") == "passed" and _repo_file_exists(test_ref)
    return bool(provenance.strip())


def evidence_source(evidence: models.Evidence) -> str | None:
    """Return the validated substrate source, falling back to its legacy source."""
    return evidence.substrate_source or evidence.source


def evidence_provenance(evidence: models.Evidence) -> str:
    """Return substrate provenance when present without rewriting legacy provenance."""
    return evidence.substrate_provenance or evidence.provenance or ""


def _is_simulated_source(source: str | None) -> bool:
    value = (source or "").strip().lower()
    return value.startswith(("simulated", "fixture", "mock", "seed", "test-data"))


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
    "booking_request": (models.BookingRequest, lambda row: f"Booking request #{row.id}"),
    "decision": (models.Decision, lambda row: _canonical_display(row, "title")),
    "scenario_prediction": (models.ScenarioPrediction, lambda row: _canonical_display(row, "claim")),
    "evidence_record": (models.Evidence, lambda row: f"Evidence record #{row.id}"),
    "experiment": (models.Experiment, lambda row: _canonical_display(row, "action")),
    "action": (models.Action, lambda row: f"{row.action_type or 'Action'} attempt #{row.id}"),
    "outcome": (models.Outcome, lambda row: f"{row.outcome_type or 'Outcome'} #{row.id}"),
    "learning_event": (models.LearningEvent, lambda row: f"Learning event #{row.id}"),
    "product": (models.Product, lambda row: _canonical_display(row, "name")),
    "repair_work_item": (models.RepairWorkItem, lambda row: _canonical_display(row, "asset_label")),
    "customer": (models.Customer, lambda row: _canonical_display(row, "name")),
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
    if not (evidence.claim or evidence.content or "").strip() or not evidence_source(evidence):
        raise SubstrateError("evidence source and claim are required")
    if evidence.support_level in {"tested", "supported", "refuted"}:
        if _is_simulated_source(evidence_source(evidence)):
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
            if not is_new and any(
                state.attrs[field].history.has_changes()
                for field in (
                    "identity_key", "source_system", "source_id", "canonical_identifier",
                    "normalized_identity", "identity_uncertainty", "identity_provenance",
                )
            ) and session.info.get(_ENTITY_SOURCE_REFRESH_AUTH_KEY) is not obj:
                raise SubstrateError("identity metadata changes must use the canonical source adapter")
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
            if not is_new and state.attrs.status.history.has_changes() and obj.status == "archived":
                if session.info.get(_ENTITY_ARCHIVE_AUTH_KEY) is not obj:
                    raise SubstrateError("entity archival must use the recorded archive service")

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
                if obj.status not in (None, "proposed") or obj.test_ref is not None:
                    raise SubstrateError("new capabilities must begin proposed without a test_ref")
            elif (
                state.attrs.status.history.has_changes()
                or state.attrs.test_ref.history.has_changes()
            ):
                authorization = session.info.get(_CAPABILITY_LIFECYCLE_AUTH_KEY)
                previous = state.attrs.status.history.deleted
                old_status = previous[0] if previous else obj.status
                if (
                    not authorization
                    or authorization[0] is not obj
                    or authorization[1:] != (old_status, obj.status)
                ):
                    raise SubstrateError("capability status and test_ref changes must use the lifecycle services")
                if obj.status == "active" and capability_activation_record(session, obj) is None:
                    raise SubstrateError("active capabilities require a passing, provenance-backed test event")
        if isinstance(obj, models.ForgeCapability):
            if is_new:
                _validate_attributes(session, "capability_type", obj.capability_type, _json_object(obj.attributes, "capability attributes"))
            elif state.attrs.attributes.history.has_changes():
                _validate_attributes(session, "capability_type", obj.capability_type, _json_object(obj.attributes, "capability attributes"))
        if isinstance(obj, models.Evidence) and obj.subject_kind is not None:
            _validate_substrate_evidence(session, obj)
