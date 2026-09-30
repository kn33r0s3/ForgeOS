import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import public_feed, public_services_substrate_adapter as adapter, world_graph


def _provider_and_listing(db, *, visible=False):
    provider = models.Provider(
        name="Koshi Repair Cooperative",
        business_name="Koshi Repair Cooperative",
        category="repair",
        summary="Repairs household equipment.",
        city="Biratnagar",
        country="Nepal",
        website="https://koshi.example/",
        phone="9800000000",
        email="hello@koshi.example",
        public_visible=visible,
        is_active=True,
        verification_status="verified" if visible else "unverified",
    )
    db.add(provider)
    db.flush()
    listing = models.ServiceListing(
        provider_id=provider.id,
        title="Appliance repair",
        description="In-home diagnostics and repair.",
        category="repair",
        location="Biratnagar",
        price_from="1500",
        currency="NPR",
        availability_status="available",
        public_visible=visible,
        is_active=True,
    )
    db.add(listing)
    db.commit()
    db.refresh(provider)
    db.refresh(listing)
    return provider, listing


def test_provider_and_listing_project_without_copying_authority_or_visibility(db):
    provider, listing = _provider_and_listing(db, visible=False)

    first = adapter.sync_public_services(db)

    provider_entity = world_graph.find_canonical_entity(db, "provider", provider.id)
    listing_entity = world_graph.find_canonical_entity(db, "service_listing", listing.id)
    relation = db.query(models.WorldRelation).filter_by(
        from_entity_id=listing_entity.id,
        to_entity_id=provider_entity.id,
        relation_type="offered_by",
    ).one()
    evidence = db.query(models.Evidence).filter_by(
        subject_kind="relation", subject_id=relation.id
    ).one()
    assert first["provider_entities_created"] == 1
    assert first["listing_entities_created"] == 1
    assert first["relations_created"] == 1
    assert first["evidence_created"] == 1
    assert provider_entity.identity_key == f"source:provider:public_providers:{provider.id}"
    assert listing_entity.identity_key == f"source:service_listing:public_service_listings:{listing.id}"
    assert json.loads(provider_entity.attributes) == {
        "canonical_ref": {"entity_type": "provider", "entity_id": provider.id}
    }
    assert provider_entity.canonical_identifier == "https://koshi.example/"
    assert relation.truth_state == "hypothesized"
    assert evidence.support_level == "hypothesized"
    assert json.loads(evidence.provenance)["source_ref"] == {
        "table": "public_service_listings", "id": listing.id
    }
    assert provider.public_visible is False
    assert provider.verification_status == "unverified"
    assert listing.public_visible is False
    private_feed = public_feed.build_public_feed(db, limit=100)
    assert all(item.entity_id != provider.id or item.entity_type != "provider" for item in private_feed)
    assert all(item.entity_id != listing.id or item.entity_type != "service_listing" for item in private_feed)

    repeated = adapter.sync_public_services(db)
    assert repeated["provider_entities_created"] == 0
    assert repeated["listing_entities_created"] == 0
    assert repeated["relations_created"] == 0
    assert repeated["evidence_created"] == 0
    assert repeated["events_created"] == 0
    assert db.query(models.Provider).count() == 1
    assert db.query(models.ServiceListing).count() == 1

    provider.business_name = "Koshi Repair Cooperative Nepal"
    listing.description = "Diagnostics and in-home repair."
    db.commit()
    refreshed = adapter.sync_public_services(db)
    assert refreshed["events_created"] == 3
    assert provider_entity.display_name == provider.business_name
    assert db.query(models.WorldRelation).filter_by(
        idempotency_key=f"public-service-listing:{listing.id}:provider:{provider.id}:offered-by-v1"
    ).count() == 1
    snapshot_events = db.query(models.WorldEvent).filter_by(
        event_type="entity_source_refreshed"
    ).all()
    assert len(snapshot_events) == 5
    source_snapshots = [
        json.loads(event.payload) for event in snapshot_events
        if "snapshot_sha256" in json.loads(event.payload)
    ]
    assert len(source_snapshots) == 4
    assert all(event["payload_copied"] is False for event in source_snapshots)


def test_public_feed_links_visible_service_to_substrate_relation_and_evidence(db):
    provider, listing = _provider_and_listing(db, visible=True)
    adapter.sync_public_services(db)

    items = public_feed.build_public_feed(db, limit=100)

    service_item = next(item for item in items if item.entity_type == "service_listing")
    relation = db.query(models.WorldRelation).filter_by(relation_type="offered_by").one()
    evidence = db.query(models.Evidence).filter_by(
        subject_kind="relation", subject_id=relation.id
    ).one()
    refs = {(ref.entity_type, ref.entity_id, ref.relation) for ref in service_item.relations}
    assert ("entity", relation.from_entity_id, "substrate_entity") in refs
    assert ("entity", relation.to_entity_id, "substrate_entity") in refs
    assert ("relation", relation.id, "substrate_relation") in refs
    assert ("evidence", evidence.id, "evidence:hypothesized") in refs
    assert ("provider", provider.id, "offered_by") in refs


def test_proposed_or_deprecated_offered_by_type_is_never_activated_by_adapter(db):
    provider, _ = _provider_and_listing(db)
    world_graph.seed_core_types(db)
    offered_by = db.query(models.TypeRegistry).filter_by(
        category="relation_type", type_name="offered_by"
    ).one()
    world_graph.set_type_status(
        db,
        offered_by,
        "deprecated",
        actor="test",
        rationale="This test confirms adapters do not revive deprecated types.",
        evidence_ref="FORGE_SUBSTRATE_BLUEPRINT.md",
    )
    db.commit()

    result = adapter.sync_public_services(db)

    db.refresh(offered_by)
    assert offered_by.status == "deprecated"
    assert result["provider_entities_created"] == 1
    assert result["listing_entities_created"] == 1
    assert result["unactivated_types"] == 1
    assert db.query(models.WorldRelation).filter_by(relation_type="offered_by").count() == 0
    assert db.query(models.Provider).filter_by(id=provider.id).count() == 1


def test_provider_adapter_restart_is_idempotent(tmp_path):
    database_path = tmp_path / "provider_adapter.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    first_session = SessionLocal()
    provider, listing = _provider_and_listing(first_session, visible=True)
    first = adapter.sync_public_services(first_session)
    first_session.commit()
    expected_ids = (provider.id, listing.id)
    first_session.close()

    restarted = SessionLocal()
    second = adapter.sync_public_services(restarted)
    restarted.commit()

    assert expected_ids == (provider.id, listing.id)
    assert second["provider_entities_created"] == 0
    assert second["listing_entities_created"] == 0
    assert second["relations_created"] == 0
    assert second["evidence_created"] == 0
    assert second["events_created"] == 0
    assert restarted.query(models.SubstrateEntity).filter_by(entity_type="provider").count() == 1
    assert restarted.query(models.SubstrateEntity).filter_by(entity_type="service_listing").count() == 1
    assert restarted.query(models.WorldRelation).filter_by(relation_type="offered_by").count() == 1
    assert first["events_created"] == 5
    restarted.close()
    engine.dispose()
