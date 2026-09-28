from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import models
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


def test_public_bolpatra_url_is_not_cleared_for_procurement_discovery(db):
    bolpatra_url = "https://bolpatra.gov.np/"
    ted_url = "https://api.ted.europa.eu/v3/notices/search"

    assert registry.clearance_for_url(bolpatra_url) is None
    assert registry.clearance_for_url(ted_url) is None
    assert registry.capabilities_for_requirement("procurement_demand_discovery") == ()
    with pytest.raises(PermissionError, match="not cleared"):
        registry.authorize_request(
            bolpatra_url,
            collector="web",
            db=db,
            today=date(2026, 9, 28),
        )
    with pytest.raises(PermissionError, match="not cleared"):
        registry.authorize_request(
            ted_url,
            collector="ted_procurement",
            db=db,
            today=date(2026, 9, 28),
        )
    assert db.query(models.SourceFetchGate).count() == 0


def test_crossref_api_clearance_is_bounded_and_current(db):
    entry = next(
        item for item in registry.source_clearances()
        if item.collector == "crossref"
    )
    assert entry.url == "https://api.crossref.org/works"
    assert entry.geographies == ("GLOBAL",)
    assert entry.min_interval_seconds == 60
    assert registry.collector_is_cleared("crossref", today=date(2026, 9, 27))
    assert not registry.collector_is_cleared("crossref", today=date(2026, 10, 28))

    authorization = registry.authorize_request(
        entry.url,
        collector="crossref",
        db=db,
        today=date(2026, 9, 27),
        now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
    )
    assert authorization.entry == entry
    with pytest.raises(registry.SourceRateLimitError):
        registry.authorize_request(
            entry.url,
            collector="crossref",
            db=db,
            today=date(2026, 9, 27),
            now=datetime(2026, 9, 27, 12, 0, 59, tzinfo=timezone.utc),
        )


def test_crossref_clearance_is_documented_in_public_source_register():
    entry = next(
        item for item in registry.source_clearances()
        if item.collector == "crossref"
    )
    source_register = Path(__file__).resolve().parents[2] / "docs" / "PUBLIC_SOURCES.md"
    register_text = source_register.read_text()

    assert entry.url in register_text
    assert all(
        reference in register_text
        if reference.startswith("https://")
        else (source_register.parents[1] / reference).exists()
        for reference in entry.evidence_references
    )
