from datetime import date, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import pytest
from sqlalchemy import event, inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import (
    collector_runner,
    opportunity_engine,
    research_planner,
    research_task_engine,
    source_clearance_registry,
)
from app.services.collectors import openalex
from app.services.observer_engine import ObserverEngine
from app.services.research_evidence_assessment import openalex_requirement_eligibility

QUERY = "postharvest loss smallholder farmers Nepal"
WORKS = {
    "meta": {"count": 2, "per_page": 2},
    "results": [
        {
            "id": "https://openalex.org/W1234567890",
            "doi": "https://doi.org/10.1234/example.1",
            "title": "Postharvest storage research",
            "publication_year": 2024,
            "cited_by_count": 17,
            "authorships": [
                {
                    "author": {
                        "id": "https://openalex.org/A123",
                        "display_name": "Example Researcher",
                    },
                    "institutions": [
                        {"display_name": "Example University", "country_code": "US"}
                    ],
                    "countries": ["US"],
                }
            ],
            "concepts": [
                {"id": "https://openalex.org/C123", "display_name": "Postharvest technology"}
            ],
            "primary_location": {
                "is_oa": True,
                "pdf_url": "https://publisher.example/article.pdf",
                "source": {"display_name": "Journal of Example Research"},
            },
            "open_access": {
                "is_oa": True,
                "oa_status": "gold",
                "oa_url": "https://publisher.example/article.pdf",
            },
            "abstract_inverted_index": {
                "This": [0],
                "study": [1],
                "describes": [2],
                "a": [3],
                "storage": [4],
                "intervention": [5],
                "for": [6],
                "smallholders.": [7],
            },
            "relevance_score": 1000,
        },
        {
            "id": "https://openalex.org/W1234567891",
            "doi": None,
            "title": "A second study of grain storage",
            "publication_year": 2022,
            "cited_by_count": 2,
            "authorships": [],
            "concepts": [],
            "primary_location": None,
            "open_access": None,
            "abstract_inverted_index": {"Evidence": [0], "is": [1], "limited.": [2]},
        },
    ],
}


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


def _authorization(db):
    entry = next(
        item for item in source_clearance_registry.source_clearances()
        if item.collector == "openalex"
    )
    return source_clearance_registry.CollectionAuthorization(
        entry=entry,
        reserved_at=datetime.now(timezone.utc),
    )


def _mock_openalex(monkeypatch, db, payload=WORKS):
    authorization = _authorization(db)
    requests = []

    class _Opener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            return _Response(payload)

    monkeypatch.setattr(openalex, "_verify_live_policy", lambda _entry: None)
    monkeypatch.setattr(openalex.urllib.request, "build_opener", lambda *_handlers: _Opener())
    monkeypatch.setattr(
        source_clearance_registry,
        "authorize_request",
        lambda *_args, **_kwargs: authorization,
    )
    return authorization, requests


def _create_openalex_task(db, question, query=QUERY):
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="openalex",
        query=query,
        objective="Retrieve scholarly abstracts as literature observations only.",
    )
    task.results = {
        **(task.results or {}),
        "research_requirement_id": "prior_research",
        "evidence_kind": "openalex_scholarly_abstract",
    }
    db.commit()
    return task


