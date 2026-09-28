"""Build bounded, requirement-first plans over the existing research records."""

from __future__ import annotations

import copy
from hashlib import sha256
import json
import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import research_task_engine, source_clearance_registry
from app.services.research_evidence_assessment import (
    explicit_contradiction_edges,
    gdelt_requirement_eligibility,
    openalex_requirement_eligibility,
    world_bank_requirement_eligibility,
)

MAX_TASKS_PER_QUESTION = 5
_OPENALEX_UNRESOLVED_DIMENSIONS = [
    "local_applicability",
    "population_alignment",
    "study_period",
    "customer_pain",
    "buyer_willingness_to_pay",
    "local_market_size",
    "product_demand",
    "commercial_viability",
]
_COMMERCIAL_REQUIREMENT_IDS = frozenset(
    {
        "buyer_willingness_to_pay",
        "customer_pain",
        "commercial_demand",
        "product_demand",
    }
)
_GEOGRAPHY_TERMS = (
    "Nepal",
    "India",
    "Bangladesh",
    "Pakistan",
    "Bhutan",
    "China",
    "United States",
    "United Kingdom",
    "Africa",
    "South Asia",
)
_POPULATION_TERMS = (
    "smallholder farmers",
    "subsistence farmers",
    "rural households",
    "urban households",
    "microenterprises",
    "small businesses",
    "farmers",
    "households",
    "students",
    "patients",
)
_QUESTION_WORDS = frozenset(
    {"what", "which", "who", "when", "where", "why", "how"}
)
_COUNTRY_ISO3 = {
    "bangladesh": "BGD",
    "bhutan": "BTN",
    "china": "CHN",
    "india": "IND",
    "nepal": "NPL",
    "pakistan": "PAK",
}

_STOP_WORDS = {
    "about", "after", "against", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "should", "some", "than", "that", "their", "there",
    "these", "they", "this", "through", "under", "using", "what", "when",
    "where", "which", "while", "with", "would", "your",
}

_UNCERTAINTIES = [
    "Problem prevalence, frequency, and severity are unverified.",
    "Affected customer groups, decision authority, and willingness to pay are unknown.",
    "Existing alternatives, prices, switching costs, and competitor performance are unverified.",
    "Required resources, capabilities, distribution, legal constraints, startup costs, and downside risk are unassessed.",
    "Disconfirming evidence has not been reviewed against source content.",
]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", text.casefold())
        if token not in _STOP_WORDS
    }


def _topic(question_text: str) -> str:
    return " ".join(question_text.split()).rstrip("?.! ")


def _objective_profile(question_text: str) -> str | None:
    if re.search(
        r"\b(?:corridor|freight|logistics|shipment|supply chain|"
        r"transport|warehouse|distribution route)\b",
        question_text,
        re.I,
    ):
        return "logistics"
    if re.search(
        r"\b(?:software|saas|service|platform|application|mobile app|"
        r"workflow|subscription|digital product|api)\b",
        question_text,
        re.I,
    ):
        return "software_service"
    if re.search(
        r"\b(?:agricultur\w*|farmer\w*|crop\w*|postharvest|post-harvest|"
        r"harvest|commodity|grain|produce|livestock|food loss)\b",
        question_text,
        re.I,
    ):
        return "agriculture_commodity"
    return None


def _country_scope(question_text: str, indicator_id: str) -> dict[str, Any] | None:
    country = _openalex_qualifications(question_text)["geographic_qualification"]
    if not country:
        return None
    country_code = _COUNTRY_ISO3.get(country.casefold())
    if not country_code:
        return None
    current_year = date.today().year
    return {
        "country_code": country_code,
        "indicator_id": indicator_id,
        "start_year": current_year - 5,
        "end_year": current_year - 1,
    }


def _domain_requirement_specs(
    question_text: str,
    profile: str,
) -> list[dict[str, Any]]:
    topic = _topic(question_text)
    country = _openalex_qualifications(question_text)["geographic_qualification"]
    specs: list[dict[str, Any]] = []

    if profile == "agriculture_commodity":
        specs.extend(
            [
                {
                    "id": "scholarly_evidence",
                    "question": f"What scholarly evidence documents {topic}?",
                    "evidence_kind": "openalex_scholarly_abstract",
                    "can_resolve_claim": False,
                    "openalex_query": topic,
                },
                {
                    "id": "documented_intervention",
                    "question": f"What documented interventions address {topic}?",
                    "evidence_kind": "openalex_scholarly_abstract",
                    "can_resolve_claim": False,
                    "openalex_query": f"documented interventions: {topic}",
                },
            ]
        )
        population_scope = _country_scope(question_text, "SP.POP.TOTL")
        if population_scope:
            specs.append(
                {
                    "id": "population_baseline",
                    "question": f"What country-level population baseline is available for {country}?",
                    "evidence_kind": "attributed_macro_indicator_observation",
                    "can_resolve_claim": False,
                    "world_bank_scope": population_scope,
                }
            )
        if re.search(r"\b(?:economic|GDP|income|macro(?:economic)? context)\b", question_text, re.I):
            economic_scope = _country_scope(question_text, "NY.GDP.MKTP.CD")
            if economic_scope:
                specs.append(
                    {
                        "id": "economic_indicator",
                        "question": f"What bounded national economic context is available for {country}?",
                        "evidence_kind": "attributed_macro_indicator_observation",
                        "can_resolve_claim": False,
                        "world_bank_scope": economic_scope,
                    }
                )
        specs.append(
            {
                "id": "buyer_willingness_to_pay",
                "question": f"What direct buyer evidence establishes willingness to pay for {topic}?",
                "evidence_kind": "buyer_response_or_transaction",
                "can_resolve_claim": True,
            }
        )
        return specs

    if profile == "software_service":
        specs.extend(
            [
                {
                    "id": "problem_incidence",
                    "question": f"What evidence measures prevalence of the software/service problem in {topic}?",
                    "evidence_kind": "observations_of_incidence",
                    "can_resolve_claim": False,
                },
                {
                    "id": "scholarly_evidence",
                    "question": f"What scholarly work discusses technical approaches relevant to {topic}?",
                    "evidence_kind": "openalex_scholarly_abstract",
                    "can_resolve_claim": False,
                    "openalex_query": topic,
                },
                {
                    "id": "bibliographic_discovery",
                    "question": f"What published solutions or related work may merit review for {topic}?",
                    "evidence_kind": "bibliographic_metadata",
                    "can_resolve_claim": False,
                },
                {
                    "id": "buyer_willingness_to_pay",
                    "question": f"What direct buyer evidence establishes willingness to pay for {topic}?",
                    "evidence_kind": "buyer_response_or_transaction",
                    "can_resolve_claim": True,
                },
            ]
        )
        return specs

    specs.extend(
        [
            {
                "id": "scholarly_evidence",
                "question": f"What scholarly work documents operational bottlenecks relevant to {topic}?",
                "evidence_kind": "openalex_scholarly_abstract",
                "can_resolve_claim": False,
                "openalex_query": topic,
            },
            {
                "id": "regulatory_environment",
                "question": f"What authoritative regulatory evidence applies to the corridor in {topic}?",
                "evidence_kind": "authoritative_regulatory_record",
                "can_resolve_claim": False,
            },
            {
                "id": "buyer_willingness_to_pay",
                "question": f"What direct buyer or transaction evidence validates demand for {topic}?",
                "evidence_kind": "buyer_response_or_transaction",
                "can_resolve_claim": True,
            },
        ]
    )
    if country:
        for requirement_id, indicator_id, label in (
            ("population_baseline", "SP.POP.TOTL", "population"),
            ("economic_indicator", "NY.GDP.MKTP.CD", "economic volume"),
        ):
            scope = _country_scope(question_text, indicator_id)
            if scope:
                specs.append(
                    {
                        "id": requirement_id,
                        "question": f"What bounded national {label} baseline is available for {country}?",
                        "evidence_kind": "attributed_macro_indicator_observation",
                        "can_resolve_claim": False,
                        "world_bank_scope": scope,
                    }
                )
    return specs


