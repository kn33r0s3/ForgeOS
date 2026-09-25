"""Incremental canonical view of existing legacy Evidence rows.

Evidence remains the raw record and source of truth during migration. This
adapter maps the same row to an existing canonical subject and records only
substrate-specific references/digests; it never copies or rewrites raw content,
provenance, direction, source, or historic confidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import world_graph


def sync_legacy_evidence(db: Session, *, limit: int = 500) -> dict[str, int]:
    """Map a bounded batch of unprojected evidence rows without creating rows."""
    world_graph.seed_core_types(db)
    result = {
        "records_seen": 0,
        "records_mapped": 0,
        "entities_created": 0,
        "unresolved_records": 0,
        "events_created": 0,
    }
    rows = (
        db.query(models.Evidence)
        .filter(models.Evidence.subject_kind.is_(None))
        .order_by(models.Evidence.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    entity_cache: dict[tuple[str, int], models.SubstrateEntity] = {}

    for evidence in rows:
        result["records_seen"] += 1
        target = _resolve_legacy_target(evidence)
        if target is None:
            result["unresolved_records"] += 1
            continue
        entity_type, source_id = target
        source_model = world_graph.CANONICAL_ADAPTERS.get(entity_type)
        if source_model is None:
            result["unresolved_records"] += 1
            continue

        cache_key = (entity_type, source_id)
        entity = entity_cache.get(cache_key)
        if entity is None:
            existing = world_graph.find_canonical_entity(db, entity_type, source_id)
            try:
                entity = world_graph.ensure_canonical_entity(
                    db,
                    entity_type,
                    source_id,
                    created_by="legacy_evidence_substrate_adapter",
                )
            except world_graph.SubstrateError:
                result["unresolved_records"] += 1
                continue
            entity_cache[cache_key] = entity
            result["entities_created"] += int(existing is None)

        signal = db.get(models.Signal, evidence.signal_id) if evidence.signal_id else None
        effective_source = (evidence.source or "").strip() or (signal.source if signal else "").strip()
        raw_content = (evidence.content or "").strip()
        if not effective_source or not raw_content:
            result["unresolved_records"] += 1
            continue

        snapshot_digest = _raw_digest(evidence)
        substrate_provenance = {
            "adapter": "legacy_evidence_substrate_adapter",
            "schema": "legacy-evidence-substrate-v1",
            "source_ref": {"table": "evidence", "id": evidence.id},
            "subject_ref": {
                "entity_type": entity_type,
                "source_id": source_id,
                "substrate_entity_id": entity.id,
            },
            "signal_ref": {"table": "signals", "id": evidence.signal_id}
            if evidence.signal_id is not None else None,
            "raw_record_sha256": snapshot_digest,
            "legacy_provenance_sha256": _sha256(evidence.provenance or ""),
            "raw_confidence_scale": "legacy_0_to_100",
        }
        was_unmapped = evidence.subject_kind is None
        world_graph.attach_legacy_evidence(
            db,
            evidence,
            subject_id=entity.id,
            source=effective_source,
            substrate_provenance=substrate_provenance,
            recorded_at=evidence.created_at or evidence.retrieved_at or models.utcnow(),
        )
        result["records_mapped"] += int(was_unmapped)

    db.flush()
    return result


def _resolve_legacy_target(evidence: models.Evidence) -> tuple[str, int] | None:
    """Resolve only one explicit FK; ambiguous multi-target rows stay unresolved."""
    explicit = [
        ("belief", evidence.belief_id),
        ("scenario_prediction", evidence.scenario_prediction_id),
        ("opportunity", evidence.opportunity_id),
    ]
    linked = [(kind, int(source_id)) for kind, source_id in explicit if source_id is not None]
    if len(linked) > 1:
        return None
    if linked:
        return linked[0]
    if evidence.signal_id is not None:
        return "signal", int(evidence.signal_id)
    return None


def _raw_digest(evidence: models.Evidence) -> str:
    raw: dict[str, Any] = {
        "id": evidence.id,
        "belief_id": evidence.belief_id,
        "scenario_prediction_id": evidence.scenario_prediction_id,
        "opportunity_id": evidence.opportunity_id,
        "signal_id": evidence.signal_id,
        "source": evidence.source,
        "content": evidence.content,
        "direction": evidence.direction,
        "confidence": evidence.confidence,
        "provenance": evidence.provenance,
        "provenance_hash": evidence.provenance_hash,
        "canonical_url": evidence.canonical_url,
        "external_id": evidence.external_id,
        "title": evidence.title,
        "published_at": evidence.published_at,
        "retrieved_at": evidence.retrieved_at,
        "created_at": evidence.created_at,
        "content_fingerprint": evidence.content_fingerprint,
        "collection_status": evidence.collection_status,
    }
    encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256(encoded)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