def test_openalex_clearance_registers_exact_https_scope_and_pacing(db, monkeypatch):
    entry = next(
        item for item in source_clearance_registry.source_clearances()
        if item.collector == "openalex"
    )
    assert entry.registry_id == "openalex-public-works-cc0"
    assert entry.url == openalex.API_URL
    assert entry.hostname == "api.openalex.org"
    assert entry.min_interval_seconds == 1
    assert entry.allowed_operation == "search_cc0_work_metadata_and_abstracts"
    assert "abstract_inverted_index" in entry.allowed_fields
    assert entry.license_tag == "CC0 Public Domain Dedication (OpenAlex Dataset Metadata)"
    assert entry.supports_requirements == (
        "scholarly_evidence",
        "prior_research",
        "documented_intervention",
        "literature_existence",
    )
    assert source_clearance_registry.collector_is_cleared("openalex", today=date(2026, 9, 27))
    assert not source_clearance_registry.capabilities_for_requirement(
        "buyer_willingness_to_pay", today=date(2026, 9, 27)
    )
    assert openalex._validate_max_records(100, "keyword") == 100
    assert openalex._validate_max_records(50, "semantic") == 50
    first_slot = source_clearance_registry.authorize_request(
        openalex.API_URL,
        collector="openalex",
        db=db,
        today=date(2026, 9, 27),
        now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
    )
    assert first_slot.entry == entry
    with pytest.raises(source_clearance_registry.SourceRateLimitError):
        source_clearance_registry.authorize_request(
            openalex.API_URL,
            collector="openalex",
            db=db,
            today=date(2026, 9, 27),
            now=datetime(2026, 9, 27, 12, 0, 0, 500000, tzinfo=timezone.utc),
        )

    requested = []

    def policy_urlopen(request, timeout):
        requested.append(request.full_url)
        if request.full_url == openalex.ROBOTS_URL:
            return _Response({"robots": "not relevant"})
        return _Response({"terms": "All data is CC0"})

    monkeypatch.setattr(openalex.urllib.request, "urlopen", policy_urlopen)
    entry = source_clearance_registry.clearance_for_url(openalex.API_URL)
    openalex._verify_live_policy(entry)
    assert requested == [openalex.ROBOTS_URL, openalex.TERMS_URL]


def test_openalex_rejects_unsafe_modes_limits_and_external_pdf_redirects():
    with pytest.raises(ValueError, match="max_records"):
        openalex._validate_max_records(101, "keyword")
    with pytest.raises(ValueError, match="search_mode"):
        openalex._validate_search_mode("search")
    with pytest.raises(ValueError, match="query"):
        openalex._validate_query(" " * 501)
    with pytest.raises(ValueError, match="max_records"):
        openalex._validate_max_records(51, "semantic")
    assert len(openalex._validate_query("x" * 2100, "semantic")) == 2000
    assert research_planner._openalex_search_mode(
        "What prior research exists about OpenAlex?",
        "prior research exists about OpenAlex",
    ) == "keyword"
    assert research_planner._openalex_search_mode(
        "What prior research exists about agricultural interventions?",
        "prior research exists about agricultural interventions",
    ) == "semantic"
    assert research_planner._openalex_search_mode(
        "Find prior studies by Jane Example.",
        "prior studies by Jane Example",
    ) == "keyword"
    assert research_planner._openalex_search_mode(
        "Find prior research for DOI 10.1234/example.7.",
        "prior research for DOI 10.1234/example.7",
    ) == "keyword"

    request = urllib.request.Request(f"{openalex.API_URL}?search=grain")
    with pytest.raises(RuntimeError, match="outside the cleared Works API endpoint"):
        openalex._SameWorksEndpointRedirect().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://publisher.example/article.pdf",
        )


def test_openalex_reconstructs_abstract_and_projects_only_safe_metadata(db, monkeypatch):
    authorization, requests = _mock_openalex(monkeypatch, db)
    items = openalex.fetch_openalex_works(
        QUERY,
        max_records=2,
        authorization=authorization,
    )

    assert len(items) == 2
    item = items[0]
    expected_id = hashlib.sha256(
        f"openalex:{WORKS['results'][0]['id']}".encode()
    ).hexdigest()
    assert item["external_id"] == expected_id
    assert item["canonical_url"] == WORKS["results"][0]["id"]
    assert item["content"] == (
        "Scholarly work: Postharvest storage research | Publication year: 2024 | "
        "Abstract: This study describes a storage intervention for smallholders. | "
        "OpenAlex cited-by count: 17"
    )
    provenance = item["provenance"]
    assert provenance["openalex_id"] == WORKS["results"][0]["id"]
    assert provenance["doi"] == "https://doi.org/10.1234/example.1"
    assert provenance["publication_year"] == 2024
    assert provenance["cited_by_count"] == 17
    assert provenance["concepts"] == [
        {"id": "https://openalex.org/C123", "name": "Postharvest technology"}
    ]
    assert provenance["authorships"][0]["countries"] == ["US"]
    assert provenance["abstract_reconstructed"] is True
    assert provenance["geographic_scope_status"] == (
        "not_assessed_from_affiliations_or_retrieval_relevance"
    )
    assert provenance["temporal_scope_status"] == "publication_year_only_not_study_period"
    assert provenance["retrieval_relevance_is_not_empirical_support"] is True
    assert provenance["external_pdf_fetched"] is False
    assert provenance["publisher_page_fetched"] is False
    assert provenance["license"] == "CC0"
    assert "publisher.example" not in json.dumps(item)
    assert "relevance_score" not in json.dumps(item)

    request, timeout = requests[0]
    assert request.full_url.startswith(f"{openalex.API_URL}?")
    assert timeout == openalex.TIMEOUT_SECONDS
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
    assert params["search"] == [QUERY]
    assert params["per_page"] == ["2"]
    assert "search.semantic" not in params
    assert "abstract_inverted_index" in params["select"][0].split(",")
    assert request.get_header("User-agent") == openalex.USER_AGENT
    assert "mailto:research@forgeos.local" in request.get_header("User-agent")