def _requirement_specs(question_text: str) -> list[dict[str, Any]]:
    topic = _topic(question_text)
    profile = _objective_profile(question_text)
    if profile:
        return _domain_requirement_specs(question_text, profile)

    requirements = [
        {
            "id": "bibliographic_discovery",
            "question": f"Which scholarly publications may merit content review for: {topic}?",
            "evidence_kind": "bibliographic_metadata",
            "can_resolve_claim": False,
        },
        {
            "id": "problem_incidence",
            "question": f"What independent observations measure whether and how often this problem occurs: {topic}?",
            "evidence_kind": "observations_of_incidence",
            "can_resolve_claim": True,
        },
        {
            "id": "alternatives_and_costs",
            "question": f"What existing alternatives and documented costs address: {topic}?",
            "evidence_kind": "solution_and_price_observations",
            "can_resolve_claim": True,
        },
        {
            "id": "disconfirming_evidence",
            "question": f"What source content could disconfirm or materially limit this premise: {topic}?",
            "evidence_kind": "claim_counterevidence",
            "can_resolve_claim": True,
        },
        {
            "id": "buyer_willingness_to_pay",
            "question": f"What actual evidence establishes buyer authority and willingness to pay for: {topic}?",
            "evidence_kind": "buyer_response_or_transaction",
            "can_resolve_claim": True,
        },
    ]
    if re.search(
        r"\bmedia\b|\bnews\b|\breporting\b|\bcoverage\b|\brecent event\b",
        question_text,
        re.I,
    ) or re.search(
        r"\b(?:credible opportunity|determine whether|postharvest loss)\b",
        question_text,
        re.I,
    ):
        if re.search(
            r"\breporting velocity\b|"
            r"\b(?:credible opportunity|determine whether|postharvest loss)\b",
            question_text,
            re.I,
        ):
            requirements.append(
                {
                    "id": "public_reporting_velocity",
                    "question": (
                        f"What uncapped count of GDELT-indexed articles matching this query was "
                        f"observed over the bounded time window for: {topic}?"
                    ),
                    "evidence_kind": "bounded_reporting_timeline",
                    "can_resolve_claim": False,
                    "gdelt_query": topic,
                }
            )
        else:
            requirement_id = (
                "recent_event_signal"
                if re.search(r"\brecent event\b", question_text, re.I)
                else "media_coverage_observation"
            )
            requirements.append(
                {
                    "id": requirement_id,
                    "question": f"What recent media coverage is indexed for: {topic}?",
                    "evidence_kind": "article_metadata_observation",
                    "can_resolve_claim": False,
                    "gdelt_query": topic,
                }
            )
    world_bank_scope = _world_bank_scope(question_text)
    if world_bank_scope:
        indicator_id = world_bank_scope["indicator_id"]
        if indicator_id.startswith("SP.POP."):
            requirement_id = "population_baseline"
        elif indicator_id.startswith(("NY.", "NE.", "FP.CPI.")):
            requirement_id = "economic_indicator"
        else:
            requirement_id = "macro_demographics"
        requirements.append(
            {
                "id": requirement_id,
                "question": (
                    f"What country-level World Bank indicator observations are available for "
                    f"{world_bank_scope['country_code']} {indicator_id} "
                    f"({world_bank_scope['start_year']}-{world_bank_scope['end_year']})?"
                ),
                "evidence_kind": "attributed_macro_indicator_observation",
                "can_resolve_claim": False,
                "world_bank_scope": world_bank_scope,
            }
        )
    broad_research_objective = re.search(
        r"\b(?:credible opportunity|determine whether|reduce|intervention|postharvest loss)\b",
        question_text,
        re.I,
    )
    has_scholarly_need = re.search(
        r"\b(scholarly evidence|prior research|prior literature|documented intervention|"
        r"literature existence|academic evidence|what studies|what research)\b",
        question_text,
        re.I,
    ) or broad_research_objective
    if has_scholarly_need:
        if re.search(r"\bdocumented intervention\b", question_text, re.I):
            scholarly_requirement_id = "documented_intervention"
        elif re.search(r"\bprior research\b|\bprior literature\b", question_text, re.I):
            scholarly_requirement_id = "prior_research"
        elif re.search(r"\bliterature existence\b", question_text, re.I):
            scholarly_requirement_id = "literature_existence"
        else:
            scholarly_requirement_id = "scholarly_evidence"
        requirements.append(
            {
                "id": scholarly_requirement_id,
                "question": f"What scholarly works and abstracts are indexed about: {topic}?",
                "evidence_kind": "openalex_scholarly_abstract",
                "can_resolve_claim": False,
                "openalex_query": topic,
            }
        )
        if (
            scholarly_requirement_id != "documented_intervention"
            and re.search(
                r"\b(?:intervention|reduce|mitigat|solution)\w*\b",
                question_text,
                re.I,
            )
        ):
            requirements.append(
                {
                    "id": "documented_intervention",
                    "question": f"What documented interventions are described in scholarly work about: {topic}?",
                    "evidence_kind": "openalex_scholarly_abstract",
                    "can_resolve_claim": False,
                    "openalex_query": f"documented interventions: {topic}",
                }
            )
        if re.search(r"\bnepal\b|\blocal(?:ly)?\b|\btarget (?:market|region)\b", question_text, re.I):
            requirements.append(
                {
                    "id": "local_applicability",
                    "question": (
                        f"Which evidence establishes whether the scholarly findings apply to the "
                        f"target geography and population for: {topic}?"
                    ),
                    "evidence_kind": "geographic_population_alignment",
                    "can_resolve_claim": False,
                }
            )

    if not world_bank_scope:
        qualification = _openalex_qualifications(question_text)
        country = qualification["geographic_qualification"]
        if (
            country
            and qualification["population_qualification"]
            and broad_research_objective
        ):
            country_code = _COUNTRY_ISO3.get(country.casefold())
            if country_code:
                current_year = date.today().year
                world_bank_scope = {
                    "country_code": country_code,
                    "indicator_id": "SP.POP.TOTL",
                    "start_year": current_year - 5,
                    "end_year": current_year - 1,
                }
                requirements.append(
                    {
                        "id": "population_baseline",
                        "question": (
                            f"What country-level population baseline is available for "
                            f"{country} ({world_bank_scope['start_year']}-"
                            f"{world_bank_scope['end_year']})?"
                        ),
                        "evidence_kind": "attributed_macro_indicator_observation",
                        "can_resolve_claim": False,
                        "world_bank_scope": world_bank_scope,
                    }
                )
        if re.search(r"\b(?:19|20)\d{2}\b", question_text):
            requirements.append(
                {
                    "id": "study_context_alignment",
                    "question": (
                        f"What evidence establishes the study period and population context for: {topic}?"
                    ),
                    "evidence_kind": "temporal_population_alignment",
                    "can_resolve_claim": False,
                }
            )
    return requirements


