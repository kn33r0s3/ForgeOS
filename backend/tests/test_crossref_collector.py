from datetime import datetime, timezone
from io import BytesIO
import json
import urllib.error
import urllib.parse

import pytest

from app import models
from app.services import collector_runner, research_task_engine
from app.services.collectors import crossref
from app.services import source_clearance_registry


TERMS_HTML = """
<html><body>
No sign-up is required to use the REST API.
Almost none of the metadata is subject to copyright.
Some abstracts contained in the metadata may be subject to copyright.
</body></html>
"""


def _authorization(db):
    return source_clearance_registry.authorize_request(
        crossref.API_URL,
        collector="crossref",
        db=db,
        today=datetime(2026, 9, 27, tzinfo=timezone.utc).date(),
        now=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
    )


def _policy_responses(monkeypatch):
    def fake_urlopen(request, timeout):
        if request.full_url == crossref.ROBOTS_URL:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
        if request.full_url == crossref.TERMS_URL:
            return BytesIO(TERMS_HTML.encode())
        raise AssertionError(f"Unexpected policy request: {request.full_url}")

    monkeypatch.setattr(crossref.urllib.request, "urlopen", fake_urlopen)


def test_crossref_collector_requests_and_persists_only_bibliographic_fields(db, monkeypatch):
    _policy_responses(monkeypatch)
    captured = {}
    payload = {
        "status": "ok",
        "message": {
            "items": [
                {
                    "DOI": "10.1234/example.1",
                    "title": ["Postharvest storage options for smallholder farmers"],
                    "publisher": "Example Academic Press",
                    "type": "journal-article",
                    "published": {"date-parts": [[2024, 5, 3]]},
                    "URL": "https://doi.org/10.1234/example.1",
                    "container-title": ["Journal of Food Systems"],
                    "is-referenced-by-count": 4,
                    "abstract": "This copyrighted abstract must never be requested or stored.",
                    "score": 27.4,
                }
            ]
        },
    }

    class FakeOpener:
        def open(self, request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(
        crossref.urllib.request,
        "build_opener",
        lambda handler: FakeOpener(),
    )
    items = crossref.CrossrefCollector().collect(
        "postharvest storage smallholder farmers",
        authorization=_authorization(db),
    )

    assert len(items) == 1
    item = items[0]
    assert item["external_id"] == "10.1234/example.1"
    assert item["canonical_url"] == "https://doi.org/10.1234/example.1"
    assert item["published_at"] == "2024-05-03T00:00:00+00:00"
    assert item["provenance"]["metadata_only"] is True
    assert item["provenance"]["abstract_or_full_text_stored"] is False
    assert "abstract" not in item["provenance"]
    assert "copyrighted abstract" not in item["content"]
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(captured["url"]).query)
    assert query["rows"] == [str(crossref.MAX_RESULTS)]
    assert "abstract" not in query["select"][0].split(",")
    assert "updated" not in query["select"][0].split(",")
    assert captured["timeout"] == crossref.TIMEOUT_SECONDS


def test_crossref_collector_requires_current_registry_authorization(db, monkeypatch):
    _policy_responses(monkeypatch)

    with pytest.raises(PermissionError, match="current source registry authorization"):
        crossref.CrossrefCollector().collect("a new research query")


def test_crossref_task_persists_attributed_metadata_evidence(db, monkeypatch):
    _policy_responses(monkeypatch)
    payload = {
        "status": "ok",
        "message": {
            "items": [
                {
                    "DOI": "10.1234/persisted.1",
                    "title": ["Measuring postharvest loss in smallholder supply chains"],
                    "publisher": "Example Academic Press",
                    "type": "journal-article",
                    "published": {"date-parts": [[2025, 3, 1]]},
                    "URL": "https://doi.org/10.1234/persisted.1",
                    "abstract": "This field must not be requested or stored.",
                }
            ]
        },
    }

    class FakeOpener:
        def open(self, request, timeout):
            return BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(
        crossref.urllib.request,
        "build_opener",
        lambda handler: FakeOpener(),
    )
    question = models.ResearchQuestion(
        question="What measurements describe postharvest loss for smallholder farmers?"
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="crossref",
        query=question.question,
    )

    result = collector_runner.execute_task(db, task)

    evidence = db.query(models.Evidence).one()
    signal = db.get(models.Signal, evidence.signal_id)
    provenance = json.loads(evidence.provenance)
    assert result["status"] == "completed"
    assert evidence.canonical_url == "https://doi.org/10.1234/persisted.1"
    assert evidence.external_id == "10.1234/persisted.1"
    assert evidence.published_at is not None
    assert evidence.retrieved_at is not None
    assert provenance["metadata_only"] is True
    assert provenance["abstract_or_full_text_stored"] is False
    assert "abstract" not in provenance
    assert signal.source_type == "external"
    assert task.idempotency_key
    assert result["evidence_found"] == 1


def test_crossref_http_429_is_a_recoverable_rate_limit(db, monkeypatch):
    _policy_responses(monkeypatch)

    class FakeOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(
        crossref.urllib.request,
        "build_opener",
        lambda handler: FakeOpener(),
    )
    with pytest.raises(source_clearance_registry.SourceRateLimitError, match="HTTP 429"):
        crossref.CrossrefCollector().collect(
            "an unrelated question",
            authorization=_authorization(db),
        )
