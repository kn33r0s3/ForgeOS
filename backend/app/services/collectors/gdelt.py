"""Bounded, metadata-only collection through the GDELT DOC API v2."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.robotparser
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from app.services import source_clearance_registry
from app.services.collectors.base import SourceCollector

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
ROBOTS_URL = "https://api.gdeltproject.org/robots.txt"
TERMS_URL = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
USER_AGENT = "ForgeOS/0.1 (GDELT metadata; https://github.com/kn33r0s3/ForgeOS)"
TIMEOUT_SECONDS = 20
MAX_RESULTS = 25
MAX_QUERY_LENGTH = 500
MAX_429_RETRIES = 2
MAX_BACKOFF_SECONDS = 30
ALLOWED_TIMESPANS = frozenset({"1d", "3d", "1w", "1m", "3m"})
ALLOWED_FIELDS = ("url", "title", "seendate", "domain", "language", "sourcecountry")
_SEENDATE = re.compile(r"^(?:\d{14}|\d{8}T\d{6}Z)$")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


class _SameDocEndpointRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        original = urlsplit(req.full_url)
        if (
            destination.scheme != "https"
            or destination.hostname != "api.gdeltproject.org"
            or destination.path != original.path
            or destination.username is not None
            or destination.password is not None
        ):
            raise RuntimeError("GDELT redirected outside the exact cleared DOC API endpoint")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GdeltCollector(SourceCollector):
    source_name = "gdelt_doc"
    source_type = "gdelt_doc"

    def collect(
        self,
        query: str,
        *,
        authorization: source_clearance_registry.CollectionAuthorization | None = None,
    ) -> list[dict[str, Any]]:
        options = _parse_task_query(query)
        return fetch_gdelt_signals(
            options["query"],
            timespan=options["timespan"],
            max_records=options["max_records"],
            authorization=authorization,
        )


def fetch_gdelt_signals(
    query: str,
    timespan: str = "1w",
    max_records: int = 25,
    *,
    authorization: source_clearance_registry.CollectionAuthorization | None = None,
) -> list[dict[str, Any]]:
    """Fetch only allowlisted article metadata; never open publisher URLs."""
    query = _validate_query(query)
    timespan = _validate_timespan(timespan)
    max_records = _validate_max_records(max_records)
    entry = source_clearance_registry.validate_authorization(
        authorization,
        url=API_URL,
        collector="gdelt_doc",
    )
    _verify_live_policy(entry)

    params = urllib.parse.urlencode(
        {
            "query": query,
            "mode": "artlist",
            "maxrecords": max_records,
            "format": "json",
            "timespan": timespan,
        }
    )
    request_url = f"{API_URL}?{params}"
    request = urllib.request.Request(
        request_url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    opener = urllib.request.build_opener(_SameDocEndpointRedirect())
    try:
        for attempt in range(MAX_429_RETRIES + 1):
            try:
                with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    raise RuntimeError(f"GDELT DOC API returned HTTP {exc.code}") from exc
                if attempt == MAX_429_RETRIES:
                    raise source_clearance_registry.SourceRateLimitError(
                        "GDELT DOC API remained rate-limited after bounded exponential backoff"
                    ) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = max(5 * (2**attempt), _retry_after_seconds(retry_after))
                if delay > MAX_BACKOFF_SECONDS:
                    raise source_clearance_registry.SourceRateLimitError(
                        f"GDELT DOC API requested a retry delay of {delay} seconds; defer the task"
                    ) from exc
                time.sleep(delay)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("GDELT DOC API returned invalid JSON") from exc
    except Exception as exc:
        if isinstance(exc, (RuntimeError, source_clearance_registry.SourceRateLimitError)):
            raise
        raise RuntimeError(f"GDELT DOC API request failed: {exc}") from exc

    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        raise RuntimeError("GDELT DOC API response did not contain an article list")

    article_count = len(articles[:max_records])
    result_set_capped = article_count >= max_records
    retrieved_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []
    for article in articles[:max_records]:
        if not isinstance(article, dict):
            raise RuntimeError("GDELT DOC API returned a non-object article record")
        metadata = _permitted_article(article)
        url = metadata["url"]
        seendate = metadata["seendate"]
        title = metadata["title"]
        external_id = sha256(f"{url}{seendate}{query}".encode("utf-8")).hexdigest()
        published_at = _published_at(seendate)
        domain = metadata["domain"]
        content = f"Title: {title} | Domain: {domain} | Date: {seendate}"
        provenance = {
            "source_registry_id": entry.registry_id,
            "api_endpoint": API_URL,
            "api_request_url": request_url,
            "source_type": "gdelt_doc",
            "source_id": external_id,
            "traceable": True,
            "metadata_only": True,
            "query": query,
            "timespan": timespan,
            "reported_result_count": article_count,
            "max_records": max_records,
            "result_set_capped": result_set_capped,
            "retrieved_at": retrieved_at,
            "published_at": published_at,
            "url": url,
            "canonical_url": url,
            "title": title,
            "seendate": seendate,
            "domain": domain,
            "language": metadata["language"],
            "country": metadata["sourcecountry"],
            "sourcecountry": metadata["sourcecountry"],
            "attribution": "GDELT Project (https://www.gdeltproject.org/)",
            "license_tag": entry.license_tag,
            "retrieved_fields": list(ALLOWED_FIELDS),
            "article_body_fetched": False,
            "publisher_page_fetched": False,
        }
        results.append(
            {
                "content": content,
                "title": title,
                "canonical_url": url,
                "external_id": external_id,
                "timestamp": retrieved_at,
                "published_at": published_at,
                "retrieved_at": retrieved_at,
                "provenance": provenance,
                "metadata": {
                    **provenance,
                    "source_type": "external",
                    "collection_status": "collected",
                },
            }
        )
    return results


def _parse_task_query(value: str) -> dict[str, Any]:
    try:
        options = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {"query": value, "timespan": "1w", "max_records": MAX_RESULTS}
    if not isinstance(options, dict) or set(options) != {"query", "timespan", "max_records"}:
        raise ValueError("GDELT task query must be plain text or the bounded query options object")
    return {
        "query": options["query"],
        "timespan": options["timespan"],
        "max_records": options["max_records"],
    }


def _validate_query(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("GDELT query must be text")
    query = " ".join(value.split())
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"GDELT query must contain 1-{MAX_QUERY_LENGTH} characters")
    return query


def _validate_timespan(value: Any) -> str:
    if not isinstance(value, str) or value not in ALLOWED_TIMESPANS:
        raise ValueError("GDELT timespan is outside the cleared bounded intervals")
    return value


def _validate_max_records(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_RESULTS:
        raise ValueError(f"GDELT max_records must be an integer from 1 to {MAX_RESULTS}")
    return value


def _permitted_article(article: dict[str, Any]) -> dict[str, str]:
    url = article.get("url")
    title = article.get("title")
    seendate = article.get("seendate")
    domain = article.get("domain")
    if not all(isinstance(value, str) and value.strip() for value in (url, title, seendate, domain)):
        raise RuntimeError("GDELT article is missing required metadata fields")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise RuntimeError("GDELT article URL is not a safe canonical HTTPS URL")
    if not _SEENDATE.fullmatch(seendate):
        raise RuntimeError("GDELT article has an invalid publication timestamp")
    try:
        _parse_seendate(seendate)
    except ValueError as exc:
        raise RuntimeError("GDELT article has an invalid publication timestamp") from exc
    return {
        "url": url.strip(),
        "title": title.strip()[:1000],
        "seendate": seendate,
        "domain": domain.strip().casefold()[:255],
        "language": _optional_text(article.get("language")),
        "sourcecountry": _optional_text(article.get("sourcecountry")),
    }


def _optional_text(value: Any) -> str:
    return value.strip()[:100] if isinstance(value, str) else ""


def _retry_after_seconds(value: str | None) -> int:
    if not value:
        return 0
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def _published_at(seendate: str) -> str:
    return _parse_seendate(seendate).replace(tzinfo=timezone.utc).isoformat()


def _parse_seendate(seendate: str) -> datetime:
    if "T" in seendate:
        return datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
    return datetime.strptime(seendate, "%Y%m%d%H%M%S")


def _verify_live_policy(entry: source_clearance_registry.SourceClearance) -> None:
    request = urllib.request.Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            robots_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError("Could not recheck GDELT API robots policy") from exc
        robots_text = ""
    except Exception as exc:
        raise RuntimeError("Could not recheck GDELT API robots policy") from exc
    if robots_text:
        robots = urllib.robotparser.RobotFileParser(ROBOTS_URL)
        robots.parse(robots_text.splitlines())
        if not robots.can_fetch(USER_AGENT, API_URL):
            raise PermissionError("GDELT API robots policy disallows the DOC endpoint")

    request = urllib.request.Request(TERMS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError("Could not recheck GDELT DOC API documentation") from exc
    parser = _TextExtractor()
    parser.feed(html)
    documented = " ".join(parser.parts).casefold()
    if not all(phrase.casefold() in documented for phrase in entry.required_terms_phrases):
        raise PermissionError("GDELT DOC API documentation no longer matches reviewed clearance")
