from fastapi.testclient import TestClient
from datetime import timedelta

from app import models
from app.database import get_db
from app.main import app
from app.services import opportunity_engine, public_feed


def _client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), lambda: app.dependency_overrides.clear()


def _public_claim(db, *, opportunity=None):
    signal = models.Signal(
        source="govinfo",
        content="A public notice describes an emerging infrastructure need.",
        title="Public infrastructure notice",
        source_type="external",
        canonical_url="https://example.gov/notice/1",
        retrieved_at=models.utcnow(),
    )
    db.add(signal)
    db.flush()
    claim = models.Claim(
        statement="The public notice identifies an infrastructure change.",
        normalized_statement="public infrastructure change",
        epistemic_state="observed",
        opportunity_id=opportunity.id if opportunity else None,
    )
    evidence = models.Evidence(
        signal_id=signal.id,
        source="govinfo",
        content=signal.content,
        canonical_url=signal.canonical_url,
    )
    db.add_all([claim, evidence])
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim.id,
        relation_type="supports",
        relation_key=f"claim:{claim.id}:evidence:{evidence.id}",
    ))
    db.flush()
    return signal, claim


def test_public_feed_projects_heterogeneous_records_with_evidence_and_relations(db):
    opportunity = models.Opportunity(problem="A hypothesis about a documented unmet infrastructure need")
    db.add(opportunity)
    db.flush()
    signal, claim = _public_claim(db)
    db.add(models.Evidence(
        opportunity_id=opportunity.id,
        signal_id=signal.id,
        source="govinfo",
        content="The published change supports this opportunity hypothesis.",
        canonical_url=signal.canonical_url,
        provenance_hash="public-feed-opportunity-evidence",
    ))
    db.add_all([
        models.ResearchQuestion(
            question="What changed in the documented infrastructure notice?",
            source_claim_id=claim.id,
        ),
        models.Pattern(
            title="Infrastructure changes recur",
            description="A tentative recurring theme.",
            origin_signal_ids=str(signal.id),
        ),
        models.Belief(
            statement="Infrastructure changes can create coordination needs.",
            supporting_signal_ids=str(signal.id),
        ),
    ])

    provider = models.Provider(
        name="Public operator",
        business_name="Verified Works",
        summary="Public capability provider.",
        country="Nepal",
        city="Kathmandu",
        phone="private-phone",
        email="private@example.com",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.flush()
    db.add_all([
        models.ServiceListing(
            provider_id=provider.id,
            title="Field assessment",
            description="A listed public capability.",
            category="research",
            public_visible=True,
            is_active=True,
        ),
        models.NetworkConnection(
            left_kind="domain_record",
            left_id=9999,
            right_kind="provider",
            right_id=provider.id,
            state="candidate",
            reason="This edge references a private or missing endpoint.",
            agreement_gap="No agreement recorded.",
            public_visible=True,
        ),
        models.DomainRecord(
            kind="job",
            title="Need local survey support",
            detail="An operator-submitted work request.",
            city="Pokhara",
            close_token_hash="test-hash",
            status="open",
        ),
        models.NetworkConnection(
            left_kind="domain_record",
            left_id=1,
            right_kind="provider",
            right_id=provider.id,
            state="candidate",
            reason="A possible capability match.",
            agreement_gap="No agreement recorded.",
            public_visible=True,
        ),
        models.Outcome(
            source="domain_record",
            outcome_type="QUALITATIVE",
            qualitative_result="The request was withdrawn by its submitter.",
            data_scope="REAL",
        ),
        models.Outcome(
            source="domain_record",
            outcome_type="QUALITATIVE",
            qualitative_result="Synthetic sandbox outcome.",
            data_scope="SANDBOX",
        ),
    ])
    db.commit()

    client, cleanup = _client(db)
    try:
        response = client.get("/public/feed")
        assert response.status_code == 200, response.text
        payload = response.json()
        alias_response = client.get("/api/public/feed?limit=2")
        assert alias_response.status_code == 200
        assert len(alias_response.json()) <= 2
        context_response = client.get(f"/public/feed?entity_type=provider&entity_id={provider.id}")
        assert context_response.status_code == 200
        assert {item["kind"] for item in context_response.json()} >= {"actor", "capability", "connection"}
    finally:
        cleanup()

    kinds = {item["kind"] for item in payload}
    assert {"signal", "question", "pattern", "belief", "opportunity", "actor", "capability", "work_item", "connection", "outcome"} <= kinds
    signal_item = next(item for item in payload if item["kind"] == "signal")
    assert signal_item["source_url"] == signal.canonical_url
    assert signal_item["relations"][0]["entity_type"] == "signal"
    capability = next(item for item in payload if item["kind"] == "capability")
    assert capability["relations"] == [{"entity_type": "provider", "entity_id": provider.id, "relation": "offered_by"}]
    assert all("private-phone" not in str(item) and "private@example.com" not in str(item) for item in payload)
    assert all("Synthetic sandbox outcome" not in item["summary"] for item in payload)
    assert all("score" not in item and "confidence" not in item for item in payload)


def test_public_feed_excludes_unverified_services_and_unlinked_internal_signals(db):
    signal = models.Signal(
        source="manual",
        content="Internal-only observation",
        source_type="manual",
        canonical_url="https://example.com/internal",
    )
    provider = models.Provider(
        name="Unverified operator",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="unverified",
    )
    db.add_all([signal, provider])
    db.flush()
    db.add(models.ServiceListing(
        provider_id=provider.id,
        title="Hidden capability",
        description="This unverified service is not public.",
        public_visible=True,
        is_active=True,
    ))
    db.commit()

    client, cleanup = _client(db)
    try:
        response = client.get("/public/feed?kind=signal")
        assert response.status_code == 200, response.text
        assert response.json() == []
        assert client.get("/public/feed?kind=capability").json() == []
        assert client.get("/public/feed?kind=connection").json() == []
        assert client.get("/public/feed?entity_type=provider").status_code == 422
        assert client.get("/public/feed?limit=101").status_code == 422
    finally:
        cleanup()


def test_discoveries_require_claim_and_keep_staleness_separate(db):
    old = models.utcnow() - timedelta(days=120)
    unclaimed = models.Signal(
        source="govinfo",
        source_type="external",
        content="A public notice without a stored claim.",
        canonical_url="https://example.gov/unclaimed",
        retrieved_at=old,
    )
    signal = models.Signal(
        source="govinfo",
        source_type="external",
        content="A public notice with one stale evidence item.",
        canonical_url="https://example.gov/stale",
        retrieved_at=old,
    )
    db.add_all([unclaimed, signal])
    db.flush()
    claim = models.Claim(
        statement="A cited observation with stale evidence.",
        normalized_statement="cited observation stale evidence",
        epistemic_state="observed",
    )
    evidence = models.Evidence(
        signal_id=signal.id,
        source="govinfo",
        content=signal.content,
        canonical_url=signal.canonical_url,
        retrieved_at=old,
    )
    db.add_all([claim, evidence])
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim.id,
        relation_type="derived_from",
        relation_key=f"stale-discovery:{claim.id}:{evidence.id}",
    ))
    db.commit()

    client, cleanup = _client(db)
    try:
        response = client.get("/public/discoveries")
        assert response.status_code == 200, response.text
        body = response.json()
        assert [row["id"] for row in body] == [claim.id]
        assert body[0]["epistemic_state"] == "observed"
        assert body[0]["stale"] is True
        assert body[0]["freshness"] == "stale"
    finally:
        cleanup()