def test_openalex_keyword_and_semantic_use_correct_endpoints_and_caps(db, monkeypatch):
    authorization, requests = _mock_openalex(monkeypatch, db)
    openalex.fetch_openalex_works(
        QUERY,
        search_mode="keyword",
        max_records=100,
        authorization=authorization,
    )
    openalex.fetch_openalex_works(
        "x" * 2100,
        search_mode="semantic",
        max_records=50,
        authorization=authorization,
    )

    keyword_params = urllib.parse.parse_qs(urllib.parse.urlsplit(requests[0][0].full_url).query)
    semantic_params = urllib.parse.parse_qs(urllib.parse.urlsplit(requests[1][0].full_url).query)
    assert keyword_params["search"] == [QUERY]
    assert keyword_params["per_page"] == ["100"]
    assert "search.semantic" not in keyword_params
    assert semantic_params["search.semantic"] == ["x" * 2000]
    assert semantic_params["per_page"] == ["50"]
    assert "search" not in semantic_params
    normalized = openalex._normalize_work(
        WORKS["results"][0],
        query=QUERY,
        search_mode="semantic",
        request_url=requests[1][0].full_url,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        entry=authorization.entry,
    )
    assert normalized["provenance"]["search_mode"] == "semantic"
    assert normalized["identity_key"] == f"openalex:{normalized['external_id']}"


def test_openalex_reconstruct_abstract_rejects_malformed_positions():
    assert openalex.reconstruct_abstract({"one": [1], "zero": [0]}) == "zero one"
    with pytest.raises(RuntimeError, match="duplicate positions"):
        openalex.reconstruct_abstract({"first": [0], "second": [0]})
    with pytest.raises(RuntimeError, match="invalid position"):
        openalex.reconstruct_abstract({"bad": [100001]})
    with pytest.raises(RuntimeError, match="missing a title"):
        openalex._normalize_work(
            {"id": "https://openalex.org/W1234567890", "title": ""},
            query=QUERY,
            search_mode="search",
            request_url=openalex.API_URL,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            entry=_authorization(None).entry,
        )


def test_openalex_429_uses_bounded_exponential_backoff(db, monkeypatch):
    authorization, _requests = _mock_openalex(monkeypatch, db)
    sleeps = []

    class _RetryingOpener:
        def __init__(self):
            self.calls = 0

        def open(self, request, timeout):
            self.calls += 1
            if self.calls < 3:
                raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
            return _Response(WORKS)

    opener = _RetryingOpener()
    monkeypatch.setattr(openalex.urllib.request, "build_opener", lambda *_handlers: opener)
    monkeypatch.setattr(openalex.time, "sleep", sleeps.append)
    items = openalex.fetch_openalex_works(QUERY, authorization=authorization)
    assert len(items) == 2
    assert opener.calls == 3
    assert sleeps == [1, 2]


