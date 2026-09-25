from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services import source_clearance_registry as registry


def test_registry_records_scope_provenance_and_clearance_evidence():
    entry = registry.source_clearances()[0]

    assert entry.registry_id == "govinfo-nepal-cultural-property-rule-2026"
    assert entry.collector == "web"
    assert entry.geographies == ("NP",)
    assert entry.categories == ("public_rule", "cultural_property")
    assert entry.robots_url.endswith("/robots.txt")
    assert entry.terms_url.endswith("/about/policies")
    assert entry.redirect_urls == (entry.url,)
    assert len(entry.evidence_references) >= 3
    source_register = Path(__file__).resolve().parents[2] / "docs" / "PUBLIC_SOURCES.md"
    register_text = source_register.read_text()
    assert entry.url in register_text
    assert all(
        (
            reference in register_text
            if reference.startswith("https://")
            else (source_register.parents[1] / reference).exists()
        )
        for reference in entry.evidence_references
    )


def test_registry_only_clears_exact_canonical_url_and_review_window():
    entry = registry.source_clearances()[0]

    assert registry.clearance_for_url(entry.url) == entry
    assert registry.clearance_error(entry.url, today=date(2026, 9, 25)) is None
    assert "not explicitly cleared" in registry.clearance_error(
        entry.url + "?download=1", today=date(2026, 9, 25)
    )
    assert "expired" in registry.clearance_error(entry.url, today=date(2026, 9, 26))


def test_registry_enforces_persistent_minimum_request_interval(db):
    entry = registry.source_clearances()[0]
    first_time = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)

    first = registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
        now=first_time,
    )
    assert first.entry == entry
    with pytest.raises(PermissionError, match="rate limit is active"):
        registry.authorize_request(
            entry.url,
            collector="web",
            db=db,
            today=date(2026, 9, 25),
            now=first_time + timedelta(seconds=3599),
        )
    later = registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
        now=first_time + timedelta(seconds=3600),
    )
    assert later.reserved_at == first_time + timedelta(seconds=3600)


def test_registry_validation_rejects_unsafe_redirect_and_missing_evidence():
    entry = registry.source_clearances()[0]

    with pytest.raises(ValueError, match="out-of-scope redirect"):
        registry.validate_registry((replace(entry, redirect_urls=(entry.url, "https://other.example/path")),))
    with pytest.raises(ValueError, match="evidence references"):
        registry.validate_registry((replace(entry, evidence_references=()),))


def test_uncleared_collector_families_are_not_active():
    assert registry.collector_is_cleared("web", today=date(2026, 9, 25))
    assert not registry.collector_is_cleared("reddit", today=date(2026, 9, 25))