_WORLD_BANK_SCOPE_PATTERN = re.compile(
    r"\bWB:([A-Z]{2,3}):([A-Z0-9._-]{1,80}):(\d{4})(?::(\d{4}))?\b",
    re.IGNORECASE,
)


def _world_bank_scope(question_text: str) -> dict[str, Any] | None:
    match = _WORLD_BANK_SCOPE_PATTERN.search(question_text)
    if not match:
        return None
    country_code, indicator_id, start_year, end_year = match.groups()
    start = int(start_year)
    end = int(end_year) if end_year else start
    if end < start or end - start > 20:
        return None
    return {
        "country_code": country_code.upper(),
        "indicator_id": indicator_id,
        "start_year": start,
        "end_year": end,
    }


def _prior_observations(db: Session, question_text: str, *, limit: int = 5) -> list[dict[str, Any]]:
    terms = _tokens(question_text)
    if not terms:
        return []
    rows = (
        db.query(models.Signal)
        .filter(
            models.Signal.source_type == "external",
            models.Signal.canonical_url.isnot(None),
            models.Signal.canonical_url != "",
        )
        .order_by(models.Signal.retrieved_at.desc(), models.Signal.id.desc())
        .limit(300)
        .all()
    )
    matches: list[tuple[float, models.Signal]] = []
    for signal in rows:
        signal_terms = _tokens(f"{signal.title or ''} {signal.content or ''}")
        overlap = terms & signal_terms
        if overlap:
            matches.append((len(overlap) / len(terms), signal))
    matches.sort(key=lambda item: (-item[0], item[1].id))

    observations: list[dict[str, Any]] = []
    for relevance, signal in matches[:limit]:
        evidence_id = (
            db.query(models.Evidence.id)
            .filter_by(signal_id=signal.id)
            .order_by(models.Evidence.id.desc())
            .limit(1)
            .scalar()
        )
        if evidence_id is None:
            continue
        observations.append(
            {
                "signal_id": signal.id,
                "evidence_id": evidence_id,
                "source": signal.source,
                "title": signal.title,
                "url": signal.canonical_url,
                "published_at": signal.published_at.isoformat() if signal.published_at else None,
                "retrieved_at": signal.retrieved_at.isoformat() if signal.retrieved_at else None,
                "matched_term_fraction": round(relevance, 3),
                "epistemic_status": "prior_observation_unverified",
                "matching_is_not_semantic_relevance": True,
            }
        )
    return observations


