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
    from app.services.public_feed import sanitize_public_text

    claims_by_id = {claim.id: claim for claim, _signal in rows}
    claim_labels = public_epistemics.public_claim_labels(db, list(claims_by_id.values()))
    discoveries = []
    seen = set()
    for claim, signal in rows:
        label = public_epistemics.public_claim_label(db, claim)
        if label is None:
            continue
        if claim.id in seen:
            continue
        seen.add(claim.id)
        excerpt = sanitize_public_text((signal.content or "").strip().replace("\n", " ")) or ""
        if len(excerpt) > 280:
            excerpt = excerpt[:277].rstrip() + "..."
        # Section 6: classify relevance honestly
        # Bibliographic sources without real-world linkage are background observations
        is_bibliographic = (signal.source or "").lower() in {"crossref", "openalex", "world_bank", "gdelt", "govinfo"}
        has_consequence = bool(
            claim.decision_id or claim.experiment_id or claim.outcome_id
        )
        if has_consequence:
            relevance_status = "validated_finding"
        elif is_bibliographic:
            relevance_status = "background_observation"
        else:
            relevance_status = "unqualified_lead"
        discoveries.append(
            schemas.PublicDiscoveryOut(
                id=claim.id,
                source=signal.source,
                title=sanitize_public_text(signal.title or claim.statement[:120]) or "",
                excerpt=excerpt,
                canonical_url=signal.canonical_url,
                retrieved_at=signal.retrieved_at,
                epistemic_state=label["epistemic_state"],
                stale=label["stale"],
                freshness="stale" if label["stale"] else "fresh",
                has_consequence=has_consequence,
                relevance_status=relevance_status,
                linked_unknown=None,  # TODO: link to defined Hami unknown when available
                next_test=None,  # TODO: populate from research plan when defined
            )
        )
    return discoveries


def _consume_public_write_limit(
    db: Session,
    request: Request,
    scope: str,
    limit: int,
) -> None:
    if not forge_bot_privacy.consume_rate_limited_request(
        db,
        request,
        hmac_key=settings.FORGE_BOT_CONTACT_HMAC_KEY,
        scope=scope,
        limit=limit,
    ):
        raise HTTPException(
            status_code=429,
            detail=f"Hourly limit reached: no more than {limit} requests per visitor per hour.",
        )


def _booking_status_signing_key() -> str:
    """Fail closed before a booking write if a secure status capability cannot be issued."""
    key = settings.FORGE_BOT_CONTACT_HMAC_KEY
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Secure booking status is unavailable until its signing key is configured.",
        )
    return key


def _booking_status_token(booking_id: int) -> str:
    """Create a non-enumerable public status capability without storing another secret or table."""
    key = _booking_status_signing_key()
    message = f"hami-public-booking-status:v1:{booking_id}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _match_tokens(text: str) -> set[str]:
    """Shared Unicode-aware terms for the public need/provider matching path."""
    return tokenize_match_terms(text)


