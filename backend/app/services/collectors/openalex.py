"""CC0 scholarly work and abstract discovery through the OpenAlex Works API."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from hashlib import sha256
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from typing import Any, Literal
from urllib.parse import urlsplit

from app.services import source_clearance_registry
from app.services.collectors.base import SourceCollector

API_URL = "https://api.openalex.org/works"
ROBOTS_URL = "https://api.openalex.org/robots.txt"
TERMS_URL = "https://help.openalex.org/api/"
USER_AGENT = "ForgeOS/1.0 (mailto:research@forgeos.local)"
TIMEOUT_SECONDS = 20
DEFAULT_RESULTS = 10
MAX_KEYWORD_RESULTS = 100
MAX_SEMANTIC_RESULTS = 50
MAX_KEYWORD_QUERY_LENGTH = 500
MAX_SEMANTIC_QUERY_LENGTH = 2000
MAX_ABSTRACT_LENGTH = 12000
MAX_RESPONSE_BYTES = 10_000_000
MAX_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 30
SELECT_FIELDS = (
    "id,doi,title,publication_year,cited_by_count,authorships,concepts,"
    "primary_location,open_access,abstract_inverted_index"
)
_OPENALEX_ID = re.compile(r"^https://openalex\.org/W\d+$")
_DOI_URL = re.compile(r"^https://doi\.org/10\.\d{4,9}/\S+$", re.IGNORECASE)
_DOI = re.compile(r"^10\.\d{4,9}/[^\s,|]+$", re.IGNORECASE)


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
        destination = urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (
            destination.scheme != "https"
            or destination.hostname != "api.openalex.org"
            or destination.path != urlsplit(API_URL).path
            or destination.username is not None
            or destination.password is not None
            or destination.port is not None
            or destination.fragment
        ):
            raise RuntimeError("OpenAlex redirected outside the cleared Works API endpoint")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class OpenAlexCollector(SourceCollector):
    source_name = "openalex"
    source_type = "scholarly_evidence"

    @staticmethod
    def validate_search_mode(value: Any) -> Literal["keyword", "semantic"]:
        return _validate_search_mode(value)

    def collect(
        self,
        query: str,
        *,
        search_mode: Literal["keyword", "semantic"] = "keyword",
        task_provenance: dict[str, Any] | None = None,
        authorization: source_clearance_registry.CollectionAuthorization | None = None,
    ) -> list[dict[str, Any]]:
        return fetch_openalex_works(
            query,
            search_mode=search_mode,
            task_provenance=task_provenance,
            authorization=authorization,
        )


def fetch_openalex_works(
    query: str,
    search_mode: Literal["keyword", "semantic"] = "keyword",
    max_records: int = DEFAULT_RESULTS,
    *,
    task_provenance: dict[str, Any] | None = None,
    authorization: source_clearance_registry.CollectionAuthorization | None = None,
) -> list[dict[str, Any]]:
    """Fetch allowlisted OpenAlex work fields; never follow external work links."""
    search_mode = _validate_search_mode(search_mode)
    query = _validate_query(query, search_mode)
    max_records = _validate_max_records(max_records, search_mode)
    context = task_provenance if isinstance(task_provenance, dict) else {}
    discovered_doi = _validate_discovered_doi(context.get("discovered_doi"))
    if discovered_doi:
        max_records = 1
    entry = source_clearance_registry.validate_authorization(
        authorization,
        url=API_URL,
        collector="openalex",
    )
    _verify_live_policy(entry)

    if discovered_doi:
        query_parameters = {
            "filter": f"doi:https://doi.org/{discovered_doi}",
            "per_page": max_records,
            "select": SELECT_FIELDS,
        }
    else:
        search_parameter = "search.semantic" if search_mode == "semantic" else "search"
        query_parameters = {
            search_parameter: query,
            "per_page": max_records,
            "select": SELECT_FIELDS,
        }
    params = urllib.parse.urlencode(query_parameters)
    request_url = f"{API_URL}?{params}"
    request = urllib.request.Request(
        request_url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    opener = urllib.request.build_opener(_SameWorksEndpointRedirect())
    try:
        for attempt in range(MAX_RETRIES + 1):
            try:
                with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("OpenAlex API response exceeded the cleared size limit")
                    payload = json.loads(body.decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    detail = exc.read(500).decode("utf-8", errors="replace").strip()
                    message = f"OpenAlex API returned HTTP {exc.code}"
                    if detail:
                        message = f"{message}: {detail}"
                    raise RuntimeError(message) from exc
                if attempt == MAX_RETRIES:
                    raise source_clearance_registry.SourceRateLimitError(
                        "OpenAlex API remained rate-limited after bounded exponential backoff"
                    ) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = max(2**attempt, _retry_after_seconds(retry_after))
                if delay > MAX_RETRY_AFTER_SECONDS:
                    raise source_clearance_registry.SourceRateLimitError(
                        f"OpenAlex API requested a retry delay of {delay} seconds; defer the task"
                    ) from exc
                time.sleep(delay)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenAlex API returned invalid JSON") from exc
    except Exception as exc:
        if isinstance(exc, (RuntimeError, source_clearance_registry.SourceRateLimitError)):
            raise
        raise RuntimeError(f"OpenAlex API request failed: {exc}") from exc

    records = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise RuntimeError("OpenAlex API response did not contain a works list")

    retrieved_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []
    for record in records[:max_records]:
        if not isinstance(record, dict):
            raise RuntimeError("OpenAlex API returned a non-object work record")
        item = _normalize_work(
            record,
            query=query,
            search_mode=search_mode,
            request_url=request_url,
            retrieved_at=retrieved_at,
            entry=entry,
            task_provenance=task_provenance,
        )
        if item is not None:
            results.append(item)
    return results


def _normalize_work(
    record: dict[str, Any],
    *,
    query: str,
    search_mode: str,
    request_url: str,
    retrieved_at: str,
    entry: source_clearance_registry.SourceClearance,
    task_provenance: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    openalex_id = record.get("id")
    title = record.get("title")
    if not isinstance(openalex_id, str) or not _OPENALEX_ID.fullmatch(openalex_id):
        raise RuntimeError("OpenAlex work is missing a canonical OpenAlex ID")
    if not isinstance(title, str) or not title.strip():
        raise RuntimeError("OpenAlex work is missing a title")
    title = title.strip()[:1000]

    abstract = reconstruct_abstract(record.get("abstract_inverted_index"))
    year = record.get("publication_year")
    if isinstance(year, bool) or not isinstance(year, int) or not 1400 <= year <= datetime.now(timezone.utc).year + 2:
        year = None
    cited_by_count = record.get("cited_by_count")
    if isinstance(cited_by_count, bool) or not isinstance(cited_by_count, int) or cited_by_count < 0:
        cited_by_count = None
    doi = record.get("doi")
    doi = doi.strip() if isinstance(doi, str) and _DOI_URL.fullmatch(doi.strip()) else None
    authorships = _authorship_summary(record.get("authorships"))
    concepts = _concept_summary(record.get("concepts"))
    location = _location_summary(record.get("primary_location"))
    open_access = _open_access_summary(record.get("open_access"))
    published_at = None

    content_parts = [f"Scholarly work: {title}"]
    if year is not None:
        content_parts.append(f"Publication year: {year}")
    if abstract:
        content_parts.append(f"Abstract: {abstract[:3000]}")
    if cited_by_count is not None:
        content_parts.append(f"OpenAlex cited-by count: {cited_by_count}")
    external_id = sha256(f"openalex:{openalex_id}".encode("utf-8")).hexdigest()
    provenance = {
        "source_registry_id": entry.registry_id,
        "api_endpoint": API_URL,
        "api_request_url": request_url,
        "source_type": "openalex",
        "source_id": external_id,
        "openalex_id": openalex_id,
        "doi": doi,
        "title": title,
        "publication_year": year,
        "cited_by_count": cited_by_count,
        "authorships": authorships,
        "concepts": concepts,
        "primary_location": location,
        "open_access": open_access,
        "abstract": abstract,
        "abstract_reconstructed": abstract is not None,
        "query": query,
        "search_mode": search_mode,
        "retrieved_at": retrieved_at,
        "published_at": published_at,
        "canonical_url": openalex_id,
        "traceable": True,
        "metadata_only": abstract is None,
        "retrieved_content_kind": (
            "work_metadata_only"
            if abstract is None
            else "work_metadata_and_reconstructed_abstract"
        ),
        "geographic_scope_status": "not_assessed_from_affiliations_or_retrieval_relevance",
        "temporal_scope_status": "publication_year_only_not_study_period",
        "retrieval_relevance_is_not_empirical_support": True,
        "external_pdf_fetched": False,
        "publisher_page_fetched": False,
        "discovered_doi": _validate_discovered_doi(
            (task_provenance or {}).get("discovered_doi")
            if isinstance(task_provenance, dict)
            else None
        ),
        "discovery_parent_evidence_id": (
            task_provenance.get("discovery_parent_evidence_id")
            if isinstance(task_provenance, dict)
            and isinstance(task_provenance.get("discovery_parent_evidence_id"), int)
            else None
        ),
        "lookup_method": (
            "exact_doi_filter"
            if isinstance(task_provenance, dict)
            and task_provenance.get("discovered_doi")
            else "keyword_or_semantic_search"
        ),
        "license": "CC0",
        "license_tag": entry.license_tag,
        "retrieved_fields": list(entry.allowed_fields),
        **_task_provenance_fields(
            task_provenance,
            derived_query=query,
            search_mode=search_mode,
        ),
    }
    return {
        "content": " | ".join(content_parts),
        "title": title,
        "canonical_url": openalex_id,
        "external_id": external_id,
        "identity_key": f"openalex:{external_id}",
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


def _task_provenance_fields(
    task_provenance: dict[str, Any] | None,
    *,
    derived_query: str,
    search_mode: Literal["keyword", "semantic"],
) -> dict[str, Any]:
    context = task_provenance if isinstance(task_provenance, dict) else {}
    original_question = context.get("original_research_question")
    geographic = context.get("geographic_qualification")
    population = context.get("population_qualification")
    unresolved = context.get("unresolved_dimensions")
    return {
        "original_research_question": (
            original_question if isinstance(original_question, str) else None
        ),
        "derived_retrieval_query": derived_query,
        "search_mode": search_mode,
        "discovered_doi": _validate_discovered_doi(
            context.get("discovered_doi")
        ),
        "geographic_qualification": geographic if isinstance(geographic, str) else None,
        "population_qualification": population if isinstance(population, str) else None,
        "unresolved_dimensions": (
            [value for value in unresolved[:30] if isinstance(value, str)][:30]
            if isinstance(unresolved, list)
            else []
        ),
    }


def reconstruct_abstract(inverted_index: Any) -> str | None:
    """Reconstruct OpenAlex's token-position map without trusting sparse offsets."""
    if inverted_index is None:
        return None
    if not isinstance(inverted_index, dict):
        raise RuntimeError("OpenAlex abstract inverted index must be an object")
    position_words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        if not isinstance(word, str) or not word or not isinstance(positions, list):
            raise RuntimeError("OpenAlex abstract inverted index contains invalid entries")
        for position in positions:
            if isinstance(position, bool) or not isinstance(position, int) or position < 0 or position > 100000:
                raise RuntimeError("OpenAlex abstract inverted index contains an invalid position")
            if position in position_words:
                raise RuntimeError("OpenAlex abstract inverted index contains duplicate positions")
            position_words[position] = word
    if not position_words:
        return None
    text = " ".join(position_words[position] for position in sorted(position_words))
    text = " ".join(text.split())
    return text[:MAX_ABSTRACT_LENGTH] or None


