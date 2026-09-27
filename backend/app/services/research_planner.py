"""Build bounded, requirement-first plans over the existing research records."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import research_task_engine, source_clearance_registry
from app.services.research_evidence_assessment import (
    explicit_contradiction_edges,
    world_bank_requirement_eligibility,
)

MAX_TASKS_PER_QUESTION = 5

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


def _requirement_specs(question_text: str) -> list[dict[str, Any]]:
    topic = _topic(question_text)
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


def build_research_plan(db: Session, question: models.ResearchQuestion) -> dict[str, Any]:
    """Describe requirements and candidate capabilities without equating metadata to answers."""
    requirements: list[dict[str, Any]] = []
    for spec in _requirement_specs(question.question):
        capabilities = source_clearance_registry.capabilities_for_requirement(spec["id"])
        requirements.append(
            {
                **spec,
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
        and task.results.get("research_requirement_id") == requirement_id
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
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source=source,
        query=query,
        objective=requirement["question"],
        claim_id=question.source_claim_id,
    )
    task.results = {
        **(task.results or {}),
        "research_requirement_id": requirement["id"],
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
    if source == "world_bank_indicators":
        task.query = json.dumps(requirement["world_bank_scope"], sort_keys=True)
    db.flush()
    return task


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


def _verified_world_bank_evidence_ids(
    db: Session,
    tasks: list[models.ResearchTask],
    requirement: dict[str, Any],
) -> list[int]:
    verified: set[int] = set()
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
            eligible, _reason = world_bank_requirement_eligibility(
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
    return sorted(verified)


def _macro_market_unresolved_reason(requirement_id: str) -> str | None:
    if not source_clearance_registry.capabilities_for_requirement("population_baseline"):
        return None
    if requirement_id in {"problem_incidence", "customer_pain", "product_demand"}:
        return "macro_indicator_data_cannot_validate_customer_pain_or_micro_incidence"
    if requirement_id in {"buyer_willingness_to_pay", "alternatives_and_costs"}:
        return "macro_indicator_data_cannot_validate_micro_demand_or_buyer_willingness_to_pay"
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
        verified_metadata_ids = (
            _verified_bibliographic_evidence_ids(db, tasks)
            if requirement["id"] == "bibliographic_discovery"
            else []
        )
        verified_world_bank_ids = (
            _verified_world_bank_evidence_ids(db, tasks, requirement)
            if requirement["id"] in {"macro_demographics", "population_baseline", "economic_indicator"}
            else []
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
            else:
                requirement["status"] = "terminal_unresolved"
                requirement["terminal_reason"] = _macro_market_unresolved_reason(
                    requirement["id"]
                ) or (
                    "no_currently_authorized_source_capability"
                    if not tasks
                    else "source_capability_unavailable_or_expired"
                )
            continue

        pending = [task for task in tasks if task.status in {"planned", "running"}]
        if pending:
            requirement["status"] = (
                "satisfied"
                if verified_metadata_ids or verified_world_bank_ids
                else "in_progress"
            )
            if verified_metadata_ids:
                requirement["evidence_ids"] = verified_metadata_ids
            elif verified_world_bank_ids:
                requirement["evidence_ids"] = verified_world_bank_ids
            requirement["terminal_reason"] = None
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
                    requirement["status"] = "satisfied" if verified_metadata_ids else "in_progress"
                    if verified_metadata_ids:
                        requirement["evidence_ids"] = verified_metadata_ids
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
                if verified_metadata_ids or verified_world_bank_ids
                else "terminal_unresolved"
            )
            requirement["evidence_ids"] = (
                verified_metadata_ids or verified_world_bank_ids or evidence_ids
            )
            if verified_metadata_ids or verified_world_bank_ids:
                requirement["terminal_reason"] = None
            elif primary.source == "crossref":
                requirement["terminal_reason"] = (
                    "metadata_leads_do_not_establish_content_relevance_or_answer_the_claim"
                )
            else:
                requirement["terminal_reason"] = (
                    "collected_evidence_has_not_been_assessed_as_direct_support"
                )
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
                active = True
                all_terminal = False
                continue

        if not tasks:
            capability = requirement["capable_sources"][0]
            if task_count < MAX_TASKS_PER_QUESTION:
                _create_task(
                    db,
                    question,
                    requirement,
                    source=capability["source"],
                    query=requirement["question"],
                )
                task_count += 1
                requirement["status"] = "in_progress"
                requirement["terminal_reason"] = None
                active = True
                all_terminal = False
                continue
            requirement["terminal_reason"] = "research_task_budget_exhausted"
        elif any(task.status in {"failed", "needs_research"} for task in tasks):
            requirement["terminal_reason"] = "source_attempt_budget_exhausted_without_answer"
        else:
            requirement["terminal_reason"] = (
                _macro_market_unresolved_reason(requirement["id"])
                or "no_successful_source_evidence"
            )
        requirement["status"] = "terminal_unresolved"

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
        if item["status"] != "satisfied"
    ]
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