def _public_matching_catalog(db: Session):
    """Load shared matching records and connection/response projections once."""
    providers = (
        _public_provider_query(db)
        .options(selectinload(models.Provider.listings))
        .all()
    )
    other_records = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open")
        .all()
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
    claims_by_id = {claim.id: claim for claim, _signal in knowledge}
    claim_labels = public_epistemics.public_claim_labels(db, list(claims_by_id.values()))

    # Keep newest row by exact endpoint key; visibility is checked only after
    # selecting it, so a newer private row masks older public history.
    record_ids = {row.id for row in other_records}
    connections_by_key: dict[tuple[str, int, str, int], models.NetworkConnection] = {}
    live_connection_need_ids: set[int] = set()
    if record_ids:
        connection_rows = (
            db.query(models.NetworkConnection)
            .filter(models.NetworkConnection.left_kind == "domain_record")
            .filter(models.NetworkConnection.left_id.in_(record_ids))
            .order_by(models.NetworkConnection.id.desc())
            .all()
        )
        for row in connection_rows:
            if row.state != "failed":
                live_connection_need_ids.add(row.left_id)
            connections_by_key.setdefault(
                (row.left_kind, row.left_id, row.right_kind, row.right_id), row
            )

    visible_latest_ids = {row.id for row in connections_by_key.values() if row.public_visible}
    response_connection_ids: set[int] = set()
    if visible_latest_ids:
        notes_rows = (
            db.query(models.Outcome.notes)
            .filter(models.Outcome.notes.like("idempotency:network-connection:%:response:%"))
            .all()
        )
        for (notes,) in notes_rows:
            if not isinstance(notes, str):
                continue
            parts = notes.split(":")
            if len(parts) < 5 or parts[:2] != ["idempotency", "network-connection"] or parts[3] != "response":
                continue
            try:
                connection_id = int(parts[2])
            except (TypeError, ValueError):
                continue
            if connection_id in visible_latest_ids:
                response_connection_ids.add(connection_id)

    return {
        "providers": providers,
        "other_records": other_records,
        "knowledge": knowledge,
        "claim_labels": claim_labels,
        "connections_by_key": connections_by_key,
        "live_connection_need_ids": live_connection_need_ids,
        "response_connection_ids": response_connection_ids,
    }