def test_openalex_fails_closed_on_server_timeout_and_malformed_json(db, monkeypatch):
    authorization = _authorization(db)
    monkeypatch.setattr(openalex, "_verify_live_policy", lambda _entry: None)

    class _FailingOpener:
        def __init__(self, failure):
            self.failure = failure

        def open(self, request, timeout):
            if isinstance(self.failure, BaseException):
                raise self.failure
            return self.failure

    malformed_json = _Response({})
    malformed_json.payload = b"not-json"
    failures = (
        (
            urllib.error.HTTPError(f"{openalex.API_URL}?search=x", 500, "Server Error", {}, None),
            "HTTP 500",
        ),
        (TimeoutError("request timed out"), "request failed"),
        (urllib.error.URLError(OSError("DNS lookup failed")), "request failed"),
        (malformed_json, "invalid JSON"),
    )
    for failure, message in failures:
        monkeypatch.setattr(
            openalex.urllib.request,
            "build_opener",
            lambda *_handlers, failure=failure: _FailingOpener(failure),
        )
        with pytest.raises(RuntimeError, match=message):
            openalex.fetch_openalex_works(QUERY, authorization=authorization)


def test_openalex_abstracts_satisfy_scholarly_only_and_not_local_or_commercial_claims():
    provenance = {
        "source_registry_id": "openalex-public-works-cc0",
        "source_type": "openalex",
        "license": "CC0",
        "traceable": True,
        "openalex_id": "https://openalex.org/W1234567890",
        "title": "Postharvest storage research",
        "abstract": "This study describes a storage intervention.",
        "abstract_reconstructed": True,
        "query": QUERY,
        "geographic_scope_status": "not_assessed_from_affiliations_or_retrieval_relevance",
        "temporal_scope_status": "publication_year_only_not_study_period",
        "retrieval_relevance_is_not_empirical_support": True,
    }
    for requirement in ("scholarly_evidence", "prior_research", "documented_intervention"):
        assert openalex_requirement_eligibility(requirement, provenance)[0] is True
    assert openalex_requirement_eligibility("literature_existence", {
        **provenance, "abstract": None, "abstract_reconstructed": False
    })[0] is True
    for requirement in (
        "buyer_willingness_to_pay",
        "customer_pain",
        "local_market_size",
        "revenue_potential",
        "product_demand",
        "local_applicability",
        "study_context_alignment",
    ):
        assert openalex_requirement_eligibility(requirement, provenance)[0] is False
    assert openalex_requirement_eligibility(
        "prior_research", {**provenance, "geographic_scope_status": "aligned"}
    )[0] is False
    semantic_provenance = {**provenance, "search_mode": "semantic"}
    assert openalex_requirement_eligibility(
        "scholarly_evidence", semantic_provenance
    )[0] is True
    assert openalex_requirement_eligibility(
        "buyer_willingness_to_pay", semantic_provenance
    )[0] is False


def test_planner_keeps_local_geographic_claim_unresolved_with_openalex_literature(db, monkeypatch):
    _authorization, _requests = _mock_openalex(monkeypatch, db)
    question = models.ResearchQuestion(
        question="What prior research exists about postharvest loss in Nepal in 2022?"
    )
    db.add(question)
    db.commit()
    planned = research_planner.plan_tasks_for_question(db, question)
    task = next(item for item in planned if item.source == "openalex")
    result = collector_runner.execute_task(db, task)
    db.refresh(question)

    scholarly = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "scholarly_evidence"
    )
    buyer = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "buyer_willingness_to_pay"
    )
    scholarly_node = next(
        item for item in question.research_plan["orchestration_requirements"]
        if item["requirement_id"] == "phenomenon_existence"
    )
    assert result["status"] == "completed"
    assert scholarly["status"] == "satisfied"
    assert len(scholarly["evidence_ids"]) == 2
    assert buyer["status"] == "terminal_unresolved"
    assert "local_applicability" in scholarly_node["unresolved_dimensions"]
    assert "study_period" in scholarly_node["unresolved_dimensions"]
    assert db.query(models.Opportunity).count() == 0


