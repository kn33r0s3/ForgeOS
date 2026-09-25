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
