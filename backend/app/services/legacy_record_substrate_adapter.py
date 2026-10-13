"""Source-linked wrappers for remaining mature Forge records.

These legacy tables remain authoritative. The adapter only creates minimal
canonical entities and digest-only audit events; it does not copy source text
or infer relations from names or similar content.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import cast, func, literal, or_, String
from sqlalchemy.orm import Session

from app import models
from app.services import world_graph


_RECORD_TYPES: tuple[tuple[str, type], ...] = (
    ("rare_signal_assessment", models.RareSignalAssessment),
    ("claim", models.Claim),
    ("research_question", models.ResearchQuestion),
    ("domain_record", models.DomainRecord),
    ("decision", models.Decision),
)


def _safe_source_fields(entity_type: str, row: Any) -> dict[str, Any]:
    """Select lifecycle/link metadata only; raw statements and private notes stay in source tables."""
    if entity_type == "rare_signal_assessment":
        # Keep source lineage and lifecycle metrics only. The label, source
        # signal IDs and explanation payload remain in the source record.
        return {
            "status": row.status,
            "frequency": row.frequency,
            "prior_frequency": row.prior_frequency,
            "recent_frequency": row.recent_frequency,
            "velocity": row.velocity,
            "acceleration": row.acceleration,
            "source_diversity": row.source_diversity,
            "score": row.score,
            "novelty": row.novelty,
            "specificity": row.specificity,
            "pain_intensity": row.pain_intensity,
            "solution_scarcity": row.solution_scarcity,
            "economic_relevance": row.economic_relevance,
            "freshness": row.freshness,
            "recurrence": row.recurrence,
            "geographic_spread": row.geographic_spread,
            "language_spread": row.language_spread,
            "pattern_id": row.pattern_id,
            "opportunity_id": row.opportunity_id,
            "research_question_id": row.research_question_id,
            "first_seen": row.first_seen,
            "last_seen": row.last_seen,
            "updated_at": row.updated_at,
        }
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
            "updated_at": row.updated_at,
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
        "updated_at": row.updated_at,
    }


def sync_legacy_records(db: Session, *, limit: int = 500) -> dict[str, int]:
    """Refresh stable references for claims, research questions, rare signals, domains, and decisions."""
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
        batch_limit = max(1, int(limit))
        source_system = source_model.__tablename__
        has_entity = (
            db.query(models.SubstrateEntity.id)
            .filter(
                models.SubstrateEntity.entity_type == entity_type,
                models.SubstrateEntity.source_system == source_system,
                models.SubstrateEntity.source_id == cast(source_model.id, String),
            )
            .correlate(source_model)
            .exists()
        )

        # New source rows always get a slot before unchanged historic rows.
        # Remaining capacity refreshes the most recently changed existing
        # rows so mutable lifecycle snapshots still advance without starving
        # higher-ID records during the initial migration.
        new_rows = (
            db.query(source_model)
            .filter(~has_entity)
            .order_by(source_model.id.asc())
            .limit(batch_limit)
            .all()
        )
        remaining = batch_limit - len(new_rows)
        existing_rows = []
        if remaining > 0:
            timestamp_fields = [
                getattr(source_model, name)
                for name in ("updated_at", "decided_at", "last_seen", "observed_at", "created_at")
                if hasattr(source_model, name)
            ]
            freshness = (
                func.coalesce(*timestamp_fields)
                if len(timestamp_fields) > 1
                else timestamp_fields[0]
                if timestamp_fields
                else source_model.id
            )
            snapshot_prefix = (
                literal(f"legacy-source-snapshot:{source_system}:")
                + cast(source_model.id, String)
                + literal(":")
            )
            last_snapshot_at = (
                db.query(func.max(models.WorldEvent.occurred_at))
                .filter(
                    models.WorldEvent.event_type == "entity_source_refreshed",
                    func.substr(
                        models.WorldEvent.idempotency_key,
                        1,
                        func.length(snapshot_prefix),
                    ) == snapshot_prefix,
                )
                .correlate(source_model)
                .scalar_subquery()
            )
            # Once a row's current digest has been recorded, it leaves the
            # scan window. New/unsnapshotted rows and rows modified after their
            # last snapshot remain eligible, so unchanged recent rows cannot
            # starve other lifecycle records.
            needs_snapshot = or_(
                last_snapshot_at.is_(None),
                freshness > last_snapshot_at,
            )
            existing_rows = (
                db.query(source_model)
                .filter(has_entity, needs_snapshot)
                .order_by(freshness.desc(), source_model.id.desc())
                .limit(remaining)
                .all()
            )
        rows = new_rows + existing_rows
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