def test_semantic_openalex_task_satisfies_literature_only(db, monkeypatch):
    _authorization, requests = _mock_openalex(monkeypatch, db)
    question = models.ResearchQuestion(
        question="What prior research exists about postharvest losses?"
    )
    db.add(question)
    db.commit()
    planned = research_planner.plan_tasks_for_question(db, question)
    task = next(item for item in planned if item.source == "openalex")
    task.results = {**task.results, "search_mode": "semantic"}
    db.commit()

    result = collector_runner.execute_task(db, task)
    db.refresh(question)
    params = urllib.parse.parse_qs(
        urllib.parse.urlsplit(requests[0][0].full_url).query
    )

    scholarly = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "scholarly_evidence"
    )
    buyer = next(
        item for item in question.research_plan["requirements"]
        if item["id"] == "buyer_willingness_to_pay"
    )
    assert result["status"] == "completed"
    assert params["search.semantic"] == [task.results["derived_retrieval_query"]]
    assert scholarly["status"] == "satisfied"
    assert buyer["status"] == "terminal_unresolved"
    assert db.query(models.Opportunity).count() == 0


def test_openalex_repeated_queries_create_no_duplicate_evidence_or_signals(db, monkeypatch):
    _authorization, _requests = _mock_openalex(monkeypatch, db)
    question = models.ResearchQuestion(question="What prior research exists on postharvest losses?")
    db.add(question)
    second_question = models.ResearchQuestion(question="Find academic papers on postharvest losses.")
    db.add(second_question)
    db.commit()
    first = _create_openalex_task(db, question)
    second = _create_openalex_task(db, second_question)

    first_result = collector_runner.execute_task(db, first)
    second_result = collector_runner.execute_task(db, second)

    assert first_result["evidence_found"] == second_result["evidence_found"] == 2
    assert db.query(models.Signal).filter_by(source="openalex").count() == 2
    assert db.query(models.Evidence).filter_by(source="openalex").count() == 2


def test_openalex_concurrent_signal_and_evidence_writes_are_idempotent(tmp_path):
    from app.services import source_manager

    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-openalex.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_busy_timeout(connection, _record):
        connection.execute("PRAGMA busy_timeout=10000")

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with session_factory() as setup_db:
        source_manager.seed_default_sources(setup_db)

    item = {
        **openalex._normalize_work(
            WORKS["results"][0],
            query=QUERY,
            search_mode="keyword",
            request_url=openalex.API_URL,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            entry=_authorization(None).entry,
        ),
        "source": "openalex",
    }

    def observe_once(_):
        barrier.wait()
        with session_factory() as session:
            signal = ObserverEngine(session).observe(
                item["content"], source="openalex", metadata=item
            )
            return signal.id

    barrier = Barrier(5)
    with ThreadPoolExecutor(max_workers=5) as executor:
        signal_ids = list(executor.map(observe_once, range(5)))

    with session_factory() as verify_db:
        assert len(set(signal_ids)) == 1
        assert verify_db.query(models.Signal).filter_by(source="openalex").count() == 1
        assert verify_db.query(models.Evidence).filter_by(source="openalex").count() == 1
    engine.dispose()


def test_openalex_task_translation_and_evidence_preserve_question_context(db, monkeypatch):
    _mock_openalex(monkeypatch, db)
    original_question = (
        'What prior research exists on "postharvest loss" among smallholder farmers in Nepal?'
    )
    question = models.ResearchQuestion(question=original_question)
    db.add(question)
    db.commit()

    tasks = research_planner.plan_tasks_for_question(db, question)
    task = next(item for item in tasks if item.source == "openalex")
    assert task.results["original_research_question"] == original_question
    assert task.results["derived_retrieval_query"] == task.query
    assert task.results["search_mode"] == "keyword"
    assert task.results["geographic_qualification"] == "Nepal"
    assert task.results["population_qualification"] == "smallholder farmers"
    assert isinstance(task.results["unresolved_dimensions"], list)

    collector_runner.execute_task(db, task)
    evidence = db.query(models.Evidence).filter_by(source="openalex").first()
    provenance = json.loads(evidence.provenance)
    assert provenance["original_research_question"] == original_question
    assert provenance["derived_retrieval_query"] == task.query
    assert provenance["search_mode"] == "keyword"
    assert provenance["geographic_qualification"] == "Nepal"
    assert provenance["population_qualification"] == "smallholder farmers"
    assert provenance["unresolved_dimensions"] == task.results["unresolved_dimensions"]


