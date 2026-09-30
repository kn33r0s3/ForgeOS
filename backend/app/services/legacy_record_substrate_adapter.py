"""Source-linked wrappers for remaining mature Forge records.

These legacy tables remain authoritative. The adapter only creates minimal
canonical entities and digest-only audit events; it does not copy source text
or infer relations from names or similar content.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import world_graph


_RECORD_TYPES: tuple[tuple[str, type], ...] = (
    ("claim", models.Claim),
    ("research_question", models.ResearchQuestion),
    ("domain_record", models.DomainRecord),
    ("decision", models.Decision),
)


def _safe_source_fields(entity_type: str, row: Any) -> dict[str, Any]:
    """Select lifecycle/link metadata only; raw statements and private notes stay in source tables."""
    if entity_type == "claim":
        return {
            "epistemic_state": row.epistemic_state,
            "opportunity_id": row.opportunity_id,
            "decision_id": row.decision_id,
            "experiment_id": row.experiment_id,
            "outcome_id": row.outcome_id,
            "updated_at": row.updated_at,
        }
    if entity_type == "research_question":
        return {
            "status": row.status,
            "source_pattern_id": row.source_pattern_id,
            "source_belief_id": row.source_belief_id,
            "source_claim_id": row.source_claim_id,
            "source_rare_signal_id": row.source_rare_signal_id,
            "created_at": row.created_at,
        }
    if entity_type == "domain_record":
        return {
            "kind": row.kind,
            "status": row.status,
            "city": row.city,
            "close_result": row.close_result,
            "updated_at": row.updated_at,
            "closed_at": row.closed_at,
        }
    return {
        "status": row.status,
        "goal_id": row.goal_id,
        "opportunity_id": row.opportunity_id,
        "strategy_id": row.strategy_id,
        "belief_id": row.belief_id,
        "chosen_option_id": row.chosen_option_id,
        "option_space_status": row.option_space_status,
        "created_at": row.created_at,
        "decided_at": row.decided_at,
    }


def sync_legacy_records(db: Session, *, limit: int = 500) -> dict[str, int]:
    """Refresh stable entity references for Claim, ResearchQuestion, DomainRecord, and Decision."""
    world_graph.seed_core_types(db)
    initial_event_count = db.query(models.WorldEvent).count()
    result: dict[str, int] = {
        "records_seen": 0,
        "entities_created": 0,
        "events_created": 0,
        "unresolved_records": 0,
    }

    for entity_type, source_model in _RECORD_TYPES:
        registered = world_graph.CANONICAL_ADAPTERS.get(entity_type)
        if registered is None or registered[0] is not source_model:
            result["unresolved_records"] += 1
            continue
        rows = (
            db.query(source_model)
            .order_by(source_model.id.asc())
            .limit(max(1, int(limit)))
            .all()
        )
        for source in rows:
            result["records_seen"] += 1
            existing = world_graph.find_canonical_entity(db, entity_type, source.id)
            try:
                entity = world_graph.ensure_canonical_entity(
                    db,
                    entity_type,
                    source.id,
                    created_by="legacy_record_substrate_adapter",
                )
            except world_graph.SubstrateError:
                result["unresolved_records"] += 1
                continue
            result["entities_created"] += int(existing is None)
            _record_snapshot(db, entity, entity_type, source, _safe_source_fields(entity_type, source))

    db.flush()
    result["events_created"] = db.query(models.WorldEvent).count() - initial_event_count
    return result


def _record_snapshot(
    db: Session,
    entity: models.SubstrateEntity,
    entity_type: str,
    source: Any,
    safe_fields: dict[str, Any],
) -> None:
    source_table = source.__tablename__
    snapshot = json.dumps(
        {"source_fields": safe_fields},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    event_key = f"legacy-source-snapshot:{source_table}:{source.id}:{digest}"
    world_graph.create_event(
        db,
        event_type="entity_source_refreshed",
        entity_id=entity.id,
        source="legacy_record_substrate_adapter",
        payload={
            "source_ref": {"table": source_table, "id": source.id},
            "snapshot_sha256": digest,
            "source_fields": sorted(safe_fields),
            "payload_copied": False,
        },
        idempotency_key=event_key,
    )
