"""Project raw market-signalling rows into the universal substrate.

This is a Wave 2 generality example: the domain stays part of the existing
Signal/Pattern/Belief/Opportunity architecture, but it gains a typed
market_signal entity, a relation back to its source signal, and evidence/history
records without creating a second domain table.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from app import models
from app.services import world_graph


def _signal_excerpt(content: str | None, limit: int = 140) -> str:
    text = (content or "").strip().replace("\n", " ")
    if not text:
        return "No signal text recorded."
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def sync_market_signal_signals(db: Session, *, limit: int = 250) -> dict[str, int]:
    """Project the newest raw market signals into the generic substrate graph.

    The underlying `signals` table remains authoritative. We create only typed
    entity/relation/event/evidence wrappers that reference its rows, preserving
    the existing source-of-truth contract.
    """
    world_graph.seed_core_types(db)
    result = {
        "signals_seen": 0,
        "entities_created": 0,
        "relations_created": 0,
        "events_created": 0,
        "evidence_created": 0,
        "unresolved_signals": 0,
    }

    projected_source_ids = (
        db.query(models.SubstrateEntity.source_id)
        .filter_by(entity_type="market_signal", source_system="signals")
    )
    signals = (
        db.query(models.Signal)
        .filter(~cast(models.Signal.id, String).in_(projected_source_ids))
        .order_by(models.Signal.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )

    for signal in signals:
        result["signals_seen"] += 1

        try:
            signal_entity = world_graph.find_canonical_entity(db, "signal", signal.id, source_system="signals")
            if signal_entity is None:
                signal_entity = world_graph.ensure_canonical_entity(
                    db,
                    "signal",
                    signal.id,
                    created_by="market_signal_substrate_adapter",
                    source_system="signals",
                )
        except world_graph.SubstrateError:
            result["unresolved_signals"] += 1
            continue

        identity = {
            "source_system": "signals",
            "source_id": str(signal.id),
            "provenance": {
                "source": signal.source or "manual",
                "source_type": signal.source_type or "manual",
                "signal_id": signal.id,
                "external_id": signal.external_id,
                "canonical_url": signal.canonical_url,
                "title": signal.title,
            },
        }

        market_signal_entity = (
            db.query(models.SubstrateEntity)
            .filter_by(entity_type="market_signal", source_system="signals", source_id=str(signal.id))
            .order_by(models.SubstrateEntity.id.asc())
            .first()
        )
        if market_signal_entity is None:
            market_signal_entity = world_graph.create_entity(
                db,
                entity_type="market_signal",
                display_name=((signal.title or "").strip() or f"Market signal #{signal.id}")[:240],
                attributes={
                    "signal_id": signal.id,
                    "source": signal.source or "manual",
                    "source_type": signal.source_type or "manual",
                    "signal_type": signal.signal_type or "observation",
                    "category": signal.category,
                    "importance_score": float(signal.importance_score or 0.0),
                    "content_excerpt": _signal_excerpt(signal.content),
                },
                created_by="market_signal_substrate_adapter",
                identity=identity,
            )
            result["entities_created"] += 1

        relation_key = f"market-signal:{signal.id}:signals:signal-v1"
        relation = db.query(models.WorldRelation).filter_by(idempotency_key=relation_key).one_or_none()
        if relation is None:
            relation = world_graph.create_relation(
                db,
                from_entity_id=market_signal_entity.id,
                to_entity_id=signal_entity.id,
                relation_type="signals",
                attributes={
                    "source_table": "signals",
                    "source_id": signal.id,
                    "source_type": signal.source_type or "manual",
                    "signal_type": signal.signal_type or "observation",
                    "relationship": "source_signal",
                },
                direction="directed",
                strength=None,
                truth_state="hypothesized",
                created_by="market_signal_substrate_adapter",
                idempotency_key=relation_key,
            )
            result["relations_created"] += 1

        event_key = f"market-signal-observed:{signal.id}:v1"
        if db.query(models.WorldEvent).filter_by(idempotency_key=event_key).one_or_none() is None:
            db.add(
                models.WorldEvent(
                    event_type="market_signal_observed",
                    entity_id=market_signal_entity.id,
                    payload=json.dumps(
                        {
                            "signal_id": signal.id,
                            "source": signal.source or "manual",
                            "source_type": signal.source_type or "manual",
                            "signal_type": signal.signal_type or "observation",
                            "importance_score": float(signal.importance_score or 0.0),
                        },
                        sort_keys=True,
                    ),
                    source="market_signal_substrate_adapter",
                    idempotency_key=event_key,
                )
            )
            result["events_created"] += 1

        evidence_key = f"market-signal-evidence:{signal.id}:v1"
        if db.query(models.Evidence).filter_by(idempotency_key=evidence_key).one_or_none() is None:
            world_graph.create_evidence(
                db,
                subject_kind="entity",
                subject_id=market_signal_entity.id,
                claim=f"Signal #{signal.id} is a market signal candidate in the current signal corpus.",
                support_level="hypothesized",
                source="market_signal_substrate_adapter",
                provenance={
                    "signal_id": signal.id,
                    "source": signal.source or "manual",
                    "source_type": signal.source_type or "manual",
                    "external_id": signal.external_id,
                    "canonical_url": signal.canonical_url,
                    "title": signal.title,
                    "content_excerpt": _signal_excerpt(signal.content),
                },
                confidence=0.35,
                idempotency_key=evidence_key,
            )
            result["evidence_created"] += 1

    db.flush()
    return result