def _match_for_need(db: Session, need: models.DomainRecord, *, matching_catalog=None) -> schemas.PublicMatchOut:
    from app.services.public_feed import sanitize_public_text

    need_title = sanitize_public_text(need.title) or ""
    need_detail = sanitize_public_text(need.detail) or ""
    need_city = sanitize_public_text(need.city)
    need_tokens = _match_tokens(f"{need_title} {need_detail}")
    if matching_catalog is None:
        matching_catalog = _public_matching_catalog(db)
    providers = matching_catalog["providers"]
    other_records = matching_catalog["other_records"]
    knowledge = matching_catalog["knowledge"]
    claim_labels = matching_catalog["claim_labels"]
    candidates: list[schemas.PublicMatchCandidate] = []
    match_terms_by_candidate: dict[tuple[str, int], set[str]] = {}
    same_city_by_candidate: dict[tuple[str, int], bool] = {}
    for provider in providers:
        provider_name = sanitize_public_text(provider.name) or ""
        provider_summary = sanitize_public_text(provider.summary) or ""
        provider_city = sanitize_public_text(provider.city)
        listings = [row for row in provider.listings if row.public_visible and row.is_active]
        listing_text = " ".join(
            f"{sanitize_public_text(row.title) or ''} {sanitize_public_text(row.description) or ''}"
            for row in listings
        )
        shared = need_tokens & _match_tokens(f"{provider_name} {provider_summary} {listing_text}")
        same_city = bool(need_city and provider_city and need_city.strip().lower() == provider_city.strip().lower())
        if not shared and not same_city:
            continue
        primary = listings[0] if listings else None
        connection = _public_candidate_connection(
            db, need.id, "provider", provider.id, matching_catalog=matching_catalog
        )
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
                name=provider_name,
                where=provider_city,
                stated_price=(
                    sanitize_public_text(f"{primary.price_from} {primary.currency or 'NPR'}")
                    if primary and primary.price_from else None
                ),
                stated_availability=primary.availability_status if primary else None,
                reasons=reasons,
                unknowns=unknowns,
                connection_id=connection.id if connection else None,
                latest_response=(
                    _public_connection_response(
                        db, connection,
                        response_connection_ids=matching_catalog["response_connection_ids"],
                    ) if connection else None
                ),
            )
        )
        match_key = ("provider", provider.id)
        match_terms_by_candidate[match_key] = set(shared)
        same_city_by_candidate[match_key] = same_city
    for other in other_records:
        if other.id == need.id:
            continue
        other_title = sanitize_public_text(other.title) or ""
        other_detail = sanitize_public_text(other.detail) or ""
        other_city = sanitize_public_text(other.city)
        shared = need_tokens & _match_tokens(f"{other_title} {other_detail}")
        same_city = bool(need_city and other_city and need_city.strip().lower() == other_city.strip().lower())
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
        connection = _public_candidate_connection(
            db, need.id, "post", other.id, matching_catalog=matching_catalog
        )
        candidates.append(
            schemas.PublicMatchCandidate(
                kind="post",
                id=other.id,
                entity_type="domain_record",
                name=other_title,
                where=other_city,
                stated_price=sanitize_public_text(other.stated_price),
                stated_availability=None,
                reasons=reasons,
                unknowns=unknowns,
                connection_id=connection.id if connection else None,
                latest_response=(
                    _public_connection_response(
                        db, connection,
                        response_connection_ids=matching_catalog["response_connection_ids"],
                    ) if connection else None
                ),
            )
        )
        match_key = ("post", other.id)
        match_terms_by_candidate[match_key] = set(shared)
        same_city_by_candidate[match_key] = same_city
    seen_claims = set()
    for claim, signal in knowledge:
        label = claim_labels.get(claim.id)
        if label is None:
            continue
        if claim.id in seen_claims:
            continue
        claim_statement = sanitize_public_text(claim.statement) or ""
        signal_title = sanitize_public_text(signal.title) or ""
        signal_content = sanitize_public_text(signal.content) or ""
        shared = need_tokens & _match_tokens(f"{claim_statement} {signal_title} {signal_content}")
        if not shared:
            continue
        seen_claims.add(claim.id)
        candidates.append(
            schemas.PublicMatchCandidate(
                kind="knowledge",
                id=claim.id,
                entity_type="claim",
                name=sanitize_public_text(signal.title or claim.statement)[:160] if sanitize_public_text(signal.title or claim.statement) else "",
                where=sanitize_public_text(signal.source) or "",
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
        match_key = ("knowledge", claim.id)
        match_terms_by_candidate[match_key] = set(shared)
        same_city_by_candidate[match_key] = False
    # Rank only candidates that already passed the existing public/epistemic
    # eligibility gates. Query-local IDF rewards distinctive overlap; it remains
    # lexical triage, not semantic relevance, availability, or proof.
    matched_document_count = sum(bool(terms) for terms in match_terms_by_candidate.values())
    document_frequency: dict[str, int] = {}
    for matched_terms in match_terms_by_candidate.values():
        for term in matched_terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1
    term_weights = {
        term: math.log(
            (matched_document_count + 1) / (document_frequency.get(term, 0) + 1)
        ) + 1.0
        for term in need_tokens
    }
    total_weight = sum(term_weights.values())

    def candidate_rank(candidate: schemas.PublicMatchCandidate) -> tuple[float, ...]:
        match_key = (candidate.kind, candidate.id)
        shared_terms = match_terms_by_candidate.get(match_key, set())
        weighted_overlap = (
            sum(term_weights[term] for term in shared_terms) / total_weight
            if total_weight else 0.0
        )
        term_coverage = len(shared_terms) / len(need_tokens) if need_tokens else 0.0
        # Prefer textual overlap to a city-only candidate; exact city is a
        # tie-breaker, never a substitute for a stronger lexical match.
        kind_priority = {"provider": 0, "post": 1, "knowledge": 2}.get(candidate.kind, 3)
        return (
            -float(bool(shared_terms)),
            -weighted_overlap,
            -term_coverage,
            -float(same_city_by_candidate.get(match_key, False)),
            float(kind_priority),
            float(candidate.id),
        )

    candidates.sort(key=candidate_rank)
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
        need_title=need_title,
        need_city=need_city,
        candidates=candidates,
        unknowns=need_unknowns,
    )


@router.get("/connections", response_model=list[schemas.PublicConnectionOut])
def list_public_connections(db: Session = Depends(get_db)):
    from app.services.network_substrate_adapter import relation_read_model
    from app.services.public_feed import build_public_feed, sanitize_public_text

    # The Feed owns the public endpoint gate. Reuse its traversal result so a
    # visible connection row cannot make a private or dangling endpoint public.
    visible_ids = {
        item.entity_id for item in build_public_feed(db, kind="connection", limit=1000)
    }
    if not visible_ids:
        return []
    rows = (
        db.query(models.NetworkConnection)
        .filter(models.NetworkConnection.public_visible.is_(True))
        .filter(models.NetworkConnection.id.in_(visible_ids))
        .order_by(models.NetworkConnection.id.desc())
        .all()
    )
    result = []
    for row in rows:
        graph = relation_read_model(db, row)
        result.append(schemas.PublicConnectionOut(
            id=row.id,
            **graph,
            left_kind=row.left_kind,
            left_id=row.left_id,
            right_kind=row.right_kind,
            right_id=row.right_id,
            state=row.state,
            reason=sanitize_public_text(row.reason) or "",
            known=sanitize_public_text(row.known),
            unknown=sanitize_public_text(row.unknown),
            agreement_gap=sanitize_public_text(row.agreement_gap) or "",
            forge_role="introducer",
            owns_either_side=False,
            latest_response=_public_connection_response(db, row),
            latest_fulfillment=_public_connection_fulfillment(db, row),
        ))
    return result


@router.get("/network", response_model=schemas.PublicNetworkSnapshot)
def get_public_network(
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Read the public Network from substrate graph rows and registered adapters."""
    from app.services.public_network import build_public_network

    return build_public_network(db, limit=limit)


def _public_connection_response(
    db: Session,
    row: models.NetworkConnection,
    *,
    response_connection_ids: set[int] | None = None,
) -> str | None:
    if not row.public_visible:
        return None
    if response_connection_ids is None:
        outcome = (
            db.query(models.Outcome)
            .filter(models.Outcome.notes.like(f"idempotency:network-connection:{row.id}:response:%"))
            .order_by(models.Outcome.id.desc())
            .first()
        )
        has_response = outcome is not None
    else:
        has_response = row.id in response_connection_ids
    return "A response was recorded. It is not acceptance, fulfillment, or payment." if has_response else None


def _public_candidate_connection(
    db: Session,
    record_id: int,
    right_kind: str,
    right_id: int,
    *,
    matching_catalog: dict | None = None,
) -> models.NetworkConnection | None:
    from app.services import network_connections

    if matching_catalog is None:
        row = network_connections.find_connection(db, "domain_record", record_id, right_kind, right_id)
    else:
        right_type = network_connections.canonical_endpoint_type(right_kind)
        row = matching_catalog["connections_by_key"].get(
            ("domain_record", record_id, right_type, right_id)
        )
    # Never fall back to an older public row after a newer private row.
    return row if row is not None and row.public_visible else None


def _connection_graph_state(db: Session, row: models.NetworkConnection) -> tuple[str, str]:
    from app.services.network_substrate_adapter import relation_read_model

    graph = relation_read_model(db, row)
    return graph["relation_type"], graph["epistemic_state"]


@router.post("/domain/{record_id}/connections/{connection_id}/response", response_model=schemas.PublicConnectionOut)
def record_public_connection_response(
    record_id: int,
    connection_id: int,
    body: schemas.PublicConnectionResponseCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _consume_public_write_limit(db, request, "public-domain-control", 20)
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
    from app.services.public_feed import sanitize_public_text

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
        reason=sanitize_public_text(connection.reason) or "",
        known=sanitize_public_text(connection.known),
        unknown=sanitize_public_text(connection.unknown),
        agreement_gap=sanitize_public_text(connection.agreement_gap) or "",
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
    return "Work was recorded as fulfilled. This is not a payment." if outcome else None


def _payment_rows(db: Session, connections: list[models.NetworkConnection]) -> dict[str, list[schemas.RecordedPaymentOut]]:
    from app.services import network_connections

    buckets = {"REPORTED": [], "VERIFIED": [], "DISPUTED": [], "SETTLED": []}
    for connection in connections:
        outcome = (
            db.query(models.Outcome)
            .filter(models.Outcome.notes == f"idempotency:network-connection:{connection.id}:paid")
            .first()
        )
        if outcome is None or outcome.actual_value is None:
            continue
        verification = outcome.verification_state
        if verification == "VERIFIED" and not (
            outcome.data_scope == "REAL"
            and outcome.source_kind == evidence_source.REAL
            and network_connections.has_independent_payment_evidence(
                db, connection.id, outcome.id
            )
        ):
            verification = "REPORTED"
        elif verification == "SETTLED" and not (
            outcome.data_scope == "REAL"
            and outcome.source_kind == evidence_source.REAL
            and network_connections.has_independent_payment_evidence(
                db,
                connection.id,
                outcome.id,
                relation_type="updates",
            )
        ):
            verification = "REPORTED"
        item = schemas.RecordedPaymentOut(
            connection_id=connection.id,
            amount=outcome.actual_value,
            unit=outcome.unit or "NPR",
            verification=verification,
        )
        buckets.get(verification, buckets["REPORTED"]).append(item)
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


@router.get("/runtime-summary", response_model=schemas.PublicRuntimeSummary)
def public_runtime_summary(db: Session = Depends(get_db)):
    """Expose aggregate operational state only; owner task/action details stay private."""
    from app.services import truth_audit

    truth = truth_audit.snapshot(db)
    operations = truth["operations"]
    epistemic = truth["epistemic_labels"]
    running_cycles = int(operations["running_cycles"])
    queued_tasks = int(operations["queued_tasks"])
    last_completed = (
        db.query(models.CycleRun.ended_at)
        .filter(
            models.CycleRun.status == "COMPLETED",
            models.CycleRun.ended_at.isnot(None),
        )
        .order_by(models.CycleRun.ended_at.desc())
        .first()
    )
    active_stage = (
        "cycle_running"
        if running_cycles
        else "tasks_queued"
        if queued_tasks
        else "idle"
    )
    return schemas.PublicRuntimeSummary(
        active_stage=active_stage,
        pending_actions=int(operations["pending_actions"]),
        queued_tasks=queued_tasks,
        running_cycles=running_cycles,
        human_validated_problems=int(epistemic["human_validated_problems"]),
        last_completed_at=last_completed[0] if last_completed else None,
    )


@router.get("/alerts", response_model=list[schemas.PublicAlertOut])
def list_public_alerts(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db)):
    """Public alert summaries reuse the canonical visibility/provenance-safe outcome projection."""
    from app.services.public_feed import build_public_feed

    outcomes = build_public_feed(db, limit=limit, kind="outcome")
    return [
        schemas.PublicAlertOut(
            id=item.entity_id,
            source=item.source,
            text=item.summary,
            classification="DERIVED",
            created_at=item.occurred_at,
        )
        for item in outcomes
    ]


@router.get("/matches", response_model=list[schemas.PublicMatchOut])
def list_public_matches(db: Session = Depends(get_db)):
    needs = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open")
        .order_by(models.DomainRecord.created_at.desc())
        .all()
    )
    if not needs:
        return []
    matching_catalog = _public_matching_catalog(db)
    return [
        _match_for_need(db, need, matching_catalog=matching_catalog)
        for need in needs
    ]


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


def _public_domain_text(value: str | None, *, max_length: int) -> str | None:
    from app.services.public_feed import sanitize_public_text

    safe = sanitize_public_text(value)
    if safe is None:
        return None
    if len(safe) <= max_length:
        return safe
    return safe[: max_length - 1].rstrip() + "…"


def _public_domain_terms(raw: str | None) -> tuple[dict[str, str | int] | None, bool]:
    """Whitelist and sanitize persisted terms once for reads and acceptance.

    Old rows can predate current field/amount limits, so malformed or oversized
    terms are omitted rather than allowed to break a public list response.
    Redacted required terms remain visible as redactions but cannot satisfy the
    acceptance contract.
    """
    if not raw:
        return None, False
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None, False
    if not isinstance(data, dict):
        return None, False

    projected: dict[str, str | int] = {}
    amount = data.get("amount_npr")
    valid_amount = (
        isinstance(amount, int)
        and not isinstance(amount, bool)
        and 0 <= amount <= 1_000_000_000_000
    )
    if valid_amount:
        projected["amount_npr"] = amount

    from app.services.public_feed import sanitize_public_text

    for key in _TERM_KEYS:
        value = data.get(key)
        if not isinstance(value, str):
            continue
        raw_value = value.strip()
        if not raw_value or len(raw_value) > 1000:
            continue
        safe_value = (sanitize_public_text(raw_value) or "").strip()
        if safe_value and len(safe_value) <= 1000:
            projected[key] = safe_value

    complete = valid_amount and all(
        key in projected
        and "[redacted-email]" not in str(projected[key]).lower()
        and "[redacted-phone]" not in str(projected[key]).lower()
        for key in _TERM_KEYS
    )
    return (projected or None), complete


def terms_complete(raw: str | None) -> bool:
    """A contract is complete only when all bounded, public-safe fields survive."""
    return _public_domain_terms(raw)[1]


def _domain_out(row: models.DomainRecord) -> schemas.DomainRecordOut:
    public_terms_data, contract_complete = _public_domain_terms(row.terms)
    public_terms = (
        schemas.DomainTerms.model_validate(public_terms_data)
        if public_terms_data is not None
        else None
    )
    return schemas.DomainRecordOut(
        id=row.id,
        kind=row.kind,
        title=_public_domain_text(row.title, max_length=160) or "",
        detail=_public_domain_text(row.detail, max_length=5000) or "",
        city=_public_domain_text(row.city, max_length=100),
        stated_price=_public_domain_text(row.stated_price, max_length=120),
        status=row.status,
        terms_complete=contract_complete,
        terms=public_terms,
        created_at=row.created_at,
    )


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
def create_domain_record(
    body: schemas.DomainRecordCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _consume_public_write_limit(db, request, "public-domain-post", 5)
    from app.services.public_feed import sanitize_public_text

    title = sanitize_public_text(body.title.strip()) or ""
    detail = sanitize_public_text(body.detail.strip()) or ""
    city = sanitize_public_text((body.city or "").strip()) or None
    if not title.strip() or not detail.strip():
        raise HTTPException(
            status_code=422,
            detail="title and detail must contain text after contact-detail redaction.",
        )
    submitted_terms = (
        json.dumps(body.terms.model_dump(exclude_none=True), ensure_ascii=False)
        if body.terms
        else None
    )
    safe_terms, _ = _public_domain_terms(submitted_terms)
    token = secrets.token_urlsafe(24)
    row = models.DomainRecord(
        kind=body.kind,
        title=title,
        detail=detail,
        city=city,
        stated_price=sanitize_public_text((body.stated_price or "").strip()) or None,
        terms=json.dumps(safe_terms, ensure_ascii=False, sort_keys=True) if safe_terms else None,
        status="open",
        close_token_hash=hashlib.sha256(token.encode()).hexdigest(),
    )
    db.add(row)
    db.flush()
    from app.services import action_engine

    try:
        action_engine.record_domain_event(
            db,
            idempotency_key=f"domain-record:{row.id}:open",
            source="domain_record",
            qualitative_result=(
                f"Domain {row.kind} {row.id} opened: {row.title}. "
                "This is a post in our records, not a completed trade or a payment."
            ),
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(row)
    created = _domain_out(row)
    return schemas.DomainRecordCreated(**created.model_dump(), close_token=token)


@router.post("/domain/{record_id}/close", response_model=schemas.DomainRecordOut)
def close_domain_record(
    record_id: int,
    body: schemas.DomainRecordClose,
    request: Request,
    db: Session = Depends(get_db),
):
    _consume_public_write_limit(db, request, "public-domain-control", 20)
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
    from app.services import action_engine
    paid = body.result == "paid"
    try:
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
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(row)
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
        # The close/dispute note stays in the canonical Outcome for audit, but
        # must not be echoed into a public projection where it could contain PII.
        if ":close" in (outcome.notes or "") and row.close_result == "paid" and outcome.success is True:
            if outcome.actual_value is None:
                payment = f"Domain {row.kind} {row.id} closed as paid. Amount not recorded."
            else:
                payment = (
                    f"Domain {row.kind} {row.id} closed as paid. "
                    f"Amount recorded: {outcome.actual_value} {outcome.unit or 'NPR'}."
                )
            payments.append(payment)
        elif ":dispute" in (outcome.notes or ""):
            disputes.append(f"Domain {row.kind} {row.id} has a dispute. No winner is recorded.")
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
def dispute_domain_record(
    record_id: int,
    body: schemas.DomainDisputeCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _consume_public_write_limit(db, request, "public-domain-control", 20)
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
def create_booking_request(
    body: schemas.BookingRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    # Check signing readiness before rate-limit, booking, or outcome writes so a
    # missing key cannot leave a stored request while telling the visitor it failed.
    _booking_status_signing_key()
    _consume_public_write_limit(db, request, "public-booking-request", 5)
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
    db.flush()
    from app.services import action_engine

    try:
        status_token = _booking_status_token(request.id)
        action_engine.record_domain_event(
            db,
            idempotency_key=f"booking-request:{request.id}",
            source="booking_request",
            qualitative_result=(
                f"Booking request {request.id} stored for provider {request.provider_id}. "
                "Status is pending. This is not acceptance and not payment."
            ),
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(request)
    return schemas.BookingRequestOut.model_validate(request).model_copy(
        update={"status_token": status_token}
    )


@router.get("/booking-requests/{booking_id}", response_model=schemas.BookingRequestStatusOut)
def get_booking_request(
    booking_id: int,
    status_token: str = Header(..., alias="X-Booking-Status-Token", min_length=64, max_length=64),
    db: Session = Depends(get_db),
):
    # Authenticate before querying so a numeric ID alone cannot enumerate stored requests.
    expected_token = _booking_status_token(booking_id)
    if not hmac.compare_digest(status_token, expected_token):
        raise HTTPException(404, "booking request not found")
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



class PublicUnknownOut(BaseModel):
    id: str
    category: str
    question: str
    state: str
    cheapest_test: str
    stake: str


class PublicStatsOut(BaseModel):
    owner_interventions_per_real_transaction: float | Literal["NOT MEASURABLE"]


class UnknownsSummaryOut(BaseModel):
    counts: dict[str, int]
    total: int
    last_loop: str | None


# ---------------------------------------------------------------------------
# Unknowns surface (read-only)
# Parses docs/UNKNOWN_MAP.md — does not touch the six-primitive substrate.
# Public unknowns (world): categories B (people) and D (discovery-sourced).
# Internal unknowns (A: reality/ops, C: system/meta) are owner-console only.
# ---------------------------------------------------------------------------

import re
from pathlib import Path

_UNKNOWN_MAP_PATH = Path(__file__).resolve().parents[3] / "docs" / "UNKNOWN_MAP.md"
_UNKNOWN_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "unknowns.json"

# Categories visible on public pages (world unknowns)
PUBLIC_UNKNOWN_CATEGORIES = ("B", "D")
# Categories reserved for owner console (internal/business/backlog)
INTERNAL_UNKNOWN_CATEGORIES = ("A", "C")

_UNKNOWN_STATES = (
    "UNKNOWN",
    "HYPOTHESIZED",
    "TESTED",
    "SUPPORTED",
    "CONTRADICTED",
    "BLOCKED_BY_MISSING_ACCESS",
)


def _parse_unknowns():
    """Load unknowns from the JSON snapshot (preferred) or parse UNKNOWN_MAP.md.

    Returns (unknowns, last_modified_iso) where unknowns is a list of dicts
    with: id, category, question, state, cheapest_test, stake.
    """
    # Prefer the JSON snapshot (deployed with the backend); fall back to markdown
    if _UNKNOWN_JSON_PATH.exists():
        try:
            data = json.loads(_UNKNOWN_JSON_PATH.read_text(encoding="utf-8"))
            return data.get("unknowns", []), data.get("last_loop")
        except Exception:
            pass
    if not _UNKNOWN_MAP_PATH.exists():
        return [], None
    text = _UNKNOWN_MAP_PATH.read_text(encoding="utf-8")
    last_modified = datetime.fromtimestamp(
        _UNKNOWN_MAP_PATH.stat().st_mtime, tz=timezone.utc
    ).isoformat()

    unknowns = []
    in_table = False
    for line in text.split("\n"):
        if line.startswith("| # |"):
            in_table = True
            continue
        if line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            # | # | Unknown | State | Cheapest test | What changes |
            if len(parts) >= 6 and re.match(r"^[A-Z]\d+$", parts[1]):
                uid = parts[1]
                category = uid[0]
                state_m = re.match(
                    r"(UNKNOWN|HYPOTHESIZED|TESTED|SUPPORTED|CONTRADICTED|BLOCKED_BY_MISSING_ACCESS)",
                    parts[3],
                )
                if state_m:
                    unknowns.append(
                        {
                            "id": uid,
                            "category": category,
                            "question": parts[2],
                            "state": state_m.group(1),
                            "cheapest_test": parts[4],
                            "stake": parts[5],
                        }
                    )
        elif in_table and line.strip() and not line.startswith("|"):
            in_table = False
    return unknowns, last_modified


def _last_loop_timestamp():
    """Best-effort last discovery loop completion time.

    Reads from the JSON snapshot (preferred) or the markdown Date header.
    Returns ISO string or None — never invented.
    """
    if _UNKNOWN_JSON_PATH.exists():
        try:
            data = json.loads(_UNKNOWN_JSON_PATH.read_text(encoding="utf-8"))
            if data.get("last_loop"):
                return data["last_loop"]
        except Exception:
            pass
    log_path = _UNKNOWN_MAP_PATH
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8")
        m = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            return m.group(1)
    return None


@router.get("/unknowns/summary", response_model=UnknownsSummaryOut)
def get_unknowns_summary():
    """Public unknown counts by state + last-loop timestamp.

    Only world unknowns (categories B, D) are counted. Internal unknowns
    (A, C) are excluded from public surfaces.
    """
    unknowns, _ = _parse_unknowns()
    public = [u for u in unknowns if u["category"] in PUBLIC_UNKNOWN_CATEGORIES]
    counts = {s: 0 for s in _UNKNOWN_STATES}
    for u in public:
        counts[u["state"]] += 1
    return {
        "counts": counts,
        "total": len(public),
        "last_loop": _last_loop_timestamp(),
    }


@router.get("/unknowns", response_model=list[PublicUnknownOut])
def list_public_unknowns(
    state: str = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """List public world unknowns with state, cheapest test, and stake.

    No hand-written entries — parsed from docs/UNKNOWN_MAP.md.
    Optional ?state= filter. Honest empty list (not filler) when none match.
    """
    unknowns, _ = _parse_unknowns()
    public = [u for u in unknowns if u["category"] in PUBLIC_UNKNOWN_CATEGORIES]
    if state:
        su = state.upper()
        if su not in _UNKNOWN_STATES:
            raise HTTPException(400, f"unknown state: {state}")
        public = [u for u in public if u["state"] == su]
    return public[:limit]


@router.get("/stats", response_model=PublicStatsOut)
def get_public_stats(db: Session = Depends(get_db)):
    """Public real-world statistics. REAL-only; TEST/MOCK/HYPOTHESIS never leak.

    Returns NOT_MEASURABLE (not 0) for metrics with no verified real data yet.
    """
    return {
        "owner_interventions_per_real_transaction": public_stats.owner_interventions_per_real_transaction(db),
    }
