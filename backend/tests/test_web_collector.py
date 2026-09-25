from datetime import date
from urllib.request import Request
from unittest.mock import patch

import pytest

from app.services import source_clearance_registry
from app.services.collectors.arxiv import ArxivCollector
from app.services.collectors.github import GithubCollector
from app.services.collectors.reddit import RedditCollector
from app.services.collectors.rss import RSSCollector
from app.services.collectors.web import WebCollector, _AllowedRedirectHandler


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def test_web_collector_rejects_unapproved_url_before_any_request(monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("unapproved URL reached the network")

    monkeypatch.setattr("app.services.collectors.web.urllib.request.urlopen", unexpected_request)
    monkeypatch.setattr("app.services.collectors.web.urllib.request.build_opener", unexpected_request)

    with pytest.raises(PermissionError, match="authorization"):
        WebCollector().collect("https://www.reddit.com/r/sysadmin/comments/example/test/")
    with pytest.raises(PermissionError, match="authorization"):
        WebCollector().collect("https://example.com/article")


def test_unapproved_collector_families_fail_before_network(monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError("uncleared collector reached the network")

    monkeypatch.setattr("urllib.request.urlopen", unexpected_request)
    collectors = (
        RedditCollector(),
        GithubCollector(),
        RSSCollector(),
        ArxivCollector(),
    )
    for collector in collectors:
        with pytest.raises(PermissionError, match="no active source-registry clearance"):
            collector.collect("automation")


def test_web_collector_extracts_substantive_text_only_with_rate_authorization(db, monkeypatch):
    body = (
        "Our company operates a support desk for a growing team. "
        "We currently manage customer requests by email and spreadsheets. "
        "We are evaluating helpdesk software because tickets are being missed. "
        "The team needs routing, assignments, reporting, and searchable history."
    )
    html = f"<html><body><script>ignore this script</script>{body}</body></html>".encode()
    entry = source_clearance_registry.source_clearances()[0]
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
    )
    monkeypatch.setattr(WebCollector, "_verify_live_clearance", lambda self, url, auth: None)

    class FakeOpener:
        def open(self, request, timeout):
            assert request.full_url == entry.url
            return FakeResponse(html)

    monkeypatch.setattr(
        "app.services.collectors.web.urllib.request.build_opener",
        lambda handler: FakeOpener(),
    )
    result = WebCollector().collect(entry.url, authorization=authorization)

    assert len(result) == 1
    assert result[0]["content"].startswith("Our company operates")
    assert result[0]["metadata"]["url"] == entry.url


def test_persistent_rate_limit_is_enforced_across_authorization_calls(db):
    entry = source_clearance_registry.source_clearances()[0]
    first = source_clearance_registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
    )
    assert first.entry == entry
    with pytest.raises(PermissionError, match="rate limit is active"):
        source_clearance_registry.authorize_request(
            entry.url,
            collector="web",
            db=db,
            today=date(2026, 9, 25),
        )


def test_cleared_page_redirect_cannot_leave_the_allowlist():
    approved = "https://www.govinfo.gov/content/pkg/FR-2026-08-12/html/2026-16432.htm"
    handler = _AllowedRedirectHandler({approved})
    request = Request(approved)

    with pytest.raises(RuntimeError, match="not explicitly cleared"):
        handler.redirect_request(request, None, 302, "Found", {}, "https://example.com/out")

    redirected = handler.redirect_request(request, None, 302, "Found", {}, approved)
    assert redirected.full_url == approved


def test_live_source_clearance_checks_robots_and_terms(db, monkeypatch):
    entry = source_clearance_registry.source_clearances()[0]
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
    )
    robots = "User-agent: *\nDisallow: /search/\nDisallow: /app/search/"
    policy = (
        "<p>Public documents can generally be reprinted without legal restriction.</p>"
        "<p>Publication in a Government document does not authorize any use or appropriation "
        "of such copyright material without consent of the owner.</p>"
    )
    fetched = []

    def fetch(self, url):
        fetched.append(url)
        return robots if url.endswith("robots.txt") else policy

    monkeypatch.setattr(WebCollector, "_fetch_policy_text", fetch)
    WebCollector()._verify_live_clearance(entry.url, authorization)

    assert fetched == [entry.robots_url, entry.terms_url]


def test_live_source_clearance_fails_when_robots_blocks_page(db, monkeypatch):
    entry = source_clearance_registry.source_clearances()[0]
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
    )
    monkeypatch.setattr(
        WebCollector,
        "_fetch_policy_text",
        lambda self, url: "User-agent: *\nDisallow: /content/",
    )

    with pytest.raises(RuntimeError, match="robots.txt disallows"):
        WebCollector()._verify_live_clearance(entry.url, authorization)


def test_live_source_clearance_fails_when_terms_permission_changes(db, monkeypatch):
    entry = source_clearance_registry.source_clearances()[0]
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector="web",
        db=db,
        today=date(2026, 9, 25),
    )
    monkeypatch.setattr(
        WebCollector,
        "_fetch_policy_text",
        lambda self, url: "User-agent: *\nDisallow: /search/" if url.endswith("robots.txt")
        else "<p>Terms updated.</p>",
    )

    with pytest.raises(RuntimeError, match="terms no longer match"):
        WebCollector()._verify_live_clearance(entry.url, authorization)
