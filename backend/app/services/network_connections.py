"""Candidate connections inside the existing Forge world.

Opportunity, Decision, Strategy, and Action cannot represent two endpoints
plus a lifecycle. This record does. A candidate is not an offer, and no
state is implied by an earlier one.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app import models
from app.api.public import _match_for_need
from app.services import world_graph

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
    world_graph.seed_core_types(db)
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
            exists = world_graph.find_match_workflow(
                db, "domain_record", need.id, candidate_type, candidate.id
            )
            if exists is not None and exists.state != "failed":
                continue
            row = models.NetworkConnection(
                left_kind="domain_record",
                left_id=need.id,
                right_kind=candidate_type,
                right_id=candidate.id,
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
                agreement_gap="A person must propose, authorize, and accept before this is an agreement.",
            )
            db.add(row)
            db.flush()
            left_entity = world_graph.ensure_canonical_entity(db, "domain_record", need.id)
            right_entity = world_graph.ensure_canonical_entity(db, candidate_type, candidate.id)
            relation = world_graph.create_relation(
                db,
                from_entity_id=left_entity.id,
                to_entity_id=right_entity.id,
                relation_type="possible_match",
                attributes={"workflow": "network_connection", "workflow_id": row.id},
                truth_state="hypothesized",
                created_by="network_connections",
                idempotency_key=f"network-connection:{row.id}:possible-match",
            )
            row.relation_id = relation.id
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
