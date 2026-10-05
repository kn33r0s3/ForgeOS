"""Durable evidence, claim, and provenance graph operations."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from sqlalchemy.exc import IntegrityError
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


def _matches_evidence_intent(
    evidence: models.Evidence,
    *,
    source: str | None,
    content: str,
    metadata: dict[str, Any],
) -> bool:
    provenance = metadata.get("provenance")
    expected = {
        "source": source,
        "content": content,
        "direction": metadata.get("direction", "supports"),
        "confidence": metadata.get("confidence", 0.0),
        "canonical_url": metadata.get("canonical_url"),
        "external_id": metadata.get("external_id"),
        "title": metadata.get("title"),
        "published_at": metadata.get("published_at"),
        "content_fingerprint": metadata.get("content_fingerprint"),
        "provenance": json.dumps(provenance, sort_keys=True) if provenance else None,
        "collection_status": metadata.get("collection_status", "collected"),
    }
    return all(getattr(evidence, field) == value for field, value in expected.items())


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
        if not _matches_evidence_intent(
            existing, source=source, content=content, metadata=metadata
        ):
            raise ValueError("provenance hash collision: existing evidence has different source content")
        return existing, False
    idempotency_key = f"evidence-provenance:{provenance_hash}"
    existing = db.query(models.Evidence).filter_by(idempotency_key=idempotency_key).first()
    if existing:
        if not _matches_evidence_intent(
            existing, source=source, content=content, metadata=metadata
        ):
            raise ValueError("evidence idempotency key collision: payload does not match")
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
        idempotency_key=idempotency_key,
    )
    db.add(evidence)
    try:
        db.commit()
    except IntegrityError:
        # This helper already owns a commit boundary. On a unique-key race,
        # roll back and resolve the winning row so the caller can continue.
        db.rollback()
        existing = db.query(models.Evidence).filter_by(idempotency_key=idempotency_key).first()
        if existing is None:
            raise
        if not _matches_evidence_intent(
            existing, source=source, content=content, metadata=metadata
        ):
            raise ValueError("evidence idempotency key collision: payload does not match")
        return existing, False
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
    # Identity covers the full scope: a statement scoped to a different
    # decision/experiment/outcome is a different claim. Matching on the
    # statement alone used to silently drop the caller's scope fields.
    for column, value in (
        (models.Claim.opportunity_id, opportunity_id),
        (models.Claim.decision_id, decision_id),
        (models.Claim.experiment_id, experiment_id),
        (models.Claim.outcome_id, outcome_id),
    ):
        if value is not None:
            query = query.filter(column == value)
        else:
            query = query.filter(column.is_(None))
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


def restore_source_addresses(db: Session, limit: int = 50) -> int:
    """Copy a source address onto the original signal when only a duplicate stored it.

    The address must already be on a duplicate of that signal, and every such
    duplicate must carry the same address. Nothing is fetched or invented.
    """
    if limit <= 0:
        return 0
    duplicate_urls = (
        db.query(models.Signal.is_duplicate_of)
        .filter(models.Signal.is_duplicate_of.isnot(None))
        .filter(models.Signal.canonical_url.isnot(None))
        .filter(models.Signal.canonical_url != "")
    )
    originals = (
        db.query(models.Signal)
        .filter(models.Signal.id.in_(duplicate_urls))
        .filter((models.Signal.canonical_url.is_(None)) | (models.Signal.canonical_url == ""))
        .order_by(models.Signal.id.desc())
        .limit(limit)
        .all()
    )
    restored = 0
    for original in originals:
        urls = {
            row.canonical_url.strip()
            for row in db.query(models.Signal.canonical_url)
            .filter(models.Signal.is_duplicate_of == original.id)
            .filter(models.Signal.canonical_url.isnot(None))
            .filter(models.Signal.canonical_url != "")
            .all()
            if row.canonical_url and row.canonical_url.strip()
        }
        if len(urls) != 1:
            continue
        original.canonical_url = urls.pop()
        restored += 1
    if restored:
        db.commit()
    return restored


def link_unclaimed_observations(db: Session, limit: int = 20) -> list[int]:
    """Open an observed claim for an external signal that already has evidence.

    The statement is the stored source text. This does not verify it, price
    it, or publish a provider. A signal that already has a claim is skipped.
    """
    if limit <= 0:
        return []
    claimed_signals = (
        db.query(models.Evidence.signal_id)
        .join(models.EvidenceRelationship, models.EvidenceRelationship.evidence_id == models.Evidence.id)
        .filter(models.EvidenceRelationship.claim_id.isnot(None))
        .filter(models.Evidence.signal_id.isnot(None))
    )
    evidence_id = (
        db.query(models.Evidence.id)
        .filter(models.Evidence.signal_id == models.Signal.id)
        .order_by(models.Evidence.id.desc())
        .limit(1)
        .correlate(models.Signal)
        .scalar_subquery()
    )
    rows = (
        db.query(models.Signal, models.Evidence)
        .join(models.Evidence, models.Evidence.id == evidence_id)
        .filter(models.Signal.source_type == "external")
        .filter(models.Signal.canonical_url.isnot(None))
        .filter(models.Signal.canonical_url != "")
        .filter(models.Signal.is_duplicate_of.is_(None))
        .filter(~models.Signal.id.in_(claimed_signals))
        .order_by(models.Signal.id.desc())
        .limit(limit)
        .all()
    )
    linked: list[int] = []
    for signal, evidence in rows:
        statement = (signal.content or "").strip().replace("\n", " ")
        if len(statement) > 400:
            statement = statement[:400].rstrip()
        if not statement:
            continue
        claim, _ = create_or_get_claim(
            db,
            statement,
            epistemic_state="observed",
            provenance={
                "signal_id": signal.id,
                "source": signal.source,
                "canonical_url": signal.canonical_url,
            },
        )
        link_evidence(db, evidence, claim=claim, relation_type="derived_from")
        linked.append(claim.id)
    return linked


def _target_key(
    *,
    claim_id: int | None,
    opportunity_id: int | None,
    decision_id: int | None,
    experiment_id: int | None,
    outcome_id: int | None,
    judgment_id: int | None = None,
    network_connection_id: int | None = None,
) -> str:
    values = {
        "claim": claim_id,
        "opportunity": opportunity_id,
        "decision": decision_id,
        "experiment": experiment_id,
        "outcome": outcome_id,
        "judgment": judgment_id,
        "network_connection": network_connection_id,
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
    network_connection: models.NetworkConnection | None = None,
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
        network_connection_id=network_connection.id if network_connection else None,
    )
    relation_key = hashlib.sha256(
        f"{evidence.id}:{target}:{relation_type}".encode("utf-8")
    ).hexdigest()
    existing = (
        db.query(models.EvidenceRelationship)
        .filter_by(idempotency_key=relation_key)
        .first()
        or db.query(models.EvidenceRelationship).filter_by(relation_key=relation_key).first()
    )
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
        network_connection_id=network_connection.id if network_connection else None,
        relation_type=relation_type,
        relation_key=relation_key,
        idempotency_key=relation_key,
    )
    try:
        with db.begin_nested():
            db.add(edge)
            db.flush()
    except IntegrityError:
        db.expire_all()
        existing = (
            db.query(models.EvidenceRelationship)
            .filter_by(idempotency_key=relation_key)
            .first()
            or db.query(models.EvidenceRelationship).filter_by(relation_key=relation_key).first()
        )
        if existing is None:
            raise
        return existing, False
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
