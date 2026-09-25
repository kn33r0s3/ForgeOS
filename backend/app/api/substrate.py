"""Transport endpoints for the canonical Universal Substrate services."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services import type_validation, world_graph

router = APIRouter(prefix="/forge/substrate", tags=["substrate"])


class TypeCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: Literal["entity_type", "relation_type", "event_type", "capability_type"]
    type_name: str = Field(min_length=1, max_length=80)
    schema_data: dict[str, Any] = Field(alias="schema")
    owner_agent: str = Field(min_length=1, max_length=160)
    description: str | None = None


class TypeStatusChange(BaseModel):
    status: Literal["active", "deprecated"]
    actor: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=2000)
    evidence_ref: str = Field(min_length=1, max_length=500)


class EntityCreate(BaseModel):
    entity_type: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=240)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(min_length=1, max_length=160)
    identity: dict[str, Any] | None = None


class IdentityChange(BaseModel):
    next_state: Literal["corroborated", "canonical"]
    actor: str = Field(min_length=1, max_length=160)
    evidence_id: int = Field(gt=0)
    rationale: str = Field(min_length=1, max_length=2000)


class EntityMerge(BaseModel):
    survivor_entity_id: int = Field(gt=0)
    actor: str = Field(min_length=1, max_length=160)
    evidence_id: int = Field(gt=0)
    rationale: str = Field(min_length=1, max_length=2000)


class EntityArchive(BaseModel):
    actor: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=2000)


class RelationCreate(BaseModel):
    from_entity_id: int = Field(gt=0)
    to_entity_id: int = Field(gt=0)
    relation_type: str = Field(min_length=1, max_length=80)
    attributes: dict[str, Any] = Field(default_factory=dict)
    direction: Literal["directed", "bidirectional"] = "directed"
    strength: float | None = Field(default=None, ge=0, le=1)
    truth_state: Literal["possible", "hypothesized"] = "hypothesized"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_by: str = Field(min_length=1, max_length=160)
    idempotency_key: str | None = Field(default=None, max_length=240)


class RelationTruthChange(BaseModel):
    next_state: Literal["possible", "hypothesized", "tested", "supported", "refuted", "unknown"]


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=240)
    payload: dict[str, Any] = Field(default_factory=dict)
    entity_id: int | None = Field(default=None, gt=0)
    relation_id: int | None = Field(default=None, gt=0)
    occurred_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=240)


class EvidenceCreate(BaseModel):
    subject_kind: Literal["entity", "relation"]
    subject_id: int = Field(gt=0)
    claim: str = Field(min_length=1, max_length=4000)
    support_level: Literal["possible", "hypothesized", "tested", "supported", "refuted", "unknown"]
    source: str = Field(min_length=1, max_length=240)
    provenance: dict[str, Any] | str
    confidence: float | None = Field(default=None, ge=0, le=1)
    idempotency_key: str | None = Field(default=None, max_length=240)


class CapabilityCreate(BaseModel):
    capability_type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    owner_agent: str = Field(min_length=1, max_length=160)
    spec_ref: str | None = Field(default=None, max_length=500)
    attributes: dict[str, Any] = Field(default_factory=dict)


class CapabilityTest(BaseModel):
    test_ref: str = Field(min_length=1, max_length=500)
    command: str = Field(min_length=1, max_length=1000)
    exit_code: int
    output_excerpt: str = Field(default="", max_length=2000)


def _json_value(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def _object(raw: str | None) -> dict[str, Any]:
    value = _json_value(raw or "{}")
    return value if isinstance(value, dict) else {}


def _type_out(row: models.TypeRegistry) -> dict[str, Any]:
    return {
        "id": row.id,
        "category": row.category,
        "type_name": row.type_name,
        "schema": _object(row.schema_json),
        "description": row.description,
        "owner_agent": row.owner_agent,
        "status": row.status,
        "status_evidence": _json_value(row.status_evidence) or [],
        "created_at": row.created_at,
    }


def _entity_out(row: models.SubstrateEntity) -> dict[str, Any]:
    return {
        "id": row.id,
        "entity_type": row.entity_type,
        "display_name": row.display_name,
        "attributes": _object(row.attributes),
        "identity_key": row.identity_key,
        "source_system": row.source_system,
        "source_id": row.source_id,
        "canonical_identifier": row.canonical_identifier,
        "normalized_identity": row.normalized_identity,
        "identity_state": row.identity_state,
        "identity_uncertainty": row.identity_uncertainty,
        "identity_provenance": _object(row.identity_provenance),
        "merged_into_id": row.merged_into_id,
        "status": row.status,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _relation_out(row: models.WorldRelation) -> dict[str, Any]:
    return {
        "id": row.id,
        "from_entity_id": row.from_entity_id,
        "to_entity_id": row.to_entity_id,
        "relation_type": row.relation_type,
        "attributes": _object(row.attributes),
        "direction": row.direction,
        "strength": row.strength,
        "truth_state": row.truth_state,
        "idempotency_key": row.idempotency_key,
        "valid_from": row.valid_from,
        "valid_to": row.valid_to,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


def _event_out(row: models.WorldEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_type": row.event_type,
        "entity_id": row.entity_id,
        "relation_id": row.relation_id,
        "payload": _object(row.payload),
        "source": row.source,
        "idempotency_key": row.idempotency_key,
        "occurred_at": row.occurred_at,
    }


def _evidence_out(row: models.Evidence) -> dict[str, Any]:
    return {
        "id": row.id,
        "subject_kind": row.subject_kind,
        "subject_id": row.subject_id,
        "claim": row.claim,
        "support_level": row.support_level,
        "confidence": row.substrate_confidence if row.substrate_confidence is not None else (
            row.confidence if row.subject_kind is not None and row.substrate_provenance is None else None
        ),
        "source": row.substrate_source or row.source,
        "provenance": _json_value(row.substrate_provenance or row.provenance),
        "legacy_ref": {"table": "evidence", "id": row.id},
        "idempotency_key": row.idempotency_key,
        "recorded_at": row.recorded_at,
    }


def _capability_out(row: models.ForgeCapability) -> dict[str, Any]:
    return {
        "id": row.id,
        "capability_type": row.capability_type,
        "name": row.name,
        "description": row.description,
        "status": row.status,
        "spec_ref": row.spec_ref,
        "test_ref": row.test_ref,
        "attributes": _object(row.attributes),
        "owner_agent": row.owner_agent,
        "created_at": row.created_at,
    }


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _write_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntegrityError):
        return HTTPException(status_code=409, detail="substrate uniqueness or idempotency conflict")
    message = str(exc)
    status = 409 if "collision" in message or "already exists" in message else 422
    return HTTPException(status_code=status, detail=message)


@router.get("/types")
def list_types(
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.TypeRegistry)
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    return [_type_out(row) for row in query.order_by(models.TypeRegistry.category, models.TypeRegistry.type_name).all()]


@router.post("/types", status_code=201)
def propose_type(body: TypeCreate, db: Session = Depends(get_db)):
    try:
        row = world_graph.register_type(
            db,
            category=body.category,
            type_name=body.type_name,
            schema=body.schema_data,
            owner_agent=body.owner_agent,
            description=body.description,
        )
        db.commit()
        return _type_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/types/{category}/{type_name}/status")
def change_type_status(category: str, type_name: str, body: TypeStatusChange, db: Session = Depends(get_db)):
    row = db.query(models.TypeRegistry).filter_by(category=category, type_name=type_name).one_or_none()
    if row is None:
        raise _not_found("type not found")
    try:
        world_graph.set_type_status(
            db, row, body.status, actor=body.actor,
            rationale=body.rationale, evidence_ref=body.evidence_ref,
        )
        db.commit()
        return _type_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.get("/entities")
def list_entities(
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.SubstrateEntity)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if status:
        query = query.filter_by(status=status)
    return [_entity_out(row) for row in query.order_by(models.SubstrateEntity.id.desc()).limit(limit).all()]


@router.get("/entities/{entity_id}")
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    row = db.get(models.SubstrateEntity, entity_id)
    if row is None:
        raise _not_found("entity not found")
    return _entity_out(row)


@router.post("/entities", status_code=201)
def add_entity(body: EntityCreate, db: Session = Depends(get_db)):
    try:
        row = world_graph.create_entity(
            db,
            entity_type=body.entity_type,
            display_name=body.display_name,
            attributes=body.attributes,
            created_by=body.created_by,
            identity=body.identity,
        )
        db.commit()
        return _entity_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/entities/{entity_id}/identity")
def change_entity_identity(entity_id: int, body: IdentityChange, db: Session = Depends(get_db)):
    entity = db.get(models.SubstrateEntity, entity_id)
    if entity is None:
        raise _not_found("entity not found")
    try:
        world_graph.transition_entity_identity(
            db, entity, body.next_state, actor=body.actor,
            evidence_id=body.evidence_id, rationale=body.rationale,
        )
        db.commit()
        return _entity_out(entity)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/entities/{entity_id}/merge")
def merge_entity(entity_id: int, body: EntityMerge, db: Session = Depends(get_db)):
    duplicate = db.get(models.SubstrateEntity, entity_id)
    survivor = db.get(models.SubstrateEntity, body.survivor_entity_id)
    if duplicate is None or survivor is None:
        raise _not_found("merge entity not found")
    try:
        row = world_graph.merge_entities(
            db, survivor, duplicate, actor=body.actor,
            rationale=body.rationale, evidence_id=body.evidence_id,
        )
        db.commit()
        return _entity_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/entities/{entity_id}/archive")
def archive_entity(entity_id: int, body: EntityArchive, db: Session = Depends(get_db)):
    row = db.get(models.SubstrateEntity, entity_id)
    if row is None:
        raise _not_found("entity not found")
    try:
        world_graph.archive_entity(db, row, actor=body.actor, rationale=body.rationale)
        db.commit()
        return _entity_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.get("/relations")
def list_relations(
    relation_type: str | None = Query(default=None),
    from_entity_id: int | None = Query(default=None, gt=0),
    to_entity_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.WorldRelation)
    if relation_type:
        query = query.filter_by(relation_type=relation_type)
    if from_entity_id:
        query = query.filter_by(from_entity_id=from_entity_id)
    if to_entity_id:
        query = query.filter_by(to_entity_id=to_entity_id)
    return [_relation_out(row) for row in query.order_by(models.WorldRelation.id.desc()).limit(limit).all()]


@router.post("/relations", status_code=201)
def add_relation(body: RelationCreate, db: Session = Depends(get_db)):
    try:
        row = world_graph.create_relation(db, **body.model_dump())
        db.commit()
        return _relation_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/relations/{relation_id}/truth")
def change_relation_truth(relation_id: int, body: RelationTruthChange, db: Session = Depends(get_db)):
    row = db.get(models.WorldRelation, relation_id)
    if row is None:
        raise _not_found("relation not found")
    try:
        world_graph.transition_relation_truth_state(db, row, body.next_state)
        db.commit()
        return _relation_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.get("/events")
def list_events(
    event_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None, gt=0),
    relation_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.WorldEvent)
    if event_type:
        query = query.filter_by(event_type=event_type)
    if entity_id:
        query = query.filter_by(entity_id=entity_id)
    if relation_id:
        query = query.filter_by(relation_id=relation_id)
    return [_event_out(row) for row in query.order_by(models.WorldEvent.id.desc()).limit(limit).all()]


@router.post("/events", status_code=201)
def add_event(body: EventCreate, db: Session = Depends(get_db)):
    try:
        row = world_graph.create_event(db, **body.model_dump())
        db.commit()
        return _event_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.get("/evidence")
def list_evidence(
    subject_kind: Literal["entity", "relation"] | None = Query(default=None),
    subject_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.Evidence).filter(models.Evidence.subject_kind.isnot(None))
    if subject_kind:
        query = query.filter_by(subject_kind=subject_kind)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    return [_evidence_out(row) for row in query.order_by(models.Evidence.id.desc()).limit(limit).all()]


@router.post("/evidence", status_code=201)
def add_evidence(body: EvidenceCreate, db: Session = Depends(get_db)):
    try:
        row = world_graph.create_evidence(db, **body.model_dump())
        db.commit()
        return _evidence_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.get("/capabilities")
def list_capabilities(
    status: str | None = Query(default=None),
    capability_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.ForgeCapability)
    if status:
        query = query.filter_by(status=status)
    if capability_type:
        query = query.filter_by(capability_type=capability_type)
    return [_capability_out(row) for row in query.order_by(models.ForgeCapability.id.desc()).limit(limit).all()]


@router.post("/capabilities", status_code=201)
def add_capability(body: CapabilityCreate, db: Session = Depends(get_db)):
    existing = db.query(models.ForgeCapability).filter_by(name=body.name.strip()).one_or_none()
    if existing is not None:
        expected = (
            existing.capability_type, existing.name, existing.description,
            existing.owner_agent, existing.spec_ref, _object(existing.attributes),
        )
        received = (
            body.capability_type, body.name.strip(), body.description.strip(),
            body.owner_agent.strip(), body.spec_ref, body.attributes,
        )
        if expected == received:
            return _capability_out(existing)
        raise HTTPException(status_code=409, detail="capability name already exists with different attributes")
    try:
        row = world_graph.create_capability(db, **body.model_dump())
        db.commit()
        return _capability_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/capabilities/{capability_id}/build")
def begin_capability_build(capability_id: int, db: Session = Depends(get_db)):
    row = db.get(models.ForgeCapability, capability_id)
    if row is None:
        raise _not_found("capability not found")
    try:
        world_graph.begin_capability_build(db, row)
        db.commit()
        return _capability_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/capabilities/{capability_id}/test")
def test_capability(capability_id: int, body: CapabilityTest, db: Session = Depends(get_db)):
    row = db.get(models.ForgeCapability, capability_id)
    if row is None:
        raise _not_found("capability not found")
    try:
        world_graph.mark_capability_tested(db, row, **body.model_dump())
        db.commit()
        return _capability_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc


@router.post("/capabilities/{capability_id}/activate")
def activate_capability(capability_id: int, db: Session = Depends(get_db)):
    row = db.get(models.ForgeCapability, capability_id)
    if row is None:
        raise _not_found("capability not found")
    try:
        world_graph.activate_capability(db, row)
        db.commit()
        return _capability_out(row)
    except (type_validation.SubstrateError, IntegrityError) as exc:
        db.rollback()
        raise _write_error(exc) from exc
