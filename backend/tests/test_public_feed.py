from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.main import app


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


def test_public_feed_composes_relations_but_keeps_endpoint_visibility_gates(db):
    from app.services.public_feed import build_public_feed
    from app.services.world_graph import create_relation

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

    first = create_relation(
        db,
        subject_type="domain_record",
        subject_id=need.id,
        relation_type="could_use",
        object_type="provider",
        object_id=provider.id,
        reason="A hypothetical connection to a verified public actor.",
    )
    first.public_visible = True
    second = create_relation(
        db,
        subject_type="network_connection",
        subject_id=first.id,
        relation_type="observed_with",
        object_type="outcome",
        object_id=result.id,
        reason="A relation can point to another relation and an outcome.",
    )
    second.public_visible = True
    private_edge = create_relation(
        db,
        subject_type="domain_record",
        subject_id=need.id,
        relation_type="could_use",
        object_type="provider",
        object_id=hidden.id,
        reason="A public edge cannot reveal an unverified actor.",
    )
    private_edge.public_visible = True
    db.commit()

    feed = build_public_feed(db, limit=100, kind="connection")
    visible_ids = {item.entity_id for item in feed}
    assert visible_ids == {first.id, second.id}
    assert all(item.epistemic_state == "hypothesized" for item in feed)
    assert next(item for item in feed if item.entity_id == first.id).relation_type == "could_use"

    context = build_public_feed(
        db,
        limit=100,
        entity_type="network_connection",
        entity_id=first.id,
    )
    assert {item.entity_id for item in context if item.kind == "connection"} == {first.id, second.id}
    assert private_edge.id not in visible_ids
