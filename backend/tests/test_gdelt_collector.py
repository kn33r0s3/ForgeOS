from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import (
    collector_runner,
    opportunity_engine,
    research_planner,
    research_task_engine,
    source_clearance_registry,
)
from app.services.collectors import gdelt
from app.services.observer_engine import ObserverEngine
from app.services.research_evidence_assessment import gdelt_requirement_eligibility

QUERY = '("supply chain" OR "logistics")'
ARTICLES = {
    "articles": [
        {
            "url": "https://news.example.org/agriculture-update",
            "title": "Small repair firms discuss appointment scheduling",
            "seendate": "20260927T123000Z",
            "domain": "news.example.org",
            "language": "English",
            "sourcecountry": "United States",
            "body": "This article body must never be copied.",
            "url_mobile": "https://m.example.org/ignored",
        },
        {
            "url": "https://journal.example.net/supply-chain",
            "title": "Supply chain update",
            "seendate": "20260926T110000Z",
            "domain": "journal.example.net",
            "language": "English",
            "sourcecountry": "United Kingdom",
        },
    ]
}


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.payload


def _mock_gdelt(monkeypatch, db, payload=ARTICLES):
    entry = next(
        item for item in source_clearance_registry.source_clearances()
        if item.collector == "gdelt_doc"
    )
    authorization = source_clearance_registry.CollectionAuthorization(
        entry=entry,
        reserved_at=datetime.now(timezone.utc),
    )
    requests = []

    class _Opener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            return _Response(payload)

    monkeypatch.setattr(gdelt, "_verify_live_policy", lambda _entry: None)
    monkeypatch.setattr(gdelt.urllib.request, "build_opener", lambda *_handlers: _Opener())
    monkeypatch.setattr(
        source_clearance_registry,
        "authorize_request",
        lambda *_args, **_kwargs: authorization,
    )
    return entry, authorization, requests


def _create_gdelt_task(db, question_text, query=QUERY):
    question = models.ResearchQuestion(question=question_text)
    db.add(question)
    db.commit()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="gdelt_doc",
        query=json.dumps({"query": query, "timespan": "1w", "max_records": 5}, sort_keys=True),
        objective="Observe GDELT media coverage metadata only.",
    )
    return question, task


