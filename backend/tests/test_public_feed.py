import json
from pathlib import Path
from fastapi.testclient import TestClient
from datetime import timedelta
from sqlalchemy import event

from app import models
from app.database import get_db
from app.main import app
from app.services import opportunity_engine, public_feed


def _client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), lambda: app.dependency_overrides.clear()


def test_vercel_api_service_routes_original_path_to_fastapi_aliases():
    config_path = Path(__file__).resolve().parents[2] / "vercel.json"
    config = json.loads(config_path.read_text())
    api_service = config["services"]["api"]

    assert api_service["root"] == "backend/"
    assert api_service["framework"] == "fastapi"
    assert api_service["entrypoint"] == "app.main:app"
    assert "routes" not in api_service
    # Better Auth is served by the web app, so its specific rewrite precedes FastAPI.
    assert config["rewrites"][0] == {
        "source": "/api/auth/(.*)",
        "destination": {"service": "web"},
    }
    assert config["rewrites"][1] == {
        "source": "/api/(.*)",
        "destination": {"service": "api"},
    }


def test_public_projection_gets_do_not_write_records(db, monkeypatch):
    from app import security

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    statements = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""
        if operation in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}:
            statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record_statement)
    client, cleanup = _client(db)
    try:
        responses = [
            client.get(path)
            for path in (
                "/public/feed",
                "/public/discoveries",
                "/public/providers",
                "/public/services",
                "/public/network",
            )
        ]
    finally:
        client.close()
        cleanup()
        event.remove(bind, "before_cursor_execute", record_statement)

    assert [response.status_code for response in responses] == [200] * 5
    assert statements == []


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


def test_network_reads_substrate_relation_after_projection_and_keeps_workflow_authority(db, monkeypatch):
    from app import security
    from app.services import network_substrate_adapter, world_graph

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "test-owner-key")
    owner_headers = {"X-API-Key": "test-owner-key"}

    need = models.DomainRecord(
        kind="job",
        title="A public repair need",
        detail="An open request from an operator.",
        close_token_hash="test-hash",
        status="open",
    )
    provider = models.Provider(
        name="Verified repair provider",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add_all([need, provider])
    db.flush()
    connection = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=provider.id,
        relation_type="offered_by",
        epistemic_state="hypothesized",
        state="candidate",
        reason="A possible repair connection.",
        agreement_gap="No agreement is implied.",
        public_visible=True,
    )
    db.add(connection)
    db.commit()

    network_substrate_adapter.sync_network_connections(db)
    db.commit()
    relation = db.get(models.WorldRelation, connection.relation_id)
    assert relation is not None
    # A legacy source label cannot bypass the substrate truth transition.
    connection.epistemic_state = "supported"
    db.commit()

    client, cleanup = _client(db)
    try:
        public_response = client.get("/public/connections")
        assert public_response.status_code == 200, public_response.text
        item = next(row for row in public_response.json() if row["id"] == connection.id)
        operator_response = client.get("/forge/connections", headers=owner_headers)
        assert operator_response.status_code == 200, operator_response.text
        operator_item = next(row for row in operator_response.json() if row["id"] == connection.id)
        feed_response = client.get("/public/feed", params={"kind": "connection"})
        assert feed_response.status_code == 200, feed_response.text
        feed_item = next(row for row in feed_response.json() if row["entity_id"] == connection.id)
    finally:
        cleanup()

    source_entity = world_graph.find_canonical_entity(db, "domain_record", need.id)
    target_entity = world_graph.find_canonical_entity(db, "provider", provider.id)
    assert item["graph_source"] == operator_item["graph_source"] == "substrate"
    assert item["substrate_relation_id"] == relation.id
    assert item["substrate_from_entity_id"] == source_entity.id
    assert item["substrate_to_entity_id"] == target_entity.id
    assert item["relation_type"] == "offered_by"
    assert item["epistemic_state"] == "hypothesized"
    assert operator_item["epistemic_state"] == "hypothesized"
    assert feed_item["relation_type"] == "offered_by"
    assert feed_item["direction"] == "directed"
    assert feed_item["epistemic_state"] == "hypothesized"
    assert item["state"] == "candidate"
    assert relation.truth_state == "hypothesized"


