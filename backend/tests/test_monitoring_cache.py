from datetime import datetime, timedelta, timezone
import json

from app import models
from app.services import intelligence_cache, opportunity_engine, opportunity_monitor
from app.services import evidence_graph


def make_opportunity(db):
    return opportunity_engine.opportunity_from_idea(db, "Small contractors lose hours scheduling repairs")


def make_evidence(db, opportunity, *, source, fingerprint, direction="supports"):
    evidence = models.Evidence(
        opportunity_id=opportunity.id,
        source=source,
        content=f"Observed evidence from {source}",
        direction=direction,
        provenance_hash=fingerprint,
        content_fingerprint=fingerprint,
        retrieved_at=datetime.now(timezone.utc),
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def test_opportunity_monitor_unchanged_and_meaningful_new_source(db):
    opportunity = make_opportunity(db)
    make_evidence(db, opportunity, source="reddit", fingerprint="one")

    first = opportunity_monitor.monitor_opportunity(db, opportunity.id, stale_after_days=999, run_judgment=False)
    unchanged = opportunity_monitor.monitor_opportunity(db, opportunity.id, stale_after_days=999, run_judgment=False)
    assert first["change"] == "changed"
    assert unchanged["status"] == "NO_MEANINGFUL_CHANGE"

    make_evidence(db, opportunity, source="github", fingerprint="two")
    changed = opportunity_monitor.monitor_opportunity(db, opportunity.id, stale_after_days=999, run_judgment=False)
    assert changed["change"] == "expanding"
    assert "new_source" in changed["changes"]
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=opportunity.id, event_type="monitoring_snapshot").count() == 2


def test_contradiction_invalidates_without_deleting_history(db):
    opportunity = make_opportunity(db)
    evidence = make_evidence(db, opportunity, source="reddit", fingerprint="contradiction")
    first = opportunity_monitor.monitor_opportunity(db, opportunity.id, stale_after_days=999, run_judgment=False)
    contradiction = models.Evidence(
        source="github", content="Contradictory source", direction="contradicts",
        provenance_hash="contradictory", content_fingerprint="contradictory",
    )
    db.add(contradiction)
    db.commit()
    evidence_graph.link_evidence(db, contradiction, opportunity_id=opportunity.id, relation_type="contradicts")

    result = opportunity_monitor.monitor_opportunity(db, opportunity.id, stale_after_days=999, run_judgment=False)

    assert result["change"] == "weakened"
    assert db.get(models.Opportunity, opportunity.id).status == "invalidated"
    assert db.query(models.OpportunityEvent).filter_by(opportunity_id=opportunity.id, event_type="opportunity_weakened").count() == 1
    assert first["snapshot"]["evidence_count"] == 1


def test_stale_monitoring_triggers_research_and_persists_snapshot(db):
    opportunity = make_opportunity(db)
    old = models.Evidence(
        opportunity_id=opportunity.id, source="rss", content="Old evidence",
        provenance_hash="old", content_fingerprint="old",
        retrieved_at=datetime.now(timezone.utc) - timedelta(days=100),
    )
    db.add(old)
    db.commit()

    result = opportunity_monitor.monitor_opportunity(db, opportunity.id, stale_after_days=30, run_judgment=False)

    assert result["change"] == "stale"
    assert result["research_question_id"] is not None
    assert db.query(models.ResearchTask).filter_by(question_id=result["research_question_id"]).count() >= 1
    assert db.query(models.OpportunityEvent).filter_by(
        opportunity_id=opportunity.id, event_type="monitoring_snapshot"
    ).count() == 1


def test_cache_identity_hit_changed_input_stale_and_persistence(db):
    key_a, fingerprint_a = intelligence_cache.cache_identity("url", "https://example.test/a", {"headers": "v1"})
    key_b, fingerprint_b = intelligence_cache.cache_identity("url", "https://example.test/a", {"headers": "v2"})
    assert key_a != key_b
    assert fingerprint_a != fingerprint_b

    entry = intelligence_cache.put(
        db, object_type="url", value="https://example.test/a", parameters={"headers": "v1"},
        content="cached content", provider="fixture", model="fixture-v1",
    )
    hit, usable = intelligence_cache.get(db, object_type="url", value="https://example.test/a", parameters={"headers": "v1"})
    miss, usable_miss = intelligence_cache.get(db, object_type="url", value="https://example.test/a", parameters={"headers": "v2"})
    assert hit.id == entry.id and usable is True
    assert miss is None and usable_miss is False

    entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    stale, stale_usable = intelligence_cache.get(db, object_type="url", value="https://example.test/a", parameters={"headers": "v1"})
    stale_allowed, allowed = intelligence_cache.get(db, object_type="url", value="https://example.test/a", parameters={"headers": "v1"}, allow_stale=True)
    assert stale.status == "stale"
    assert stale_usable is False
    assert stale_allowed.id == entry.id and allowed is True

    intelligence_cache.invalidate(db, entry)
    db.expunge_all()
    restored = db.get(models.IntelligenceCacheEntry, entry.id)
    assert restored.status == "invalidated"


def test_cache_identity_case_sensitive_strings():
    # YouTube video IDs are case-sensitive; casefolding identity would let two
    # distinct videos share one cache row (the second put overwrites the
    # first). Case is preserved; identical inputs still hash identically.
    key_a, _ = intelligence_cache.cache_identity("youtube_metadata", "dQw4w9WgXcQ")
    key_b, _ = intelligence_cache.cache_identity("youtube_metadata", "dqw4w9wgxcq")
    key_a2, _ = intelligence_cache.cache_identity("youtube_metadata", "dQw4w9WgXcQ")
    assert key_a != key_b
    assert key_a == key_a2