def _validate_query(value: Any, search_mode: Literal["keyword", "semantic"] = "keyword") -> str:
    if not isinstance(value, str):
        raise ValueError("OpenAlex query must be text")
    query = " ".join(value.split())
    if search_mode == "semantic":
        query = query[:MAX_SEMANTIC_QUERY_LENGTH].strip()
        maximum = MAX_SEMANTIC_QUERY_LENGTH
    else:
        maximum = MAX_KEYWORD_QUERY_LENGTH
    if not query or len(query) > maximum:
        raise ValueError(f"OpenAlex query must contain 1-{maximum} characters")
    return query


def _validate_discovered_doi(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("OpenAlex discovered DOI must be text")
    doi = value.strip()
    if not _DOI.fullmatch(doi):
        raise ValueError("OpenAlex discovered DOI is not a valid DOI identifier")
    return doi


def _validate_search_mode(value: Any) -> Literal["keyword", "semantic"]:
    if value == "keyword":
        return "keyword"
    if value == "semantic":
        return "semantic"
    raise ValueError("OpenAlex search_mode must be 'keyword' or 'semantic'")


def _validate_max_records(
    value: Any,
    search_mode: Literal["keyword", "semantic"] = "keyword",
) -> int:
    maximum = MAX_SEMANTIC_RESULTS if search_mode == "semantic" else MAX_KEYWORD_RESULTS
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"OpenAlex max_records must be an integer from 1 to {maximum}")
    return value


