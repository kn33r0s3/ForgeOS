from unittest.mock import patch
from urllib.request import Request

import pytest

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


def test_web_collector_rejects_reddit_shell_text():
    html = b"<html><body>Reddit</body></html>"

    with patch(
        "app.services.collectors.web.urllib.request.urlopen",
        return_value=FakeResponse(html),
    ):
        result = WebCollector().collect(
            "https://www.reddit.com/r/sysadmin/comments/example/test/"
        )

    assert result == []


def test_web_collector_rejects_short_shell_text():
    html = b"<html><body>Home Login Pricing</body></html>"

    with patch(
        "app.services.collectors.web.urllib.request.urlopen",
        return_value=FakeResponse(html),
    ):
        result = WebCollector().collect("https://example.com")

    assert result == []


def test_web_collector_keeps_substantive_page_text():
    body = (
        "Our company operates a support desk for a growing team. "
        "We currently manage customer requests by email and spreadsheets. "
        "We are evaluating helpdesk software because tickets are being missed. "
        "The team needs routing, assignments, reporting, and searchable history."
    )
    html = f"<html><body>{body}</body></html>".encode()

    with patch(
        "app.services.collectors.web.urllib.request.urlopen",
        return_value=FakeResponse(html),
    ):
        result = WebCollector().collect("https://example.com/article")

    assert len(result) == 1
    assert result[0]["content"].startswith("Our company operates")
    assert result[0]["metadata"]["url"] == "https://example.com/article"


def test_web_collector_extracts_reddit_post_from_json():
    reddit_json = b'''[
      {
        "data": {
          "children": [
            {
              "data": {
                "title": "Looking for a new ticketing system",
                "author": "example_sysadmin",
                "subreddit_name_prefixed": "r/sysadmin",
                "selftext": "We are a construction company with about 100 employees and a two-person IT team. Our current ticketing system is causing workflow problems, so we are actively evaluating replacement helpdesk software. We need email intake, assignments, reporting, and a simple experience for users."
              }
            }
          ]
        }
      },
      {
        "data": {
          "children": []
        }
      }
    ]'''

    with patch(
        "app.services.collectors.web.urllib.request.urlopen",
        return_value=FakeResponse(reddit_json),
    ):
        result = WebCollector().collect(
            "https://www.reddit.com/r/sysadmin/comments/example/test/"
        )

    assert len(result) == 1
    assert "Looking for a new ticketing system" in result[0]["content"]
    assert "construction company" in result[0]["content"]
    assert "actively evaluating replacement helpdesk software" in result[0]["content"]
    assert result[0]["metadata"]["extraction"] == "reddit_json"


def test_web_collector_falls_closed_when_reddit_json_has_no_substantive_post():
    reddit_json = b'''[
      {
        "data": {
          "children": [
            {
              "data": {
                "title": "Help",
                "author": "x",
                "subreddit_name_prefixed": "r/sysadmin",
                "selftext": ""
              }
            }
          ]
        }
      }
    ]'''

    with patch(
        "app.services.collectors.web.urllib.request.urlopen",
        return_value=FakeResponse(reddit_json),
    ):
        result = WebCollector().collect(
            "https://www.reddit.com/r/sysadmin/comments/example/test/"
        )

    assert result == []


def test_cleared_page_redirect_cannot_leave_the_allowlist():
    approved = "https://www.govinfo.gov/content/pkg/FR-2026-08-12/html/2026-16432.htm"
    handler = _AllowedRedirectHandler({approved})
    request = Request(approved)

    with pytest.raises(RuntimeError, match="not explicitly cleared"):
        handler.redirect_request(request, None, 302, "Found", {}, "https://example.com/out")

    redirected = handler.redirect_request(request, None, 302, "Found", {}, approved)
    assert redirected.full_url == approved
