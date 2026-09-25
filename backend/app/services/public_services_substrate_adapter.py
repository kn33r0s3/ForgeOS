"""Read-only substrate projection for the existing provider directory.

The public provider and service listing tables remain their own write
authority during migration. This adapter creates source-linked substrate
entities and `offered_by` relations without copying provider/listing payloads
or changing their visibility, verification, booking, or pricing state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import type_validation, world_graph


def sync_public_services(db: Session, *, limit: int = 500) -> dict[str, int]:
    """Project existing provider rows and their listing ownership links."""
    world_graph.seed_core_types(db)
    initial_event_count = db.query(models.WorldEvent).count()
    result = {
        "provider_entities_created": 0,
        "listing_entities_created": 0,
        "relations_created": 0,
        "evidence_created": 0,
        "events_created": 0,
        "unresolved_service_listings": 0,
        "unactivated_types": 0,
    }

    try:
        type_validation.resolve_type(db, "entity_type", "provider")
        type_validation.resolve_type(db, "entity_type", "service_listing")
    except type_validation.SubstrateError:
        result["unactivated_types"] += 1
        return result

    providers = (
        db.query(models.Provider)
        .order_by(models.Provider.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    listings = (
        db.query(models.ServiceListing)
        .order_by(models.ServiceListing.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )

    provider_entities: dict[int, models.SubstrateEntity] = {}
    for provider in providers:
        entity, created = _ensure_source_entity(db, "provider", provider)
        provider_entities[provider.id] = entity
        result["provider_entities_created"] += int(created)
        _record_source_snapshot(db, entity, provider)

    for listing in listings:
        entity, created = _ensure_source_entity(db, "service_listing", listing)
        result["listing_entities_created"] += int(created)
        _record_source_snapshot(db, entity, listing)

        provider_entity = provider_entities.get(listing.provider_id)
        if provider_entity is None:
            provider = db.get(models.Provider, listing.provider_id)
            if provider is not None:
                provider_entity, created = _ensure_source_entity(db, "provider", provider)
                provider_entities[provider.id] = provider_entity
                result["provider_entities_created"] += int(created)
                _record_source_snapshot(db, provider_entity, provider)
        if provider_entity is None:
            result["unresolved_service_listings"] += 1
            continue

        try:
            type_validation.resolve_type(db, "relation_type", "offered_by")
        except type_validation.SubstrateError:
            result["unactivated_types"] += 1
            continue

        relation_key = (
            f"public-service-listing:{listing.id}:provider:{listing.provider_id}:offered-by-v1"
        )
        existing = db.query(models.WorldRelation).filter_by(idempotency_key=relation_key).one_or_none()
        try:
            relation = world_graph.create_relation(
                db,
                from_entity_id=entity.id,
                to_entity_id=provider_entity.id,
                relation_type="offered_by",
                attributes={
                    "source_ref": {"table": "public_service_listings", "id": listing.id},
                    "provider_source_ref": {"table": "public_providers", "id": listing.provider_id},
                },
                direction="directed",
                truth_state="hypothesized",
                created_by="public_services_substrate_adapter",
                idempotency_key=relation_key,
            )
        except type_validation.SubstrateError:
            result["unresolved_service_listings"] += 1
            continue
        result["relations_created"] += int(existing is None)

        evidence_key = (
            f"public-service-listing:{listing.id}:provider:{listing.provider_id}:offered-by-evidence-v1"
        )
        evidence_before = db.query(models.Evidence).filter_by(idempotency_key=evidence_key).one_or_none()
        world_graph.create_evidence(
            db,
            subject_kind="relation",
            subject_id=relation.id,
            claim=f"Source listing {listing.id} records provider_id={listing.provider_id}.",
            support_level="hypothesized",
            source="public_service_listings",
            provenance={
                "adapter": "public_services_substrate_adapter",
                "source_ref": {"table": "public_service_listings", "id": listing.id},
                "field": "provider_id",
                "provider_source_ref": {"table": "public_providers", "id": listing.provider_id},
            },
            idempotency_key=evidence_key,
        )
        result["evidence_created"] += int(evidence_before is None)

    db.flush()
    result["events_created"] = db.query(models.WorldEvent).count() - initial_event_count
    return result


def _ensure_source_entity(
    db: Session, entity_type: str, source: models.Provider | models.ServiceListing
) -> tuple[models.SubstrateEntity, bool]:
    existing = world_graph.find_canonical_entity(db, entity_type, source.id)
    entity = world_graph.ensure_canonical_entity(db, entity_type, source.id)
    return entity, existing is None


def _record_source_snapshot(
    db: Session, entity: models.SubstrateEntity, source: models.Provider | models.ServiceListing
) -> int:
    if isinstance(source, models.Provider):
        source_table = "public_providers"
        source_values: dict[str, Any] = {
            "name": source.name,
            "business_name": source.business_name,
            "category": source.category,
            "summary": source.summary,
            "region": source.region,
            "city": source.city,
            "country": source.country,
            "website": source.website,
            "phone": source.phone,
            "email": source.email,
            "is_active": source.is_active,
            "public_visible": source.public_visible,
            "verification_status": source.verification_status,
            "verification_notes": source.verification_notes,
        }
    else:
        source_table = "public_service_listings"
        source_values = {
            "provider_id": source.provider_id,
            "title": source.title,
            "description": source.description,
            "category": source.category,
            "location": source.location,
            "price_from": source.price_from,
            "currency": source.currency,
            "availability_status": source.availability_status,
            "is_active": source.is_active,
            "public_visible": source.public_visible,
        }
    source_updated_at = source.updated_at.isoformat() if source.updated_at else None
    snapshot = json.dumps(
        {"source_values": source_values, "source_updated_at": source_updated_at},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    key = f"public-source-snapshot:{source_table}:{source.id}:{digest}"
    existed = db.query(models.WorldEvent).filter_by(idempotency_key=key).first() is not None
    world_graph.create_event(
        db,
        event_type="entity_source_refreshed",
        entity_id=entity.id,
        source="public_services_substrate_adapter",
        payload={
            "source_ref": {"table": source_table, "id": source.id},
            "snapshot_sha256": digest,
            "source_updated_at": source_updated_at,
            "payload_copied": False,
        },
        idempotency_key=key,
    )
    return int(not existed)