def test_public_opportunity_requires_question_after_evidenced_claim(db):
    from app.services.public_feed import build_public_feed

    opportunity = models.Opportunity(problem="A documented hypothesis that needs more research")
    db.add(opportunity)
    db.flush()
    _signal, claim = _public_claim(db, opportunity=opportunity)
    db.commit()

    assert not any(item.entity_type == "opportunity" for item in build_public_feed(db))

    question = models.ResearchQuestion(
        question="What additional public evidence tests the documented hypothesis?",
        source_claim_id=claim.id,
    )
    db.add(question)
    db.commit()

    opportunity_item = next(
        item for item in build_public_feed(db) if item.entity_type == "opportunity"
    )
    assert [relation.model_dump() for relation in opportunity_item.relations] == [
        {"entity_type": "claim", "entity_id": claim.id, "relation": "informed_by"}
    ]


def test_public_feed_composes_connections_but_keeps_endpoint_visibility_gates(db):
    from app.services.public_feed import build_public_feed

    provider = models.Provider(
        name="Verified test actor",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    hidden = models.Provider(
        name="Unverified test actor",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="unverified",
    )
    need = models.DomainRecord(
        kind="job",
        title="A public test need",
        detail="A bounded operator-submitted record.",
        close_token_hash="test-hash",
        status="open",
    )
    result = models.Outcome(
        source="domain_record",
        outcome_type="QUALITATIVE",
        qualitative_result="A real recorded test outcome.",
        data_scope="REAL",
    )
    db.add_all([provider, hidden, need, result])
    db.flush()

    first = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=provider.id,
        state="candidate",
        reason="A hypothetical connection to a verified public actor.",
        agreement_gap="No agreement recorded.",
        public_visible=True,
    )
    db.add(first)
    db.flush()
    second = models.NetworkConnection(
        left_kind="network_connection",
        left_id=first.id,
        right_kind="outcome",
        right_id=result.id,
        state="candidate",
        reason="A connection can point to another connection and an outcome.",
        agreement_gap="No agreement recorded.",
        public_visible=True,
    )
    private_edge = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=hidden.id,
        state="candidate",
        reason="A public connection cannot reveal an unverified actor.",
        agreement_gap="No agreement recorded.",
        public_visible=True,
    )
    db.add_all([second, private_edge])
    db.commit()

    from app.services import network_substrate_adapter
    network_substrate_adapter.sync_network_connections(db)
    db.commit()

    feed = build_public_feed(db, limit=100, kind="connection")
    visible_ids = {item.entity_id for item in feed}
    assert visible_ids == {first.id, second.id}
    assert all(item.epistemic_state == "hypothesized" for item in feed)
    assert next(item for item in feed if item.entity_id == first.id).relation_type == "possible_match"
    by_id = {item.entity_id: item for item in feed}
    for source_connection in (first, second):
        projected = next(
            relation for relation in by_id[source_connection.id].relations
            if relation.relation == "substrate_relation"
        )
        assert (projected.entity_type, projected.entity_id) == (
            "relation", source_connection.relation_id
        )

    context = build_public_feed(
        db,
        limit=100,
        entity_type="network_connection",
        entity_id=first.id,
    )
    assert {item.entity_id for item in context if item.kind == "connection"} == {first.id, second.id}
    assert private_edge.id not in visible_ids