def _orchestration_requirement_specs(
    question_text: str,
    planned_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive domain-specific needs and attach only registered source candidates."""
    qualifications = _openalex_qualifications(question_text)
    by_id = {requirement["id"]: requirement for requirement in planned_requirements}

    def candidates_for(requirement_ids: tuple[str, ...]) -> list[dict[str, Any]]:
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for requirement_id in requirement_ids:
            requirement = by_id.get(requirement_id)
            if requirement is None:
                continue
            for capability in requirement["capable_sources"]:
                source_key = (capability["source"], capability["registry_id"])
                evidence_type = (
                    "bibliographic_metadata_lead_only"
                    if capability["source"] == "crossref"
                    else requirement["evidence_kind"]
                )
                candidates[source_key] = {
                    "source": capability["source"],
                    "registry_id": capability["registry_id"],
                    "endpoint": capability["endpoint"],
                    "operation": capability["operation"],
                    "required_evidence_type": evidence_type,
                }
        return list(candidates.values())

    profile = _objective_profile(question_text)
    topic = _topic(question_text)
    if profile == "agriculture_commodity":
        specifications = [
            ("phenomenon_existence", "scholarly_abstract", ("scholarly_evidence",), ["prevalence", "causality", "study_period", "population_alignment", "local_applicability"]),
            ("affected_population", "national_population_baseline", ("population_baseline",), ["target_population_share", "affected_population_count", "customer_impact"]),
            ("geographic_baseline", "country_scoped_macro_observation", ("population_baseline", "economic_indicator"), ["subnational_variation", "local_customer_distribution"]),
            ("documented_interventions", "scholarly_abstract", ("documented_intervention",), ["effectiveness", "local_transferability", "implementation_cost"]),
            ("commercial_validation_gap", "direct_customer_or_transaction_evidence", (), ["customer_pain", "buyer_willingness_to_pay", "commercial_demand"]),
        ]
    elif profile == "software_service":
        specifications = [
            ("problem_prevalence", "direct_incidence_or_user_study", ("problem_incidence",), ["frequency", "severity", "sampling_bias"]),
            ("technical_feasibility", "technical_research_and_test_evidence", ("scholarly_evidence",), ["prototype_test", "integration_constraints", "operational_reliability"]),
            ("existing_solutions", "published_solution_metadata", ("bibliographic_discovery",), ["current_products", "pricing", "switching_costs"]),
            ("target_user_segment", "direct_user_and_population_evidence", ("problem_incidence",), ["decision_authority", "segment_size", "user_buyer_alignment"]),
            ("commercial_validation_gap", "direct_customer_or_transaction_evidence", (), ["customer_pain", "buyer_willingness_to_pay", "commercial_demand"]),
        ]
    elif profile == "logistics":
        specifications = [
            ("operational_bottleneck", "route_specific_operational_observations", ("scholarly_evidence",), ["route_level_delay", "throughput", "cause"]),
            ("geographic_corridor", "country_macro_baseline", ("population_baseline", "economic_indicator"), ["border_crossing_data", "route_volume", "subnational_alignment"]),
            ("regulatory_environment", "authoritative_regulatory_records", ("regulatory_environment",), ["current_rules", "jurisdiction", "implementation"]),
            ("macro_economic_volume", "attributed_country_economic_indicator", ("economic_indicator",), ["sector_specific_volume", "local_market_size", "commercial_demand"]),
            ("commercial_validation_gap", "direct_customer_or_transaction_evidence", (), ["customer_pain", "buyer_willingness_to_pay", "commercial_demand"]),
        ]
    else:
        specifications = []
        for requirement in planned_requirements:
            requirement_id = requirement["id"]
            if requirement_id in _COMMERCIAL_REQUIREMENT_IDS:
                continue
            specifications.append(
                (
                    requirement_id,
                    requirement["evidence_kind"],
                    (requirement_id,),
                    list(requirement.get("unresolved_dimensions", _OPENALEX_UNRESOLVED_DIMENSIONS)),
                )
            )
        if "buyer_willingness_to_pay" in by_id:
            specifications.append(
                (
                    "commercial_validation_gap",
                    "direct_customer_or_transaction_evidence",
                    ("buyer_willingness_to_pay",),
                    ["customer_pain", "buyer_willingness_to_pay", "commercial_demand"],
                )
            )

    nodes = []
    for requirement_id, evidence_type, related_ids, unresolved in specifications:
        candidate_sources = candidates_for(related_ids)
        nodes.append(
            {
                "requirement_id": requirement_id,
                "original_research_question": question_text,
                "objective_subject": topic,
                "required_evidence_type": evidence_type,
                "geographic_qualification": qualifications["geographic_qualification"],
                "population_qualification": qualifications["population_qualification"],
                "epistemic_state": "unresolved",
                "candidate_sources": candidate_sources,
                "unresolved_dimensions": unresolved,
                "related_requirement_ids": [value for value in related_ids if value in by_id],
                "resolution_state": (
                    "unresolved"
                    if candidate_sources
                    else "blocked_external_evidence_required"
                ),
            }
        )
    return nodes


def build_research_plan(db: Session, question: models.ResearchQuestion) -> dict[str, Any]:
    """Describe requirements and candidate capabilities without equating metadata to answers."""
    requirements: list[dict[str, Any]] = []
    qualifications = _openalex_qualifications(question.question)
    for spec in _requirement_specs(question.question):
        capabilities = source_clearance_registry.capabilities_for_requirement(spec["id"])
        candidate_sources = [
            {
                "source": entry.collector,
                "registry_id": entry.registry_id,
                "endpoint": entry.url,
                "operation": entry.allowed_operation,
                "required_evidence_type": spec["evidence_kind"],
            }
            for entry in capabilities
        ]
        if spec["id"] == "bibliographic_discovery":
            candidate_sources = [
                {
                    "source": entry.collector,
                    "registry_id": entry.registry_id,
                    "endpoint": entry.url,
                    "operation": entry.allowed_operation,
                    "required_evidence_type": "bibliographic_metadata_lead_only",
                }
                for entry in source_clearance_registry.capabilities_for_requirement(
                    "bibliographic_discovery"
                )
            ]
        requirements.append(
            {
                **spec,
                "requirement_id": spec["id"],
                "original_research_question": question.question,
                "required_evidence_type": spec["evidence_kind"],
                "geographic_qualification": qualifications["geographic_qualification"],
                "population_qualification": qualifications["population_qualification"],
                "epistemic_state": "unresolved",
                "candidate_sources": candidate_sources,
                "unresolved_dimensions": list(_OPENALEX_UNRESOLVED_DIMENSIONS),
                "status": "pending" if capabilities else "terminal_unresolved",
                "capable_sources": [
                    {
                        "source": entry.collector,
                        "registry_id": entry.registry_id,
                        "endpoint": entry.url,
                        "operation": entry.allowed_operation,
                        "allowed_fields": list(entry.allowed_fields),
                        "provenance_requirements": list(entry.provenance_requirements),
                    }
                    for entry in capabilities
                ],
                "terminal_reason": None if capabilities else "no_currently_authorized_source_capability",
                "evidence_ids": [],
                "task_ids": [],
            }
        )

    orchestration_requirements = _orchestration_requirement_specs(
        question.question, requirements
    )
    candidates = []
    for entry in source_clearance_registry.source_clearances():
        candidates.append(
            {
                "source": entry.collector,
                "registry_id": entry.registry_id,
                "available": source_clearance_registry.collector_is_cleared(entry.collector),
                "endpoint": entry.url,
                "operation": entry.allowed_operation,
                "allowed_fields": list(entry.allowed_fields),
                "supports_requirements": list(entry.supports_requirements),
                "valid_through": entry.valid_through.isoformat(),
                "rate_limit_seconds": entry.min_interval_seconds,
            }
        )
    candidates.extend(
        [
            {
                "source": "web_search",
                "available": False,
                "reason": "No currently reviewed general web-search capability is configured.",
            },
            {
                "source": "direct_web",
                "available": False,
                "reason": "The direct-page clearance has expired; no page will be fetched.",
            },
        ]
    )
    return {
        "question_id": question.id,
        "question": question.question,
        "status": "research_in_progress",
        "subquestions": [item["question"] for item in requirements],
        "requirements": requirements,
        "orchestration_requirements": orchestration_requirements,
        "known_observations": _prior_observations(db, question.question),
        "assumptions": [
            "The premise and wording supplied by the requester are not external evidence.",
            "Bibliographic metadata identifies a record only; paper contents have not been retrieved or reviewed.",
            "Lexical overlap is a discovery cue, not semantic relevance or claim support.",
            "No customer, market demand, price, revenue, transaction, or human response is inferred.",
        ],
        "unknowns": list(_UNCERTAINTIES),
        "candidate_sources": candidates,
        "stopping_conditions": [
            "A requirement is grounded only by persisted evidence assessed as directly relevant to that requirement.",
            "End unresolved requirements explicitly when no current authorized capability can answer them.",
            f"Stop after at most {MAX_TASKS_PER_QUESTION} persisted tasks for this question.",
            "Never describe a terminal-but-unresolved loop as a validated research conclusion.",
        ],
        "budget": {"max_tasks": MAX_TASKS_PER_QUESTION},
    }


def _question_plan(question: models.ResearchQuestion) -> dict[str, Any]:
    plan = question.research_plan
    if isinstance(plan, dict) and isinstance(plan.get("requirements"), list):
        return copy.deepcopy(plan)
    return {}


def _tasks_for_requirement(
    db: Session,
    question_id: int,
    requirement_id: str,
) -> list[models.ResearchTask]:
    rows = db.query(models.ResearchTask).filter_by(question_id=question_id).order_by(models.ResearchTask.id).all()
    return [
        task
        for task in rows
        if isinstance(task.results, dict)
        and (
            task.results.get("research_requirement_id") == requirement_id
            or (
                isinstance(task.results.get("research_requirement_ids"), list)
                and requirement_id in task.results["research_requirement_ids"]
            )
        )
    ]


def _create_task(
    db: Session,
    question: models.ResearchQuestion,
    requirement: dict[str, Any],
    *,
    source: str,
    query: str,
    follow_up_of: int | None = None,
    follow_up_depth: int = 0,
) -> models.ResearchTask:
    task_query = " ".join(query.split())[:300] if source == "crossref" else query
    openalex_context: dict[str, Any] = {}
    search_mode = "not_applicable"
    if source == "openalex":
        original_question = question.question
        derived_query = requirement.get("openalex_query", _topic(original_question))
        search_mode = _openalex_search_mode(original_question, derived_query)
        max_length = 2000 if search_mode == "semantic" else 500
        task_query = " ".join(str(derived_query).split())[:max_length].strip()
        if not task_query:
            raise ValueError("OpenAlex retrieval query must not be empty")
        openalex_context = {
            "original_research_question": original_question,
            "derived_retrieval_query": task_query,
            "search_mode": search_mode,
            **_openalex_qualifications(original_question),
            "unresolved_dimensions": list(_OPENALEX_UNRESOLVED_DIMENSIONS),
        }
    elif source == "world_bank_indicators":
        task_query = json.dumps(requirement["world_bank_scope"], sort_keys=True)
    elif source == "gdelt_doc":
        gdelt_query = " ".join(
            str(requirement.get("gdelt_query", _topic(question.question))).split()
        )[:500]
        task_query = json.dumps(
            {
                "query": gdelt_query,
                "timespan": "1w",
                "max_records": 25,
            },
            sort_keys=True,
        )

    identity_material = "\0".join(
        (
            str(question.id),
            requirement["id"],
            source,
            search_mode,
            task_query,
        )
    )
    task_identity = sha256(identity_material.encode("utf-8")).hexdigest()

    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source=source,
        query=task_query,
        objective=requirement["question"],
        claim_id=question.source_claim_id,
        idempotency_key=task_identity,
    )
    task_results = task.results if isinstance(task.results, dict) else {}
    requirement_ids = task_results.get("research_requirement_ids", [])
    if not isinstance(requirement_ids, list):
        requirement_ids = []
    if task_results.get("research_requirement_id") and not requirement_ids:
        requirement_ids = [task_results["research_requirement_id"]]
    if requirement["id"] not in requirement_ids:
        requirement_ids.append(requirement["id"])
    requirement_contexts = task_results.get("requirement_contexts", [])
    if not isinstance(requirement_contexts, list):
        requirement_contexts = []
    if not any(
        isinstance(context, dict) and context.get("requirement_id") == requirement["id"]
        for context in requirement_contexts
    ):
        requirement_contexts.append(
            {
                "requirement_id": requirement["id"],
                "objective": requirement["question"],
                "evidence_kind": requirement["evidence_kind"],
            }
        )
    task.results = {
        **task_results,
        "research_requirement_id": requirement_ids[0],
        "research_requirement_ids": requirement_ids,
        "requirement_contexts": requirement_contexts,
        "evidence_kind": requirement["evidence_kind"],
        "source_registry_id": next(
            (
                capability["registry_id"]
                for capability in requirement["capable_sources"]
                if capability["source"] == source
            ),
            None,
        ),
        "follow_up_of_task_id": follow_up_of,
        "follow_up_depth": follow_up_depth,
        "research_question_id": question.id,
    }
    task_context = {
        "original_research_question": question.question,
        "derived_retrieval_query": task_query,
        "source_type": source,
        "search_mode": None,
        **_openalex_qualifications(question.question),
        "unresolved_dimensions": list(_OPENALEX_UNRESOLVED_DIMENSIONS),
    }
    if source == "world_bank_indicators":
        task_context["derived_retrieval_query"] = task.query
    elif source == "gdelt_doc":
        task_context["derived_retrieval_query"] = json.loads(task.query)["query"]
    elif source == "openalex":
        task.results = {**task.results, **openalex_context}
        task_context = {**task_context, **openalex_context, "source_type": source}
    task.results = {**task.results, **task_context}
    db.flush()
    return task


def _openalex_search_mode(question: str, query: str) -> str:
    """Choose exact lookup for explicit identifiers/names, semantic otherwise."""
    exact_lookup = re.search(
        r"""(?ix)
        \b(?:doi\s*:\s*|https?://doi\.org/)?10\.\d{4,9}/[-._;()/:A-Z0-9]+
        |\b(?:author|authored\s+by|written\s+by|works?\s+by|publications?\s+by)\b
        |\b(?:paper|article|study|work)\s+(?:titled|called|named)\b
        |["“][^"”\n]{2,}["”]
        """,
        question,
    )
    geo_terms = {term.casefold() for term in _GEOGRAPHY_TERMS}
    named_entity = any(
        match.start() > 0
        and match.group().casefold() not in _QUESTION_WORDS | geo_terms
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9&.-]{2,}\b", question)
    )
    if exact_lookup or named_entity or re.search(
        r"""(?ix)\b(?:find|identify)\s+(?:the\s+)?(?:author|researcher|paper|article)\b""",
        query,
    ):
        return "keyword"
    return "semantic"


def _openalex_qualifications(question: str) -> dict[str, str | None]:
    geographic = next(
        (
            term
            for term in _GEOGRAPHY_TERMS
            if re.search(rf"\b{re.escape(term)}\b", question, re.I)
        ),
        None,
    )
    population = next(
        (
            term
            for term in _POPULATION_TERMS
            if re.search(rf"\b{re.escape(term)}\b", question, re.I)
        ),
        None,
    )
    return {
        "geographic_qualification": geographic,
        "population_qualification": population,
    }


def _follow_up_query(task: models.ResearchTask) -> str | None:
    results = task.results if isinstance(task.results, dict) else {}
    records = results.get("source_results")
    if not isinstance(records, list):
        return None
    title = next(
        (row.get("title") for row in records if isinstance(row, dict) and row.get("title")),
        None,
    )
    if not title:
        return None
    return f"Bibliographic follow-up for unresolved publication lead: {title}"


def _verified_bibliographic_evidence_ids(
    db: Session,
    tasks: list[models.ResearchTask],
) -> list[int]:
    verified: set[int] = set()
    for task in tasks:
        if task.source != "crossref" or task.status != "completed":
            continue
        results = task.results if isinstance(task.results, dict) else {}
        source_results = results.get("source_results")
        if not isinstance(source_results, list):
            continue
        for result in source_results:
            if not isinstance(result, dict):
                continue
            evidence_id = result.get("evidence_id")
            if not isinstance(evidence_id, int):
                continue
            evidence = db.get(models.Evidence, evidence_id)
            if (
                evidence is None
                or evidence_id not in {
                    int(value)
                    for value in (task.evidence_ids or "").split(",")
                    if value.isdigit()
                }
                or not evidence.canonical_url
                or not evidence.external_id
                or evidence.retrieved_at is None
                or not evidence.provenance
            ):
                continue
            try:
                provenance = json.loads(evidence.provenance)
            except (TypeError, json.JSONDecodeError):
                continue
            if (
                isinstance(provenance, dict)
                and provenance.get("metadata_only") is True
                and provenance.get("source_registry_id") == "crossref-public-works-metadata"
            ):
                verified.add(evidence_id)
    return sorted(verified)


def _verified_openalex_evidence_ids(
    db: Session,
    tasks: list[models.ResearchTask],
    requirement: dict[str, Any],
) -> tuple[list[int], str | None]:
    verified: set[int] = set()
    rejected_reasons: list[str] = []
    for task in tasks:
        if task.source != "openalex" or task.status != "completed":
            continue
        results = task.results if isinstance(task.results, dict) else {}
        source_results = results.get("source_results")
        if not isinstance(source_results, list):
            continue
        task_evidence_ids = {
            int(value)
            for value in (task.evidence_ids or "").split(",")
            if value.isdigit()
        }
        for result in source_results:
            if not isinstance(result, dict) or not isinstance(result.get("evidence_id"), int):
                continue
            evidence_id = result["evidence_id"]
            evidence = db.get(models.Evidence, evidence_id)
            if (
                evidence is None
                or evidence_id not in task_evidence_ids
                or evidence.source != "openalex"
                or not evidence.provenance
            ):
                continue
            try:
                provenance = json.loads(evidence.provenance)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(provenance, dict):
                continue
            eligible, reason = openalex_requirement_eligibility(requirement["id"], provenance)
            if eligible:
                verified.add(evidence_id)
            else:
                rejected_reasons.append(reason)
    return sorted(verified), next(iter(rejected_reasons), None)


def _verified_world_bank_evidence_ids(
    db: Session,
    tasks: list[models.ResearchTask],
    requirement: dict[str, Any],
) -> tuple[list[int], str | None]:
    verified: set[int] = set()
    rejected_reasons: list[str] = []
    scope = requirement.get("world_bank_scope") or {}
    for task in tasks:
        if task.source != "world_bank_indicators" or task.status != "completed":
            continue
        results = task.results if isinstance(task.results, dict) else {}
        source_results = results.get("source_results")
        if not isinstance(source_results, list):
            continue
        task_evidence_ids = {
            int(value)
            for value in (task.evidence_ids or "").split(",")
            if value.isdigit()
        }
        for result in source_results:
            if not isinstance(result, dict) or not isinstance(result.get("evidence_id"), int):
                continue
            evidence_id = result["evidence_id"]
            if evidence_id not in task_evidence_ids:
                continue
            evidence = db.get(models.Evidence, evidence_id)
            if (
                evidence is None
                or evidence.source != "world_bank_indicators"
                or not evidence.provenance
            ):
                continue
            try:
                provenance = json.loads(evidence.provenance)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(provenance, dict):
                continue
            eligible, reason = world_bank_requirement_eligibility(
                requirement["id"],
                provenance,
                expected_country=scope.get("country_code"),
                expected_indicator=scope.get("indicator_id"),
                expected_years=(
                    (scope["start_year"], scope["end_year"])
                    if "start_year" in scope and "end_year" in scope
                    else None
                ),
            )
            if eligible:
                verified.add(evidence_id)
            else:
                rejected_reasons.append(reason)
    return sorted(verified), next(iter(rejected_reasons), None)


def _verified_gdelt_evidence_ids(
    db: Session,
    tasks: list[models.ResearchTask],
    requirement: dict[str, Any],
) -> tuple[list[int], str | None]:
    verified: set[int] = set()
    rejected_reasons: list[str] = []
    for task in tasks:
        if task.source != "gdelt_doc" or task.status != "completed":
            continue
        results = task.results if isinstance(task.results, dict) else {}
        source_results = results.get("source_results")
        if not isinstance(source_results, list):
            continue
        task_evidence_ids = {
            int(value)
            for value in (task.evidence_ids or "").split(",")
            if value.isdigit()
        }
        for result in source_results:
            if not isinstance(result, dict) or not isinstance(result.get("evidence_id"), int):
                continue
            evidence_id = result["evidence_id"]
            evidence = db.get(models.Evidence, evidence_id)
            if evidence is None or evidence_id not in task_evidence_ids or evidence.source != "gdelt_doc":
                continue
            try:
                provenance = json.loads(evidence.provenance) if evidence.provenance else {}
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(provenance, dict):
                continue
            eligible, reason = gdelt_requirement_eligibility(requirement["id"], provenance)
            if eligible:
                verified.add(evidence_id)
            else:
                rejected_reasons.append(reason)
    return sorted(verified), next(iter(rejected_reasons), None)


def _macro_market_unresolved_reason(requirement_id: str) -> str | None:
    if not source_clearance_registry.capabilities_for_requirement("population_baseline"):
        return None
    if requirement_id in {"problem_incidence", "customer_pain", "product_demand"}:
        return "macro_indicator_data_cannot_validate_customer_pain_or_micro_incidence"
    if requirement_id in {"buyer_willingness_to_pay", "alternatives_and_costs"}:
        return "macro_indicator_data_cannot_validate_micro_demand_or_buyer_willingness_to_pay"
    return None


def _create_next_unqueried_capability_task(
    db: Session,
    question: models.ResearchQuestion,
    requirement: dict[str, Any],
    tasks: list[models.ResearchTask],
    *,
    task_count: int,
) -> models.ResearchTask | None:
    if task_count >= MAX_TASKS_PER_QUESTION:
        return None
    queried_registry_ids = {
        (task.results or {}).get("source_registry_id")
        for task in tasks
        if isinstance(task.results, dict)
    }
    active_registry_ids = {
        (task.results or {}).get("source_registry_id")
        for task in tasks
        if task.status in {"planned", "running"}
        and isinstance(task.results, dict)
    }
    for capability in requirement["capable_sources"]:
        registry_id = capability["registry_id"]
        if registry_id in queried_registry_ids or registry_id in active_registry_ids:
            continue
        if capability["source"] == "openalex":
            query = requirement.get("openalex_query", requirement["question"])
        else:
            query = requirement["question"]
        return _create_task(
            db,
            question,
            requirement,
            source=capability["source"],
            query=query,
            follow_up_of=tasks[-1].id if tasks else None,
            follow_up_depth=max(
                (
                    int((task.results or {}).get("follow_up_depth") or 0)
                    for task in tasks
                    if isinstance(task.results, dict)
                ),
                default=0,
            )
            + 1,
        )
    return None


def _refresh_plan_from_tasks(
    db: Session,
    question: models.ResearchQuestion,
    plan: dict[str, Any],
) -> None:
    task_count = db.query(models.ResearchTask).filter_by(question_id=question.id).count()
    active = False
    all_terminal = True
    for requirement in plan["requirements"]:
        task_count = db.query(models.ResearchTask).filter_by(question_id=question.id).count()
        active_capabilities = source_clearance_registry.capabilities_for_requirement(
            requirement["id"]
        )
        requirement["capable_sources"] = [
            {
                "source": entry.collector,
                "registry_id": entry.registry_id,
                "endpoint": entry.url,
                "operation": entry.allowed_operation,
                "allowed_fields": list(entry.allowed_fields),
                "provenance_requirements": list(entry.provenance_requirements),
            }
            for entry in active_capabilities
        ]
        tasks = _tasks_for_requirement(db, question.id, requirement["id"])
        evidence_ids = sorted(
            {
                int(value)
                for task in tasks
                for value in (task.evidence_ids or "").split(",")
                if value.isdigit()
            }
        )
        requirement["task_ids"] = [task.id for task in tasks]
        requirement["evidence_ids"] = evidence_ids
        requirement["task_failures"] = [
            {
                "task_id": task.id,
                "source": task.source,
                "status": task.status,
                "errors": list(task.errors or []),
            }
            for task in tasks
            if task.status in {"failed", "needs_research"}
        ]
        verified_metadata_ids = (
            _verified_bibliographic_evidence_ids(db, tasks)
            if requirement["id"] == "bibliographic_discovery"
            else []
        )
        verified_openalex_ids, openalex_rejection_reason = (
            _verified_openalex_evidence_ids(
                db,
                tasks,
                requirement,
            )
            if requirement["id"]
            in {"scholarly_evidence", "prior_research", "documented_intervention", "literature_existence"}
            else ([], None)
        )
        verified_world_bank_ids, world_bank_rejection_reason = (
            _verified_world_bank_evidence_ids(db, tasks, requirement)
            if requirement["id"] in {"macro_demographics", "population_baseline", "economic_indicator"}
            else ([], None)
        )
        verified_gdelt_ids, gdelt_rejection_reason = (
            _verified_gdelt_evidence_ids(db, tasks, requirement)
            if requirement["id"]
            in {"media_coverage_observation", "recent_event_signal", "public_reporting_velocity"}
            else ([], None)
        )
        if not requirement["capable_sources"]:
            if verified_metadata_ids:
                requirement["status"] = "satisfied"
                requirement["evidence_ids"] = verified_metadata_ids
                requirement["terminal_reason"] = None
            elif verified_world_bank_ids:
                requirement["status"] = "satisfied"
                requirement["evidence_ids"] = verified_world_bank_ids
                requirement["terminal_reason"] = None
            elif verified_gdelt_ids:
                requirement["status"] = "satisfied"
                requirement["evidence_ids"] = verified_gdelt_ids
                requirement["terminal_reason"] = None
            elif verified_openalex_ids:
                requirement["status"] = "satisfied"
                requirement["evidence_ids"] = verified_openalex_ids
                requirement["terminal_reason"] = None
            else:
                requirement["status"] = "terminal_unresolved"
                requirement["terminal_reason"] = (
                    openalex_rejection_reason
                    or gdelt_rejection_reason
                    or _macro_market_unresolved_reason(requirement["id"])
                    or (
                    "no_currently_authorized_source_capability"
                    if not tasks
                    else "source_capability_unavailable_or_expired"
                    )
                )
            requirement["epistemic_state"] = (
                "supported" if requirement["status"] == "satisfied" else "blocked"
            )
            requirement["resolution_state"] = (
                requirement["epistemic_state"]
                if requirement["status"] == "satisfied"
                else "blocked_external_evidence_required"
            )
            continue

        pending = [task for task in tasks if task.status in {"planned", "running"}]
        if pending:
            requirement["status"] = (
                "satisfied"
                if verified_metadata_ids
                or verified_world_bank_ids
                or verified_gdelt_ids
                or verified_openalex_ids
                else "in_progress"
            )
            if verified_metadata_ids:
                requirement["evidence_ids"] = verified_metadata_ids
            elif verified_world_bank_ids:
                requirement["evidence_ids"] = verified_world_bank_ids
            elif verified_gdelt_ids:
                requirement["evidence_ids"] = verified_gdelt_ids
            elif verified_openalex_ids:
                requirement["evidence_ids"] = verified_openalex_ids
            requirement["terminal_reason"] = None
            requirement["epistemic_state"] = (
                "supported"
                if requirement["status"] == "satisfied"
                else "unresolved"
            )
            requirement["resolution_state"] = requirement["epistemic_state"]
            active = True
            all_terminal = False
            continue

        successful = [task for task in tasks if task.status == "completed" and task.evidence_ids]
        if successful:
            primary = successful[0]
            depth = int((primary.results or {}).get("follow_up_depth") or 0)
            followups = [task for task in tasks if int((task.results or {}).get("follow_up_depth") or 0) > 0]
            if (
                primary.source == "crossref"
                and not followups
                and depth == 0
                and task_count < MAX_TASKS_PER_QUESTION
            ):
                query = _follow_up_query(primary)
                if query:
                    _create_task(
                        db,
                        question,
                        requirement,
                        source=primary.source,
                        query=query,
                        follow_up_of=primary.id,
                        follow_up_depth=1,
                    )
                    task_count += 1
                    verified_metadata_ids = (
                        _verified_bibliographic_evidence_ids(db, tasks)
                        if requirement["id"] == "bibliographic_discovery"
                        else []
                    )
                    requirement["status"] = (
                        "satisfied"
                        if verified_metadata_ids or verified_openalex_ids
                        else "in_progress"
                    )
                    if verified_metadata_ids or verified_openalex_ids:
                        requirement["evidence_ids"] = verified_metadata_ids or verified_openalex_ids
                    requirement["terminal_reason"] = None
                    active = active or bool(
                        db.query(models.ResearchTask)
                        .filter_by(question_id=question.id, status="planned")
                        .count()
                    )
                    all_terminal = False
                    continue
            verified_metadata_ids = (
                _verified_bibliographic_evidence_ids(db, tasks)
                if requirement["id"] == "bibliographic_discovery"
                else []
            )
            requirement["status"] = (
                "satisfied"
                if verified_metadata_ids
                or verified_world_bank_ids
                or verified_gdelt_ids
                or verified_openalex_ids
                else "terminal_unresolved"
            )
            requirement["evidence_ids"] = (
                verified_metadata_ids
                or verified_openalex_ids
                or verified_world_bank_ids
                or verified_gdelt_ids
                or (
                    evidence_ids
                    if primary.source not in {"world_bank_indicators", "gdelt_doc", "openalex"}
                    else []
                )
            )
            if verified_metadata_ids or verified_openalex_ids or verified_world_bank_ids or verified_gdelt_ids:
                requirement["terminal_reason"] = None
            elif openalex_rejection_reason:
                requirement["terminal_reason"] = openalex_rejection_reason
            elif gdelt_rejection_reason:
                requirement["terminal_reason"] = gdelt_rejection_reason
            elif world_bank_rejection_reason:
                requirement["terminal_reason"] = world_bank_rejection_reason
            elif primary.source == "crossref":
                requirement["terminal_reason"] = (
                    "metadata_leads_do_not_establish_content_relevance_or_answer_the_claim"
                )
            else:
                requirement["terminal_reason"] = (
                    "collected_evidence_has_not_been_assessed_as_direct_support"
                )
            requirement["epistemic_state"] = (
                "supported"
                if requirement["status"] == "satisfied"
                else "unresolved"
            )
            requirement["resolution_state"] = requirement["epistemic_state"]
            continue

        retryable = [
            task
            for task in tasks
            if task.status in {"failed", "needs_research"} and task.attempts < task.max_attempts
        ]
        if retryable:
            retried = research_task_engine.retry_task(db, retryable[0])
            if retried.status == "planned":
                requirement["status"] = "in_progress"
                requirement["terminal_reason"] = None
                requirement["epistemic_state"] = "unresolved"
                requirement["resolution_state"] = "unresolved"
                active = True
                all_terminal = False
                continue

        if not tasks:
            capability = requirement["capable_sources"][0]
            if task_count < MAX_TASKS_PER_QUESTION:
                planned_task = _create_task(
                    db,
                    question,
                    requirement,
                    source=capability["source"],
                    query=requirement["question"],
                )
                requirement["task_ids"] = [planned_task.id]
                task_count = db.query(models.ResearchTask).filter_by(
                    question_id=question.id
                ).count()
                requirement["status"] = "in_progress"
                requirement["terminal_reason"] = None
                requirement["epistemic_state"] = "unresolved"
                requirement["resolution_state"] = "unresolved"
                active = True
                all_terminal = False
                continue
            requirement["terminal_reason"] = "research_task_budget_exhausted"
        elif any(task.status in {"failed", "needs_research"} for task in tasks):
            requirement["terminal_reason"] = "source_attempt_budget_exhausted_without_answer"
        else:
            requirement["terminal_reason"] = (
                openalex_rejection_reason
                or gdelt_rejection_reason
                or _macro_market_unresolved_reason(requirement["id"])
                or "no_successful_source_evidence"
            )
        requirement["status"] = "terminal_unresolved"
        requirement["epistemic_state"] = "unresolved"
        requirement["resolution_state"] = (
            "blocked_external_evidence_required"
            if not requirement["capable_sources"]
            else "unresolved"
        )

    all_evidence_ids = sorted(
        {
            evidence_id
            for requirement in plan["requirements"]
            for evidence_id in requirement["evidence_ids"]
        }
    )
    plan["contradictions"] = explicit_contradiction_edges(db, all_evidence_ids)
    plan["contradiction_assessment"] = (
        "explicit_relationships_recorded"
        if plan["contradictions"]
        else "unassessed"
    )
    from app.services.research_synthesis_engine import synthesize_research_plan

    plan["synthesis"] = synthesize_research_plan(db, plan)
    for requirement in plan["requirements"]:
        if requirement.get("epistemic_state") not in {
            "unresolved",
            "partially_supported",
        }:
            continue
        current_tasks = _tasks_for_requirement(db, question.id, requirement["id"])
        if any(task.status in {"planned", "running"} for task in current_tasks):
            continue
        task_count = db.query(models.ResearchTask).filter_by(
            question_id=question.id
        ).count()
        next_task = _create_next_unqueried_capability_task(
            db,
            question,
            requirement,
            current_tasks,
            task_count=task_count,
        )
        if next_task is None:
            continue
        requirement["task_ids"] = [task.id for task in current_tasks] + [next_task.id]
        requirement["status"] = "in_progress"
        requirement["terminal_reason"] = None
        requirement["epistemic_state"] = "unresolved"
        requirement["resolution_state"] = "unresolved"
        active = True
        all_terminal = False
    if any(
        requirement.get("status") in {"in_progress", "satisfied"}
        and requirement.get("task_ids")
        for requirement in plan["requirements"]
    ):
        active = active or bool(
            db.query(models.ResearchTask)
            .filter(
                models.ResearchTask.question_id == question.id,
                models.ResearchTask.status.in_(("planned", "running")),
            )
            .count()
        )
    plan["synthesis"] = synthesize_research_plan(db, plan)
    task_count = db.query(models.ResearchTask).filter_by(question_id=question.id).count()
    plan["budget"] = {
        "max_tasks": MAX_TASKS_PER_QUESTION,
        "tasks_created": task_count,
        "remaining_tasks": max(0, MAX_TASKS_PER_QUESTION - task_count),
    }
    plan["status"] = "research_in_progress" if active else "research_terminal_unresolved"
    plan["unresolved_requirements"] = [
        item["id"]
        for item in plan["requirements"]
        if item["epistemic_state"] not in {"supported"}
    ]
    plan["terminal_reason"] = None if active else (
        "one_or_more_requirements_remain_unresolved_under_current_source_clearances"
        if all_terminal
        else "research_remains_active"
    )
    question.research_plan = plan
    question.status = "planned" if active else "closed"
    db.flush()


def plan_tasks_for_question(db: Session, question: models.ResearchQuestion) -> list[models.ResearchTask]:
    """Persist idempotent tasks for resolvable requirements and explicit terminal gaps."""
    plan = _question_plan(question) or build_research_plan(db, question)
    created_before = {
        task.id
        for task in db.query(models.ResearchTask).filter_by(question_id=question.id).all()
    }
    _refresh_plan_from_tasks(db, question, plan)
    db.commit()
    return [
        task
        for task in db.query(models.ResearchTask)
        .filter_by(question_id=question.id)
        .order_by(models.ResearchTask.id)
        .all()
        if task.id not in created_before
    ]


def plan_tasks_for_open_questions(db: Session, limit: int = 20) -> list[models.ResearchTask]:
    """Plan bounded tasks for open questions, excluding synthetic gap prompts."""
    questions = (
        db.query(models.ResearchQuestion)
        .filter(models.ResearchQuestion.status == "open")
        .filter(~models.ResearchQuestion.question.like("Gap:%"))
        .order_by(models.ResearchQuestion.priority_score.desc())
        .limit(limit)
        .all()
    )
    all_tasks: list[models.ResearchTask] = []
    for question in questions:
        all_tasks.extend(plan_tasks_for_question(db, question))
    return all_tasks
