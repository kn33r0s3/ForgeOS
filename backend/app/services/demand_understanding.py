"""Demand-first understanding over the existing event/evidence substrate."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.services import (
    capability_discovery,
    observer_engine,
    source_clearance_registry,
    world_graph,
)

_DEFAULT_UNRESOLVED = (
    "quantity",
    "frequency",
    "acceptable_substitute",
    "location",
    "price_tolerance",
    "delivery_window",
    "quality_requirement",
)


@dataclass(frozen=True)
class DemandUnderstanding:
    """Auditable interpretation; fields remain hypotheses, not market facts."""

    state: str
    observation_ids: tuple[int, ...]
    possible_demand: str | None
    inferred_need_id: int | None
    desired_outcome: str | None
    unresolved_questions: tuple[str, ...]
    evidence_ids: tuple[int, ...]


def _key(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode()).hexdigest()


def enqueue_understanding(
    db: Session,
    observation_ids: Iterable[int],
    *,
    desired_outcome: str | None = None,
    object_description: str | None = None,
    unresolved_questions: Iterable[str] | None = None,
    sufficient: bool = False,
    priority: int = 0,
) -> models.WorkerTask:
    """Queue one deterministic, bounded demand-understanding worker task."""
    ids = tuple(sorted({int(value) for value in observation_ids}))
    if not ids:
        raise ValueError("at least one observation is required")
    questions = tuple(unresolved_questions or ())
    identity = _key(
        "demand-understanding-v1",
        *ids,
        desired_outcome or "",
        object_description or "",
        *questions,
        sufficient,
    )
    existing = db.query(models.WorkerTask).filter_by(idempotency_key=identity).one_or_none()
    if existing is not None:
        return existing
    task = models.WorkerTask(
        worker_type="demand_understanding",
        task_name="understand_demand",
        idempotency_key=identity,
        priority=max(-100, min(int(priority), 100)),
        inputs={
            "observation_ids": list(ids),
            "desired_outcome": desired_outcome,
            "object_description": object_description,
            "unresolved_questions": list(questions),
            "sufficient": bool(sufficient),
        },
        max_attempts=2,
    )
    try:
        with db.begin_nested():
            db.add(task)
            db.flush()
        db.commit()
        db.refresh(task)
        return task
    except IntegrityError:
        winner = (
            db.query(models.WorkerTask)
            .filter_by(idempotency_key=identity)
            .one_or_none()
        )
        if winner is None:
            raise
        return winner


def process_understanding_task(db: Session, task: models.WorkerTask) -> dict[str, Any]:
    """Execute only demand interpretation; it never performs an external action."""
    inputs = task.inputs or {}
    result = understand(
        db,
        inputs.get("observation_ids") or (),
        desired_outcome=inputs.get("desired_outcome"),
        object_description=inputs.get("object_description"),
        unresolved_questions=inputs.get("unresolved_questions"),
        sufficient=bool(inputs.get("sufficient")),
    )
    return {
        "state": result.state,
        "observation_ids": list(result.observation_ids),
        "need_id": result.inferred_need_id,
        "evidence_ids": list(result.evidence_ids),
        "unresolved_questions": list(result.unresolved_questions),
        "external_action": False,
    }


def _event(
    db: Session,
    *,
    event_type: str,
    entity_id: int,
    payload: dict[str, Any],
    key: str,
) -> models.WorldEvent:
    existing = db.query(models.WorldEvent).filter_by(idempotency_key=key).one_or_none()
    if existing is not None:
        return existing
    event = models.WorldEvent(
        event_type=event_type,
        entity_id=entity_id,
        payload=json.dumps(payload, sort_keys=True),
        source="demand_understanding",
        idempotency_key=key,
    )
    db.add(event)
    db.flush()
    return event


def record_raw_observation(
    db: Session,
    content: str,
    *,
    source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> models.Signal:
    """Persist an uncategorized observation before any need classification."""
    safe_content = _normalize_observation_content(content)
    safe_metadata = _minimize_metadata(metadata or {})
    signal = observer_engine.ObserverEngine(db).observe(
        safe_content,
        source=source,
        metadata=safe_metadata,
        persist_evidence=False,
    )
    world_graph.seed_core_types(db)
    signal_entity = world_graph.ensure_canonical_entity(
        db,
        "signal",
        signal.id,
        created_by="demand_understanding",
        source_system="signals",
    )
    _event(
        db,
        event_type="demand_observed",
        entity_id=signal_entity.id,
        payload={
            "signal_id": signal.id,
            "normalized_observation": signal.content,
            "source": signal.source,
            "provenance": safe_metadata,
        },
        key=f"demand-observed:{signal.id}:v1",
    )
    evidence_key = f"demand-observation-evidence:{signal.id}:v1"
    if db.query(models.Evidence).filter_by(idempotency_key=evidence_key).one_or_none() is None:
        world_graph.create_evidence(
            db,
            subject_kind="entity",
            subject_id=signal_entity.id,
            claim="The raw demand-shaped observation was recorded.",
            support_level="possible",
            source=source,
            provenance={
                "signal_id": signal.id,
                "source": source,
                "metadata": safe_metadata,
                "observation_timestamp": signal.retrieved_at.isoformat()
                if signal.retrieved_at
                else None,
            },
            confidence=0.25,
            idempotency_key=evidence_key,
        )
    db.commit()
    return signal


def record_authorized_source_observation(
    db: Session,
    content: str,
    *,
    authorization: source_clearance_registry.CollectionAuthorization,
    source_reference: str,
    observation_field: str,
    source_timestamp: datetime | None,
    observation_identity: str,
    metadata: dict[str, Any] | None = None,
) -> models.Signal:
    """Persist an adapter result only under a current exact source clearance.

    This function records data already returned by an authorized adapter; it
    does not fetch URLs or treat public visibility as permission.
    """
    if not isinstance(authorization, source_clearance_registry.CollectionAuthorization):
        raise PermissionError("source collection authorization is required")
    entry = source_clearance_registry.validate_authorization(
        authorization,
        url=source_reference,
        collector=authorization.entry.collector,
    )
    gate = db.get(models.SourceFetchGate, entry.registry_id)
    if gate is None:
        raise PermissionError("persistent source clearance reservation is missing")
    reserved_at = authorization.reserved_at
    stored_at = gate.last_reserved_at
    if stored_at.tzinfo is None:
        stored_at = stored_at.replace(tzinfo=timezone.utc)
    if reserved_at.tzinfo is None:
        reserved_at = reserved_at.replace(tzinfo=timezone.utc)
    if stored_at != reserved_at:
        raise PermissionError("source authorization reservation is stale or superseded")
    if not observation_identity.strip():
        raise ValueError("a stable source observation identity is required")
    if observation_field not in entry.allowed_fields:
        raise PermissionError("source field is not covered by the exact clearance")
    if source_timestamp is not None and source_timestamp.tzinfo is None:
        source_timestamp = source_timestamp.replace(tzinfo=timezone.utc)
    normalized_metadata = _minimize_metadata(metadata or {})
    normalized_metadata.update(
        {
            "canonical_url": entry.url,
            "external_id": _key("source-observation-id-v1", entry.registry_id, observation_identity.strip()),
            "source_type": "external",
            "source_timestamp": source_timestamp.isoformat() if source_timestamp else None,
            "published_at": source_timestamp.isoformat() if source_timestamp else None,
            "retrieved_at": authorization.reserved_at.isoformat(),
            "identity_key": _key(
                "authorized-observation-v1",
                entry.registry_id,
                observation_identity.strip(),
                source_timestamp.isoformat() if source_timestamp else "",
                _key(_normalize_observation_content(content)),
            ),
            "collection_status": "authorized_observed",
            "provenance": {
                **(normalized_metadata.get("provenance") or {}),
                "source_registry_id": entry.registry_id,
                "source_identity": entry.display_name,
                "source_type": entry.collector,
                "source_reference": source_reference,
                "observation_field": observation_field,
                "source_timestamp": source_timestamp.isoformat() if source_timestamp else None,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "authorization_reserved_at": authorization.reserved_at.isoformat(),
                "allowed_operation": entry.allowed_operation,
                "license_tag": entry.license_tag,
            },
        }
    )
    return record_raw_observation(
        db,
        content,
        source=entry.collector,
        metadata=normalized_metadata,
    )


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")


def _normalize_observation_content(content: str) -> str:
    normalized = " ".join((content or "").split())
    normalized = _EMAIL.sub("[redacted-email]", normalized)
    return _PHONE.sub("[redacted-phone]", normalized)


def _minimize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "canonical_url",
        "external_id",
        "identity_key",
        "title",
        "published_at",
        "timestamp",
        "retrieved_at",
        "source_type",
        "collection_status",
        "provenance",
        "source_timestamp",
    }
    result = {
        key: _redact_metadata_value(value)
        for key, value in metadata.items()
        if key in allowed
    }
    for key in ("external_id", "identity_key"):
        if result.get(key):
            result[key] = _key("observation-identity-v1", result[key])
    title = result.get("title")
    if isinstance(title, str):
        result["title"] = _normalize_observation_content(title)[:500]
    return result


def _redact_metadata_value(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_observation_content(value)
    if isinstance(value, list):
        return [_redact_metadata_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _redact_metadata_value(item)
            for key, item in value.items()
            if not re.search(r"email|phone|address|recipient|person_name", str(key), re.I)
        }
    return value


def understand(
    db: Session,
    observation_ids: Iterable[int],
    *,
    desired_outcome: str | None = None,
    object_description: str | None = None,
    unresolved_questions: Iterable[str] | None = None,
    sufficient: bool = False,
) -> DemandUnderstanding:
    """Interpret one or more observations without inventing actors or economics."""
    ids = tuple(sorted({int(value) for value in observation_ids}))
    if not ids:
        raise ValueError("at least one observation is required")
    signals = db.query(models.Signal).filter(models.Signal.id.in_(ids)).all()
    by_id = {row.id: row for row in signals}
    if len(by_id) != len(ids):
        raise ValueError("all observations must exist")
    world_graph.seed_core_types(db)
    signal_entities = [
        world_graph.ensure_canonical_entity(
            db, "signal", signal_id, created_by="demand_understanding", source_system="signals"
        )
        for signal_id in ids
    ]
    object_text = (object_description or "").strip() or None
    outcome_text = (desired_outcome or "").strip() or None
    questions = tuple(
        dict.fromkeys(
            question.strip()
            for question in (
                unresolved_questions
                if unresolved_questions is not None
                else _DEFAULT_UNRESOLVED
            )
            if question and question.strip()
        )
    )
    if not object_text:
        state = "possible_demand"
        possible = "The observations may indicate an unmet requirement."
        return _persist_interpretation(
            db, ids, signal_entities, state, possible, None, outcome_text, questions
        )
    state = "hypothesized"
    possible = f"Possible demand for {object_text}."
    if len(ids) >= 2:
        possible = f"Repeated observations indicate possible recurring demand for {object_text}."
    need_id = None
    remaining = () if sufficient else questions
    if sufficient and outcome_text and not remaining:
        need = _ensure_need(
            db,
            ids,
            signal_entities,
            object_text=object_text,
            outcome_text=outcome_text,
            questions=remaining,
        )
        need_id = need.id
        state = "sufficiently_understood_need"
    return _persist_interpretation(
        db, ids, signal_entities, state, possible, need_id, outcome_text, remaining
    )


def _persist_interpretation(
    db: Session,
    ids: tuple[int, ...],
    signal_entities: list[models.SubstrateEntity],
    state: str,
    possible: str,
    need_id: int | None,
    outcome: str | None,
    questions: tuple[str, ...],
) -> DemandUnderstanding:
    evidence_ids: list[int] = []
    support = "hypothesized" if len(ids) >= 2 else "possible"
    for entity in signal_entities:
        key = f"demand-interpretation:{entity.id}:{_key(state, possible, need_id)}"
        existing = db.query(models.Evidence).filter_by(idempotency_key=key).one_or_none()
        evidence = existing or world_graph.create_evidence(
            db,
            subject_kind="entity",
            subject_id=entity.id,
            claim=possible,
            support_level=support,
            source="demand_understanding",
            provenance={"signal_id": entity.source_id, "interpretation": state},
            confidence=0.4 if support == "hypothesized" else 0.2,
            idempotency_key=key,
        )
        evidence_ids.append(evidence.id)
    if need_id is not None:
        _event(
            db,
            event_type="demand_understood",
            entity_id=need_id,
            payload={
                "need_id": need_id,
                "observation_ids": list(ids),
                "unresolved_questions": list(questions),
            },
            key=f"demand-understood:{need_id}:v1",
        )
    db.commit()
    return DemandUnderstanding(
        state=state,
        observation_ids=ids,
        possible_demand=possible,
        inferred_need_id=need_id,
        desired_outcome=outcome,
        unresolved_questions=questions,
        evidence_ids=tuple(evidence_ids),
    )


def _ensure_need(
    db: Session,
    ids: tuple[int, ...],
    signal_entities: list[models.SubstrateEntity],
    *,
    object_text: str,
    outcome_text: str,
    questions: tuple[str, ...],
) -> models.SubstrateEntity:
    identity = f"demand-need:{_key(object_text.casefold(), outcome_text.casefold(), *ids)}"
    existing = db.query(models.SubstrateEntity).filter_by(identity_key=identity).one_or_none()
    if existing is not None:
        return existing
    need = world_graph.create_entity(
        db,
        entity_type="need",
        display_name=f"Need: {object_text}"[:240],
        attributes={
            "object": object_text,
            "desired_outcome": outcome_text,
            "epistemic_state": "hypothesized",
            "observation_ids": list(ids),
            "unresolved_questions": list(questions),
            "category": None,
        },
        created_by="demand_understanding",
        identity={
            "source_system": "demand_understanding",
            "source_id": identity,
            "provenance": {"observation_ids": list(ids), "synthetic_fixture": False},
        },
    )
    for entity in signal_entities:
        world_graph.create_relation(
            db,
            from_entity_id=need.id,
            to_entity_id=entity.id,
            relation_type="derived_from",
            attributes={"observation_id": int(entity.source_id)},
            direction="directed",
            truth_state="hypothesized",
            created_by="demand_understanding",
            idempotency_key=f"need-observation:{need.id}:{entity.id}:v1",
        )
    db.flush()
    return need


def search_existing_capabilities(
    db: Session,
    understanding: DemandUnderstanding,
    *,
    requirement_id: str,
    required_evidence_type: str,
    geographic_scope: str | None = None,
    population_scope: str | None = None,
) -> dict[str, Any]:
    """Search existing authorized capabilities, then record a bounded gap if none fit."""
    if understanding.inferred_need_id is None:
        raise ValueError("capability search requires a sufficiently understood need")
    requirement = {
        "id": requirement_id,
        "question": understanding.desired_outcome or "What outcome satisfies this need?",
        "original_research_question": understanding.possible_demand,
        "required_evidence_type": required_evidence_type,
        "geographic_qualification": geographic_scope,
        "population_qualification": population_scope,
        "unresolved_dimensions": list(understanding.unresolved_questions),
        "need_id": understanding.inferred_need_id,
    }
    sources = capability_discovery.active_cleared_sources(db, requirement_id)
    _event(
        db,
        event_type="capability_search_performed",
        entity_id=understanding.inferred_need_id,
        payload={
            "requirement_id": requirement_id,
            "sources": [entry.registry_id for entry in sources],
            "need_id": understanding.inferred_need_id,
        },
        key=f"capability-search:{understanding.inferred_need_id}:{requirement_id}:v1",
    )
    need_entity = db.get(models.SubstrateEntity, understanding.inferred_need_id)
    if need_entity is None or need_entity.entity_type != "need":
        raise ValueError("sufficiently understood need entity is unavailable")
    search_key = (
        f"need-capability-search-evidence:{understanding.inferred_need_id}:"
        f"{_key(requirement_id, *(entry.registry_id for entry in sources))}"
    )
    if db.query(models.Evidence).filter_by(idempotency_key=search_key).one_or_none() is None:
        world_graph.create_evidence(
            db,
            subject_kind="entity",
            subject_id=need_entity.id,
            claim=(
                f"Capability search for this need identified {len(sources)} "
                "currently cleared matching capability record(s)."
            ),
            support_level="possible",
            source="demand_understanding",
            provenance={
                "need_id": need_entity.id,
                "requirement_id": requirement_id,
                "source_registry_ids": [entry.registry_id for entry in sources],
                "event_idempotency_key": (
                    f"capability-search:{understanding.inferred_need_id}:{requirement_id}:v1"
                ),
                "claim_boundary": "A cleared capability match is not proof of fit, availability, or fulfillment.",
            },
            confidence=0.25,
            idempotency_key=search_key,
        )
    gap = None
    if not sources:
        gap = capability_discovery.ensure_capability_gap(db, _question_for_need(db, understanding), requirement)
    db.commit()
    return {
        "need_id": understanding.inferred_need_id,
        "matched_sources": tuple(entry.registry_id for entry in sources),
        "capability_gap_id": gap.id if gap is not None else None,
        "research_eligible": gap is not None,
    }


def _question_for_need(db: Session, understanding: DemandUnderstanding) -> models.ResearchQuestion:
    text = f"Understand demand: {understanding.possible_demand}"
    existing = db.query(models.ResearchQuestion).filter_by(question=text).one_or_none()
    if existing is not None:
        return existing
    question = models.ResearchQuestion(question=text, status="open")
    db.add(question)
    db.flush()
    return question
