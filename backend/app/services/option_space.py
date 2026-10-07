"""Evidence-constrained option generation and decision-space evaluation."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app import models

OPTION_CLASSES = (
    ("validate", "Run the cheapest reversible validation experiment before building."),
    ("build", "Build a narrow solution for the observed workflow."),
    ("service", "Deliver the workflow manually or as a productized service."),
    ("buy_or_integrate", "Use or integrate an existing solution where evidence supports it."),
    ("defer", "Gather more evidence before committing resources."),
    ("do_nothing", "Do nothing until the uncertainty or opportunity cost changes."),
)


def _key(opportunity_id: int, option_class: str) -> str:
    return hashlib.sha256(f"{opportunity_id}:{option_class}".encode()).hexdigest()


def generate_options(db: Session, opportunity_id: int) -> list[models.Option]:
    opportunity = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opportunity:
        raise ValueError("opportunity not found")
    evidence = db.query(models.Evidence).filter_by(opportunity_id=opportunity_id).all()
    evidence_ids = ",".join(str(item.id) for item in evidence) or None
    created: list[models.Option] = []
    for option_class, description in OPTION_CLASSES:
        identity = _key(opportunity_id, option_class)
        option = db.query(models.Option).filter_by(identity_key=identity).first()
        if option:
            continue
        assumptions = []
        uncertainties = []
        if option_class in {"build", "service", "buy_or_integrate"}:
            assumptions.append("The problem recurs for the identified customer.")
            uncertainties.append("Willingness to pay is not established unless evidence says otherwise.")
        if option_class in {"validate", "defer"}:
            uncertainties.append("The cheapest useful test and success condition require confirmation.")
        option = models.Option(
            opportunity_id=opportunity_id,
            name=f"{option_class.replace('_', ' ').title()} opportunity #{opportunity_id}",
            option_class=option_class,
            description=description,
            origin="existing_evidence",
            evidence_ids=evidence_ids,
            assumptions=assumptions,
            uncertainties=uncertainties,
            status="candidate",
            identity_key=identity,
        )
        db.add(option)
        created.append(option)
    db.commit()
    for option in created:
        db.refresh(option)
    return created


def evaluate_option_space(db: Session, opportunity_id: int) -> dict[str, Any]:
    options = db.query(models.Option).filter_by(opportunity_id=opportunity_id).order_by(models.Option.id.asc()).all()
    if not options:
        options = generate_options(db, opportunity_id)
    viable = [option for option in options if option.status == "candidate"]
    unknowns = sorted({unknown for option in viable for unknown in (option.uncertainties or [])})
    status = "MULTIPLE_OPTIONS_COMPARED" if len(viable) > 1 else "ONE_OPTION_FOUND" if viable else "OPTION_SPACE_EXHAUSTED"
    research_question = None
    if unknowns:
        text = f"Resolve option uncertainty for opportunity #{opportunity_id}: {unknowns[0]}"
        research_question = db.query(models.ResearchQuestion).filter_by(question=text).first()
        if not research_question:
            research_question = models.ResearchQuestion(question=text, priority_score=70.0, status="open")
            db.add(research_question)
            db.commit()
            db.refresh(research_question)
            from app.services import research_planner

            research_planner.plan_tasks_for_question(db, research_question)
    return {
        "status": status,
        "option_ids": [option.id for option in options],
        "unknowns": unknowns,
        "research_question_id": research_question.id if research_question else None,
        "scores": {},
        "note": "Unknown dimensions remain unscored; no fabricated comparison values are used.",
    }


def reject_option(db: Session, option_id: int, reason: str) -> models.Option:
    option = db.query(models.Option).filter_by(id=option_id).first()
    if not option:
        raise ValueError("option not found")
    option.status = "rejected"
    option.rejection_reason = reason
    db.commit()
    db.refresh(option)
    return option


def create_decision_from_options(db: Session, opportunity_id: int) -> models.Decision:
    from app.services import decision_engine

    evaluation = evaluate_option_space(db, opportunity_id)
    options = db.query(models.Option).filter(models.Option.id.in_(evaluation["option_ids"])).all()
    existing = db.query(models.Decision).filter_by(opportunity_id=opportunity_id).filter(models.Decision.status == "proposed").first()
    if existing:
        return existing
    alternatives = "; ".join(option.name for option in options)
    return decision_engine.propose_decision(
        db,
        title=f"Compare options for opportunity #{opportunity_id}",
        rationale="Options were generated from the existing opportunity and evidence graph; unknown dimensions remain explicit.",
        opportunity_id=opportunity_id,
        alternatives_considered=alternatives,
        expected_outcome="Reduce the most decision-relevant uncertainty with a reversible experiment.",
        risk_notes="No external side effect is authorized by this proposal.",
    )
