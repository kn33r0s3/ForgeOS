import pytest

from app import models
from app.services import market_signal_substrate_adapter, world_graph


def test_market_signal_projection_uses_generic_substrate(db):
    world_graph.seed_core_types(db)

    registry = (
        db.query(models.TypeRegistry)
        .filter_by(category="entity_type", type_name="market_signal")
        .one()
    )
    assert registry.status == "active"

    signal = models.Signal(
        source="market_feed",
        source_type="external",
        signal_type="demand",
        category="pricing",
        title="Shipping price frustration",
        content="Customers are asking for faster delivery windows and lower shipping costs.",
        importance_score=82.0,
        tags="shipping,pricing,customer demand",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    result = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=10)

    assert result["signals_seen"] == 1
    assert result["entities_created"] >= 1
    assert result["relations_created"] >= 1
    assert result["events_created"] >= 1
    assert result["evidence_created"] >= 1

    substrate = (
        db.query(models.SubstrateEntity)
        .filter_by(entity_type="market_signal", source_system="signals", source_id=str(signal.id))
        .one()
    )
    assert substrate.display_name.startswith("Shipping price frustration")

    relation = (
        db.query(models.WorldRelation)
        .filter_by(idempotency_key=f"market-signal:{signal.id}:signals:signal-v1")
        .one()
    )
    assert relation.relation_type == "signals"
    assert relation.from_entity_id == substrate.id

    event = (
        db.query(models.WorldEvent)
        .filter_by(idempotency_key=f"market-signal-observed:{signal.id}:v1")
        .one()
    )
    assert event.event_type == "market_signal_observed"
    assert event.entity_id == substrate.id

    evidence = (
        db.query(models.Evidence)
        .filter_by(idempotency_key=f"market-signal-evidence:{signal.id}:v1")
        .one()
    )
    assert evidence.subject_kind == "entity"
    assert evidence.subject_id == substrate.id
    assert evidence.support_level == "hypothesized"

    repeat = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=10)
    assert repeat["entities_created"] == 0
    assert repeat["relations_created"] == 0
    assert repeat["events_created"] == 0
    assert repeat["evidence_created"] == 0


def test_market_signal_projection_repairs_missing_relation_event_and_evidence(db):
    world_graph.seed_core_types(db)
    signal = models.Signal(
        source="market_feed",
        source_type="external",
        signal_type="demand",
        category="operations",
        title="Repeated scheduling delays",
        content="Several public records describe repeated scheduling delays.",
        importance_score=55.0,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    # Simulate a valid partial projection left by an interrupted earlier run:
    # both source-linked entities exist, but the relation/event/evidence do not.
    world_graph.ensure_canonical_entity(
        db,
        "signal",
        signal.id,
        created_by="market_signal_substrate_adapter",
        source_system="signals",
    )
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
    partial = world_graph.create_entity(
        db,
        entity_type="market_signal",
        display_name=signal.title,
        attributes={
            "signal_id": signal.id,
            "source": signal.source or "manual",
            "source_type": signal.source_type or "manual",
            "signal_type": signal.signal_type or "observation",
            "category": signal.category,
            "importance_score": float(signal.importance_score or 0.0),
            "content_excerpt": market_signal_substrate_adapter._signal_excerpt(signal.content),
        },
        created_by="market_signal_substrate_adapter",
        identity=identity,
    )
    db.commit()

    repaired = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=10)

    assert repaired["signals_seen"] == 1
    assert repaired["entities_created"] == 0
    assert repaired["relations_created"] == 1
    assert repaired["events_created"] == 1
    assert repaired["evidence_created"] == 1
    assert db.query(models.WorldRelation).filter_by(
        idempotency_key=f"market-signal:{signal.id}:signals:signal-v1"
    ).one().from_entity_id == partial.id
    assert db.query(models.WorldEvent).filter_by(
        idempotency_key=f"market-signal-observed:{signal.id}:v1"
    ).count() == 1
    assert db.query(models.Evidence).filter_by(
        idempotency_key=f"market-signal-evidence:{signal.id}:v1"
    ).count() == 1

    repeated = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=10)
    assert repeated["signals_seen"] == 0
    assert repeated["entities_created"] == 0
    assert repeated["relations_created"] == 0
    assert repeated["events_created"] == 0
    assert repeated["evidence_created"] == 0


def test_market_signal_projection_fails_closed_when_required_type_is_inactive(db):
    world_graph.seed_core_types(db)
    signal = models.Signal(content="A market signal waits for the type registry.")
    db.add(signal)
    db.commit()

    signals_type = db.query(models.TypeRegistry).filter_by(
        category="relation_type",
        type_name="signals",
    ).one()
    world_graph.set_type_status(
        db,
        signals_type,
        "deprecated",
        actor="test",
        rationale="Test inactive relationship type handling.",
        evidence_ref="backend/tests/test_wave2_market_signal_domain.py",
    )
    db.commit()

    result = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=10)

    assert result["signals_seen"] == 0
    assert result["unresolved_signals"] == 1
    assert db.query(models.SubstrateEntity).filter_by(
        entity_type="market_signal",
        source_system="signals",
        source_id=str(signal.id),
    ).count() == 0
    assert db.query(models.WorldRelation).filter_by(
        idempotency_key=f"market-signal:{signal.id}:signals:signal-v1"
    ).count() == 0


def test_market_signal_projection_keeps_programming_failures_visible(db, monkeypatch):
    signal = models.Signal(content="A recorded market observation.")
    db.add(signal)
    db.commit()

    def fail_unexpectedly(*args, **kwargs):
        raise RuntimeError("unexpected adapter failure")

    monkeypatch.setattr(world_graph, "ensure_canonical_entity", fail_unexpectedly)

    with pytest.raises(RuntimeError, match="unexpected adapter failure"):
        market_signal_substrate_adapter.sync_market_signal_signals(db)


def test_market_signal_projection_counts_known_substrate_conflict_as_unresolved(db, monkeypatch):
    signal = models.Signal(content="A recorded market observation.")
    db.add(signal)
    db.commit()

    def fail_with_substrate_conflict(*args, **kwargs):
        raise world_graph.SubstrateError("canonical source identity changed")

    monkeypatch.setattr(world_graph, "ensure_canonical_entity", fail_with_substrate_conflict)

    result = market_signal_substrate_adapter.sync_market_signal_signals(db)

    assert result["signals_seen"] == 1
    assert result["unresolved_signals"] == 1


def test_market_signal_projection_advances_across_bounded_batches(db):
    world_graph.seed_core_types(db)
    signals = [models.Signal(content=f"Recorded market observation {index}.") for index in range(3)]
    db.add_all(signals)
    db.commit()

    first = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=2)
    second = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=2)
    third = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=2)

    assert first["signals_seen"] == 2
    assert second["signals_seen"] == 1
    assert third["signals_seen"] == 0
    assert db.query(models.SubstrateEntity).filter_by(
        entity_type="market_signal", source_system="signals"
    ).count() == 3