def test_gdelt_clearance_is_bounded_documented_and_paced(db):
    entry = next(
        item for item in source_clearance_registry.source_clearances()
        if item.collector == "gdelt_doc"
    )

    assert entry.registry_id == "gdelt-doc-api-v2"
    assert entry.url == gdelt.API_URL
    assert entry.allowed_operation == "search_bounded_article_metadata"
    assert entry.allowed_fields == ("url", "title", "seendate", "domain", "language", "sourcecountry")
    assert entry.license_tag == (
        "GDELT Open Data (Unlimited reuse with attribution to "
        "https://www.gdeltproject.org/)"
    )
    assert entry.min_interval_seconds == 5
    assert entry.supports_requirements == (
        "media_coverage_observation",
        "recent_event_signal",
        "public_reporting_velocity",
    )
    assert source_clearance_registry.collector_is_cleared(
        "gdelt_doc", today=date(2026, 9, 27)
    )
    assert source_clearance_registry.capabilities_for_requirement(
        "media_coverage_observation", today=date(2026, 9, 27)
    ) == (entry,)
    assert not source_clearance_registry.capabilities_for_requirement(
        "buyer_willingness_to_pay", today=date(2026, 9, 27)
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

    first = source_clearance_registry.authorize_request(
        entry.url,
        collector=entry.collector,
        db=db,
        today=date(2026, 9, 27),
        now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
    )
    assert first.entry == entry
    with pytest.raises(source_clearance_registry.SourceRateLimitError):
        source_clearance_registry.authorize_request(
            entry.url,
            collector=entry.collector,
            db=db,
            today=date(2026, 9, 27),
            now=datetime(2026, 9, 27, 12, 0, 4, tzinfo=timezone.utc),
        )


def test_gdelt_parser_stores_only_metadata_and_uses_bounded_request(db, monkeypatch):
    entry, authorization, requests = _mock_gdelt(monkeypatch, db)
    items = gdelt.fetch_gdelt_signals(
        QUERY,
        timespan="1w",
        max_records=1,
        authorization=authorization,
    )

    assert len(items) == 1
    item = items[0]
    expected_id = hashlib.sha256(
        f"{ARTICLES['articles'][0]['url']}{ARTICLES['articles'][0]['seendate']}{QUERY}".encode()
    ).hexdigest()
    assert item["external_id"] == expected_id
    assert item["content"] == (
        "Title: Small repair firms discuss appointment scheduling | "
        "Domain: news.example.org | Date: 20260927T123000Z"
    )
    assert item["canonical_url"] == ARTICLES["articles"][0]["url"]
    provenance = item["provenance"]
    assert provenance["source_registry_id"] == entry.registry_id
    assert provenance["source_type"] == "gdelt_doc"
    assert provenance["source_id"] == expected_id
    assert provenance["traceable"] is True
    assert provenance["metadata_only"] is True
    assert provenance["attribution"] == "GDELT Project (https://www.gdeltproject.org/)"
    assert provenance["domain"] == "news.example.org"
    assert provenance["language"] == "English"
    assert provenance["country"] == "United States"
    assert provenance["sourcecountry"] == "United States"
    assert provenance["reported_result_count"] == 1
    assert provenance["max_records"] == 1
    assert provenance["result_set_capped"] is True
    assert provenance["article_body_fetched"] is False
    assert provenance["publisher_page_fetched"] is False
    assert "body" not in provenance
    assert "This article body" not in json.dumps(item)

    requested = requests[0][0]
    parsed = urllib.parse.urlparse(requested.full_url)
    params = urllib.parse.parse_qs(parsed.query)
    assert set(params) == {"query", "mode", "maxrecords", "format", "timespan"}
    assert params == {
        "query": [QUERY],
        "mode": ["artlist"],
        "maxrecords": ["1"],
        "format": ["json"],
        "timespan": ["1w"],
    }


def test_gdelt_rejects_overbroad_limits_modes_and_missing_authorization():
    with pytest.raises(ValueError, match="max_records"):
        gdelt.fetch_gdelt_signals(QUERY, max_records=26)
    with pytest.raises(ValueError, match="timespan"):
        gdelt.fetch_gdelt_signals(QUERY, timespan="1y")
    with pytest.raises(ValueError, match="bounded query options"):
        gdelt._parse_task_query(
            json.dumps({"query": QUERY, "timespan": "1w", "max_records": 5, "mode": "scrape"})
        )
    with pytest.raises(PermissionError, match="authorization"):
        gdelt.fetch_gdelt_signals(QUERY)


def test_gdelt_http_429_defers_task_without_consuming_attempt(db, monkeypatch):
    entry, authorization, _requests = _mock_gdelt(monkeypatch, db)

    class _RateLimitedOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {},
                None,
            )

    monkeypatch.setattr(
        gdelt.urllib.request,
        "build_opener",
        lambda *_handlers: _RateLimitedOpener(),
    )
    sleeps = []
    monkeypatch.setattr(gdelt.time, "sleep", sleeps.append)
    question, task = _create_gdelt_task(db, "GDELT recent media coverage")

    result = collector_runner.execute_task(db, task)
    db.refresh(task)
    db.refresh(question)

    assert result["status"] == "planned"
    assert result["deferred"] is True
    assert task.status == "planned"
    assert task.attempts == 0
    assert sleeps == [5, 10]
    assert db.query(models.Signal).filter_by(source="gdelt_doc").count() == 0
    assert db.query(models.Evidence).filter_by(source="gdelt_doc").count() == 0
    assert db.query(models.ResearchTaskEvent).filter_by(
        task_id=task.id,
        event_type="deferred",
    ).count() == 1


def test_gdelt_retries_429_with_exponential_backoff(db, monkeypatch):
    _entry, authorization, _requests = _mock_gdelt(monkeypatch, db)
    sleeps = []

    class _RetryingOpener:
        def __init__(self):
            self.calls = 0

        def open(self, request, timeout):
            self.calls += 1
            if self.calls < 3:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    {},
                    None,
                )
            return _Response(ARTICLES)

    opener = _RetryingOpener()
    monkeypatch.setattr(gdelt.urllib.request, "build_opener", lambda *_handlers: opener)
    monkeypatch.setattr(gdelt.time, "sleep", sleeps.append)

    items = gdelt.fetch_gdelt_signals(
        QUERY,
        max_records=5,
        authorization=authorization,
    )

    assert len(items) == 2
    assert opener.calls == 3
    assert sleeps == [5, 10]


