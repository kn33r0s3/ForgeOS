"""Build the public feed as a projection over Forge's canonical records.

Feed items keep source identity and relationships; they are not persisted as a
second copy of signals, needs, opportunities, people, or outcomes.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models, schemas
from app.services import network_endpoints, public_epistemics


_PUBLIC_OUTCOME_SOURCES = ("domain_record", "booking_request", "network_connection")
_EVIDENCE_TARGET_COLUMNS = {
    "claim": models.EvidenceRelationship.claim_id,
    "opportunity": models.EvidenceRelationship.opportunity_id,
    "decision": models.EvidenceRelationship.decision_id,
    "experiment": models.EvidenceRelationship.experiment_id,
    "outcome": models.EvidenceRelationship.outcome_id,
    "network_connection": models.EvidenceRelationship.network_connection_id,
}
_DIRECT_EVIDENCE_TARGET_COLUMNS = {
    "opportunity": models.Evidence.opportunity_id,
}


def _date_key(value: datetime | None) -> float:
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    found: set[int] = set()
    for value in raw.split(","):
        try:
            found.add(int(value.strip()))
        except (TypeError, ValueError):
            continue
    return found


def _attach_public_trace_refs(db: Session, items: list[schemas.PublicFeedItem]) -> None:
    """Attach read-only references to available substrate and evidence history.

    The feed item itself names its migration-stage source row. This adds links
    to any existing substrate wrapper, event, and evidence record without
    creating rows or copying private evidence content into the public response.
    """
    from app.services import world_graph

    entity_cache: dict[tuple[str, int], models.SubstrateEntity | None] = {}
    event_cache: dict[tuple[str, int], list[models.WorldEvent]] = {}
    evidence_source_cache: dict[tuple[str, int], list[tuple[int, str]]] = {}
    evidence_subject_cache: dict[tuple[str, int], list[models.Evidence]] = {}
    evidence_exists_cache: dict[int, bool] = {}

    for item in items:
        references = list(item.relations)
        seen_refs = {(ref.entity_type, ref.entity_id, ref.relation) for ref in references}

        def add_ref(entity_type: str, entity_id: int | None, relation: str) -> None:
            if entity_id is None:
                return
            key = (entity_type, entity_id, relation)
            if key not in seen_refs:
                references.append(schemas.PublicFeedRelation(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    relation=relation,
                ))
                seen_refs.add(key)

        source_refs = [(item.entity_type, item.entity_id)] + [
            (ref.entity_type, ref.entity_id) for ref in references
            if ref.entity_type not in {"entity", "event", "evidence", "relation"}
        ]
        substrate_entities: dict[int, models.SubstrateEntity] = {}
        substrate_entities_by_source: dict[tuple[str, int], models.SubstrateEntity] = {}
        for source_type, source_id in source_refs:
            if source_type == "network_connection":
                continue
            identity_key = (source_type, source_id)
            if identity_key not in entity_cache:
                entity_cache[identity_key] = world_graph.find_canonical_entity(
                    db, source_type, source_id
                )
            source_entity = entity_cache[identity_key]
            if source_entity is not None:
                substrate_entities[source_entity.id] = source_entity
                substrate_entities_by_source[(source_type, source_id)] = source_entity
                add_ref("entity", source_entity.id, "substrate_entity")

        # When an item already declares a typed source relationship (for
        # example a public ServiceListing's offered_by Provider), attach its
        # matching substrate relation and trace its events/evidence below.
        root_entity = substrate_entities_by_source.get((item.entity_type, item.entity_id))
        if root_entity is not None:
            for source_ref in list(item.relations):
                target_entity = substrate_entities_by_source.get(
                    (source_ref.entity_type, source_ref.entity_id)
                )
                if target_entity is None or not source_ref.relation:
                    continue
                matching_relations = db.query(models.WorldRelation).filter_by(
                    from_entity_id=root_entity.id,
                    to_entity_id=target_entity.id,
                    relation_type=source_ref.relation,
                ).all()
                for relation in matching_relations:
                    add_ref("relation", relation.id, "substrate_relation")

        relation_ids = {
            ref.entity_id for ref in references if ref.entity_type == "relation"
        }
        if item.entity_type == "network_connection":
            source_connection = db.get(models.NetworkConnection, item.entity_id)
            if source_connection is not None and source_connection.relation_id is not None:
                relation_ids.add(source_connection.relation_id)

        event_rows: dict[int, models.WorldEvent] = {}
        for source_entity in substrate_entities.values():
            cache_key = ("entity", source_entity.id)
            if cache_key not in event_cache:
                event_cache[cache_key] = db.query(models.WorldEvent).filter_by(
                    entity_id=source_entity.id
                ).all()
            for event in event_cache[cache_key]:
                event_rows[event.id] = event
        for relation_id in relation_ids:
            cache_key = ("relation", relation_id)
            if cache_key not in event_cache:
                event_cache[cache_key] = db.query(models.WorldEvent).filter_by(
                    relation_id=relation_id
                ).all()
            for event in event_cache[cache_key]:
                event_rows[event.id] = event
        for event in event_rows.values():
            add_ref("event", event.id, f"event:{event.event_type}")

        evidence_refs: dict[tuple[int, str], None] = {}

        def add_evidence(evidence_id: int, relation: str) -> None:
            if evidence_id not in evidence_exists_cache:
                evidence_exists_cache[evidence_id] = db.get(models.Evidence, evidence_id) is not None
            if evidence_exists_cache[evidence_id]:
                evidence_refs[(evidence_id, relation)] = None

        public_source_refs = source_refs
        visited_source_refs: set[tuple[str, int]] = set()
        for source_type, source_id in public_source_refs:
            if (source_type, source_id) in visited_source_refs:
                continue
            visited_source_refs.add((source_type, source_id))
            cache_key = (source_type, source_id)
            if cache_key not in evidence_source_cache:
                source_evidence: list[tuple[int, str]] = []
                if source_type == "signal":
                    source_evidence.extend(
                        (evidence.id, "source_evidence")
                        for evidence in db.query(models.Evidence).filter_by(signal_id=source_id).all()
                    )
                direct_column = _DIRECT_EVIDENCE_TARGET_COLUMNS.get(source_type)
                if direct_column is not None:
                    source_evidence.extend(
                        (evidence.id, "source_evidence")
                        for evidence in db.query(models.Evidence).filter(direct_column == source_id).all()
                    )
                target_column = _EVIDENCE_TARGET_COLUMNS.get(source_type)
                if target_column is not None:
                    source_evidence.extend(
                        (link.evidence_id, f"evidence:{link.relation_type}")
                        for link in db.query(models.EvidenceRelationship)
                        .filter(target_column == source_id).all()
                    )
                evidence_source_cache[cache_key] = source_evidence
            for evidence_id, relation in evidence_source_cache[cache_key]:
                add_evidence(evidence_id, relation)

        for source_entity in substrate_entities.values():
            cache_key = ("entity", source_entity.id)
            if cache_key not in evidence_subject_cache:
                evidence_subject_cache[cache_key] = db.query(models.Evidence).filter_by(
                    subject_kind="entity", subject_id=source_entity.id
                ).all()
            for evidence in evidence_subject_cache[cache_key]:
                add_evidence(evidence.id, f"evidence:{evidence.support_level or 'unknown'}")
        for relation_id in relation_ids:
            cache_key = ("relation", relation_id)
            if cache_key not in evidence_subject_cache:
                evidence_subject_cache[cache_key] = db.query(models.Evidence).filter_by(
                    subject_kind="relation", subject_id=relation_id
                ).all()
            for evidence in evidence_subject_cache[cache_key]:
                add_evidence(evidence.id, f"evidence:{evidence.support_level or 'unknown'}")
        for evidence_id, relation in evidence_refs:
            add_ref("evidence", evidence_id, relation)

        item.relations = references


def build_public_feed(
    db: Session,
    *,
    limit: int = 30,
    kind: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> list[schemas.PublicFeedItem]:
    """Return recent public changes from existing evidence and network records.

    Candidate rank is chronological only. No synthetic engagement or trust
    score is introduced; source-specific visibility gates remain authoritative.
    """
    from app.services.network_substrate_adapter import relation_read_model

    requested_kind = (kind or "").strip().lower()
    requested_entity_type = (
        network_endpoints.canonical_endpoint_type(entity_type, strict=False)
        if entity_type is not None
        else None
    ) or entity_type
    items: list[schemas.PublicFeedItem] = []

    # A signal enters the public network only when it is externally sourced,
    # has a canonical source URL, and supports a public-state claim.
    evidence_rows = (
        db.query(models.Claim, models.Signal)
        .join(models.EvidenceRelationship, models.EvidenceRelationship.claim_id == models.Claim.id)
        .join(models.Evidence, models.Evidence.id == models.EvidenceRelationship.evidence_id)
        .join(models.Signal, models.Signal.id == models.Evidence.signal_id)
        .filter(models.Signal.source_type == "external")
        .filter(models.Signal.canonical_url.isnot(None))
        .filter(models.Signal.is_duplicate_of.is_(None))
        .order_by(models.Claim.updated_at.desc(), models.Signal.retrieved_at.desc())
        .limit(limit * 4)
        .all()
    )
    public_claims: dict[int, tuple[models.Claim, models.Signal]] = {}
    public_labels: dict[int, public_epistemics.PublicClaimLabel] = {}
    public_question_ids: set[int] = set()
    public_question_claim_ids: set[int] = set()
    public_pattern_ids: set[int] = set()
    public_belief_ids: set[int] = set()
    public_opportunity_ids: set[int] = set()
    for claim, signal in evidence_rows:
        label = public_epistemics.public_claim_label(db, claim)
        if label is None:
            continue
        public_claims.setdefault(claim.id, (claim, signal))
        public_labels.setdefault(claim.id, label)
    public_signal_ids = {signal.id for _, signal in public_claims.values()}

    for claim, signal in public_claims.values():
        label = public_labels[claim.id]
        excerpt = " ".join((signal.content or "").split())
        if len(excerpt) > 280:
            excerpt = excerpt[:277].rstrip() + "..."
        items.append(schemas.PublicFeedItem(
            id=f"claim:{claim.id}",
            kind="signal",
            entity_type="claim",
            entity_id=claim.id,
            title=signal.title or claim.statement[:120],
            summary=excerpt or claim.statement,
            occurred_at=signal.published_at or signal.retrieved_at or signal.timestamp,
            updated_at=claim.updated_at,
            status=None,
            epistemic_state=label["epistemic_state"],
            stale=label["stale"],
            source=signal.source,
            source_url=signal.canonical_url,
            relations=[schemas.PublicFeedRelation(
                entity_type="signal", entity_id=signal.id, relation="supported_by"
            )],
        ))

    # Research questions become feed items only when tied to a publicly
    # evidenced claim. Internal plans/tasks remain private.
    if public_claims:
        questions = (
            db.query(models.ResearchQuestion)
            .filter(models.ResearchQuestion.source_claim_id.in_(list(public_claims)))
            .order_by(models.ResearchQuestion.created_at.desc())
            .limit(limit)
            .all()
        )
        for question in questions:
            public_question_ids.add(question.id)
            public_question_claim_ids.add(question.source_claim_id)
            claim, signal = public_claims[question.source_claim_id]
            items.append(schemas.PublicFeedItem(
                id=f"research-question:{question.id}",
                kind="question",
                entity_type="research_question",
                entity_id=question.id,
                title=question.question,
                summary="An open research question linked to a publicly cited observation.",
                occurred_at=question.created_at,
                status=question.status,
                epistemic_state="question",
                source="Forge research",
                source_url=signal.canonical_url,
                relations=[
                    schemas.PublicFeedRelation(entity_type="claim", entity_id=claim.id, relation="asks_about"),
                    schemas.PublicFeedRelation(entity_type="signal", entity_id=signal.id, relation="grounded_in"),
                ],
            ))

    # General knowledge records enter only when their own signal links point
    # to the public evidence set above. Scores/confidence stay out of the feed.
    patterns = db.query(models.Pattern).order_by(models.Pattern.last_seen.desc()).limit(limit * 2).all()
    for pattern in patterns:
        related_signal_ids = sorted(_ids(pattern.origin_signal_ids) & public_signal_ids)
        if not related_signal_ids:
            continue
        public_pattern_ids.add(pattern.id)
        items.append(schemas.PublicFeedItem(
            id=f"pattern:{pattern.id}",
            kind="pattern",
            entity_type="pattern",
            entity_id=pattern.id,
            title=pattern.title,
            summary=pattern.description,
            occurred_at=pattern.last_seen or pattern.created_at,
            updated_at=pattern.last_seen,
            epistemic_state="inferred_pattern",
            source="Forge pattern engine",
            relations=[schemas.PublicFeedRelation(
                entity_type="signal", entity_id=sid, relation="derived_from"
            ) for sid in related_signal_ids],
        ))

    beliefs = db.query(models.Belief).order_by(models.Belief.last_updated.desc()).limit(limit * 2).all()
    for belief in beliefs:
        related_signal_ids = sorted(_ids(belief.supporting_signal_ids) & public_signal_ids)
        if not related_signal_ids:
            continue
        public_belief_ids.add(belief.id)
        items.append(schemas.PublicFeedItem(
            id=f"belief:{belief.id}",
            kind="belief",
            entity_type="belief",
            entity_id=belief.id,
            title=belief.statement,
            summary="A working belief linked to externally sourced observations; it remains revisable.",
            occurred_at=belief.created_at,
            updated_at=belief.last_updated,
            epistemic_state="inference",
            source="Forge knowledge graph",
            relations=[schemas.PublicFeedRelation(
                entity_type="signal", entity_id=sid, relation="supported_by"
            ) for sid in related_signal_ids],
        ))

    # Opportunities are hypotheses here, not offers. Require the complete
    # public chain: external Signal -> eligible Claim -> ResearchQuestion ->
    # Opportunity. The legacy claim pointer and Evidence rows may connect the
    # last edge, but neither can skip the ResearchQuestion.
    opportunity_claims: dict[int, list[int]] = {}
    claims_by_signal_id: dict[int, set[int]] = {}
    for claim, _ in public_claims.values():
        if claim.id in public_question_claim_ids and claim.opportunity_id is not None:
            opportunity_claims.setdefault(claim.opportunity_id, []).append(claim.id)
    for claim, signal in public_claims.values():
        if claim.id in public_question_claim_ids:
            claims_by_signal_id.setdefault(signal.id, set()).add(claim.id)
    if public_signal_ids:
        opportunity_evidence = (
            db.query(models.Evidence.opportunity_id, models.Evidence.signal_id)
            .filter(models.Evidence.opportunity_id.isnot(None))
            .filter(models.Evidence.signal_id.in_(list(public_signal_ids)))
            .all()
        )
        for opportunity_id, signal_id in opportunity_evidence:
            for claim_id in claims_by_signal_id.get(signal_id, ()):
                opportunity_claims.setdefault(opportunity_id, []).append(claim_id)
    opportunity_claims = {
        opportunity_id: sorted(set(claim_ids))
        for opportunity_id, claim_ids in opportunity_claims.items()
        if claim_ids
    }
    if opportunity_claims:
        opportunities = (
            db.query(models.Opportunity)
            .filter(models.Opportunity.id.in_(list(opportunity_claims)))
            .filter(models.Opportunity.status.notin_(("invalidated", "abandoned")))
            .all()
        )
        for opportunity in opportunities:
            public_opportunity_ids.add(opportunity.id)
            items.append(schemas.PublicFeedItem(
                id=f"opportunity:{opportunity.id}",
                kind="opportunity",
                entity_type="opportunity",
                entity_id=opportunity.id,
                title=opportunity.problem,
                summary="Evidence-linked opportunity hypothesis. Demand, price, and resolution remain unknown until observed.",
                occurred_at=opportunity.created_at,
                updated_at=opportunity.updated_at,
                status=opportunity.status,
                epistemic_state="hypothesis",
                source="Forge opportunity engine",
                relations=[schemas.PublicFeedRelation(
                    entity_type="claim", entity_id=claim_id, relation="informed_by"
                ) for claim_id in opportunity_claims[opportunity.id]],
            ))

    providers = (
        db.query(models.Provider)
        .filter(models.Provider.public_visible.is_(True), models.Provider.is_active.is_(True))
        .filter(models.Provider.verification_status == "verified")
        .order_by(models.Provider.updated_at.desc())
        .limit(limit)
        .all()
    )
    for provider in providers:
        items.append(schemas.PublicFeedItem(
            id=f"provider:{provider.id}",
            kind="actor",
            entity_type="provider",
            entity_id=provider.id,
            title=provider.business_name or provider.name,
            summary=provider.summary or "Verified public network participant.",
            occurred_at=provider.created_at,
            updated_at=provider.updated_at,
            location=", ".join(filter(None, [provider.city, provider.region, provider.country])) or None,
            status="verified",
            epistemic_state="verified_record",
            source="public provider registry",
        ))

    services = (
        db.query(models.ServiceListing, models.Provider)
        .join(models.Provider)
        .filter(models.ServiceListing.public_visible.is_(True), models.ServiceListing.is_active.is_(True))
        .filter(models.Provider.public_visible.is_(True), models.Provider.is_active.is_(True))
        .filter(models.Provider.verification_status == "verified")
        .order_by(models.ServiceListing.updated_at.desc())
        .limit(limit)
        .all()
    )
    public_service_ids: set[int] = set()
    for listing, provider in services:
        public_service_ids.add(listing.id)
        items.append(schemas.PublicFeedItem(
            id=f"service:{listing.id}",
            kind="capability",
            category=listing.category,
            entity_type="service_listing",
            entity_id=listing.id,
            title=listing.title,
            summary=listing.description,
            occurred_at=listing.created_at,
            updated_at=listing.updated_at,
            location=listing.location or provider.city,
            status=listing.availability_status,
            epistemic_state="verified_provider_listing",
            source="public service registry",
            relations=[schemas.PublicFeedRelation(
                entity_type="provider", entity_id=listing.provider_id, relation="offered_by"
            )],
        ))

    needs = (
        db.query(models.DomainRecord)
        .filter(models.DomainRecord.status == "open")
        .order_by(models.DomainRecord.updated_at.desc())
        .limit(limit)
        .all()
    )
    public_domain_ids = {need.id for need in needs}
    for need in needs:
        items.append(schemas.PublicFeedItem(
            id=f"domain-record:{need.id}",
            kind="work_item",
            category=need.kind,
            entity_type="domain_record",
            entity_id=need.id,
            title=need.title,
            summary=need.detail,
            occurred_at=need.created_at,
            updated_at=need.updated_at,
            location=need.city,
            status=need.status,
            epistemic_state="operator_submitted_unverified",
            source="public work board",
        ))

    # A public edge does not make either endpoint public by itself. Build the
    # direct endpoint set from the existing per-record visibility gates.
    public_provider_ids = {
        provider.id for provider in db.query(models.Provider)
        .filter(models.Provider.public_visible.is_(True), models.Provider.is_active.is_(True))
        .filter(models.Provider.verification_status == "verified")
        .all()
    }
    outcomes = (
        db.query(models.Outcome)
        .filter(models.Outcome.source.in_(_PUBLIC_OUTCOME_SOURCES))
        .filter(models.Outcome.data_scope == "REAL")
        .filter(models.Outcome.qualitative_result.isnot(None))
        .order_by(models.Outcome.observed_at.desc())
        .limit(limit)
        .all()
    )
    public_outcome_ids = {
        outcome.id for outcome in outcomes if (outcome.qualitative_result or "").strip()
    }
    public_references = (
        {("claim", claim_id) for claim_id in public_claims}
        | {("signal", signal_id) for signal_id in public_signal_ids}
        | {("research_question", question_id) for question_id in public_question_ids}
        | {("pattern", pattern_id) for pattern_id in public_pattern_ids}
        | {("belief", belief_id) for belief_id in public_belief_ids}
        | {("opportunity", opportunity_id) for opportunity_id in public_opportunity_ids}
        | {("provider", provider_id) for provider_id in public_provider_ids}
        | {("service_listing", service_id) for service_id in public_service_ids}
        | {("domain_record", record_id) for record_id in public_domain_ids}
        | {("outcome", outcome_id) for outcome_id in public_outcome_ids}
    )
    connections = (
        db.query(models.NetworkConnection)
        .filter(models.NetworkConnection.public_visible.is_(True))
        .order_by(models.NetworkConnection.updated_at.desc())
        .limit(limit * 4)
        .all()
    )

    # Relation endpoints can themselves be relations. Resolve that closure
    # only through explicitly public links whose two endpoints are already
    # visible. A dangling/private node cannot become public through an edge.
    visible_connection_ids: set[int] = set()
    pending = list(connections)
    while pending:
        newly_visible = []
        for connection in pending:
            left_type = network_endpoints.canonical_endpoint_type(connection.left_kind, strict=False)
            right_type = network_endpoints.canonical_endpoint_type(connection.right_kind, strict=False)
            if left_type is None or right_type is None:
                continue
            if (left_type, connection.left_id) in public_references and (
                right_type, connection.right_id
            ) in public_references:
                newly_visible.append(connection)
        if not newly_visible:
            break
        for connection in newly_visible:
            pending.remove(connection)
            visible_connection_ids.add(connection.id)
            public_references.add(("network_connection", connection.id))

    for connection in connections:
        if connection.id not in visible_connection_ids:
            continue
        left_type = network_endpoints.canonical_endpoint_type(connection.left_kind, strict=False)
        right_type = network_endpoints.canonical_endpoint_type(connection.right_kind, strict=False)
        if left_type is None or right_type is None:
            continue
        graph = relation_read_model(db, connection)
        relation_type = graph["relation_type"]
        truth_state = graph["epistemic_state"]
        items.append(schemas.PublicFeedItem(
            id=f"connection:{connection.id}",
            kind="connection",
            entity_type="network_connection",
            entity_id=connection.id,
            title=(
                f"{connection.left_kind.replace('_', ' ').title()} "
                f"{relation_type.replace('_', ' ')} "
                f"{connection.right_kind.replace('_', ' ').title()}"
            ),
            summary=connection.reason,
            occurred_at=connection.created_at,
            updated_at=connection.updated_at,
            status=connection.state,
            epistemic_state=truth_state,
            source="public Forge network",
            relation_type=relation_type,
            direction=graph["direction"],
            relations=[
                schemas.PublicFeedRelation(entity_type=left_type, entity_id=connection.left_id, relation="left_side"),
                schemas.PublicFeedRelation(entity_type=right_type, entity_id=connection.right_id, relation="right_side"),
            ] + (
                [schemas.PublicFeedRelation(
                    entity_type="relation",
                    entity_id=connection.relation_id,
                    relation="substrate_relation",
                )]
                if connection.relation_id is not None else []
            ),
        ))

    for outcome in outcomes:
        if not (outcome.qualitative_result or "").strip():
            continue
        items.append(schemas.PublicFeedItem(
            id=f"outcome:{outcome.id}",
            kind="outcome",
            entity_type="outcome",
            entity_id=outcome.id,
            title="Recorded outcome",
            summary=outcome.qualitative_result,
            occurred_at=outcome.observed_at,
            status=outcome.verification_state.lower(),
            epistemic_state="observed_outcome",
            source=outcome.source,
        ))

    if requested_kind:
        items = [item for item in items if item.kind == requested_kind]
    _attach_public_trace_refs(db, items)

    if entity_type is not None and entity_id is not None:
        items = [
            item for item in items
            if (item.entity_type == requested_entity_type and item.entity_id == entity_id)
            or any(
                relation.entity_type == requested_entity_type and relation.entity_id == entity_id
                for relation in item.relations
            )
        ]
    items.sort(key=lambda item: (_date_key(item.updated_at or item.occurred_at), item.id), reverse=True)
    return items[:limit]