def test_openalex_broad_planner_request_uses_semantic_mode(db):
    question = models.ResearchQuestion(
        question=(
            "What prior research exists about postharvest interventions for "
            "smallholder farmers in Nepal?"
        )
    )
    db.add(question)
    db.commit()

    tasks = research_planner.plan_tasks_for_question(db, question)
    task = next(item for item in tasks if item.source == "openalex")

    assert task.results["search_mode"] == "semantic"
    assert task.results["original_research_question"] == question.question
    assert task.results["geographic_qualification"] == "Nepal"
    assert task.results["population_qualification"] == "smallholder farmers"


def test_openalex_empty_result_is_recorded_without_advancing_claim_or_requirements(
    db, monkeypatch
):
    _mock_openalex(monkeypatch, db, payload={"results": []})
    question = models.ResearchQuestion(
        question="What prior research exists about postharvest losses?"
    )
    db.add(question)
    db.commit()
    research_planner.plan_tasks_for_question(db, question)
    task = _create_openalex_task(db, question)
    claim = models.Claim(
        statement="OpenAlex empty results cannot update this claim.",
        normalized_statement="openalex empty results cannot update this claim",
        epistemic_state="unresolved",
    )
    db.add(claim)
    db.commit()
    task.claim_id = claim.id
    db.commit()
    claim_evaluations = []
    monkeypatch.setattr(
        research_task_engine,
        "evaluate_claim_after_research",
        lambda *_args, **_kwargs: claim_evaluations.append(True),
    )

    result = collector_runner.execute_task(db, task)
    db.refresh(question)
    db.refresh(task)

    assert result["status"] == "needs_research", result
    observation = task.results["retrieval_observation"]
    assert observation["source"] == "openalex"
    assert observation["source_registry_id"] == "openalex-public-works-cc0"
    assert observation["source_accessed"] is True
    assert observation["query"] == task.query
    assert observation["search_mode"] == "keyword"
    assert observation["source_records_returned"] == 0
    assert observation["returned_works"] == 0
    assert observation["outcome"] == "valid_empty_retrieval"
    assert observation["claim_effect"] == "none"
    assert isinstance(observation["retrieved_at"], str)
    observation_signal = (
        db.query(models.Signal)
        .filter_by(source="openalex", collection_status="valid_empty_retrieval")
        .one()
    )
    assert "0 scholarly works found" in observation_signal.content
    assert observation_signal.identity_key.startswith("openalex:empty:")
    assert json.loads(observation_signal.provenance)["claim_effect"] == "none"
    assert db.query(models.Signal).filter_by(source="openalex").count() == 1
    assert db.query(models.Evidence).filter_by(source="openalex").count() == 0
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Experiment).count() == 0
    assert claim_evaluations == []
    db.refresh(claim)
    assert claim.epistemic_state == "unresolved"
    assert all(
        requirement["status"] not in {"satisfied", "research_completed"}
        for requirement in question.research_plan["requirements"]
        if requirement["id"] in {"prior_research", "scholarly_evidence"}
    )
    assert question.research_plan["status"] != "research_completed"


def test_signal_identity_migration_preserves_duplicate_legacy_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-signals.sqlite3'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE signals")
        connection.exec_driver_sql(
            "CREATE TABLE signals (id INTEGER PRIMARY KEY, identity_key VARCHAR, "
            "source VARCHAR NOT NULL, content TEXT NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO signals (id, identity_key, source, content) VALUES "
            "(1, 'openalex:legacy-duplicate', 'openalex', 'first'), "
            "(2, 'openalex:legacy-duplicate', 'openalex', 'second')"
        )

    applied = run_migrations(engine)
    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT id, identity_key, content FROM signals ORDER BY id"
        ).all()
    assert any("preserved 1 duplicate legacy signals" in action for action in applied)
    assert rows == [
        (1, "openalex:legacy-duplicate", "first"),
        (2, None, "second"),
    ]
    assert any(
        index["name"] == "uq_signals_identity_key"
        for index in inspect(engine).get_indexes("signals")
    )
    engine.dispose()


