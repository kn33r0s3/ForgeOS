"""Bounded research-capability gap and candidate lifecycle on the substrate."""

from __future__ import annotations

import hashlib
import json
import re
from threading import Lock
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.services import source_clearance_registry, world_graph

MAX_CANDIDATES_PER_GAP = 3
MAX_DISCOVERY_DEPTH = 1
MAX_REQUESTS_PER_CYCLE = 0
MAX_DISCOVERY_SECONDS = 2.0
_CANDIDATE_KINDS = (
    ("structured_api", "A bounded structured API adapter"),
    ("documented_dataset", "A documented dataset adapter"),
    ("primary_observation", "A primary-source observation adapter"),
)
_COMMERCIAL_REQUIREMENTS = frozenset(
    {"customer_pain", "buyer_willingness_to_pay", "commercial_demand", "product_demand"}
)
_CAPABILITY_WRITE_LOCK = Lock()


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load(value: str | None) -> dict[str, Any]:
    parsed = json.loads(value or "{}")
    return parsed if isinstance(parsed, dict) else {}


def _key(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _insert_event_once(db: Session, event: models.WorldEvent) -> models.WorldEvent:
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
        return event
    except IntegrityError:
        winner = db.query(models.WorldEvent).filter_by(
            idempotency_key=event.idempotency_key
        ).one_or_none()
        if winner is None:
            raise
        return winner


def _discovery_data(capability: models.ForgeCapability) -> dict[str, Any]:
    attributes = _load(capability.attributes)
    value = attributes.get("capability_discovery")
    return value if isinstance(value, dict) else {}


def _persist_discovery_data(
    capability: models.ForgeCapability, data: dict[str, Any]
) -> None:
    attributes = _load(capability.attributes)
    attributes["capability_discovery"] = data
    capability.attributes = _dump(attributes)


def _upsert_capability(
    db: Session,
    *,
    name: str,
    description: str,
    spec_ref: str,
    attributes: dict[str, Any],
) -> models.ForgeCapability:
    existing = db.query(models.ForgeCapability).filter_by(name=name).one_or_none()
    if existing is not None:
        return existing
    with _CAPABILITY_WRITE_LOCK:
        world_graph.seed_core_types(db)
        try:
            with db.begin_nested():
                capability = world_graph.create_capability(
                    db,
                    capability_type="integration",
                    name=name,
                    description=description,
                    owner_agent="research_capability_discovery",
                    spec_ref=spec_ref,
                    attributes=attributes,
                )
                db.flush()
            return capability
        except IntegrityError:
            winner = db.query(models.ForgeCapability).filter_by(name=name).one_or_none()
            if winner is None:
                raise
            return winner


def _temporal_scope(text: str) -> str | None:
    year_or_range = re.search(r"\b(?:19|20)\d{2}(?:\s*[-–]\s*(?:19|20)\d{2})?\b", text)
    if year_or_range:
        return year_or_range.group()
    time_phrase = re.search(
        r"\b(?:last|past|next)\s+(?:\d+\s+)?(?:days?|weeks?|months?|years?)\b",
        text,
        re.IGNORECASE,
    )
    return time_phrase.group() if time_phrase else None


def _scope_for(question: models.ResearchQuestion, requirement: dict[str, Any]) -> dict[str, Any]:
    original = str(requirement.get("original_research_question") or question.question)
    return {
        "required_evidence_type": requirement.get(
            "required_evidence_type", requirement.get("evidence_kind")
        ),
        "geographic_scope": requirement.get("geographic_qualification"),
        "temporal_scope": _temporal_scope(
            " ".join(
                (
                    original,
                    str(requirement.get("question") or ""),
                    str(requirement.get("temporal_qualification") or ""),
                )
            )
        ),
        "population_entity_scope": requirement.get("population_qualification"),
        "unresolved_dimensions": list(requirement.get("unresolved_dimensions") or []),
    }


def ensure_capability_gap(
    db: Session,
    question: models.ResearchQuestion,
    requirement: dict[str, Any],
) -> models.ForgeCapability:
    """Persist one idempotent CAPABILITY record for an unserved requirement."""
    requirement_id = str(requirement["id"])
    identity = _key("research-capability-gap-v1", question.id, requirement_id)
    name = f"research-gap-{identity[:32]}"
    reason = (
        "direct_customer_or_transaction_evidence_required"
        if requirement_id in _COMMERCIAL_REQUIREMENTS
        else "no_active_cleared_capability"
    )
    registered_sources = source_clearance_registry.capabilities_for_requirement(requirement_id)
    searched_at = datetime.now(timezone.utc).isoformat()
    gap_data = {
        "record_kind": "research_capability_gap",
        "idempotency_key": identity,
        "research_question_id": question.id,
        "requirement_id": requirement_id,
        "required_scope": _scope_for(question, requirement),
        "why_insufficient": reason,
        "search_result": {
            "searched_at": searched_at,
            "search_method": "current exact source-clearance registry lookup",
            "registered_sources_considered": [entry.registry_id for entry in registered_sources],
            "active_cleared_sources_found": [],
            "candidate_capabilities_found": [],
            "insufficiency_reason": reason,
        },
        "candidate_discovery_status": "not_started",
        "clearance_status": "not_cleared",
        "candidate_ids": [],
        "discovery_depth": 0,
        "provenance": {
            "kind": "research_plan_requirement",
            "research_question_id": question.id,
            "original_research_question": question.question,
            "requirement_id": requirement_id,
            "need_id": requirement.get("need_id"),
        },
        "bounded_next_action": (
            "Obtain consent-based direct customer or transaction evidence."
            if reason == "direct_customer_or_transaction_evidence_required"
            else (
                "Review documented source catalogs or add a separately reviewed "
                "metadata-discovery clearance; do not collect from a candidate."
            )
        ),
    }
    capability = _upsert_capability(
        db,
        name=name,
        description=(
            f"Unresolved research capability gap for requirement {requirement_id}; "
            "this record is not evidence and does not authorize collection."
        ),
        spec_ref=f"research_question:{question.id}#requirement:{requirement_id}",
        attributes={
            "capability_discovery": gap_data,
            "logical_primitive": "CAPABILITY",
            "executable": False,
        },
    )
    if not requirement.get("capability_gap_id"):
        requirement["capability_gap_id"] = capability.id
    question_entity = world_graph.ensure_canonical_entity(
        db,
        "research_question",
        question.id,
        created_by="research_capability_discovery",
    )
    event_key = f"capability-gap-recorded:{identity}"
    need_id = requirement.get("need_id")
    need_entity = db.get(models.SubstrateEntity, need_id) if need_id is not None else None
    event_entity = (
        need_entity
        if need_entity is not None and need_entity.entity_type == "need"
        else question_entity
    )
    event = db.query(models.WorldEvent).filter_by(idempotency_key=event_key).one_or_none()
    if event is None:
        event = _insert_event_once(db, models.WorldEvent(
            event_type="capability_gap_recorded",
            entity_id=event_entity.id,
            payload=_dump(
                {
                    "capability_gap_id": capability.id,
                    "research_question_id": question.id,
                    "requirement_id": requirement_id,
                    "need_id": requirement.get("need_id"),
                    "searched_at": searched_at,
                    **gap_data["search_result"],
                }
            ),
            source="research_capability_discovery",
            idempotency_key=event_key,
        ))
    evidence_key = f"capability-gap-evidence:{identity}"
    evidence = db.query(models.Evidence).filter_by(idempotency_key=evidence_key).one_or_none()
    if evidence is None:
        evidence = world_graph.create_evidence(
            db,
            subject_kind="entity",
            subject_id=event_entity.id,
            claim=(
                f"An exact source-clearance registry search for requirement "
                f"{requirement_id} found no active cleared capability."
            ),
            support_level="possible",
            source="research_capability_discovery",
            provenance={
                "capability_gap_id": capability.id,
                "research_question_id": question.id,
                "requirement_id": requirement_id,
                "need_id": requirement.get("need_id"),
                "search_result": gap_data["search_result"],
                "event_id": event.id,
                "candidate_ids": list(gap_data.get("candidate_ids") or []),
                "claim_boundary": "This records the bounded registry search, not evidence that no capability exists in the world.",
            },
            confidence=0.25,
            idempotency_key=evidence_key,
        )
    gap_data["search_result"]["event_id"] = event.id
    gap_data["search_result"]["evidence_id"] = evidence.id
    _persist_discovery_data(capability, gap_data)
    return capability


def discover_candidates(
    db: Session,
    question: models.ResearchQuestion,
    requirement: dict[str, Any],
    *,
    max_candidates: int = MAX_CANDIDATES_PER_GAP,
    time_budget_seconds: float = MAX_DISCOVERY_SECONDS,
) -> list[models.ForgeCapability]:
    """Create bounded capability hypotheses without querying or asserting a source."""
    started = monotonic()
    gap = ensure_capability_gap(db, question, requirement)
    gap_data = _discovery_data(gap)
    if gap_data.get("record_kind") != "research_capability_gap":
        raise ValueError("capability-gap identity refers to a non-gap capability")
    if int(gap_data.get("discovery_depth", 0)) >= MAX_DISCOVERY_DEPTH:
        return [
            db.get(models.ForgeCapability, candidate_id)
            for candidate_id in gap_data.get("candidate_ids", [])
            if db.get(models.ForgeCapability, candidate_id) is not None
        ]

    candidate_limit = max(0, min(int(max_candidates), MAX_CANDIDATES_PER_GAP))
    proposals: list[models.ForgeCapability] = []
    scope = gap_data["required_scope"]
    for kind, label in _CANDIDATE_KINDS[:candidate_limit]:
        if monotonic() - started >= max(
            0.0, min(float(time_budget_seconds), MAX_DISCOVERY_SECONDS)
        ):
            break
        identity = _key(
            "research-capability-candidate-v1",
            question.id,
            requirement["id"],
            kind,
            json.dumps(scope, sort_keys=True, separators=(",", ":")),
        )
        name = f"research-candidate-{identity[:32]}"
        candidate_data = {
            "record_kind": "source_capability_candidate",
            "idempotency_key": identity,
            "candidate_kind": kind,
            "research_question_id": question.id,
            "requirement_id": requirement["id"],
            "parent_gap_id": gap.id,
            "required_scope": scope,
            "lifecycle": "candidate",
            "clearance_status": "not_cleared",
            "source_registry_id": None,
            "source_collector": None,
            "source_endpoint": None,
            "external_source_identity": None,
            "provenance": {
                "kind": "requirement_derived_capability_hypothesis",
                "parent_gap_id": gap.id,
                "research_question_id": question.id,
                "requirement_id": requirement["id"],
                "external_metadata_queried": False,
                "requests_made": 0,
            },
            "bounded_next_action": (
                "Identify an actual source and provide its provenance for review; "
                "this hypothesis is not a discovered provider or clearance."
            ),
        }
        candidate = _upsert_capability(
            db,
            name=name,
            description=(
                f"{label} may be evaluated for evidence type "
                f"{scope.get('required_evidence_type')!r}; no source is identified."
            ),
            spec_ref=f"research_capability_gap:{gap.id}#candidate:{kind}",
            attributes={
                "capability_discovery": candidate_data,
                "logical_primitive": "CAPABILITY",
                "executable": False,
            },
        )
        proposals.append(candidate)

    candidate_ids = sorted(
        {
            *gap_data.get("candidate_ids", []),
            *(candidate.id for candidate in proposals),
        }
    )
    gap_data.update(
        {
            "candidate_discovery_status": (
                "candidate_capabilities_proposed" if candidate_ids else "bounded_discovery_exhausted"
            ),
            "candidate_ids": candidate_ids[:MAX_CANDIDATES_PER_GAP],
            "discovery_depth": 1,
            "discovery_limits": {
                "max_candidates": MAX_CANDIDATES_PER_GAP,
                "max_depth": MAX_DISCOVERY_DEPTH,
                "max_requests_per_cycle": MAX_REQUESTS_PER_CYCLE,
                "requests_made": 0,
                "max_execution_seconds": MAX_DISCOVERY_SECONDS,
            },
        }
    )
    _persist_discovery_data(gap, gap_data)
    candidate_event_key = (
        f"capability-gap-candidates:{gap_data['idempotency_key']}:"
        f"{_key(*candidate_ids)}"
    )
    if candidate_ids and db.query(models.WorldEvent).filter_by(
        idempotency_key=candidate_event_key
    ).one_or_none() is None:
        question = db.get(models.ResearchQuestion, gap_data["research_question_id"])
        if question is not None:
            question_entity = world_graph.ensure_canonical_entity(
                db,
                "research_question",
                question.id,
                created_by="research_capability_discovery",
            )
            event = _insert_event_once(db, models.WorldEvent(
                event_type="capability_gap_candidates_discovered",
                entity_id=question_entity.id,
                payload=_dump(
                    {
                        "capability_gap_id": gap.id,
                        "requirement_id": requirement["id"],
                        "candidate_ids": candidate_ids,
                        "discovery_limits": gap_data.get("discovery_limits"),
                    }
                ),
                source="research_capability_discovery",
                idempotency_key=candidate_event_key,
            ))
            world_graph.create_evidence(
                db,
                subject_kind="entity",
                subject_id=question_entity.id,
                claim=(
                    f"Bounded capability hypothesis discovery produced "
                    f"{len(candidate_ids)} inactive candidate records."
                ),
                support_level="possible",
                source="research_capability_discovery",
                provenance={
                    "capability_gap_id": gap.id,
                    "requirement_id": requirement["id"],
                    "candidate_ids": candidate_ids,
                    "event_id": event.id,
                    "requests_made": 0,
                    "candidates_are_not_sources_or_evidence": True,
                },
                confidence=0.25,
                idempotency_key=f"{candidate_event_key}:evidence",
            )
    return proposals


def _find_candidate(db: Session, candidate_id: int) -> models.ForgeCapability:
    candidate = db.get(models.ForgeCapability, candidate_id)
    if candidate is None:
        raise ValueError("capability candidate does not exist")
    data = _discovery_data(candidate)
    if data.get("record_kind") != "source_capability_candidate":
        raise ValueError("capability record is not a source candidate")
    return candidate


def review_candidate(
    db: Session,
    candidate_id: int,
    *,
    source_registry_id: str,
    actor: str,
    rationale: str,
    provenance_references: list[str],
) -> models.ForgeCapability:
    """Attach a real, already-registered source candidate for explicit review."""
    candidate = _find_candidate(db, candidate_id)
    data = _discovery_data(candidate)
    if data.get("lifecycle") not in {"candidate", "reviewed"}:
        raise ValueError("candidate must be in candidate state to be reviewed")
    entry = next(
        (
            item
            for item in source_clearance_registry.source_clearances()
            if item.registry_id == source_registry_id
        ),
        None,
    )
    if entry is None:
        raise ValueError("candidate source must be present in the reviewed source registry")
    if not actor.strip() or not rationale.strip() or not provenance_references:
        raise ValueError("candidate review requires actor, rationale, and provenance references")
    if any(not isinstance(reference, str) or not reference.strip() for reference in provenance_references):
        raise ValueError("candidate provenance references must be non-empty")

    data.update(
        {
            "lifecycle": "reviewed",
            "review": {
                "actor": actor.strip(),
                "rationale": rationale.strip(),
                "provenance_references": sorted(set(provenance_references)),
            },
            "source_registry_id": entry.registry_id,
            "source_collector": entry.collector,
            "source_endpoint": entry.url,
            "external_source_identity": entry.display_name,
            "clearance_status": "not_cleared",
        }
    )
    _persist_discovery_data(candidate, data)
    db.flush()
    return candidate


def clear_candidate(
    db: Session,
    candidate_id: int,
    *,
    actor: str,
    rationale: str,
    provenance_reference: str,
) -> models.ForgeCapability:
    """Bind a reviewed proposal to a current exact registry clearance."""
    candidate = _find_candidate(db, candidate_id)
    data = _discovery_data(candidate)
    if data.get("lifecycle") != "reviewed":
        raise ValueError("candidate must be reviewed before clearance")
    if not actor.strip() or not rationale.strip() or not provenance_reference.strip():
        raise ValueError("clearance requires actor, rationale, and provenance reference")
    requirement_id = str(data["requirement_id"])
    entry = next(
        (
            item
            for item in source_clearance_registry.capabilities_for_requirement(requirement_id)
            if item.registry_id == data.get("source_registry_id")
            and item.collector == data.get("source_collector")
            and item.url == data.get("source_endpoint")
        ),
        None,
    )
    if entry is None:
        raise PermissionError("no current exact source clearance covers this requirement")
    data.update(
        {
            "lifecycle": "cleared",
            "clearance_status": "cleared",
            "clearance": {
                "actor": actor.strip(),
                "rationale": rationale.strip(),
                "provenance_reference": provenance_reference.strip(),
                "registry_id": entry.registry_id,
                "reviewed_on": entry.reviewed_on.isoformat(),
                "valid_through": entry.valid_through.isoformat(),
            },
        }
    )
    _persist_discovery_data(candidate, data)
    db.flush()
    return candidate


def activate_candidate(
    db: Session,
    candidate_id: int,
    *,
    test_ref: str,
    command: str,
    exit_code: int,
    output_excerpt: str,
) -> models.ForgeCapability:
    """Activate only a cleared candidate with a passing substrate test record."""
    candidate = _find_candidate(db, candidate_id)
    data = _discovery_data(candidate)
    if data.get("lifecycle") == "active" and candidate.status == "active":
        return candidate
    if data.get("lifecycle") != "cleared" or data.get("clearance_status") != "cleared":
        raise PermissionError("candidate must have active source clearance before activation")
    if candidate.status != "proposed":
        raise ValueError("candidate capability must still be proposed before activation")
    world_graph.begin_capability_build(db, candidate)
    world_graph.mark_capability_tested(
        db,
        candidate,
        test_ref=test_ref,
        command=command,
        exit_code=exit_code,
        output_excerpt=output_excerpt,
    )
    if candidate.status != "tested":
        raise RuntimeError("candidate capability test did not pass")
    world_graph.activate_capability(db, candidate)
    data["lifecycle"] = "active"
    data["activation"] = {
        "test_ref": candidate.test_ref,
        "clearance_registry_id": data["source_registry_id"],
    }
    _persist_discovery_data(candidate, data)
    db.flush()
    return candidate


def _managed_candidates_for(
    db: Session, requirement_id: str, registry_id: str
) -> list[models.ForgeCapability]:
    rows = db.query(models.ForgeCapability).filter_by(capability_type="integration").all()
    return [
        row
        for row in rows
        if (
            (data := _discovery_data(row)).get("record_kind") == "source_capability_candidate"
            and data.get("requirement_id") == requirement_id
            and data.get("source_registry_id") == registry_id
        )
    ]


def active_cleared_sources(
    db: Session,
    requirement_id: str,
) -> tuple[source_clearance_registry.SourceClearance, ...]:
    """Filter registry entries by activation when a candidate manages their scope."""
    entries = source_clearance_registry.capabilities_for_requirement(requirement_id)
    gap_rows = db.query(models.ForgeCapability).filter_by(
        capability_type="integration"
    ).all()
    discovered_gap = any(
        (data := _discovery_data(row)).get("record_kind") == "research_capability_gap"
        and data.get("requirement_id") == requirement_id
        and data.get("candidate_ids")
        for row in gap_rows
    )
    if discovered_gap:
        entries = tuple(
            entry
            for entry in entries
            if any(
                candidate.status == "active"
                and (data := _discovery_data(candidate)).get("lifecycle") == "active"
                and data.get("clearance_status") == "cleared"
                and data.get("source_registry_id") == entry.registry_id
                and data.get("source_endpoint") == entry.url
                and data.get("source_collector") == entry.collector
                for candidate in _managed_candidates_for(
                    db, requirement_id, entry.registry_id
                )
            )
        )
        return tuple(entries)
    usable = []
    for entry in entries:
        managed = _managed_candidates_for(db, requirement_id, entry.registry_id)
        if managed and not any(
            row.status == "active"
            and (data := _discovery_data(row)).get("lifecycle") == "active"
            and data.get("clearance_status") == "cleared"
            and data.get("source_endpoint") == entry.url
            and data.get("source_collector") == entry.collector
            for row in managed
        ):
            continue
        usable.append(entry)
    return tuple(usable)


def active_capability_id(
    db: Session, requirement_id: str, registry_id: str
) -> int | None:
    for candidate in _managed_candidates_for(db, requirement_id, registry_id):
        data = _discovery_data(candidate)
        if (
            candidate.status == "active"
            and data.get("lifecycle") == "active"
            and data.get("clearance_status") == "cleared"
        ):
            return candidate.id
    return None


def gap_candidates(db: Session, gap_id: int) -> list[models.ForgeCapability]:
    """Return persisted candidate capabilities linked to one gap."""
    gap = db.get(models.ForgeCapability, gap_id)
    if gap is None or _discovery_data(gap).get("record_kind") != "research_capability_gap":
        raise ValueError("capability gap does not exist")
    candidate_ids = _discovery_data(gap).get("candidate_ids", [])
    candidates = [db.get(models.ForgeCapability, candidate_id) for candidate_id in candidate_ids]
    return [candidate for candidate in candidates if candidate is not None]


def source_url_is_canonical(url: str) -> bool:
    """Small shared guard for any future source-candidate metadata adapter."""
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )
