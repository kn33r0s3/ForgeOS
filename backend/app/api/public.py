import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import public_epistemics

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/feed", response_model=list[schemas.PublicFeedItem])
def list_public_feed(
    limit: int = Query(default=30, ge=1, le=100),
    kind: str | None = Query(default=None, min_length=1, max_length=32),
    entity_type: str | None = Query(default=None, min_length=1, max_length=64),
    entity_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    """Chronological public projection of canonical Forge evidence and network records."""
    from app.services.public_feed import build_public_feed

    if (entity_type is None) != (entity_id is None):
        raise HTTPException(status_code=422, detail="entity_type and entity_id must be provided together")
    return build_public_feed(
        db,
        limit=limit,
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def evidence_freshness(when: datetime | None) -> str:
    """fresh, stale, or unknown. Age never becomes a new fact."""
    if when is None:
        return "unknown"
    observed = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    days = int(os.environ.get("FORGEOS_EVIDENCE_FRESH_DAYS", "90"))
    age = datetime.now(timezone.utc) - observed
    return "stale" if age.days > days else "fresh"


def _public_provider_query(db: Session):
    return (
        db.query(models.Provider)
        .filter(models.Provider.public_visible.is_(True))
        .filter(models.Provider.is_active.is_(True))
        .filter(models.Provider.verification_status == "verified")
    )


def _public_service_query(db: Session):
    return (
        db.query(models.ServiceListing)
        .join(models.Provider)
        .filter(models.Provider.public_visible.is_(True))
        .filter(models.Provider.is_active.is_(True))
        .filter(models.Provider.verification_status == "verified")
        .filter(models.ServiceListing.public_visible.is_(True))
        .filter(models.ServiceListing.is_active.is_(True))
    )


def _like(value: str) -> str:
    return f"%{value.strip()}%"


def _matching_listing_provider_ids(db: Session, q: str):
    like = _like(q)
    return (
        db.query(models.ServiceListing.provider_id)
        .filter(models.ServiceListing.public_visible.is_(True))
        .filter(models.ServiceListing.is_active.is_(True))
        .filter(
            or_(
                models.ServiceListing.title.ilike(like),
                models.ServiceListing.description.ilike(like),
                models.ServiceListing.category.ilike(like),
                models.ServiceListing.location.ilike(like),
            )
        )
    )


@router.get("/providers", response_model=list[schemas.PublicProviderOut])
def list_public_providers(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    city: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = _public_provider_query(db)
    if category and category.strip() and category.strip().lower() != "all":
        query = query.filter(models.Provider.category.ilike(category.strip()))
    if city and city.strip():
        query = query.filter(models.Provider.city.ilike(_like(city)))
    if q and q.strip():
        like = _like(q)
        query = query.filter(
            or_(
                models.Provider.name.ilike(like),
                models.Provider.business_name.ilike(like),
                models.Provider.summary.ilike(like),
                models.Provider.category.ilike(like),
                models.Provider.city.ilike(like),
                models.Provider.region.ilike(like),
                models.Provider.id.in_(_matching_listing_provider_ids(db, q)),
            )
        )
    return query.order_by(models.Provider.created_at.desc()).all()


@router.get("/providers/{provider_id}", response_model=schemas.PublicProviderOut)
def get_public_provider(provider_id: int, db: Session = Depends(get_db)):
    row = (
        _public_provider_query(db)
        .filter(models.Provider.id == provider_id)
        .first()
    )
    if row is None:
        raise HTTPException(404, "provider not found")
    return row


@router.get("/services", response_model=list[schemas.PublicServiceListingOut])
def list_public_services(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    city: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = _public_service_query(db)
    if category and category.strip() and category.strip().lower() != "all":
        query = query.filter(models.ServiceListing.category.ilike(category.strip()))
    if city and city.strip():
        like = _like(city)
        query = query.filter(
            or_(models.ServiceListing.location.ilike(like), models.Provider.city.ilike(like))
        )
    if q and q.strip():
        like = _like(q)
        query = query.filter(
            or_(
                models.ServiceListing.title.ilike(like),
                models.ServiceListing.description.ilike(like),
                models.ServiceListing.category.ilike(like),
                models.ServiceListing.location.ilike(like),
                models.Provider.name.ilike(like),
                models.Provider.city.ilike(like),
            )
        )
    return query.order_by(models.ServiceListing.created_at.desc()).all()


@router.get("/discoveries", response_model=list[schemas.PublicDiscoveryOut])
def list_public_discoveries(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db)):
    """Claims the evidence graph already holds. Internal scores stay off this response."""
    rows = (
        db.query(models.Claim, models.Signal)
        .join(models.EvidenceRelationship, models.EvidenceRelationship.claim_id == models.Claim.id)
        .join(models.Evidence, models.Evidence.id == models.EvidenceRelationship.evidence_id)
        .join(models.Signal, models.Signal.id == models.Evidence.signal_id)
        .filter(models.Signal.source_type == "external")
        .filter(models.Signal.canonical_url.isnot(None))
        .filter(models.Signal.is_duplicate_of.is_(None))
        .order_by(models.Claim.updated_at.desc())
        .limit(limit)
        .all()
    )
    discoveries = []
    seen = set()
    for claim, signal in rows:
        label = public_epistemics.public_claim_label(db, claim)
        if label is None:
            continue
        if claim.id in seen:
            continue
        seen.add(claim.id)
        excerpt = (signal.content or "").strip().replace("\n", " ")
        if len(excerpt) > 280:
            excerpt = excerpt[:277].rstrip() + "..."
        discoveries.append(
            schemas.PublicDiscoveryOut(
                id=claim.id,
                source=signal.source,
                title=signal.title or claim.statement[:120],
                excerpt=excerpt,
                canonical_url=signal.canonical_url,
                retrieved_at=signal.retrieved_at,
                epistemic_state=label["epistemic_state"],
                stale=label["stale"],
                freshness="stale" if label["stale"] else "fresh",
            )
        )
    return discoveries


_MATCH_STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "your", "need", "someone"}


def _match_tokens(text: str) -> set[str]:
    words = []
    for raw in (text or "").lower().replace(",", " ").split():
        word = "".join(ch for ch in raw if ch.isalnum())
        if len(word) >= 4 and word not in _MATCH_STOP:
            words.append(word)
    return set(words)


def _match_for_need(db: Session, need: models.DomainRecord) -> schemas.PublicMatchOut:
    need_tokens = _match_tokens(f"{need.title} {need.detail}")
    candidates: list[schemas.PublicMatchCandidate] = []
    providers = _public_provider_query(db).all()
    for provider in providers:
        listings = [row for row in provider.listings if row.public_visible and row.is_active]
        listing_text = " ".join(f"{row.title} {row.description}" for row in listings)
        shared = need_tokens & _match_tokens(f"{provider.name} {provider.summary or ''} {listing_text}")
        same_city = bool(need.city and provider.city and need.city.strip().lower() == provider.city.strip().lower())
        if not shared and not same_city:
            continue
        primary = listings[0] if listings else None
        connection = _public_candidate_connection(db, need.id, "provider", provider.id)
        reasons = []
        if same_city:
            reasons.append("same city")
        if shared:
            reasons.append("shared words: " + ", ".join(sorted(shared)[:6]))
        unknowns = []
        if not (primary and primary.price_from):
            unknowns.append("price not stated")
        if not (primary and primary.availability_status):
            unknowns.append("availability not stated")
        unknowns.append("no completed outcome is tied to this provider")
        candidates.append(
            schemas.PublicMatchCandidate(
                kind="provider",
                id=provider.id,
                entity_type="provider",
                name=provider.name,
                where=provider.city,
                stated_price=f"{primary.price_from} {primary.currency or 'NPR'}" if primary and primary.price_from else None,
                stated_availability=primary.availability_status if primary else None,
                reasons=reasons,
                unknowns=unknowns,
                connection_id=connection.id if connection else None,
                latest_response=_public_connection_response(db, connection) if connection else None,
            )
        )
    others = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open", models.DomainRecord.id != need.id)
        .all()
    )
    for other in others:
        shared = need_tokens & _match_tokens(f"{other.title} {other.detail}")
        same_city = bool(need.city and other.city and need.city.strip().lower() == other.city.strip().lower())
        if not shared and not same_city:
            continue
        reasons = []
        if same_city:
            reasons.append("same city")
        if shared:
            reasons.append("shared words: " + ", ".join(sorted(shared)[:6]))
        unknowns = []
        if not other.stated_price:
            unknowns.append("price not stated")
        unknowns.append("no completed outcome is tied to this post")
        connection = _public_candidate_connection(db, need.id, "post", other.id)
        candidates.append(
            schemas.PublicMatchCandidate(
                kind="post",
                id=other.id,
                entity_type="domain_record",
                name=other.title,
                where=other.city,
                stated_price=other.stated_price,
                stated_availability=None,
                reasons=reasons,
                unknowns=unknowns,
                connection_id=connection.id if connection else None,
                latest_response=_public_connection_response(db, connection) if connection else None,
            )
        )
    knowledge = (
        db.query(models.Claim, models.Signal)
        .join(models.EvidenceRelationship, models.EvidenceRelationship.claim_id == models.Claim.id)
        .join(models.Evidence, models.Evidence.id == models.EvidenceRelationship.evidence_id)
        .join(models.Signal, models.Signal.id == models.Evidence.signal_id)
        .filter(models.Signal.canonical_url.isnot(None))
        .filter(models.Signal.is_duplicate_of.is_(None))
        .all()
    )
    seen_claims = set()
    for claim, signal in knowledge:
        label = public_epistemics.public_claim_label(db, claim)
        if label is None:
            continue
        if claim.id in seen_claims:
            continue
        shared = need_tokens & _match_tokens(f"{claim.statement} {signal.title or ''} {signal.content}")
        if not shared:
            continue
        seen_claims.add(claim.id)
        candidates.append(
            schemas.PublicMatchCandidate(
                kind="knowledge",
                id=claim.id,
                entity_type="claim",
                name=(signal.title or claim.statement)[:160],
                where=signal.source,
                stated_price=None,
                stated_availability=None,
                reasons=["shared words: " + ", ".join(sorted(shared)[:6]), f"from {signal.source}"],
                unknowns=[
                    f"epistemic state is {label['epistemic_state']}",
                    "evidence is stale" if label["stale"] else "evidence is not marked stale",
                    "not a verified counterparty",
                    "not a completed trade",
                ],
            )
        )
    need_unknowns = []
    if not need.city:
        need_unknowns.append("city not stated")
    if not need.stated_price:
        need_unknowns.append("price not stated")
    if not candidates:
        need_unknowns.append("no recorded counterparty")
    return schemas.PublicMatchOut(
        need_id=need.id,
        need_kind=need.kind,
        need_title=need.title,
        need_city=need.city,
        candidates=candidates,
        unknowns=need_unknowns,
    )


@router.get("/connections", response_model=list[schemas.PublicConnectionOut])
def list_public_connections(db: Session = Depends(get_db)):
    rows = (
        db.query(models.NetworkConnection)
        .filter(models.NetworkConnection.public_visible.is_(True))
        .order_by(models.NetworkConnection.id.desc())
        .all()
    )
    return [
        schemas.PublicConnectionOut(
            id=row.id,
            substrate_relation_id=row.relation_id,
            left_kind=row.left_kind,
            left_id=row.left_id,
            relation_type=_connection_graph_state(db, row)[0],
            right_kind=row.right_kind,
            right_id=row.right_id,
            state=row.state,
            epistemic_state=_connection_graph_state(db, row)[1],
            reason=row.reason,
            known=row.known,
            unknown=row.unknown,
            agreement_gap=row.agreement_gap,
            forge_role="introducer",
            owns_either_side=False,
            latest_response=_public_connection_response(db, row),
            latest_fulfillment=_public_connection_fulfillment(db, row),
        )
        for row in rows
    ]


def _public_connection_response(db: Session, row: models.NetworkConnection) -> str | None:
    if not row.public_visible:
        return None
    outcome = (
        db.query(models.Outcome)
        .filter(models.Outcome.notes.like(f"idempotency:network-connection:{row.id}:response:%"))
        .order_by(models.Outcome.id.desc())
        .first()
    )
    return outcome.qualitative_result if outcome else None


def _public_candidate_connection(
    db: Session, record_id: int, right_kind: str, right_id: int
) -> models.NetworkConnection | None:
    from app.services import network_connections

    row = network_connections.find_connection(db, "domain_record", record_id, right_kind, right_id)
    return row if row is not None and row.public_visible else None


def _connection_graph_state(db: Session, row: models.NetworkConnection) -> tuple[str, str]:
    return row.relation_type or "possible_match", row.epistemic_state or "hypothesized"


@router.post("/domain/{record_id}/connections/{connection_id}/response", response_model=schemas.PublicConnectionOut)
def record_public_connection_response(
    record_id: int,
    connection_id: int,
    body: schemas.PublicConnectionResponseCreate,
    db: Session = Depends(get_db),
):
    row = db.query(models.DomainRecord).filter_by(id=record_id).first()
    if row is None:
        raise HTTPException(404, "record not found")
    digest = hashlib.sha256(body.close_token.encode()).hexdigest()
    if not hmac.compare_digest(digest, row.close_token_hash):
        raise HTTPException(403, "close token does not match")
    connection = (
        db.query(models.NetworkConnection)
        .filter_by(id=connection_id, public_visible=True)
        .first()
    )
    if connection is None or not (
        connection.left_kind == "domain_record" and connection.left_id == record_id
        or connection.right_kind == "domain_record" and connection.right_id == record_id
    ):
        raise HTTPException(404, "connection not found for this record")
    if connection.state not in {"proposed", "authorized", "contacted"}:
        raise HTTPException(409, "a response is only recorded before acceptance")
    from app.services import network_connections
    try:
        network_connections.record_response(db, connection, body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    relation_type, epistemic_state = _connection_graph_state(db, connection)
    return schemas.PublicConnectionOut(
        id=connection.id,
        substrate_relation_id=connection.relation_id,
        left_kind=connection.left_kind,
        left_id=connection.left_id,
        relation_type=relation_type,
        right_kind=connection.right_kind,
        right_id=connection.right_id,
        state=connection.state,
        epistemic_state=epistemic_state,
        reason=connection.reason,
        known=connection.known,
        unknown=connection.unknown,
        agreement_gap=connection.agreement_gap,
        latest_response=_public_connection_response(db, connection),
        latest_fulfillment=_public_connection_fulfillment(db, connection),
    )


def _public_connection_fulfillment(db: Session, row: models.NetworkConnection) -> str | None:
    if not row.public_visible:
        return None
    outcome = (
        db.query(models.Outcome)
        .filter(models.Outcome.notes == f"idempotency:network-connection:{row.id}:fulfilled")
        .first()
    )
    return outcome.qualitative_result if outcome else None


def _payment_rows(db: Session, connections: list[models.NetworkConnection]) -> dict[str, list[schemas.RecordedPaymentOut]]:
    buckets = {"REPORTED": [], "VERIFIED": [], "DISPUTED": [], "SETTLED": []}
    for connection in connections:
        outcome = (
            db.query(models.Outcome)
            .filter(models.Outcome.notes == f"idempotency:network-connection:{connection.id}:paid")
            .first()
        )
        if outcome is None or outcome.actual_value is None:
            continue
        item = schemas.RecordedPaymentOut(
            connection_id=connection.id,
            amount=outcome.actual_value,
            unit=outcome.unit or "NPR",
            verification=outcome.verification_state,
        )
        buckets.get(outcome.verification_state, buckets["REPORTED"]).append(item)
    return buckets


@router.get("/trust/{subject_kind}/{subject_id}", response_model=schemas.PublicTrustOut)
def public_trust(subject_kind: str, subject_id: int, db: Session = Depends(get_db)):
    if subject_kind == "provider":
        provider = _public_provider_query(db).filter(models.Provider.id == subject_id).first()
        if provider is None:
            raise HTTPException(404, "provider not found or not publicly verified")
        requests = (
            db.query(models.Outcome)
            .filter(models.Outcome.source == "booking_request")
            .filter(models.Outcome.qualitative_result.like(f"%provider {subject_id}.%"))
            .count()
        )
        connections = (
            db.query(models.NetworkConnection)
            .filter(
                ((models.NetworkConnection.left_kind == "provider") & (models.NetworkConnection.left_id == subject_id))
                | ((models.NetworkConnection.right_kind == "provider") & (models.NetworkConnection.right_id == subject_id))
            )
            .all()
        )
        payments = _payment_rows(db, connections)
        reported, verified = payments["REPORTED"], payments["VERIFIED"]
        unknowns = []
        if not any(payments.values()):
            unknowns.append("no payment recorded")
        if requests == 0:
            unknowns.append("no booking request recorded")
        return schemas.PublicTrustOut(
            subject_kind="provider",
            subject_id=subject_id,
            recorded_requests=requests,
            reported_payments=reported,
            verified_payments=verified,
            disputed_payments=payments["DISPUTED"],
            settled_payments=payments["SETTLED"],
            disputes=len(payments["DISPUTED"]),
            unknowns=unknowns,
        )
    if subject_kind == "domain_record":
        row = db.query(models.DomainRecord).filter_by(id=subject_id).first()
        if row is None:
            raise HTTPException(404, "record not found")
        events = domain_record_events(subject_id, db)
        connections = (
            db.query(models.NetworkConnection)
            .filter_by(left_kind="domain_record", left_id=subject_id)
            .all()
        )
        payments = _payment_rows(db, connections)
        return schemas.PublicTrustOut(
            subject_kind="domain_record",
            subject_id=subject_id,
            recorded_requests=0,
            reported_payments=payments["REPORTED"],
            verified_payments=payments["VERIFIED"],
            disputed_payments=payments["DISPUTED"],
            settled_payments=payments["SETTLED"],
            disputes=len(events.disputes),
            unknowns=events.unknowns,
        )
    raise HTTPException(404, "unknown subject")


@router.get("/revenue-miner", response_model=schemas.PublicRevenueMinerOut)
def public_revenue_miner(db: Session = Depends(get_db)):
    """Recorded paid-offer counts. No customer, price, or income claim."""
    from app.services.revenue_miner import revenue_miner_public_summary

    return schemas.PublicRevenueMinerOut(**revenue_miner_public_summary(db))


@router.get("/alerts", response_model=list[schemas.PublicAlertOut])
def list_public_alerts(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db)):
    """Recorded changes only. No alert is created unless an outcome already exists."""
    rows = (
        db.query(models.Outcome)
        .filter(models.Outcome.source.in_(["domain_record", "booking_request", "network_connection"]))
        .order_by(models.Outcome.id.desc())
        .limit(limit)
        .all()
    )
    return [
        schemas.PublicAlertOut(
            id=row.id,
            source=row.source,
            text=row.qualitative_result or "",
            created_at=row.observed_at,
        )
        for row in rows
        if row.qualitative_result
    ]


@router.get("/matches", response_model=list[schemas.PublicMatchOut])
def list_public_matches(db: Session = Depends(get_db)):
    needs = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open")
        .order_by(models.DomainRecord.created_at.desc())
        .all()
    )
    return [_match_for_need(db, need) for need in needs]


_TERM_KEYS = (
    "requested",
    "who_can_submit",
    "success",
    "evidence_required",
    "ownership",
    "payment_due",
    "partial",
    "rejection",
    "resale",
    "costs",
)


def terms_complete(raw: str | None) -> bool:
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    amount = data.get("amount_npr")
    if not isinstance(amount, int) or amount < 0:
        return False
    return all(str(data.get(key) or "").strip() for key in _TERM_KEYS)


def _domain_out(row: models.DomainRecord) -> schemas.DomainRecordOut:
    base = schemas.DomainRecordOut.model_validate(row)
    return base.model_copy(update={"terms_complete": terms_complete(row.terms)})


@router.get("/domain", response_model=list[schemas.DomainRecordOut])
def list_domain_records(
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.DomainRecord).filter(models.DomainRecord.status == "open")
    if kind and kind.strip().lower() != "all":
        query = query.filter(models.DomainRecord.kind == kind.strip().lower())
    if city and city.strip():
        query = query.filter(models.DomainRecord.city.ilike(_like(city)))
    if q and q.strip():
        like = _like(q)
        query = query.filter(
            or_(
                models.DomainRecord.title.ilike(like),
                models.DomainRecord.detail.ilike(like),
                models.DomainRecord.city.ilike(like),
            )
        )
    return [_domain_out(row) for row in query.order_by(models.DomainRecord.created_at.desc()).all()]


@router.post("/domain", response_model=schemas.DomainRecordCreated)
def create_domain_record(body: schemas.DomainRecordCreate, db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(24)
    row = models.DomainRecord(
        kind=body.kind,
        title=body.title.strip(),
        detail=body.detail.strip(),
        city=(body.city or "").strip() or None,
        stated_price=(body.stated_price or "").strip() or None,
        terms=json.dumps(body.terms) if body.terms else None,
        status="open",
        close_token_hash=hashlib.sha256(token.encode()).hexdigest(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    from app.services import action_engine
    action_engine.record_domain_event(
        db,
        idempotency_key=f"domain-record:{row.id}:open",
        source="domain_record",
        qualitative_result=(
            f"Domain {row.kind} {row.id} opened: {row.title}. "
            "This is a post in our records, not a completed trade or a payment."
        ),
    )
    created = schemas.DomainRecordOut.model_validate(row)
    return schemas.DomainRecordCreated(**created.model_dump(), close_token=token)


@router.post("/domain/{record_id}/close", response_model=schemas.DomainRecordOut)
def close_domain_record(record_id: int, body: schemas.DomainRecordClose, db: Session = Depends(get_db)):
    row = db.query(models.DomainRecord).filter_by(id=record_id).first()
    if row is None:
        raise HTTPException(404, "record not found")
    if row.status != "open":
        raise HTTPException(409, "record is already closed")
    digest = hashlib.sha256(body.close_token.encode()).hexdigest()
    if not hmac.compare_digest(digest, row.close_token_hash):
        raise HTTPException(403, "close token does not match")
    if body.result == "paid" and body.amount_npr is None:
        raise HTTPException(422, "a paid close needs the amount actually received")
    if body.result == "paid" and body.amount_npr is not None and body.amount_npr < 0:
        raise HTTPException(422, "amount cannot be negative")
    row.status = "closed"
    row.close_result = body.result
    row.close_note = body.note.strip()
    row.closed_at = models.utcnow()
    db.commit()
    db.refresh(row)
    from app.services import action_engine
    paid = body.result == "paid"
    action_engine.record_domain_event(
        db,
        idempotency_key=f"domain-record:{row.id}:close",
        source="domain_record",
        success=True if paid else (False if body.result == "withdrawn" else None),
        actual_value=float(body.amount_npr) if paid else None,
        unit="NPR" if paid else None,
        qualitative_result=(
            f"Domain {row.kind} {row.id} closed as {body.result}. Note: {row.close_note}"
        ),
    )
    return _domain_out(row)


def _domain_outcomes(db: Session, record_id: int) -> list[models.Outcome]:
    prefix = f"idempotency:domain-record:{record_id}:"
    return (
        db.query(models.Outcome)
        .filter(models.Outcome.source == "domain_record")
        .filter(models.Outcome.notes.like(f"{prefix}%"))
        .order_by(models.Outcome.id.asc())
        .all()
    )


@router.get("/domain/{record_id}/events", response_model=schemas.DomainRecordEventsOut)
def domain_record_events(record_id: int, db: Session = Depends(get_db)):
    row = db.query(models.DomainRecord).filter_by(id=record_id).first()
    if row is None:
        raise HTTPException(404, "record not found")
    payments = []
    disputes = []
    completions = 0
    for outcome in _domain_outcomes(db, record_id):
        text = outcome.qualitative_result or ""
        if ":close" in (outcome.notes or "") and row.close_result == "paid" and outcome.success is True:
            payments.append(f"{text} Amount recorded: {outcome.actual_value} {outcome.unit or 'NPR'}.")
        elif ":dispute" in (outcome.notes or ""):
            disputes.append(text)
        elif ":close" in (outcome.notes or "") and row.close_result == "completed":
            completions += 1
    unknowns = []
    if not payments:
        unknowns.append("no payment recorded")
    if not disputes:
        unknowns.append("no dispute recorded")
    return schemas.DomainRecordEventsOut(
        record_id=record_id,
        payments=payments,
        disputes=disputes,
        completions=completions,
        unknowns=unknowns,
    )


@router.post("/domain/{record_id}/dispute", response_model=schemas.DomainRecordEventsOut)
def dispute_domain_record(record_id: int, body: schemas.DomainDisputeCreate, db: Session = Depends(get_db)):
    row = db.query(models.DomainRecord).filter_by(id=record_id).first()
    if row is None:
        raise HTTPException(404, "record not found")
    digest = hashlib.sha256(body.close_token.encode()).hexdigest()
    if not hmac.compare_digest(digest, row.close_token_hash):
        raise HTTPException(403, "close token does not match")
    from app.services import action_engine
    action_engine.record_domain_event(
        db,
        idempotency_key=f"domain-record:{row.id}:dispute",
        source="domain_record",
        success=None,
        qualitative_result=(
            f"Domain {row.kind} {row.id} has a dispute. No winner is recorded. Note: {body.note.strip()}"
        ),
    )
    return domain_record_events(record_id, db)


@router.post("/booking-requests", response_model=schemas.BookingRequestOut)
def create_booking_request(body: schemas.BookingRequestCreate, db: Session = Depends(get_db)):
    provider = (
        _public_provider_query(db)
        .filter(models.Provider.id == body.provider_id)
        .first()
    )
    if provider is None:
        raise HTTPException(404, "provider not found or not publicly verified")

    listing = None
    if body.service_listing_id is not None:
        listing = (
            _public_service_query(db)
            .filter(models.ServiceListing.id == body.service_listing_id)
            .filter(models.ServiceListing.provider_id == provider.id)
            .first()
        )
        if listing is None:
            raise HTTPException(404, "service listing not found for this verified provider")

    request = models.BookingRequest(
        provider_id=provider.id,
        service_listing_id=listing.id if listing else None,
        requester_name=body.requester_name,
        requester_phone=body.requester_phone,
        requester_email=body.requester_email,
        requested_service=body.requested_service,
        requested_date=body.requested_date,
        requested_time=body.requested_time,
        notes=body.notes,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    from app.services import action_engine
    action_engine.record_domain_event(
        db,
        idempotency_key=f"booking-request:{request.id}",
        source="booking_request",
        qualitative_result=(
            f"Booking request {request.id} stored for provider {request.provider_id}. "
            "Status is pending. This is not acceptance and not payment."
        ),
    )
    return request


@router.get("/booking-requests/{booking_id}", response_model=schemas.BookingRequestStatusOut)
def get_booking_request(booking_id: int, db: Session = Depends(get_db)):
    row = db.query(models.BookingRequest).filter_by(id=booking_id).first()
    if row is None:
        raise HTTPException(404, "booking request not found")

    return schemas.BookingRequestStatusOut(
        id=row.id,
        provider_id=row.provider_id,
        provider_name=row.provider.name if row.provider else None,
        service_listing_id=row.service_listing_id,
        requested_service=row.requested_service,
        requested_date=row.requested_date,
        requested_time=row.requested_time,
        status=row.status,
        provider_response=row.provider_response,
        created_at=row.created_at,
        updated_at=row.updated_at,
        accepted_at=row.accepted_at,
    )
