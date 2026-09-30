"""Meaningful opportunity monitoring built on OpportunityEvent and the evidence graph."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json

from sqlalchemy.orm import Session

from app import models
from app.services import multi_judge, research_planner


def utcnow():
    return datetime.now(timezone.utc)


def _as_utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _snapshot(db: Session, opportunity: models.Opportunity) -> dict:
    evidence = db.query(models.Evidence).filter_by(opportunity_id=opportunity.id).all()
    claims = db.query(models.Claim).filter_by(opportunity_id=opportunity.id).all()
    if claims:
        claim_ids = [claim.id for claim in claims]
        evidence_ids = {
            edge.evidence_id
            for edge in db.query(models.EvidenceRelationship).filter(
                models.EvidenceRelationship.claim_id.in_(claim_ids)
            ).all()
        }
        evidence.extend(db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all())
    evidence_by_id = {item.id: item for item in evidence}
    sources = sorted({item.source for item in evidence_by_id.values() if item.source})
    contradictions = db.query(models.EvidenceRelationship).filter_by(opportunity_id=opportunity.id, relation_type="contradicts").count()
    if claims:
        contradictions += db.query(models.EvidenceRelationship).filter(
            models.EvidenceRelationship.claim_id.in_([claim.id for claim in claims]),
            models.EvidenceRelationship.relation_type == "contradicts",
        ).count()
    last_evidence = max((_as_utc(item.retrieved_at or item.created_at) for item in evidence_by_id.values()), default=None)
    return {
        "evidence_ids": sorted(evidence_by_id),
        "evidence_count": len(evidence_by_id),
        "source_count": len(sources),
        "sources": sources,
        "claim_states": sorted(claim.epistemic_state for claim in claims),
        "contradictions": contradictions,
        "last_evidence_at": last_evidence.isoformat() if last_evidence else None,
        "score": opportunity.score,
        "status": opportunity.status,
        "uncertainty": opportunity.uncertainty,
    }


def _fingerprint(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


def _latest_snapshot(db: Session, opportunity_id: int) -> tuple[dict | None, str | None]:
    event = (
        db.query(models.OpportunityEvent)
        .filter_by(opportunity_id=opportunity_id, event_type="monitoring_snapshot")
        .order_by(models.OpportunityEvent.id.desc())
        .first()
    )
    if not event:
        return None, None
    try:
        return json.loads(event.details or "{}"), event.event_key
    except json.JSONDecodeError:
        return None, event.event_key


def _research_for_change(db: Session, opportunity: models.Opportunity, change: str) -> models.ResearchQuestion:
    text = f"Monitor opportunity {opportunity.id}: investigate {change} for {opportunity.problem}"
    question = db.query(models.ResearchQuestion).filter_by(question=text).first()
    if question:
        return question
    question = models.ResearchQuestion(question=text, priority_score=80.0, status="open")
    db.add(question)
    db.commit()
    db.refresh(question)
    research_planner.plan_tasks_for_question(db, question)
    return question


def monitor_opportunity(
    db: Session,
    opportunity_id: int,
    *,
    stale_after_days: int = 30,
    run_judgment: bool = True,
) -> dict:
    opportunity = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opportunity:
        return {"status": "not_found", "opportunity_id": opportunity_id}
    current = _snapshot(db, opportunity)
    fingerprint = _fingerprint(current)
    previous, previous_key = _latest_snapshot(db, opportunity_id)
    if previous_key == fingerprint:
        return {"status": "NO_MEANINGFUL_CHANGE", "change": "unchanged", "snapshot": current, "research_question_id": None, "judgment": None}

    changes = []
    if previous:
        if current["evidence_count"] > previous.get("evidence_count", 0):
            changes.append("new_evidence")
        if current["source_count"] > previous.get("source_count", 0):
            changes.append("new_source")
        if current["contradictions"] > previous.get("contradictions", 0):
            changes.append("contradiction_added")
        if current["score"] != previous.get("score"):
            changes.append("score_changed")
        if current["status"] != previous.get("status"):
            changes.append("status_changed")
        if current["claim_states"] != previous.get("claim_states"):
            changes.append("claim_state_changed")
    else:
        changes.append("initial_snapshot")
    last_evidence = datetime.fromisoformat(current["last_evidence_at"]) if current["last_evidence_at"] else None
    stale = last_evidence is None or utcnow() - _as_utc(last_evidence) > timedelta(days=stale_after_days)
    if stale:
        changes.append("stale")

    if "contradiction_added" in changes:
        change_class = "weakened"
        if opportunity.status not in {"validated", "win", "loss"}:
            opportunity.status = "invalidated"
    elif "new_evidence" in changes or "new_source" in changes:
        change_class = "expanding"
    elif "stale" in changes:
        change_class = "stale"
    else:
        change_class = "changed"

    event_key = fingerprint
    event = db.query(models.OpportunityEvent).filter_by(
        opportunity_id=opportunity.id, event_type="monitoring_snapshot", event_key=event_key
    ).first()
    if not event:
        event = models.OpportunityEvent(
            opportunity_id=opportunity.id,
            event_type="monitoring_snapshot",
            event_key=event_key,
            details=json.dumps({"snapshot": current, "changes": changes, "classification": change_class}, sort_keys=True),
        )
        db.add(event)
        if change_class in {"weakened", "stale"}:
            db.add(models.OpportunityEvent(
                opportunity_id=opportunity.id,
                event_type=f"opportunity_{change_class}",
                event_key=hashlib.sha256(f"{opportunity.id}:{change_class}:{fingerprint}".encode()).hexdigest(),
                details=json.dumps({"changes": changes, "snapshot": current}, sort_keys=True),
            ))
    opportunity.updated_at = utcnow()
    db.commit()
    db.refresh(opportunity)

    research_question = None
    if any(change in changes for change in ("new_evidence", "new_source", "contradiction_added", "stale")):
        research_question = _research_for_change(db, opportunity, ", ".join(changes))

    judgment = None
    if run_judgment and "new_evidence" in changes:
        claims = db.query(models.Claim).filter_by(opportunity_id=opportunity.id).all()
        if claims:
            evidence_ids = []
            for claim in claims:
                evidence_ids.extend(
                    edge.evidence_id
                    for edge in db.query(models.EvidenceRelationship).filter_by(claim_id=claim.id).all()
                )
            if evidence_ids:
                question = f"Reassess opportunity {opportunity.id}: {opportunity.problem}"
                judgments = multi_judge.run_judgments(db, question=question, evidence_ids=sorted(set(evidence_ids)), opportunity_id=opportunity.id, claim_id=claims[0].id)
                comparison = multi_judge.compare_judgments(db, question=question, judgment_ids=[item.id for item in judgments], evidence_ids=sorted(set(evidence_ids)), claim_id=claims[0].id)
                judgment = {"judgment_ids": [item.id for item in judgments], "comparison_id": comparison.id, "outcome": comparison.outcome}

    return {
        "status": opportunity.status,
        "change": change_class,
        "changes": changes,
        "snapshot": current,
        "research_question_id": research_question.id if research_question else None,
        "judgment": judgment,
    }
