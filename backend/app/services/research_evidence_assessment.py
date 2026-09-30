"""Conservative, explainable metadata assessment for research source records."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app import models
from sqlalchemy.orm import Session

_STOP_WORDS = {
    "about", "after", "against", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "should", "some", "than", "that", "their", "there",
    "these", "they", "this", "through", "under", "using", "what", "when",
    "where", "which", "while", "with", "would", "your",
}

WORLD_BANK_MACRO_REQUIREMENTS = frozenset(
    {"macro_demographics", "population_baseline", "economic_indicator"}
)
WORLD_BANK_MICRO_REQUIREMENTS = frozenset(
    {
        "buyer_willingness_to_pay",
        "product_demand",
        "customer_pain",
        "problem_incidence",
        "alternatives_and_costs",
        "disconfirming_evidence",
    }
)
GDELT_MARKET_REQUIREMENTS = frozenset(
    {"customer_pain", "buyer_willingness_to_pay", "product_demand", "market_size", "financial_viability"}
)
OPENALEX_SCHOLARLY_REQUIREMENTS = frozenset(
    {
        "scholarly_evidence",
        "prior_research",
        "documented_intervention",
        "literature_existence",
    }
)


def openalex_requirement_eligibility(
    requirement_id: str,
    provenance: dict[str, Any],
) -> tuple[bool, str]:
    """Use OpenAlex only for traceable literature observations, not market claims."""
    if requirement_id in {
        "customer_pain",
        "buyer_willingness_to_pay",
        "local_market_size",
        "market_size",
        "revenue_potential",
        "product_demand",
    }:
        return False, "scholarly_retrieval_cannot_validate_local_demand_or_revenue"
    if requirement_id == "local_applicability":
        return False, "openalex_affiliations_and_abstracts_do_not_establish_local_applicability"
    if requirement_id not in OPENALEX_SCHOLARLY_REQUIREMENTS:
        return False, "openalex_work_not_scoped_to_this_requirement"
    if provenance.get("source_registry_id") != "openalex-public-works-cc0":
        return False, "openalex_source_clearance_provenance_missing"
    if provenance.get("source_type") != "openalex" or provenance.get("license") != "CC0":
        return False, "openalex_cc0_provenance_missing"
    if provenance.get("traceable") is not True:
        return False, "openalex_work_is_not_traceable"
    openalex_id = provenance.get("openalex_id")
    if not isinstance(openalex_id, str) or not re.fullmatch(
        r"https://openalex\.org/W\d+",
        openalex_id,
    ):
        return False, "openalex_work_identity_missing"
    if not provenance.get("title") or not provenance.get("query"):
        return False, "openalex_title_or_search_query_missing"
    if requirement_id != "literature_existence" and (
        provenance.get("abstract_reconstructed") is not True
        or not isinstance(provenance.get("abstract"), str)
        or not provenance["abstract"].strip()
    ):
        return False, "openalex_abstract_not_available_for_scholarly_observation"
    if provenance.get("geographic_scope_status") != "not_assessed_from_affiliations_or_retrieval_relevance":
        return False, "openalex_geographic_alignment_must_remain_unassessed"
    if provenance.get("temporal_scope_status") != "publication_year_only_not_study_period":
        return False, "openalex_temporal_alignment_must_remain_unassessed"
    if provenance.get("retrieval_relevance_is_not_empirical_support") is not True:
        return False, "openalex_retrieval_relevance_cannot_be_empirical_support"
    return True, "openalex_literature_record_observed_without_local_or_empirical_claim"


def gdelt_requirement_eligibility(
    requirement_id: str,
    provenance: dict[str, Any],
) -> tuple[bool, str]:
    """Treat GDELT records as evidence of coverage, never of article claims."""
    if requirement_id in GDELT_MARKET_REQUIREMENTS:
        return False, "media_coverage_metadata_cannot_validate_commercial_demand_or_viability"
    if requirement_id not in {
        "media_coverage_observation",
        "recent_event_signal",
        "public_reporting_velocity",
    }:
        return False, "gdelt_article_metadata_not_scoped_to_this_requirement"
    if provenance.get("source_registry_id") != "gdelt-doc-api-v2":
        return False, "gdelt_source_clearance_provenance_missing"
    if provenance.get("source_type") != "gdelt_doc" or provenance.get("metadata_only") is not True:
        return False, "gdelt_article_content_was_not_reviewed"
    if provenance.get("traceable") is not True:
        return False, "gdelt_article_metadata_is_not_traceable"
    if not provenance.get("canonical_url") or not provenance.get("domain"):
        return False, "gdelt_article_url_or_domain_missing"
    if not provenance.get("published_at") or not provenance.get("retrieved_at"):
        return False, "gdelt_article_publication_or_retrieval_time_missing"
    if not provenance.get("query") or provenance.get("attribution") != (
        "GDELT Project (https://www.gdeltproject.org/)"
    ):
        return False, "gdelt_query_or_attribution_missing"
    if provenance.get("article_body_fetched") is not False:
        return False, "gdelt_article_body_retrieval_not_permitted"
    if requirement_id == "public_reporting_velocity":
        result_count = provenance.get("reported_result_count")
        max_records = provenance.get("max_records")
        if (
            provenance.get("result_set_capped") is not False
            or not isinstance(result_count, int)
            or isinstance(result_count, bool)
            or result_count < 1
            or not isinstance(max_records, int)
            or isinstance(max_records, bool)
            or not result_count < max_records <= 25
            or provenance.get("timespan") not in {"1d", "3d", "1w", "1m", "3m"}
        ):
            return False, "capped_or_unbounded_gdelt_result_set_cannot_measure_reporting_velocity"
        return True, "bounded_gdelt_indexed_article_count_over_declared_timespan"
    return True, "attributable_observation_of_media_coverage_only"


def world_bank_requirement_eligibility(
    requirement_id: str,
    provenance: dict[str, Any],
    *,
    expected_country: str | None = None,
    expected_indicator: str | None = None,
    expected_years: tuple[int, int] | None = None,
) -> tuple[bool, str]:
    """Allow attributable macro observations only; never use them for market claims."""
    if requirement_id in {"problem_incidence", "customer_pain"}:
        return False, "macro_indicator_data_cannot_validate_customer_pain_or_micro_incidence"
    if requirement_id == "alternatives_and_costs":
        return False, "macro_indicator_data_cannot_validate_product_alternatives_or_prices"
    if requirement_id in WORLD_BANK_MICRO_REQUIREMENTS:
        return False, "macro_indicator_data_cannot_validate_micro_demand_or_buyer_willingness_to_pay"
    if requirement_id not in WORLD_BANK_MACRO_REQUIREMENTS:
        return False, "world_bank_indicator_not_scoped_to_this_requirement"
    if provenance.get("source_registry_id") != "world-bank-indicators-v2":
        return False, "world_bank_source_clearance_provenance_missing"
    if not provenance.get("canonical_url") or not provenance.get("attribution"):
        return False, "world_bank_canonical_source_or_attribution_missing"
    if not provenance.get("indicator_id") or not provenance.get("country_code"):
        return False, "world_bank_indicator_or_country_identity_missing"
    if not isinstance(provenance.get("value"), (int, float)) or isinstance(
        provenance.get("value"), bool
    ):
        return False, "world_bank_observation_value_missing_or_non_numeric"
    if not isinstance(provenance.get("third_party_sources_indicated"), bool):
        return False, "world_bank_third_party_source_assessment_missing"
    if provenance["third_party_sources_indicated"] and (
        provenance.get("license_status") != "confirmed_cc_by_4.0"
        or provenance.get("license_compatibility_verified") is not True
    ):
        return False, "world_bank_third_party_license_unconfirmed"
    if expected_country and provenance["country_code"].casefold() != expected_country.casefold():
        return False, "world_bank_observation_country_out_of_scope"
    if expected_indicator and provenance["indicator_id"] != expected_indicator:
        return False, "world_bank_observation_indicator_out_of_scope"
    if expected_years:
        year = provenance.get("year")
        if not isinstance(year, int) or not expected_years[0] <= year <= expected_years[1]:
            return False, "world_bank_observation_year_out_of_scope"
    return True, "attributable_macro_indicator_observation"


def _terms(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", value.casefold())
        if token not in _STOP_WORDS
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assess_source_record(
    query: str,
    *,
    title: str | None,
    content: str | None,
    published_at: datetime | None,
    retrieved_at: datetime | None,
    source_identity: str | None = None,
    canonical_url: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe observable metadata without inferring semantic support."""
    query_terms = _terms(query)
    record_terms = _terms(f"{title or ''} {content or ''}")
    matched_terms = sorted(query_terms & record_terms)

    publication_age_days = None
    if published_at is not None and retrieved_at is not None:
        publication_age_days = (
            _as_utc(retrieved_at) - _as_utc(published_at)
        ).days

    return {
        "assessment_state": (
            "metadata_only_lead"
            if provenance and provenance.get("metadata_only") is True
            else "content_not_reviewed"
        ),
        "provenance": {
            "present": bool(provenance),
            "source_registry_id": (provenance or {}).get("source_registry_id"),
            "retrieval_timestamp": _as_utc(retrieved_at).isoformat() if retrieved_at else None,
            "publication_timestamp": _as_utc(published_at).isoformat() if published_at else None,
            "canonical_url": canonical_url,
            "source_identity": source_identity,
        },
        "keyword_overlap": {
            "method": "case-insensitive exact-token overlap; not semantic relevance",
            "query_term_count": len(query_terms),
            "matched_terms": matched_terms,
            "unmatched_terms": sorted(query_terms - record_terms),
        },
        "publication_age_days": publication_age_days,
        "freshness_basis": (
            "publication date compared with retrieval time"
            if publication_age_days is not None
            else "publication age unavailable because a date is missing"
        ),
        "source_record": "retrieved record; substantive claims not reviewed",
        "source_reliability": "unassessed",
        "semantic_relevance": "unassessed",
        "contradictions": "unassessed",
        "claim_support": "not_inferred",
    }


def explicit_contradiction_edges(
    db: Session,
    evidence_ids: list[int],
) -> list[dict[str, int]]:
    """Return only persisted, explicitly typed contradiction relationships."""
    if not evidence_ids:
        return []
    rows = (
        db.query(models.EvidenceRelationship)
        .filter(
            models.EvidenceRelationship.evidence_id.in_(set(evidence_ids)),
            models.EvidenceRelationship.relation_type == "contradicts",
        )
        .order_by(models.EvidenceRelationship.id)
        .all()
    )
    return [
        {"evidence_id": row.evidence_id, "claim_id": row.claim_id}
        for row in rows
    ]