def _retry_after_seconds(value: str | None) -> int:
    if not value:
        return 0
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def _authorship_summary(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    summary: list[dict[str, Any]] = []
    for item in value[:50]:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        institutions = item.get("institutions")
        institution_summary = []
        if isinstance(institutions, list):
            for institution in institutions[:10]:
                if isinstance(institution, dict):
                    institution_summary.append(
                        {
                            "name": _bounded_text(institution.get("display_name"), 300),
                            "country_code": _bounded_text(institution.get("country_code"), 2),
                        }
                    )
        summary.append(
            {
                "author_id": _bounded_text(author.get("id"), 200) if isinstance(author, dict) else None,
                "author_name": _bounded_text(author.get("display_name"), 300) if isinstance(author, dict) else None,
                "institutions": institution_summary,
                "countries": [
                    code
                    for code in (
                        _bounded_text(country, 2)
                        for country in item.get("countries", [])[:10]
                    )
                    if code
                ]
                if isinstance(item.get("countries"), list)
                else [],
            }
        )
    return summary


def _concept_summary(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "id": _bounded_text(item.get("id"), 200),
            "name": _bounded_text(item.get("display_name"), 300),
        }
        for item in value[:50]
        if isinstance(item, dict)
    ]


def _location_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    source = value.get("source")
    return {
        "source_name": _bounded_text(source.get("display_name"), 300) if isinstance(source, dict) else None,
        "is_oa": value.get("is_oa") if isinstance(value.get("is_oa"), bool) else None,
    }


def _open_access_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    status = value.get("oa_status")
    return {
        "is_oa": value.get("is_oa") if isinstance(value.get("is_oa"), bool) else None,
        "oa_status": _bounded_text(status, 50),
    }


def _bounded_text(value: Any, maximum: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:maximum]


def _verify_live_policy(entry: source_clearance_registry.SourceClearance) -> None:
    request = urllib.request.Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            robots_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise RuntimeError("Could not recheck OpenAlex API robots policy") from exc
        robots_text = ""
    except Exception as exc:
        raise RuntimeError("Could not recheck OpenAlex API robots policy") from exc
    if robots_text:
        robots = urllib.robotparser.RobotFileParser(ROBOTS_URL)
        robots.parse(robots_text.splitlines())
        if not robots.can_fetch(USER_AGENT, API_URL):
            raise PermissionError("OpenAlex robots policy disallows the Works API")

    request = urllib.request.Request(TERMS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError("Could not recheck OpenAlex API terms") from exc
    parser = _TextExtractor()
    parser.feed(html)
    terms = " ".join(parser.parts).casefold()
    if not all(phrase.casefold() in terms for phrase in entry.required_terms_phrases):
        raise PermissionError("OpenAlex terms no longer match the reviewed clearance")