def test_schema_migration_runs_against_populated_test_database(db):
    signal = models.Signal(
        source="openalex",
        source_type="external",
        content="Historical scholarly signal remains.",
        identity_key=None,
    )
    evidence = models.Evidence(
        signal_id=None,
        source="openalex",
        content="Historical scholarly evidence remains.",
        idempotency_key=None,
    )
    db.add_all([signal, evidence])
    db.commit()
    engine = db.get_bind()

    run_migrations(engine)
    assert db.query(models.Signal).filter_by(content=signal.content).count() == 1
    assert db.query(models.Evidence).filter_by(content=evidence.content).count() == 1
    identity_unique = any(
        tuple(constraint["column_names"]) == ("identity_key",)
        for constraint in inspect(engine).get_unique_constraints("signals")
    ) or any(
        index["name"] == "uq_signals_identity_key"
        for index in inspect(engine).get_indexes("signals")
    )
    assert identity_unique


def test_openalex_api_failure_marks_task_failed(db, monkeypatch):
    authorization = _authorization(db)
    monkeypatch.setattr(openalex, "_verify_live_policy", lambda _entry: None)
    monkeypatch.setattr(
        source_clearance_registry,
        "authorize_request",
        lambda *_args, **_kwargs: authorization,
    )

    class _UnavailableOpener:
        def open(self, request, timeout):
            raise TimeoutError("OpenAlex request timed out")

    monkeypatch.setattr(
        openalex.urllib.request,
        "build_opener",
        lambda *_handlers: _UnavailableOpener(),
    )
    question = models.ResearchQuestion(
        question="What prior research exists about postharvest losses?"
    )
    db.add(question)
    db.commit()
    task = _create_openalex_task(db, question)

    result = collector_runner.execute_task(db, task)
    db.refresh(task)

    assert result["status"] == "failed"
    assert task.status == "failed"
    assert "request failed" in task.errors[-1]["error"]
    assert db.query(models.Signal).filter_by(source="openalex").count() == 0
    assert db.query(models.Evidence).filter_by(source="openalex").count() == 0
    assert db.query(models.Opportunity).count() == 0


def test_openalex_invalid_task_mode_fails_before_http_request(db, monkeypatch):
    _authorization, requests = _mock_openalex(monkeypatch, db)
    question = models.ResearchQuestion(
        question="What prior research exists about postharvest losses?"
    )
    db.add(question)
    db.commit()
    task = _create_openalex_task(db, question)
    task.results = {**task.results, "search_mode": "semantic-or-keyword"}
    db.commit()

    result = collector_runner.execute_task(db, task)

    assert result["status"] == "failed"
    assert "search_mode must be" in result["reason"]
    assert requests == []
    assert db.query(models.Evidence).filter_by(source="openalex").count() == 0
    assert db.query(models.Opportunity).count() == 0


