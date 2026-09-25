"""Candidate connections inside the existing Forge world.

Opportunity, Decision, Strategy, and Action cannot represent two endpoints
plus a lifecycle. This record does. A candidate is not an offer, and no
state is implied by an earlier one.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.api.public import _match_for_need
from app.services import evidence_graph
from app.services.network_endpoints import (
    canonical_endpoint_type,
    resolve_endpoint,
)

STATES = (
    "candidate",
    "evidenced",
    "viable",
    "proposed",
    "authorized",
    "contacted",
    "accepted",
    "fulfilled",
    "paid",
    "completed",
    "failed",
)
PUBLISHABLE = {"authorized", "contacted", "accepted", "fulfilled", "paid", "completed"}
RELATION_EPISTEMIC_STATES = {
    "possible", "hypothesized", "tested", "supported", "refuted", "unknown"
}
RELATION_DIRECTIONS = {"directed", "bidirectional"}
_RELATION_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


def normalize_relation_type(value: str) -> str:
    relation_type = (value or "").strip().casefold()
    if not _RELATION_TYPE_PATTERN.fullmatch(relation_type):
        raise ValueError("relation_type must be a non-empty lowercase snake-case value")
    return relation_type


def find_connection(
    db: Session,
    left_kind: str,
    left_id: int,
    right_kind: str,
    right_id: int,
) -> models.NetworkConnection | None:
    left = canonical_endpoint_type(left_kind)
    right = canonical_endpoint_type(right_kind)
    return (
        db.query(models.NetworkConnection)
        .filter_by(left_kind=left, left_id=left_id, right_kind=right, right_id=right_id)
        .order_by(models.NetworkConnection.id.desc())
        .first()
    )


def create_connection(
    db: Session,
    *,
    left_kind: str,
    left_id: int,
    right_kind: str,
    right_id: int,
    relation_type: str,
    reason: str,
    epistemic_state: str = "hypothesized",
    direction: str = "directed",
    context: dict[str, Any] | None = None,
    uncertainty: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    evidence_ids: list[int] | None = None,
    public_visible: bool = False,
) -> models.NetworkConnection:
    """Create one relation over existing canonical records.

    Relation predicates are open vocabulary. Their epistemic state is separate
    from the connection workflow state, which always begins as a candidate.
    """
    left_kind, _left = resolve_endpoint(db, left_kind, left_id)
    right_kind, _right = resolve_endpoint(db, right_kind, right_id)
    relation_type = normalize_relation_type(relation_type)
    if epistemic_state not in RELATION_EPISTEMIC_STATES:
        raise ValueError("invalid relation epistemic_state")
    if direction not in RELATION_DIRECTIONS:
        raise ValueError("direction must be directed or bidirectional")
    if not (reason or "").strip():
        raise ValueError("a relation needs a reason")
    if valid_from is not None and valid_until is not None and valid_until < valid_from:
        raise ValueError("valid_until cannot precede valid_from")

    stored_evidence = [db.get(models.Evidence, evidence_id) for evidence_id in evidence_ids or []]
    if any(evidence is None for evidence in stored_evidence):
        raise ValueError("every evidence_id must identify stored evidence")
    if epistemic_state in {"tested", "supported", "refuted"} and not stored_evidence:
        raise ValueError(f"{epistemic_state} relations require stored evidence")

    connection = models.NetworkConnection(
        left_kind=left_kind,
        left_id=left_id,
        right_kind=right_kind,
        right_id=right_id,
        relation_type=relation_type,
        direction=direction,
        epistemic_state=epistemic_state,
        state="candidate",
        reason=reason.strip(),
        context=context,
        uncertainty=uncertainty,
        provenance=provenance,
        valid_from=valid_from,
        valid_until=valid_until,
        observed_at=models.utcnow(),
        public_visible=public_visible,
        agreement_gap="No agreement is implied by this relation.",
    )
    db.add(connection)
    db.flush()
    for evidence in stored_evidence:
        relation = (
            "supports" if epistemic_state == "supported"
            else "contradicts" if epistemic_state == "refuted"
            else "derived_from"
        )
        _link_evidence_row(db, connection, evidence, relation)
    db.commit()
    db.refresh(connection)
    return connection


def _link_evidence_row(
    db: Session,
    connection: models.NetworkConnection,
    evidence: models.Evidence,
    relation_type: str,
) -> tuple[models.EvidenceRelationship, bool]:
    return evidence_graph.link_evidence(
        db,
        evidence,
        relation_type=relation_type,
        network_connection=connection,
    )


def attach_evidence(
    db: Session,
    connection: models.NetworkConnection,
    evidence_id: int,
    *,
    relation_type: str = "derived_from",
) -> tuple[models.EvidenceRelationship, bool]:
    """Attach one existing evidence row to a connection idempotently."""
    if db.get(models.NetworkConnection, connection.id) is None:
        raise ValueError("connection must already be stored")
    evidence = db.get(models.Evidence, evidence_id)
    if evidence is None:
        raise ValueError("evidence_id must identify stored evidence")
    relation_type = relation_type.strip().casefold()
    edge, created = _link_evidence_row(db, connection, evidence, relation_type)
    if created:
        db.commit()
        db.refresh(edge)
    return edge, created


def evidence_for_connection(db: Session, connection_id: int) -> list[models.Evidence]:
    return (
        db.query(models.Evidence)
        .join(
            models.EvidenceRelationship,
            models.EvidenceRelationship.evidence_id == models.Evidence.id,
        )
        .filter(models.EvidenceRelationship.network_connection_id == connection_id)
        .order_by(models.Evidence.id.asc())
        .all()
    )


def record_response(db: Session, connection: models.NetworkConnection, note: str) -> models.Outcome:
    """Record a response without changing connection state or implying acceptance."""
    clean_note = note.strip()
    if not clean_note:
        raise ValueError("a response needs a note")
    note_hash = hashlib.sha256(clean_note.encode("utf-8")).hexdigest()
    from app.services import action_engine

    outcome = action_engine.record_domain_event(
        db,
        idempotency_key=f"network-connection:{connection.id}:response:{note_hash}",
        source="network_connection",
        qualitative_result=(
            f"Connection {connection.id} received a response. "
            f"It is not acceptance. Note: {clean_note}"
        ),
    )
    return outcome


def _hypothesis(db: Session, connection: models.NetworkConnection, need: models.DomainRecord) -> models.Opportunity:
    """An internal possible opportunity. Not an offer, not a buyer, not a price."""
    key = (
        f"connection:{connection.left_kind}:{connection.left_id}:"
        f"{connection.right_kind}:{connection.right_id}"
    )
    existing = db.query(models.Opportunity).filter(models.Opportunity.identity_key == key).first()
    if existing:
        return existing
    opportunity = models.Opportunity(
        problem=f"Possible introduction: {need.title}. Reason: {connection.reason}",
        target_customer="Not identified. No buyer has been recorded.",
        solution="Introduce the two recorded sides. Forge does not own either side.",
        business_model="mediation",
        status="identified",
        market_confidence=0.0,
        revenue_confidence=0.0,
        uncertainty=100.0,
        identity_key=key,
        economic_evidence_summary=connection.reason,
        monetization_model="unknown",
    )
    db.add(opportunity)
    return opportunity


def can_advance(current: str, nxt: str) -> bool:
    if current in {"failed", "completed"}:
        return False
    if nxt == "failed":
        return True
    if current not in STATES or nxt not in STATES:
        return False
    return STATES.index(nxt) == STATES.index(current) + 1


def scan_candidates(db: Session, limit: int = 50) -> list[models.NetworkConnection]:
    created: list[models.NetworkConnection] = []
    needs = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open")
        .order_by(models.DomainRecord.id.desc())
        .all()
    )
    for need in needs:
        if len(created) >= limit:
            break
        match = _match_for_need(db, need)
        for candidate in match.candidates:
            if len(created) >= limit:
                break
            candidate_type = candidate.entity_type or candidate.kind
            left_kind, _left = resolve_endpoint(db, "domain_record", need.id)
            candidate_type, _candidate = resolve_endpoint(db, candidate_type, candidate.id)
            exists = find_connection(
                db, left_kind, need.id, candidate_type, candidate.id
            )
            if exists is not None and exists.state != "failed":
                continue
            row = models.NetworkConnection(
                left_kind=left_kind,
                left_id=need.id,
                right_kind=candidate_type,
                right_id=candidate.id,
                relation_type="possible_match",
                direction="directed",
                epistemic_state="hypothesized",
                state="candidate",
                reason="; ".join(candidate.reasons),
                known="; ".join(
                    part
                    for part in (
                        f"price {candidate.stated_price}" if candidate.stated_price else "",
                        f"availability {candidate.stated_availability}" if candidate.stated_availability else "",
                    )
                    if part
                )
                or None,
                unknown="; ".join(candidate.unknowns),
                context={"city": need.city} if need.city else {},
                provenance={"created_by": "candidate_scan", "source": "stored_records"},
                agreement_gap="A person must propose, authorize, and accept before this is an agreement.",
            )
            db.add(row)
            db.flush()
            _hypothesis(db, row, need)
            created.append(row)
    if created:
        db.commit()
        for row in created:
            db.refresh(row)
    record_unmatched_gaps(db)
    return created


def gap_question(need: models.DomainRecord) -> str:
    """A stable question about a missing side. Not an offer and not a buyer."""
    place = (need.city or "").strip() or "place not recorded"
    return (
        f'Gap: open {need.kind} #{need.id} "{need.title}" has no recorded counterparty. '
        f"Place: {place}. This asks who could satisfy it. It is not an offer, a buyer, or a price."
    )


def record_unmatched_gaps(db: Session) -> list[models.ResearchQuestion]:
    """Turn an open need with no live candidate into one research question.

    A later candidate closes that question. If every candidate fails, the
    same question opens again. Nothing here invents the missing side.
    """
    changed: list[models.ResearchQuestion] = []
    needs = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open")
        .order_by(models.DomainRecord.id.asc())
        .all()
    )
    for need in needs:
        text = gap_question(need)
        live = (
            db.query(models.NetworkConnection)
            .filter_by(left_kind="domain_record", left_id=need.id)
            .filter(models.NetworkConnection.state != "failed")
            .first()
        )
        existing = (
            db.query(models.ResearchQuestion)
            .filter(models.ResearchQuestion.question == text)
            .first()
        )
        if live is not None:
            if existing is not None and existing.status == "open":
                existing.status = "closed"
                changed.append(existing)
            continue
        if existing is None:
            question = models.ResearchQuestion(
                question=text,
                priority_score=80.0,
                status="open",
            )
            db.add(question)
            changed.append(question)
            continue
        if existing.status != "open":
            existing.status = "open"
            changed.append(existing)
    if changed:
        db.commit()
        for row in changed:
            db.refresh(row)
    return changed
