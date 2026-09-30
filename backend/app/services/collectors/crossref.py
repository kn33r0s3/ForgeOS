"""Search Crossref's documented public API for reusable bibliographic metadata.

Only metadata fields are requested. Abstracts and full text are intentionally
excluded because some abstracts may carry third-party copyright restrictions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from typing import Any

from app.services import source_clearance_registry
from app.services.collectors.base import SourceCollector

API_URL = "https://api.crossref.org/works"
ROBOTS_URL = "https://api.crossref.org/robots.txt"
TERMS_URL = "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"
USER_AGENT = "ForgeOS/0.1 (research metadata; https://github.com/kn33r0s3/ForgeOS)"
TIMEOUT_SECONDS = 12
MAX_RESULTS = 5
SELECT_FIELDS = (
    "DOI,title,publisher,type,published,published-print,published-online,"
    "created,URL,container-title,is-referenced-by-count,author,score"
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


class _SameWorksEndpointRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        target = urllib.parse.urlsplit(API_URL)
        if (
            destination.scheme != "https"
            or destination.hostname != target.hostname
            or destination.path != target.path
        ):
            raise RuntimeError("Crossref redirected outside the cleared works API endpoint")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class CrossrefCollector(SourceCollector):
    source_name = "crossref"
    source_type = "scholarly_metadata"

    def collect(
        self,
        query: str,
        *,
        authorization: source_clearance_registry.CollectionAuthorization | None = None,
    ) -> list[dict[str, Any]]:
        source_clearance_registry.validate_authorization(
            authorization,
            url=API_URL,
            collector=self.source_name,
        )
        self._verify_live_policy()
        params = urllib.parse.urlencode(
            {
                "query.bibliographic": " ".join(query.split())[:300],
                "rows": MAX_RESULTS,
                "select": SELECT_FIELDS,
            }
        )
        request = urllib.request.Request(
            f"{API_URL}?{params}",
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        opener = urllib.request.build_opener(_SameWorksEndpointRedirect())
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise source_clearance_registry.SourceRateLimitError(
                    "Crossref public API returned HTTP 429; retry after its rate window"
                ) from exc
            detail = exc.read(500).decode("utf-8", errors="replace").strip()
            message = f"Crossref API returned HTTP {exc.code}"
            if detail:
                message = f"{message}: {detail}"
            raise RuntimeError(message) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Crossref API returned invalid JSON") from exc
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"Crossref API request failed: {exc}") from exc

        message = payload.get("message")
        items = message.get("items") if isinstance(message, dict) else None
        if payload.get("status") != "ok" or not isinstance(items, list):
            raise RuntimeError("Crossref API response did not contain a valid works list")

        retrieved_at = datetime.now(timezone.utc).isoformat()
        results: list[dict[str, Any]] = []
        for rank, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            doi = item.get("DOI")
            title = _first_text(item.get("title"))
            if not isinstance(doi, str) or not doi.strip() or not title:
                continue
            doi = doi.strip()
            published_at = _publication_date(item)
            publisher = _first_text(item.get("publisher"))
            journal = _first_text(item.get("container-title"))
            content = f"Crossref metadata record: {title}"
            if publisher:
                content += f" — {publisher}"
            if published_at:
                content += f" ({published_at[:4]})"
            provenance = {
                "source_registry_id": "crossref-public-works-metadata",
                "api_endpoint": API_URL,
                "query": query,
                "retrieved_at": retrieved_at,
                "doi": doi,
                "publisher": publisher,
                "container_title": journal,
                "publication_type": item.get("type"),
                "published_at": published_at,
                "provider_rank": rank,
                "provider_relevance": item.get("score"),
                "cited_by_count": item.get("is-referenced-by-count"),
                "metadata_only": True,
                "abstract_or_full_text_stored": False,
            }
            results.append(
                {
                    "content": content,
                    "title": title,
                    "canonical_url": f"https://doi.org/{doi}",
                    "external_id": doi,
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

    def _verify_live_policy(self) -> None:
        request = urllib.request.Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                robots_text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise RuntimeError("Could not recheck Crossref API robots policy") from exc
            robots_text = ""
        except Exception as exc:
            raise RuntimeError("Could not recheck Crossref API robots policy") from exc

        if robots_text:
            robots = urllib.robotparser.RobotFileParser(ROBOTS_URL)
            robots.parse(robots_text.splitlines())
            if not robots.can_fetch(USER_AGENT, API_URL):
                raise PermissionError("Crossref robots policy disallows the works API")

        request = urllib.request.Request(TERMS_URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise RuntimeError("Could not recheck Crossref REST API terms") from exc
        parser = _TextExtractor()
        parser.feed(html)
        terms = " ".join(parser.parts).casefold()
        clearance = source_clearance_registry.clearance_for_url(API_URL)
        if clearance is None or not all(
            phrase.casefold() in terms for phrase in clearance.required_terms_phrases
        ):
            raise PermissionError("Crossref REST API terms no longer match the reviewed clearance")


def _first_text(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return None


def _publication_date(item: dict[str, Any]) -> str | None:
    for key in ("published", "published-online", "published-print", "created"):
        date_info = item.get(key)
        parts = date_info.get("date-parts") if isinstance(date_info, dict) else None
        first_parts = parts[0] if isinstance(parts, list) and parts else None
        if not isinstance(first_parts, list) or not first_parts:
            continue
        try:
            year = int(first_parts[0])
            month = int(first_parts[1]) if len(first_parts) > 1 else 1
            day = int(first_parts[2]) if len(first_parts) > 2 else 1
            return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
        except (TypeError, ValueError):
            continue
    return None