def test_opportunity_claim_question_link_respects_regulated_publication_gate(db):
    signal = models.Signal(
        source="market bulletin",
        content="A public bulletin describes a change in equity prices.",
        source_type="external",
        canonical_url="https://example.gov/equity-update",
        retrieved_at=models.utcnow(),
    )
    opportunity = models.Opportunity(problem="A hypothesis about a reported equity change")
    claim = models.Claim(
        statement="The bulletin reports that equity prices changed.",
        normalized_statement="the bulletin reports that equity prices changed",
        epistemic_state="observed",
        provenance='{"regulated_asset_class":"equity"}',
    )
    claim_evidence = models.Evidence(
        signal=signal,
        source=signal.source,
        content=signal.content,
        canonical_url=signal.canonical_url,
    )
    opportunity_evidence = models.Evidence(
        opportunity=opportunity,
        signal=signal,
        source=signal.source,
        content="A stored opportunity evidence link.",
        canonical_url=signal.canonical_url,
    )
    db.add_all([signal, opportunity, claim, claim_evidence, opportunity_evidence])
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=claim_evidence.id,
        claim_id=claim.id,
        relation_type="derived_from",
        relation_key=f"claim:{claim.id}:signal:{signal.id}",
    ))
    db.commit()

    assert opportunity_engine.link_opportunity_evidence_to_claim_questions(db) == 0
    assert db.query(models.ResearchQuestion).filter_by(source_claim_id=claim.id).count() == 0
    assert not any(
        item.entity_type == "opportunity"
        for item in public_feed.build_public_feed(db)
    )