def test_gdelt_epistemic_requirements_bound_velocity_and_reject_commercial_claims():
    provenance = {
        "source_registry_id": "gdelt-doc-api-v2",
        "source_type": "gdelt_doc",
        "metadata_only": True,
        "traceable": True,
        "canonical_url": "https://news.example.org/article",
        "domain": "news.example.org",
        "published_at": "2026-09-27T12:30:00+00:00",
        "retrieved_at": "2026-09-27T12:35:00+00:00",
        "query": QUERY,
        "attribution": "GDELT Project (https://www.gdeltproject.org/)",
        "article_body_fetched": False,
        "timespan": "1w",
        "reported_result_count": 2,
        "max_records": 5,
        "result_set_capped": False,
    }

    eligible, reason = gdelt_requirement_eligibility("media_coverage_observation", provenance)
    assert eligible is True
    assert reason == "attributable_observation_of_media_coverage_only"
    for requirement_id in ("recent_event_signal",):
        assert gdelt_requirement_eligibility(requirement_id, provenance)[0] is True
    for requirement_id in (
        "buyer_willingness_to_pay",
        "product_demand",
        "customer_pain",
        "market_size",
        "financial_viability",
    ):
        eligible, _reason = gdelt_requirement_eligibility(requirement_id, provenance)
        assert eligible is False
    eligible, reason = gdelt_requirement_eligibility("public_reporting_velocity", provenance)
    assert eligible is True
    assert reason == "bounded_gdelt_indexed_article_count_over_declared_timespan"
    capped = {**provenance, "reported_result_count": 25, "max_records": 25, "result_set_capped": True}
    eligible, reason = gdelt_requirement_eligibility("public_reporting_velocity", capped)
    assert eligible is False
    assert reason == "capped_or_unbounded_gdelt_result_set_cannot_measure_reporting_velocity"


def test_planner_can_satisfy_only_uncapped_gdelt_reporting_velocity(db, monkeypatch):
    _mock_gdelt(monkeypatch, db)
    question = models.ResearchQuestion(
        question="Measure public reporting velocity for repair-shop scheduling."
    )
    db.add(question)
    db.commit()

    planned = research_planner.plan_tasks_for_question(db, question)
    task = next(item for item in planned if item.source == "gdelt_doc")
    result = collector_runner.execute_task(db, task)
    db.refresh(question)

    velocity_requirement = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "public_reporting_velocity"
    )
    assert result["status"] == "completed"
    assert velocity_requirement["status"] == "satisfied"
    assert len(velocity_requirement["evidence_ids"]) == 2


def test_planner_media_coverage_does_not_clear_demand_or_create_opportunity(db, monkeypatch):
    _entry, _authorization, _requests = _mock_gdelt(monkeypatch, db)
    question = models.ResearchQuestion(
        question="What recent media coverage exists for repair-shop appointment scheduling?"
    )
    db.add(question)
    db.commit()
    planned = research_planner.plan_tasks_for_question(db, question)
    task = next(item for item in planned if item.source == "gdelt_doc")
    result = collector_runner.execute_task(db, task)
    db.refresh(question)

    assert result["status"] == "completed"
    coverage_requirement = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "media_coverage_observation"
    )
    assert coverage_requirement["status"] == "satisfied", (
        coverage_requirement,
        result,
        [(signal.source, signal.id, signal.external_id) for signal in db.query(models.Signal).all()],
        [(item.source, item.id, item.provenance) for item in db.query(models.Evidence).all()],
    )
    assert len(coverage_requirement["evidence_ids"]) == 2
    assert len({signal.canonical_url for signal in db.query(models.Signal).filter_by(source="gdelt_doc")}) == 2
    for requirement_id in ("buyer_willingness_to_pay", "problem_incidence"):
        requirement = next(
            item for item in question.research_plan["requirements"]
            if item["id"] == requirement_id
        )
        assert requirement["status"] == "terminal_unresolved"

    signals = db.query(models.Signal).filter_by(source="gdelt_doc").all()
    assert len(signals) == 2
    pattern = models.Pattern(
        title="Potential repair-shop market",
        description="A market claim based only on news titles.",
        frequency=25,
        confidence_score=99,
        origin_signal_ids=",".join(str(signal.id) for signal in signals),
    )
    db.add(pattern)
    db.commit()
    assert opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern) is None
    assert all(
        opportunity_engine.generate_opportunity_from_signal_if_strong(db, signal) is None
        for signal in signals
    )
    assert db.query(models.Opportunity).count() == 0
    candidate = models.Opportunity(
        problem="Existing candidate grounded in non-GDELT evidence.",
        pattern_id=pattern.id,
        status="identified",
        market_confidence=0,
        uncertainty=100,
    )
    db.add(candidate)
    db.commit()

    assert opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern) is None
    db.refresh(candidate)
    assert candidate.status == "identified"
    assert candidate.market_confidence == 0
    assert candidate.uncertainty == 100


