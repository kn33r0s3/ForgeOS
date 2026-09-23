from app import models
from app.services.observer_engine import ObserverEngine
from app.services import opportunity_engine


def test_collector_evidence_deduplicates_and_changed_content_is_historical(db):
    observer = ObserverEngine(db)
    metadata = {
        "url": "HTTPS://Example.com/article/?b=2&a=1#fragment",
        "external_id": "article-1",
        "title": "Maintenance pain",
        "timestamp": "2026-09-11T12:00:00+00:00",
        "provenance": {"feed": "test"},
    }

    first = observer.observe("Contractors manually lose hours every week.", source="rss", metadata=metadata)
    same = observer.observe(
        "Contractors manually lose hours every week.",
        source="rss",
        metadata={**metadata, "url": "https://example.com/article?a=1&b=2"},
    )

    assert same.id == first.id
    assert db.query(models.Signal).count() == 1
    assert db.query(models.Evidence).count() == 1

    changed = observer.observe(
        "Contractors manually lose hours every day now.",
        source="rss",
        metadata=metadata,
    )

    assert changed.id != first.id
    assert changed.supersedes_signal_id == first.id
    assert db.query(models.Signal).count() == 2
    assert db.query(models.Evidence).count() == 2


def test_pattern_opportunity_creation_is_idempotent_and_history_is_deduplicated(db):
    pattern = models.Pattern(
        title="Recurring theme: contractors, manually",
        description="Contractors manually lose hours every week.",
        frequency=2,
        confidence_score=80,
        origin_signal_ids="1,2",
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)

    first = opportunity_engine.opportunity_from_pattern(db, pattern)
    second = opportunity_engine.opportunity_from_pattern(db, pattern)

    assert first.id == second.id
    assert db.query(models.Opportunity).filter_by(pattern_id=pattern.id).count() == 1
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=first.id, event_type="created").count() == 1


def test_new_economic_evidence_updates_existing_opportunity(db):
    observer = ObserverEngine(db)
    first_signal = observer.observe(
        "Small contractors waste hours manually coordinating maintenance requests.",
        source="rss",
        metadata={"url": "https://example.com/1", "external_id": "1"},
    )
    second_signal = observer.observe(
        "Small contractors spend hours each week chasing tenant photos by email.",
        source="rss",
        metadata={"url": "https://example.com/2", "external_id": "2"},
    )
    pattern = models.Pattern(
        title="Recurring theme: contractors, maintenance",
        description="Small contractors waste hours manually coordinating maintenance requests.",
        frequency=2,
        confidence_score=80,
        origin_signal_ids=f"{first_signal.id},{second_signal.id}",
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)

    first_opportunity = opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern)
    second_opportunity = opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern)

    assert first_opportunity is not None
    assert second_opportunity.id == first_opportunity.id
    assert db.query(models.Opportunity).filter_by(pattern_id=pattern.id).count() == 1
    assert db.query(models.Evidence).filter_by(opportunity_id=first_opportunity.id).count() == 2
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=first_opportunity.id, event_type="created").count() == 1
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=first_opportunity.id, event_type="evidence_added").count() == 1
