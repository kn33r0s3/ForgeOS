"""Durable evidence, claim, and provenance graph operations."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app import models

RELATION_TYPES = {
    "supports",
    "contradicts",
    "duplicates",
    "derived_from",
    "translated_from",
    "summarizes",
    "updates",
    "supersedes",
}
CLAIM_STATES = {"observed", "supported", "contested", "weakened", "superseded", "verified", "rejected"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_statement(statement: str) -> str:
    return " ".join(re.findall(r"\S+", statement.strip().casefold()))


def get_or_create_evidence(
    db: Session,
    *,
    provenance_hash: str,
    source: str | None,
    content: str,
    **metadata: Any,
) -> tuple[models.Evidence, bool]:
    """Reuse evidence with the same deterministic provenance identity."""
    existing = db.query(models.Evidence).filter_by(provenance_hash=provenance_hash).first()
    if existing:
        return existing, False
    evidence = models.Evidence(
        provenance_hash=provenance_hash,
        source=source,
        content=content,
        direction=metadata.get("direction", "supports"),
        confidence=metadata.get("confidence", 0.0),
        canonical_url=metadata.get("canonical_url"),
        external_id=metadata.get("external_id"),
        title=metadata.get("title"),
        published_at=metadata.get("published_at"),
        retrieved_at=metadata.get("retrieved_at") or utcnow(),
        content_fingerprint=metadata.get("content_fingerprint"),
        provenance=json.dumps(metadata.get("provenance"), sort_keys=True) if metadata.get("provenance") else None,
        collection_status=metadata.get("collection_status", "collected"),
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence, True


def create_or_get_claim(
    db: Session,
    statement: str,
    *,
    epistemic_state: str = "observed",
    opportunity_id: int | None = None,
    decision_id: int | None = None,
    experiment_id: int | None = None,
    outcome_id: int | None = None,
    provenance: dict | None = None,
) -> tuple[models.Claim, bool]:
    if epistemic_state not in CLAIM_STATES:
        raise ValueError(f"invalid claim state: {epistemic_state}")
    normalized = normalize_statement(statement)
    if not normalized:
        raise ValueError("claim statement required")
    query = db.query(models.Claim).filter_by(normalized_statement=normalized)
    if opportunity_id is not None:
        query = query.filter_by(opportunity_id=opportunity_id)
    else:
        query = query.filter(models.Claim.opportunity_id.is_(None))
    claim = query.first()
    if claim:
        if claim.epistemic_state == "observed" and epistemic_state != "observed":
            claim.epistemic_state = epistemic_state
        claim.updated_at = utcnow()
        db.commit()
        db.refresh(claim)
        return claim, False
    claim = models.Claim(
        statement=statement.strip(),
        normalized_statement=normalized,
        epistemic_state=epistemic_state,
        confidence=None,
        opportunity_id=opportunity_id,
        decision_id=decision_id,
        experiment_id=experiment_id,
        outcome_id=outcome_id,
        provenance=json.dumps(provenance, sort_keys=True) if provenance else None,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim, True


def _target_key(
    *,
    claim_id: int | None,
    opportunity_id: int | None,
    decision_id: int | None,
    experiment_id: int | None,
    outcome_id: int | None,
    judgment_id: int | None = None,
) -> str:
    values = {
        "claim": claim_id,
        "opportunity": opportunity_id,
        "decision": decision_id,
        "experiment": experiment_id,
        "outcome": outcome_id,
        "judgment": judgment_id,
    }
    target = next(((kind, value) for kind, value in values.items() if value is not None), None)
    if target is None:
        raise ValueError("relationship target required")
    return f"{target[0]}:{target[1]}"


def link_evidence(
    db: Session,
    evidence: models.Evidence,
    *,
    relation_type: str,
    claim: models.Claim | None = None,
    opportunity_id: int | None = None,
    decision_id: int | None = None,
    experiment_id: int | None = None,
    outcome_id: int | None = None,
    judgment_id: int | None = None,
) -> tuple[models.EvidenceRelationship, bool]:
    if relation_type not in RELATION_TYPES:
        raise ValueError(f"invalid evidence relationship: {relation_type}")
    claim_id = claim.id if claim else None
    target = _target_key(
        claim_id=claim_id,
        opportunity_id=opportunity_id,
        decision_id=decision_id,
        experiment_id=experiment_id,
        outcome_id=outcome_id,
        judgment_id=judgment_id,
    )
    relation_key = hashlib.sha256(
        f"{evidence.id}:{target}:{relation_type}".encode("utf-8")
    ).hexdigest()
    existing = db.query(models.EvidenceRelationship).filter_by(relation_key=relation_key).first()
    if existing:
        return existing, False
    edge = models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim_id,
        opportunity_id=opportunity_id,
        decision_id=decision_id,
        experiment_id=experiment_id,
        outcome_id=outcome_id,
        judgment_id=judgment_id,
        relation_type=relation_type,
        relation_key=relation_key,
    )
    db.add(edge)
    if claim:
        if relation_type == "contradicts" and claim.epistemic_state in {"observed", "supported"}:
            claim.epistemic_state = "contested"
        elif relation_type == "supports" and claim.epistemic_state == "observed":
            claim.epistemic_state = "supported"
        elif relation_type == "supersedes":
            claim.epistemic_state = "superseded"
        claim.updated_at = utcnow()
    db.commit()
    db.refresh(edge)
    return edge, True


def set_claim_state(db: Session, claim: models.Claim, state: str) -> models.Claim:
    if state not in CLAIM_STATES:
        raise ValueError(f"invalid claim state: {state}")
    claim.epistemic_state = state
    claim.updated_at = utcnow()
    db.commit()
    db.refresh(claim)
    return claim


def trace_opportunity(db: Session, opportunity_id: int) -> dict[str, Any] | None:
    opportunity = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opportunity:
        return None
    direct_evidence = db.query(models.Evidence).filter_by(opportunity_id=opportunity_id).all()
    edges = db.query(models.EvidenceRelationship).filter_by(opportunity_id=opportunity_id).all()
    claim_ids = {edge.claim_id for edge in edges if edge.claim_id is not None}
    claim_ids.update(claim.id for claim in opportunity.claims)
    claims = db.query(models.Claim).filter(models.Claim.id.in_(claim_ids)).all() if claim_ids else []
    if claim_ids:
        claim_edges = db.query(models.EvidenceRelationship).filter(
            models.EvidenceRelationship.claim_id.in_(claim_ids)
        ).all()
        edges = list({edge.id: edge for edge in [*edges, *claim_edges]}.values())
    evidence_ids = {evidence.id for evidence in direct_evidence}
    evidence_ids.update(edge.evidence_id for edge in edges)
    evidence_rows = db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all() if evidence_ids else []
    edge_rows = db.query(models.EvidenceRelationship).filter(models.EvidenceRelationship.evidence_id.in_(evidence_ids)).all() if evidence_ids else []
    judgments = db.query(models.Judgment).filter(
        (models.Judgment.opportunity_id == opportunity_id)
        | (models.Judgment.claim_id.in_(claim_ids) if claim_ids else False)
    ).all()
    judgment_ids = {judgment.id for judgment in judgments}
    comparisons = []
    for comparison in db.query(models.JudgmentComparison).all():
        if judgment_ids.intersection(set(comparison.judgment_ids or [])):
            comparisons.append(comparison)
    return {
        "opportunity": opportunity,
        "claims": claims,
        "evidence": evidence_rows,
        "relationships": edge_rows,
        "judgments": judgments,
        "comparisons": comparisons,
        "why": [
            {
                "claim": claim.statement,
                "state": claim.epistemic_state,
                "evidence": [
                    {
                        "id": evidence.id,
                        "source": evidence.source,
                        "title": evidence.title,
                        "canonical_url": evidence.canonical_url,
                        "content": evidence.content,
                        "relation": next(
                            (edge.relation_type for edge in edge_rows if edge.evidence_id == evidence.id and edge.claim_id == claim.id),
                            evidence.direction or "supports",
                        ),
                    }
                    for evidence in evidence_rows
                    if any(edge.evidence_id == evidence.id and edge.claim_id == claim.id for edge in edge_rows)
                ],
            }
            for claim in claims
        ],
    }
