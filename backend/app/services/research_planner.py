"""Build reusable, evidence-aware plans over the existing research task model."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import research_task_engine, source_clearance_registry

_STOP_WORDS = {
    "about", "after", "against", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "should", "some", "than", "that", "their", "there",
    "these", "they", "this", "through", "under", "using", "what", "when",
    "where", "which", "while", "with", "would", "your",
}

_UNCERTAINTIES = [
    "Prevalence, frequency, and severity are not established by a publication record alone.",
    "Willingness to pay and buyer authority remain unknown until directly evidenced.",
    "Affected customer or beneficiary groups and decision context remain unidentified.",
    "Existing alternatives, prices, switching costs, and competitor performance need source-level verification.",
    "Required resources, capabilities, distribution, legal constraints, startup cost, and downside risk remain unassessed.",
    "Evidence that would disprove the premise must be sought before treating the opportunity as supported.",
]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", text.casefold())
        if token not in _STOP_WORDS
    }


def _subquestions(question_text: str) -> list[str]:
    topic = " ".join(question_text.split()).rstrip("?.! ")
    return [
        f"What verifiable observations or measurements address: {topic}?",
        f"What existing solutions, alternatives, providers, and documented costs address: {topic}?",
        f"What evidence contradicts or limits the premise: {topic}?",
    ]


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
            }
        )
    return observations


def build_research_plan(db: Session, question: models.ResearchQuestion) -> dict[str, Any]:
    """Describe known observations, unknowns, assumptions, and permitted strategies."""
    candidates: list[dict[str, Any]] = [
        {
            "source": "internal_evidence",
            "available": True,
            "rank": 1,
            "rationale": "Reuse attributable prior external observations without creating duplicates.",
        }
    ]
    external_sources = []
    for entry in source_clearance_registry.source_clearances():
        active = source_clearance_registry.collector_is_cleared(entry.collector)
        candidate = {
            "source": entry.collector,
            "available": active,
            "rank": len(candidates) + 1,
            "scope": entry.url,
            "rationale": entry.allowed_need,
            "registry_id": entry.registry_id,
        }
        candidates.append(candidate)
        if active:
            external_sources.append(entry.collector)
    candidates.extend(
        [
            {
                "source": "web_search",
                "available": False,
                "rank": len(candidates) + 1,
                "reason": "No currently reviewed general web-search API is configured.",
            },
            {
                "source": "direct_web",
                "available": False,
                "rank": len(candidates) + 2,
                "reason": "The only direct-page clearance is expired; no page will be fetched.",
            },
        ]
    )
    subquestions = _subquestions(question.question)
    return {
        "question_id": question.id,
        "subquestions": subquestions,
        "known_observations": _prior_observations(db, question.question),
        "assumptions": [
            "The question's premise is unverified; wording is not evidence.",
            "A Crossref metadata match proves a bibliographic record exists, not that the publication supports the premise.",
            "No commercial demand, customer, price, revenue, or transaction is inferred from scholarly metadata.",
        ],
        "unknowns": list(_UNCERTAINTIES),
        "candidate_sources": candidates,
        "selected_sources": external_sources,
        "stopping_conditions": [
            "Stop a source task when the source returns attributable records or a recorded no-result outcome.",
            "Keep the overall question open while subquestions are queued, source access is blocked, or material unknowns remain.",
            "Do not create a supported claim or opportunity from metadata discovery alone.",
        ],
    }


def _sources_for_question(question_text: str) -> list[str]:
    """Return only currently cleared general-purpose discovery sources."""
    del question_text
    return [
        entry.collector
        for entry in source_clearance_registry.source_clearances()
        if entry.collector != "web"
        and source_clearance_registry.collector_is_cleared(entry.collector)
    ]


def plan_tasks_for_question(db: Session, question: models.ResearchQuestion) -> list[models.ResearchTask]:
    """Persist idempotent, source-specific tasks for answerable subquestions."""
    plan = build_research_plan(db, question)
    sources = _sources_for_question(question.question)
    created: list[models.ResearchTask] = []

    for subquestion in plan["subquestions"]:
        for source in sources:
            existing = (
                db.query(models.ResearchTask)
                .filter_by(
                    question_id=question.id,
                    source=source,
                    query=subquestion,
                )
                .first()
            )
            if existing is not None:
                existing.results = {
                    **(existing.results or {}),
                    "research_plan": plan,
                }
                if existing.status in {"needs_research", "failed"}:
                    retried = research_task_engine.retry_task(db, existing)
                    if retried.status == "planned":
                        created.append(retried)
                continue
            task = research_task_engine.create_task(
                db,
                question_id=question.id,
                source=source,
                query=subquestion,
                objective=subquestion,
                claim_id=question.source_claim_id,
            )
            task.results = {
                **(task.results or {}),
                "research_plan": plan,
            }
            created.append(task)

    if created:
        db.commit()
        for task in created:
            db.refresh(task)
    return created


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
        tasks = plan_tasks_for_question(db, question)
        all_tasks.extend(tasks)
        question_tasks = db.query(models.ResearchTask).filter_by(question_id=question.id).all()
        has_pending_or_evidence = any(
            task.status in {"planned", "running"} or bool((task.evidence_ids or "").strip())
            for task in question_tasks
        )
        question.status = "planned" if has_pending_or_evidence else "open"

    db.commit()
    return all_tasks