def test_unprojected_public_connection_uses_registered_legacy_adapter(db):
    need = models.DomainRecord(
        kind="job",
        title="A public need awaiting projection",
        detail="An open request.",
        close_token_hash="test-hash",
        status="open",
    )
    provider = models.Provider(
        name="Verified provider awaiting projection",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add_all([need, provider])
    db.flush()
    connection = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=provider.id,
        relation_type="possible_match",
        epistemic_state="possible",
        state="candidate",
        reason="Awaiting adapter cycle.",
        agreement_gap="No agreement is implied.",
        public_visible=True,
    )
    db.add(connection)
    db.commit()

    client, cleanup = _client(db)
    try:
        response = client.get("/public/connections")
        assert response.status_code == 200, response.text
        item = next(row for row in response.json() if row["id"] == connection.id)
    finally:
        cleanup()

    assert item["graph_source"] == "legacy_adapter"
    assert item["substrate_relation_id"] is None
    assert item["relation_type"] == "possible_match"
    assert item["epistemic_state"] == "possible"


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

    from app.services import world_graph
    world_graph.sync_intelligence_path(db, limit=100)
    db.commit()
    substrate_counts_before = (
        db.query(models.SubstrateEntity).count(),
        db.query(models.WorldRelation).count(),
        db.query(models.WorldEvent).count(),
    )
    projected_items = public_feed.build_public_feed(db, limit=100)
    substrate_counts_after = (
        db.query(models.SubstrateEntity).count(),
        db.query(models.WorldRelation).count(),
        db.query(models.WorldEvent).count(),
    )
    assert substrate_counts_after == substrate_counts_before
    assert all(item.entity_type and item.entity_id > 0 and item.source for item in projected_items)
    by_identity = {(item.entity_type, item.entity_id): item for item in projected_items}
    signal_evidence_ids = {
        evidence_id for (evidence_id,) in db.query(models.Evidence.id).filter_by(signal_id=signal.id).all()
    }
    signal_item = next(item for item in projected_items if item.kind == "signal")
    assert signal_item.entity_type == "claim" and signal_item.entity_id == claim.id
    assert any(
        ref.entity_type == "evidence" and ref.entity_id in signal_evidence_ids
        for ref in signal_item.relations
    )
    substrate_signal = world_graph.find_canonical_entity(db, "signal", signal.id)
    assert any(
        ref.entity_type == "entity" and ref.entity_id == substrate_signal.id
        for ref in signal_item.relations
    )
    assert any(ref.entity_type == "event" for ref in signal_item.relations)

    client, cleanup = _client(db)
    try:
        response = client.get("/public/feed")
        assert response.status_code == 200, response.text
        payload = response.json()
        health_alias_response = client.get("/api/health")
        assert health_alias_response.status_code == 200, health_alias_response.text
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
    assert any(
        relation.entity_type == "claim" and relation.entity_id == claim.id
        and relation.relation == "informed_by"
        for relation in opportunity_item.relations
    )
    assert any(relation.entity_type == "evidence" for relation in opportunity_item.relations)


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
    private_evidence = models.Evidence(
        source="private operator note",
        content="This evidence belongs to a hidden endpoint connection.",
    )
    db.add_all([second, private_edge, private_evidence])
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=private_evidence.id,
        network_connection_id=private_edge.id,
        relation_type="derived_from",
        relation_key=f"hidden-edge-evidence:{private_edge.id}",
    ))
    db.commit()

    from app.services import network_substrate_adapter
    network_substrate_adapter.sync_network_connections(db)
    db.commit()

    feed = build_public_feed(db, limit=100, kind="connection")
    visible_ids = {item.entity_id for item in feed}
    assert visible_ids == {first.id, second.id}
    assert all(item.epistemic_state == "hypothesized" for item in feed)
    first_item = next(item for item in feed if item.entity_id == first.id)
    assert first_item.relation_type == "possible_match"
    assert "A public test need" in first_item.title
    assert "Verified test actor" in first_item.title
    second_item = next(item for item in feed if item.entity_id == second.id)
    assert "Recorded outcome" in second_item.title
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
    client, cleanup = _client(db)
    try:
        public_connections = client.get("/public/connections")
        assert public_connections.status_code == 200, public_connections.text
        assert {item["id"] for item in public_connections.json()} == {first.id, second.id}
    finally:
        cleanup()
    all_public_evidence_ids = {
        relation.entity_id
        for item in feed
        for relation in item.relations
        if relation.entity_type == "evidence"
    }
    assert private_evidence.id not in all_public_evidence_ids
    assert "hidden endpoint connection" not in str(feed)


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


def test_public_feed_preserves_outcome_verification_state(db):
    for verification_state in ("REPORTED", "VERIFIED", "DISPUTED"):
        db.add(models.Outcome(
            source="domain_record",
            outcome_type="QUALITATIVE",
            qualitative_result=f"{verification_state.lower()} outcome note.",
            verification_state=verification_state,
            data_scope="REAL",
        ))
    db.commit()

    items = public_feed.build_public_feed(db, kind="outcome", limit=10)
    states = {item.status: item.epistemic_state for item in items}

    assert states == {
        "reported": "reported_outcome",
        "verified": "verified_outcome",
        "disputed": "disputed_outcome",
    }
