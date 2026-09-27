"""Validated runtime registry for lawfully cleared external collection targets.

`Source` remains reliability history; it is not permission to fetch. Every
external collection target must have a reviewed record here and a matching
evidence row in ``docs/PUBLIC_SOURCES.md``. The registry intentionally stores
exact URLs: adding a source never grants a crawler permission to roam a host.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app import models


@dataclass(frozen=True)
class SourceClearance:
    registry_id: str
    display_name: str
    collector: str
    url: str
    hostname: str
    geographies: tuple[str, ...]
    categories: tuple[str, ...]
    allowed_need: str
    evidence_references: tuple[str, ...]
    reviewed_on: date
    valid_through: date
    robots_url: str
    terms_url: str
    required_terms_phrases: tuple[str, ...]
    redirect_urls: tuple[str, ...]
    allowed_operation: str
    allowed_fields: tuple[str, ...]
    supports_requirements: tuple[str, ...]
    provenance_requirements: tuple[str, ...]
    min_interval_seconds: int = 3600
    policy_hostnames: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollectionAuthorization:
    """Short-lived in-process proof that a database rate slot was reserved."""

    entry: SourceClearance
    reserved_at: datetime


_GOVINFO_URL = "https://www.govinfo.gov/content/pkg/FR-2026-08-12/html/2026-16432.htm"
_GOVINFO_ROBOTS = "https://www.govinfo.gov/robots.txt"
_GOVINFO_TERMS = "https://www.govinfo.gov/about/policies"
_CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_CROSSREF_ROBOTS = "https://api.crossref.org/robots.txt"
_CROSSREF_TERMS = "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"
_WORLD_BANK_V2_URL = "https://api.worldbank.org/v2"
_WORLD_BANK_ROBOTS = "https://api.worldbank.org/robots.txt"
_WORLD_BANK_TERMS = "https://datacatalog.worldbank.org/public-licenses"


class SourceRateLimitError(PermissionError):
    """A cleared source is temporarily unavailable under its rate policy."""

SOURCE_CLEARANCES: tuple[SourceClearance, ...] = (
    SourceClearance(
        registry_id="govinfo-nepal-cultural-property-rule-2026",
        display_name="GovInfo Federal Register notice",
        collector="web",
        url=_GOVINFO_URL,
        hostname="www.govinfo.gov",
        geographies=("NP",),
        categories=("public_rule", "cultural_property"),
        allowed_need="Public rule describing Nepal cultural-property import restrictions.",
        evidence_references=(
            "docs/PUBLIC_SOURCES.md",
            _GOVINFO_URL,
            _GOVINFO_ROBOTS,
            _GOVINFO_TERMS,
        ),
        reviewed_on=date(2026, 9, 25),
        valid_through=date(2026, 9, 25),
        robots_url=_GOVINFO_ROBOTS,
        terms_url=_GOVINFO_TERMS,
        required_terms_phrases=(
            "public documents can generally be reprinted without legal restriction",
            "does not authorize any use or appropriation of such copyright material without consent",
        ),
        redirect_urls=(_GOVINFO_URL,),
        allowed_operation="retrieve_exact_publication",
        allowed_fields=("public_document_text", "publication_date", "document_url"),
        supports_requirements=("public_rule_text",),
        provenance_requirements=("canonical_url", "retrieved_at", "source_registry_id", "policy_review"),
    ),
    SourceClearance(
        registry_id="crossref-public-works-metadata",
        display_name="Crossref public scholarly metadata API",
        collector="crossref",
        url=_CROSSREF_WORKS_URL,
        hostname="api.crossref.org",
        geographies=("GLOBAL",),
        categories=("scholarly_metadata", "research_discovery"),
        allowed_need=(
            "Discover scholarly publication metadata relevant to a research question; "
            "do not retrieve or persist abstracts or full text."
        ),
        evidence_references=(
            "docs/PUBLIC_SOURCES.md",
            _CROSSREF_WORKS_URL,
            _CROSSREF_ROBOTS,
            _CROSSREF_TERMS,
        ),
        reviewed_on=date(2026, 9, 27),
        valid_through=date(2026, 10, 27),
        robots_url=_CROSSREF_ROBOTS,
        terms_url=_CROSSREF_TERMS,
        required_terms_phrases=(
            "no sign-up is required to use the REST API",
            "almost none of the metadata is subject to copyright",
            "some abstracts contained in the metadata may be subject to copyright",
        ),
        redirect_urls=(_CROSSREF_WORKS_URL,),
        allowed_operation="search_bibliographic_metadata",
        allowed_fields=(
            "DOI", "title", "publisher", "type", "published", "created", "URL",
            "container-title", "is-referenced-by-count", "author", "score",
        ),
        supports_requirements=("bibliographic_discovery",),
        provenance_requirements=(
            "canonical_url", "external_id", "retrieved_at", "published_at",
            "source_registry_id", "query", "metadata_only",
        ),
        min_interval_seconds=60,
        policy_hostnames=("api.crossref.org", "www.crossref.org"),
    ),
    SourceClearance(
        registry_id="world-bank-indicators-v2",
        display_name="World Bank Indicators API v2",
        collector="world_bank_indicators",
        url=_WORLD_BANK_V2_URL,
        hostname="api.worldbank.org",
        geographies=("GLOBAL",),
        categories=("public_statistics", "macro_demographics", "economic_indicators"),
        allowed_need=(
            "Retrieve bounded country-level annual indicator observations and indicator-level "
            "attribution metadata. Macro statistics do not establish local customer demand."
        ),
        evidence_references=(
            "docs/PUBLIC_SOURCES.md",
            "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation",
            "https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures",
            _WORLD_BANK_TERMS,
            _WORLD_BANK_ROBOTS,
            "https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL",
            "https://api.worldbank.org/v2/indicator/SP.POP.TOTL",
        ),
        reviewed_on=date(2026, 9, 27),
        valid_through=date(2026, 10, 27),
        robots_url=_WORLD_BANK_ROBOTS,
        terms_url=_WORLD_BANK_TERMS,
        required_terms_phrases=(
            "licenses datasets under the creative commons attribution 4.0 international license",
            "many datasets are available under other licenses",
            "license specified externally",
        ),
        redirect_urls=(_WORLD_BANK_V2_URL,),
        allowed_operation="read_indicator_observations_and_indicator_attribution",
        allowed_fields=(
            "indicator.id",
            "indicator.value",
            "country.id",
            "country.value",
            "date",
            "value",
            "unit",
            "source.id",
            "source.value",
            "sourceOrganization",
            "sourceNote",
        ),
        supports_requirements=(
            "macro_demographics",
            "population_baseline",
            "economic_indicator",
        ),
        provenance_requirements=(
            "canonical_url",
            "retrieved_at",
            "source_registry_id",
            "indicator_id",
            "country_code",
            "source_organization",
            "third_party_sources_indicated",
            "attribution",
            "license_basis",
        ),
        min_interval_seconds=1,
        policy_hostnames=(
            "api.worldbank.org",
            "datahelpdesk.worldbank.org",
            "datacatalog.worldbank.org",
        ),
    ),
)


def _valid_https_url(value: str, *, hostname: str | None = None) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and (hostname is None or parsed.hostname == hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def validate_registry(entries: tuple[SourceClearance, ...]) -> tuple[SourceClearance, ...]:
    """Reject ambiguous or overbroad approvals when the registry is loaded."""
    ids: set[str] = set()
    urls: set[str] = set()
    for entry in entries:
        if not entry.registry_id.strip() or entry.registry_id in ids:
            raise ValueError("Source registry IDs must be non-empty and unique")
        if not entry.display_name.strip() or not entry.allowed_need.strip():
            raise ValueError(f"Source registry entry {entry.registry_id} needs a name and bounded need")
        if entry.collector not in {"web", "crossref", "world_bank_indicators"}:
            raise ValueError("Source clearance collector is not supported")
        if not _valid_https_url(entry.url, hostname=entry.hostname) or entry.url in urls:
            raise ValueError(f"Source registry entry {entry.registry_id} needs a unique canonical HTTPS URL")
        if not entry.geographies or any(
            code != "GLOBAL" and (code != code.upper() or len(code) != 2)
            for code in entry.geographies
        ):
            raise ValueError(f"Source registry entry {entry.registry_id} needs normalized geography codes")
        if not entry.categories or any(not value.strip() for value in entry.categories):
            raise ValueError(f"Source registry entry {entry.registry_id} needs at least one category")
        if not entry.evidence_references or any(not value.strip() for value in entry.evidence_references):
            raise ValueError(f"Source registry entry {entry.registry_id} needs review evidence references")
        for reference in entry.evidence_references:
            if reference.startswith("https://"):
                if not _valid_https_url(reference):
                    raise ValueError(f"Source registry entry {entry.registry_id} has an invalid evidence URL")
            else:
                path = PurePosixPath(reference)
                if not reference.startswith("docs/") or ".." in path.parts or path.suffix != ".md":
                    raise ValueError(f"Source registry entry {entry.registry_id} has an invalid documentation reference")
        if entry.reviewed_on > entry.valid_through:
            raise ValueError(f"Source registry entry {entry.registry_id} has an invalid review window")
        policy_hostnames = entry.policy_hostnames or (entry.hostname,)
        if entry.hostname not in policy_hostnames or any(
            not hostname or hostname != hostname.casefold()
            for hostname in policy_hostnames
        ):
            raise ValueError(f"Source registry entry {entry.registry_id} needs explicit policy hosts")
        if not any(_valid_https_url(entry.robots_url, hostname=hostname) for hostname in policy_hostnames):
            raise ValueError(f"Source registry entry {entry.registry_id} needs approved HTTPS robots evidence")
        if not any(_valid_https_url(entry.terms_url, hostname=hostname) for hostname in policy_hostnames):
            raise ValueError(f"Source registry entry {entry.registry_id} needs approved HTTPS terms evidence")
        if not entry.required_terms_phrases or any(not phrase.strip() for phrase in entry.required_terms_phrases):
            raise ValueError(f"Source registry entry {entry.registry_id} needs reviewed terms language")
        if not entry.redirect_urls or entry.url not in entry.redirect_urls:
            raise ValueError(f"Source registry entry {entry.registry_id} must allow its canonical target")
        if any(not _valid_https_url(url, hostname=entry.hostname) for url in entry.redirect_urls):
            raise ValueError(f"Source registry entry {entry.registry_id} has an out-of-scope redirect")
        if entry.min_interval_seconds <= 0:
            raise ValueError(f"Source registry entry {entry.registry_id} needs a positive request interval")
        if not entry.allowed_operation or not entry.allowed_fields:
            raise ValueError(f"Source registry entry {entry.registry_id} needs a bounded operation and fields")
        if not entry.supports_requirements or any(
            not requirement.strip() for requirement in entry.supports_requirements
        ):
            raise ValueError(f"Source registry entry {entry.registry_id} needs explicit evidence requirements")
        if not entry.provenance_requirements or any(
            not requirement.strip() for requirement in entry.provenance_requirements
        ):
            raise ValueError(f"Source registry entry {entry.registry_id} needs provenance requirements")
        ids.add(entry.registry_id)
        urls.add(entry.url)
    return entries


SOURCE_CLEARANCES = validate_registry(SOURCE_CLEARANCES)


def source_clearances() -> tuple[SourceClearance, ...]:
    return SOURCE_CLEARANCES


def capabilities_for_requirement(
    requirement: str,
    *,
    today: date | None = None,
) -> tuple[SourceClearance, ...]:
    """Return only currently cleared capabilities scoped to this evidence need."""
    current_date = today or datetime.now(timezone.utc).date()
    return tuple(
        entry
        for entry in SOURCE_CLEARANCES
        if requirement in entry.supports_requirements
        and entry.reviewed_on <= current_date <= entry.valid_through
    )


def clearance_for_url(url: str) -> SourceClearance | None:
    return next((entry for entry in SOURCE_CLEARANCES if entry.url == url), None)


def clearance_error(url: str, *, today: date | None = None) -> str | None:
    entry = clearance_for_url(url)
    if entry is None:
        return "Source target is not explicitly cleared in docs/PUBLIC_SOURCES.md"
    if not _valid_https_url(url, hostname=entry.hostname) or url != entry.url:
        return "Web URL is not a canonical cleared URL"
    current_date = today or datetime.now(timezone.utc).date()
    if current_date < entry.reviewed_on or current_date > entry.valid_through:
        return f"{entry.display_name} robots and terms clearance has expired; review it before collection"
    return None


def collector_is_cleared(collector: str, *, today: date | None = None) -> bool:
    current_date = today or datetime.now(timezone.utc).date()
    return any(
        entry.collector == collector
        and entry.reviewed_on <= current_date <= entry.valid_through
        for entry in SOURCE_CLEARANCES
    )


def authorize_request(
    url: str,
    *,
    collector: str,
    db,
    today: date | None = None,
    now: datetime | None = None,
) -> CollectionAuthorization:
    """Validate exact scope and reserve a cross-instance persistent rate slot."""
    entry = clearance_for_url(url)
    if entry is None or entry.collector != collector:
        raise PermissionError("Requested source target is not cleared for this collector")
    error = clearance_error(url, today=today)
    if error:
        raise PermissionError(error)
    if db is None:
        raise PermissionError("A database-backed source rate reservation is required")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(seconds=entry.min_interval_seconds)
    gate = models.SourceFetchGate
    dialect_name = db.get_bind().dialect.name
    values = {"registry_id": entry.registry_id, "last_reserved_at": current}
    if dialect_name == "sqlite":
        statement = sqlite_insert(gate).values(**values).on_conflict_do_update(
            index_elements=[gate.registry_id],
            set_={"last_reserved_at": current},
            where=gate.last_reserved_at <= cutoff,
        )
    elif dialect_name == "postgresql":
        statement = pg_insert(gate).values(**values).on_conflict_do_update(
            index_elements=[gate.registry_id],
            set_={"last_reserved_at": current},
            where=gate.last_reserved_at <= cutoff,
        )
    else:
        raise RuntimeError(f"Persistent source rate limits are unsupported for {dialect_name}")
    result = db.execute(statement)
    db.commit()
    if result.rowcount != 1:
        raise SourceRateLimitError("Source rate limit is active; retry after the clearance interval")
    return CollectionAuthorization(entry=entry, reserved_at=current)


def validate_authorization(
    authorization: CollectionAuthorization | None,
    *,
    url: str,
    collector: str,
    today: date | None = None,
) -> SourceClearance:
    if not isinstance(authorization, CollectionAuthorization):
        raise PermissionError("A current source registry authorization is required")
    entry = clearance_for_url(url)
    if entry is None or entry != authorization.entry or entry.collector != collector:
        raise PermissionError("Source authorization does not match the requested target")
    error = clearance_error(url, today=today)
    if error:
        raise PermissionError(error)
    return entry


def clearance_metadata(entry: SourceClearance) -> dict:
    data = asdict(entry)
    for key in ("reviewed_on", "valid_through"):
        data[key] = data[key].isoformat()
    for key in (
        "geographies", "categories", "evidence_references",
        "required_terms_phrases", "redirect_urls", "policy_hostnames",
        "allowed_fields", "supports_requirements", "provenance_requirements",
    ):
        data[key] = list(data[key])
    return data
