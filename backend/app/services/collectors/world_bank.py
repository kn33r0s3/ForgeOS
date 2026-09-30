"""Bounded, attributed observations from the World Bank Indicators API v2."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.robotparser
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import source_clearance_registry
from app.services.collectors.base import SourceCollector

API_ROOT = "https://api.worldbank.org/v2"
ROBOTS_URL = "https://api.worldbank.org/robots.txt"
TERMS_URL = "https://datacatalog.worldbank.org/public-licenses"
USER_AGENT = "ForgeOS/0.1 (World Bank Indicators; https://github.com/kn33r0s3/ForgeOS)"
TIMEOUT_SECONDS = 15
MAX_YEAR_SPAN = 20
_COUNTRY_CODE = re.compile(r"^[A-Za-z]{2,3}$")
_INDICATOR_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_PERMITTED_OBSERVATION_FIELDS = (
    "indicator",
    "country",
    "date",
    "value",
    "unit",
    "source",
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


class _SameWorldBankApiRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        original = urllib.parse.urlsplit(req.full_url)
        if (
            destination.scheme != "https"
            or destination.hostname != "api.worldbank.org"
            or destination.path != original.path
            or destination.username is not None
            or destination.password is not None
        ):
            raise RuntimeError("World Bank API redirected outside the exact cleared API path")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class WorldBankCollector(SourceCollector):
    source_name = "world_bank_indicators"
    source_type = "world_bank_indicators"

    def collect(self, query: str, *, db: Session) -> list[dict[str, Any]]:
        request_spec = _parse_request(query)
        return self.fetch_indicator(db=db, **request_spec)

    def fetch_indicator(
        self,
        *,
        db: Session,
        country_code: str,
        indicator_id: str,
        start_year: int,
        end_year: int,
    ) -> list[dict[str, Any]]:
        country_code, indicator_id = _validate_scope(
            country_code, indicator_id, start_year, end_year
        )
        entry = _active_clearance()
        self._verify_live_policy(entry)

        metadata_url = f"{API_ROOT}/indicator/{indicator_id}"
        self._request_authorization(db, entry)
        indicator_metadata = _read_json(metadata_url, {"format": "json", "per_page": "1"})
        metadata = _indicator_metadata(indicator_metadata, indicator_id)

        data_url = f"{API_ROOT}/country/{country_code}/indicator/{indicator_id}"
        self._request_authorization(db, entry)
        payload = _read_json(
            data_url,
            {
                "format": "json",
                "date": f"{start_year}:{end_year}",
                "per_page": str(MAX_YEAR_SPAN + 1),
            },
        )
        observations = _observation_rows(payload)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        results: list[dict[str, Any]] = []
        for row in observations:
            observation = _permitted_observation(row)
            if observation["value"] is None:
                continue
            country = observation["country"]
            indicator = observation["indicator"]
            year = observation["date"]
            if not isinstance(country, dict) or not isinstance(indicator, dict):
                raise RuntimeError("World Bank observation is missing country or indicator identity")
            if not isinstance(year, str) or not year.isdigit():
                raise RuntimeError("World Bank observation has an invalid year")
            response_iso3 = row.get("countryiso3code")
            if (
                str(country.get("id", "")).casefold() != country_code.casefold()
                and (
                    not isinstance(response_iso3, str)
                    or response_iso3.casefold() != country_code.casefold()
                )
            ):
                raise RuntimeError("World Bank observation country does not match the requested country")
            if str(indicator.get("id", "")) != indicator_id:
                raise RuntimeError("World Bank observation indicator does not match the requested indicator")
            if not start_year <= int(year) <= end_year:
                raise RuntimeError("World Bank observation year is outside the requested range")

            country_name = _required_text(country.get("value"), "country name")
            indicator_name = _required_text(indicator.get("value"), "indicator name")
            external_id = f"{country_code.upper()}:{indicator_id}:{year}"
            source_organizations = metadata["source_organization"]
            third_party_sources = bool(source_organizations)
            content = (
                f"Country: {country_name}, Indicator: {indicator_name}, Year: {year}, "
                f"Value: {observation['value']}"
            )
            if observation["unit"]:
                content += f" {observation['unit']}"
            provenance = {
                "source_registry_id": entry.registry_id,
                "api_endpoint": data_url,
                "canonical_url": _request_url(
                    data_url,
                    {
                        "format": "json",
                        "date": f"{start_year}:{end_year}",
                        "per_page": str(MAX_YEAR_SPAN + 1),
                    },
                ),
                "metadata_endpoint": _request_url(
                    metadata_url, {"format": "json", "per_page": "1"}
                ),
                "retrieved_at": retrieved_at,
                "source_type": self.source_name,
                "traceable": True,
                "country_code": country_code.upper(),
                "country_name": country_name,
                "indicator_id": indicator_id,
                "indicator_name": indicator_name,
                "year": int(year),
                "value": observation["value"],
                "unit": observation["unit"],
                "source_id": external_id,
                "world_bank_source_id": metadata["source_id"],
                "source_name": metadata["source_name"],
                "source_organization": source_organizations,
                "source_note": metadata["source_note"],
                "third_party_sources_indicated": third_party_sources,
                "ownership_assessment": (
                    "third-party source organizations listed; ownership is not inferred"
                    if third_party_sources
                    else "no source organizations listed; this does not prove exclusive ownership"
                ),
                "license_basis": (
                    "World Bank Data Catalog states CC BY 4.0 is the default for World Bank-produced "
                    "open datasets and that some datasets use other licenses; the API response does "
                    "not provide an indicator-specific license."
                ),
                "license_status": (
                    "unconfirmed_third_party"
                    if third_party_sources
                    else "dataset_default_requires_attribution; indicator_specific_license_unreported"
                ),
                "license_compatibility_verified": False,
                "attribution": _attribution(metadata),
                "retrieved_fields": list(_PERMITTED_OBSERVATION_FIELDS),
                "metadata_fields": ["name", "source.id", "source.value", "sourceOrganization", "sourceNote"],
                "observation": observation,
            }
            results.append(
                {
                    "content": content,
                    "title": f"{indicator_name} — {country_name} ({year})",
                    "canonical_url": provenance["canonical_url"],
                    "external_id": external_id,
                    "timestamp": retrieved_at,
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

    def _request_authorization(self, db: Session, entry) -> None:
        while True:
            try:
                authorization = source_clearance_registry.authorize_request(
                    API_ROOT,
                    collector=self.source_name,
                    db=db,
                )
                source_clearance_registry.validate_authorization(
                    authorization,
                    url=API_ROOT,
                    collector=self.source_name,
                )
                return
            except source_clearance_registry.SourceRateLimitError:
                gate = (
                    db.query(models.SourceFetchGate)
                    .filter_by(registry_id=entry.registry_id)
                    .first()
                )
                if gate is None:
                    raise
                now = datetime.now(timezone.utc)
                last_reserved = gate.last_reserved_at
                if last_reserved.tzinfo is None:
                    last_reserved = last_reserved.replace(tzinfo=timezone.utc)
                elapsed = (now - last_reserved).total_seconds()
                time.sleep(max(0.01, entry.min_interval_seconds - elapsed + 0.02))

    def _verify_live_policy(self, entry) -> None:
        request = urllib.request.Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                robots_text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise RuntimeError("Could not recheck World Bank API robots policy") from exc
            robots_text = ""
        except Exception as exc:
            raise RuntimeError("Could not recheck World Bank API robots policy") from exc
        if robots_text:
            robots = urllib.robotparser.RobotFileParser(ROBOTS_URL)
            robots.parse(robots_text.splitlines())
            if not robots.can_fetch(USER_AGENT, API_ROOT):
                raise PermissionError("World Bank API robots policy disallows this API")

        request = urllib.request.Request(TERMS_URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise RuntimeError("Could not recheck World Bank data license terms") from exc
        parser = _TextExtractor()
        parser.feed(html)
        terms = " ".join(parser.parts).casefold()
        if not all(phrase.casefold() in terms for phrase in entry.required_terms_phrases):
            raise PermissionError("World Bank data license terms no longer match reviewed clearance")


def fetch_indicator(
    country_code: str,
    indicator_id: str,
    start_year: int,
    end_year: int,
    *,
    db: Session,
) -> list[models.Evidence]:
    """Fetch and persist attributable observations through the shared evidence pipeline."""
    collector = WorldBankCollector()
    items = collector.fetch_indicator(
        db=db,
        country_code=country_code,
        indicator_id=indicator_id,
        start_year=start_year,
        end_year=end_year,
    )
    from app.services.observer_engine import ObserverEngine

    observer = ObserverEngine(db)
    evidence_items: list[models.Evidence] = []
    for item in items:
        normalized = collector.normalize(item)
        signal = observer.observe(
            normalized["content"],
            source=collector.source_name,
            metadata=normalized,
        )
        evidence = (
            db.query(models.Evidence)
            .filter_by(signal_id=signal.id)
            .order_by(models.Evidence.id.desc())
            .first()
        )
        if evidence is not None:
            evidence_items.append(evidence)
    return evidence_items


def _active_clearance():
    entry = source_clearance_registry.clearance_for_url(API_ROOT)
    if entry is None or entry.collector != WorldBankCollector.source_name:
        raise PermissionError("World Bank Indicators API has no active source clearance")
    error = source_clearance_registry.clearance_error(API_ROOT)
    if error:
        raise PermissionError(error)
    return entry


def _validate_scope(
    country_code: str,
    indicator_id: str,
    start_year: int,
    end_year: int,
) -> tuple[str, str]:
    if not isinstance(country_code, str) or not _COUNTRY_CODE.fullmatch(country_code):
        raise ValueError("country_code must be a 2- or 3-letter ISO code")
    if not isinstance(indicator_id, str) or not _INDICATOR_ID.fullmatch(indicator_id):
        raise ValueError("indicator_id contains unsupported characters")
    current_year = datetime.now(timezone.utc).year
    if (
        isinstance(start_year, bool)
        or isinstance(end_year, bool)
        or not isinstance(start_year, int)
        or not isinstance(end_year, int)
        or start_year < 1900
        or end_year < start_year
        or end_year > current_year
        or end_year - start_year > MAX_YEAR_SPAN
    ):
        raise ValueError(f"year range must be ordered, current, and no wider than {MAX_YEAR_SPAN} years")
    return country_code.upper(), indicator_id


def _parse_request(query: str) -> dict[str, Any]:
    try:
        value = json.loads(query)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("World Bank task query must be a JSON object with an explicit country, indicator, and year range") from exc
    if not isinstance(value, dict):
        raise ValueError("World Bank task query must be a JSON object")
    return {
        "country_code": value.get("country_code"),
        "indicator_id": value.get("indicator_id"),
        "start_year": value.get("start_year"),
        "end_year": value.get("end_year"),
    }


def _request_url(endpoint: str, params: dict[str, str]) -> str:
    return f"{endpoint}?{urllib.parse.urlencode(params)}"


def _read_json(endpoint: str, params: dict[str, str]) -> Any:
    url = _request_url(endpoint, params)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    opener = urllib.request.build_opener(_SameWorldBankApiRedirect())
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise source_clearance_registry.SourceRateLimitError(
                "World Bank Indicators API returned HTTP 429; defer until its rate window"
            ) from exc
        detail = exc.read(500).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"World Bank Indicators API returned HTTP {exc.code}: {detail}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("World Bank Indicators API returned invalid JSON") from exc
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"World Bank Indicators API request failed: {exc}") from exc
    return payload


def _indicator_metadata(payload: Any, expected_id: str) -> dict[str, Any]:
    rows = _response_rows(payload)
    metadata = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and row.get("id") == expected_id
        ),
        None,
    )
    if metadata is None:
        raise RuntimeError("World Bank indicator metadata did not contain the requested indicator")
    source = metadata.get("source")
    source = source if isinstance(source, dict) else {}
    return {
        "indicator_name": _required_text(metadata.get("name"), "indicator name"),
        "unit": metadata.get("unit") if isinstance(metadata.get("unit"), str) else "",
        "source_id": source.get("id"),
        "source_name": source.get("value"),
        "source_organization": (
            metadata.get("sourceOrganization")
            if isinstance(metadata.get("sourceOrganization"), str)
            else ""
        ),
        "source_note": (
            metadata.get("sourceNote")
            if isinstance(metadata.get("sourceNote"), str)
            else ""
        ),
    }


def _response_rows(payload: Any) -> list[Any]:
    if (
        isinstance(payload, list)
        and len(payload) >= 2
        and isinstance(payload[1], list)
    ):
        return payload[1]
    if isinstance(payload, list) and len(payload) >= 2 and isinstance(payload[1], dict):
        messages = payload[1].get("message")
        if isinstance(messages, list):
            raise RuntimeError(
                "World Bank API rejected the request: "
                + "; ".join(str(item.get("value", "")) for item in messages if isinstance(item, dict))
            )
    raise RuntimeError("World Bank API response did not contain the expected JSON envelope")


def _observation_rows(payload: Any) -> list[dict[str, Any]]:
    rows = _response_rows(payload)
    return [row for row in rows if isinstance(row, dict)]


def _permitted_observation(row: dict[str, Any]) -> dict[str, Any]:
    result = {field: row.get(field) for field in _PERMITTED_OBSERVATION_FIELDS}
    indicator = result["indicator"]
    country = result["country"]
    result["indicator"] = {
        key: indicator.get(key)
        for key in ("id", "value")
        if isinstance(indicator, dict)
    }
    result["country"] = {
        key: country.get(key)
        for key in ("id", "value")
        if isinstance(country, dict)
    }
    source = result["source"]
    result["source"] = {
        key: source.get(key)
        for key in ("id", "value")
        if isinstance(source, dict)
    }
    return result


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"World Bank API did not provide {name}")
    return value.strip()


def _attribution(metadata: dict[str, Any]) -> str:
    if metadata.get("source_name"):
        parts = [f"World Bank, {metadata['source_name']}"]
    else:
        parts = ["World Bank, World Development Indicators"]
    if metadata.get("source_organization"):
        parts.append(f"underlying source organizations: {metadata['source_organization']}")
    return "; ".join(parts)