def test_openalex_metadata_cannot_create_or_advance_an_opportunity(db, monkeypatch):
    _authorization, _requests = _mock_openalex(monkeypatch, db)
    question = models.ResearchQuestion(question="What prior research exists on postharvest losses?")
    db.add(question)
    db.commit()
    task = _create_openalex_task(db, question)
    collector_runner.execute_task(db, task)

    signals = db.query(models.Signal).filter_by(source="openalex").all()
    pattern = models.Pattern(
        title="Potential grain-storage opportunity",
        description="Abstract and citation count only.",
        frequency=10,
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


@pytest.mark.skipif(
    os.environ.get("FORGEOS_LIVE_OPENALEX_TEST") != "1",
    reason="Set FORGEOS_LIVE_OPENALEX_TEST=1 to make one bounded OpenAlex API request.",
)
def test_live_openalex_query_persists_evidence_and_signals_through_sqlite_reopen():
    from app.services import source_manager

    with tempfile.TemporaryDirectory(prefix="forgeos-openalex-") as temporary_dir:
        database_path = Path(temporary_dir) / "openalex.sqlite3"
        engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = session_factory()
        source_manager.seed_default_sources(db)
        outbound_urls = []
        original_build_opener = openalex.urllib.request.build_opener

        def recording_build_opener(*handlers):
            opener = original_build_opener(*handlers)

            class _RecordingOpener:
                def open(self, request, *args, **kwargs):
                    outbound_urls.append(request.full_url)
                    return opener.open(request, *args, **kwargs)

            return _RecordingOpener()

        openalex.urllib.request.build_opener = recording_build_opener
        try:
            authorization = source_clearance_registry.authorize_request(
                openalex.API_URL,
                collector="openalex",
                db=db,
            )
            items = openalex.fetch_openalex_works(
                QUERY,
                search_mode="semantic",
                max_records=5,
                task_provenance={
                    "original_research_question": QUERY,
                    "derived_retrieval_query": QUERY,
                    "geographic_qualification": "Nepal",
                    "population_qualification": "smallholder farmers",
                    "unresolved_dimensions": ["local_applicability", "buyer_willingness_to_pay"],
                },
                authorization=authorization,
            )
        except source_clearance_registry.SourceRateLimitError as exc:
            db.close()
            engine.dispose()
            pytest.skip(f"OpenAlex provider rate-limited the one live request: {exc}")
        finally:
            openalex.urllib.request.build_opener = original_build_opener
        assert items, "The bounded live OpenAlex query returned no work metadata."
        assert len(items) <= 5
        observer = ObserverEngine(db)
        for item in items:
            normalized = openalex.OpenAlexCollector().normalize(item)
            observer.observe(normalized["content"], source="openalex", metadata=normalized)
        db.commit()

        evidence_rows = db.query(models.Evidence).filter_by(source="openalex").all()
        signal_rows = db.query(models.Signal).filter_by(source="openalex").all()
        assert len(evidence_rows) == len(signal_rows) == len(items)
        for evidence in evidence_rows:
            provenance = json.loads(evidence.provenance)
            assert provenance["openalex_id"].startswith("https://openalex.org/W")
            assert provenance["title"]
            assert provenance["license"] == "CC0"
            assert provenance["source_registry_id"] == "openalex-public-works-cc0"
            assert provenance["external_pdf_fetched"] is False
            assert provenance["publisher_page_fetched"] is False
            assert provenance["abstract_reconstructed"] == bool(provenance["abstract"])
            assert provenance["original_research_question"] == QUERY
            assert provenance["derived_retrieval_query"] == QUERY
            assert provenance["search_mode"] == "semantic"
            assert provenance["geographic_qualification"] == "Nepal"
            assert provenance["population_qualification"] == "smallholder farmers"
            assert provenance["unresolved_dimensions"] == [
                "local_applicability",
                "buyer_willingness_to_pay",
            ]
        counts = (len(evidence_rows), len(signal_rows))
        print(f"Query: {QUERY}")
        print("Mode: semantic")
        print(f"Returned Works Count: {len(items)}")
        print(f"Persisted Evidence Count: {counts[0]}")
        print(f"Persisted Signal Count: {counts[1]}")
        assert all(
            urllib.parse.urlsplit(url).hostname in {"api.openalex.org", "help.openalex.org"}
            for url in outbound_urls
        ), outbound_urls
        observed_hosts = sorted(
            {urllib.parse.urlsplit(url).hostname for url in outbound_urls}
        )
        print(f"Observed Outbound Hosts: {observed_hosts}")
        db.close()
        engine.dispose()

        reopened_engine = create_engine(f"sqlite:///{database_path}")
        reopened = sessionmaker(bind=reopened_engine)()
        try:
            reopened_evidence = reopened.query(models.Evidence).filter_by(source="openalex").count()
            reopened_signals = reopened.query(models.Signal).filter_by(source="openalex").count()
            print(f"Reopened DB Evidence Count: {reopened_evidence}")
            print(f"Reopened DB Signal Count: {reopened_signals}")
            assert reopened_evidence == counts[0]
            assert reopened_signals == counts[1]
        finally:
            reopened.close()
            reopened_engine.dispose()