def test_repeated_gdelt_queries_are_idempotent_across_tasks(db, monkeypatch):
    _mock_gdelt(monkeypatch, db)
    first_question, first_task = _create_gdelt_task(db, "Media coverage for supply chains")
    second_question, second_task = _create_gdelt_task(db, "Recent reporting about agriculture")

    first = collector_runner.execute_task(db, first_task)
    second = collector_runner.execute_task(db, second_task)

    assert first["evidence_found"] == second["evidence_found"] == 2
    assert db.query(models.Signal).filter_by(source="gdelt_doc").count() == 2, (
        first,
        second,
        [(signal.source, signal.id, signal.external_id) for signal in db.query(models.Signal).all()],
    )
    assert db.query(models.Evidence).filter_by(source="gdelt_doc").count() == 2
    assert first_question.id != second_question.id


@pytest.mark.skipif(
    os.environ.get("FORGEOS_LIVE_GDELT_TEST") != "1",
    reason="Set FORGEOS_LIVE_GDELT_TEST=1 to make one bounded external API request.",
)
def test_live_gdelt_query_persists_metadata_through_sqlite_reopen():
    from app.services import source_manager

    with tempfile.TemporaryDirectory(prefix="forgeos-gdelt-") as temporary_dir:
        database_path = Path(temporary_dir) / "gdelt.sqlite3"
        engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = session_factory()
        source_manager.seed_default_sources(db)
        entry = next(
            item for item in source_clearance_registry.source_clearances()
            if item.collector == "gdelt_doc"
        )
        authorization = source_clearance_registry.authorize_request(
            entry.url,
            collector=entry.collector,
            db=db,
        )
        try:
            items = gdelt.fetch_gdelt_signals(
                QUERY,
                timespan="1w",
                max_records=5,
                authorization=authorization,
            )
        except source_clearance_registry.SourceRateLimitError as exc:
            db.close()
            engine.dispose()
            pytest.skip(f"GDELT provider rate-limited the one live request: {exc}")
        assert items, "The bounded live query returned no article metadata to persist."
        assert len(items) <= 5
        observer = ObserverEngine(db)
        for item in items:
            normalized = gdelt.GdeltCollector().normalize(item)
            observer.observe(normalized["content"], source="gdelt_doc", metadata=normalized)
        db.commit()
        evidence_count = db.query(models.Evidence).filter_by(source="gdelt_doc").count()
        signal_count = db.query(models.Signal).filter_by(source="gdelt_doc").count()
        assert evidence_count == signal_count == len(items)
        for signal in db.query(models.Signal).filter_by(source="gdelt_doc").all():
            provenance = json.loads(signal.provenance)
            assert signal.canonical_url.startswith("https://")
            assert provenance["domain"]
            assert provenance["source_registry_id"] == "gdelt-doc-api-v2"
            assert provenance["article_body_fetched"] is False
        db.close()
        engine.dispose()

        reopened_engine = create_engine(f"sqlite:///{database_path}")
        reopened = sessionmaker(bind=reopened_engine)()
        try:
            assert reopened.query(models.Evidence).filter_by(source="gdelt_doc").count() == evidence_count
            assert reopened.query(models.Signal).filter_by(source="gdelt_doc").count() == signal_count
        finally:
            reopened.close()
            reopened_engine.dispose()
