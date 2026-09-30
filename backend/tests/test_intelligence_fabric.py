from app import models
from app.services.observer_engine import ObserverEngine
from app.services import opportunity_engine, reality_memory
import json
import pytest


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
    first_evidence = db.query(models.Evidence).one()
    assert first_evidence.idempotency_key is not None

    changed = observer.observe(
        "Contractors manually lose hours every day now.",
        source="rss",
        metadata=metadata,
    )

    assert changed.id != first.id
    assert changed.supersedes_signal_id == first.id
    assert db.query(models.Signal).count() == 2
    assert db.query(models.Evidence).count() == 2
    evidence_keys = [row.idempotency_key for row in db.query(models.Evidence).all()]
    assert all(evidence_keys)
    assert len(set(evidence_keys)) == 2


def test_pattern_opportunity_creation_is_idempotent_and_history_is_deduplicated(db):
    signals = [
        models.Signal(source="manual", content=f"Contractor report {index}: contractors lose hours.")
        for index in range(2)
    ]
    db.add_all(signals)
    db.flush()
    evidence_rows = [
        models.Evidence(
            signal_id=signal.id,
            source=signal.source,
            content=signal.content,
            provenance=json.dumps({"source_type": "manual"}),
        )
        for signal in signals
    ]
    db.add_all(evidence_rows)
    pattern = models.Pattern(
        title="Recurring theme: contractors, manually",
        description="Contractors manually lose hours every week.",
        frequency=2,
        confidence_score=80,
        origin_signal_ids=",".join(str(signal.id) for signal in signals),
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)

    first = opportunity_engine.opportunity_from_pattern(db, pattern)
    second = opportunity_engine.opportunity_from_pattern(db, pattern)

    assert first.id == second.id
    assert db.query(models.Opportunity).filter_by(pattern_id=pattern.id).count() == 1
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=first.id, event_type="created").count() == 1
    assert db.query(models.EvidenceRelationship).filter_by(
        opportunity_id=first.id, relation_type="derived_from"
    ).count() == 2


def test_pattern_opportunity_rejects_missing_or_metadata_only_evidence(db):
    pattern = models.Pattern(
        title="Unsupported source-less pattern",
        description="A pattern without attributable evidence.",
        frequency=1,
        confidence_score=99,
    )
    db.add(pattern)
    db.commit()
    with pytest.raises(ValueError, match="attributable source evidence"):
        opportunity_engine.opportunity_from_pattern(db, pattern)

    signal = models.Signal(
        source="crossref",
        source_type="external",
        content="Crossref metadata record: plausible sounding commercial claim.",
        canonical_url="https://doi.org/10.1234/metadata",
        external_id="10.1234/metadata",
        provenance=json.dumps({"metadata_only": True}),
    )
    db.add(signal)
    db.flush()
    db.add(models.Evidence(signal_id=signal.id, source="crossref", content=signal.content))
    pattern.origin_signal_ids = str(signal.id)
    db.commit()
    with pytest.raises(ValueError, match="Bibliographic metadata"):
        opportunity_engine.opportunity_from_pattern(db, pattern)


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
    opportunity_evidence_keys = [
        row.idempotency_key
        for row in db.query(models.Evidence).filter_by(opportunity_id=first_opportunity.id).all()
    ]
    assert all(opportunity_evidence_keys)
    assert len(set(opportunity_evidence_keys)) == 2
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=first_opportunity.id, event_type="created").count() == 1
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=first_opportunity.id, event_type="evidence_added").count() == 1


def test_reality_memory_evidence_has_stable_identity(db):
    signal = models.Signal(source="manual", content="A specific observed claim.")
    belief = models.Belief(statement="A testable belief supported by a signal.")
    db.add_all([signal, belief])
    db.commit()
    db.refresh(signal)
    db.refresh(belief)

    item = {"signal_id": signal.id, "content": "A specific observed claim."}
    first = reality_memory.record_evidence(db, belief, [item])
    repeated = reality_memory.record_evidence(db, belief, [item])

    assert len(first) == 1
    assert repeated == []
    assert first[0].idempotency_key == f"belief-signal:{belief.id}:{signal.id}"
    assert db.query(models.Evidence).filter_by(belief_id=belief.id, signal_id=signal.id).count() == 1
