from fastapi.testclient import TestClient
import pytest

from app import models
from app.database import get_db
from app.main import app
from app.services import network_connections, network_substrate_adapter, public_network, world_graph


def _client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), lambda: app.dependency_overrides.clear()


def _public_signal_claim(db):
    signal = models.Signal(
        source="public bulletin",
        source_type="external",
        canonical_url="https://example.gov/network-test",
        title="Public infrastructure notice",
        content="A public bulletin describes an infrastructure change.",
        retrieved_at=models.utcnow(),
    )
    db.add(signal)
    db.flush()
    claim = models.Claim(
        statement="The bulletin reports an infrastructure change.",
        normalized_statement="bulletin reports infrastructure change",
        epistemic_state="observed",
    )
    evidence = models.Evidence(
        signal_id=signal.id,
        source="public bulletin",
        content=signal.content,
        canonical_url=signal.canonical_url,
    )
    db.add_all([claim, evidence])
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim.id,
        relation_type="supports",
        relation_key=f"public-network-claim:{claim.id}:evidence:{evidence.id}",
    ))
    db.flush()
    return signal, evidence



def test_new_network_connections_cannot_self-declare_supported_truth(db):
    need = models.DomainRecord(
        kind="job", title="TEST candidate request", detail="A possible need.",
        close_token_hash="test-candidate-hash", status="open",
    )
    provider = models.Provider(
        name="TEST possible provider", country="Nepal",
        public_visible=True, is_active=True, verification_status="verified",
    )
    evidence = models.Evidence(
        source="test_fixture_observation",
        content="A row existing in the database is not, by itself, a reviewed support assessment.",
        canonical_url="https://example.test/network-evidence",
        provenance='{"test_fixture": true}',
    )
    db.add_all([need, provider, evidence])
    db.commit()
    before = db.query(models.NetworkConnection).count()

    for asserted_state in ("tested", "supported", "refuted"):
        with pytest.raises(
            ValueError,
            match="new connections must begin possible or hypothesized",
        ):
            network_connections.create_connection(
                db,
                left_kind="domain_record",
                left_id=need.id,
                right_kind="provider",
                right_id=provider.id,
                relation_type="possible_match",
                reason="TEST a state string cannot authenticate its own evidence.",
                epistemic_state=asserted_state,
                evidence_ids=[evidence.id],
            )
        assert db.query(models.NetworkConnection).count() == before

    candidate = network_connections.create_connection(
        db,
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=provider.id,
        relation_type="possible_match",
        reason="A candidate that remains a hypothesis.",
        epistemic_state="hypothesized",
    )
    assert candidate.epistemic_state == "hypothesized"
    assert candidate.state == "candidate"


def test_public_network_traverses_intelligence_relations_with_evidence_and_events(db):
    signal, evidence = _public_signal_claim(db)
    pattern = models.Pattern(
        title="Infrastructure changes recur",
        description="A tentative pattern grounded in a public observation.",
        origin_signal_ids=str(signal.id),
    )
    db.add(pattern)
    db.flush()
    belief = models.Belief(
        statement="Infrastructure changes may create coordination needs.",
        pattern_id=pattern.id,
        supporting_signal_ids=str(signal.id),
    )
    db.add(belief)
    db.commit()

    world_graph.sync_intelligence_path(db, limit=100)
    db.commit()
    counts_before = (
        db.query(models.SubstrateEntity).count(),
        db.query(models.WorldRelation).count(),
        db.query(models.WorldEvent).count(),
        db.query(models.Evidence).count(),
    )
    snapshot = public_network.build_public_network(db, limit=100)
    counts_after = (
        db.query(models.SubstrateEntity).count(),
        db.query(models.WorldRelation).count(),
        db.query(models.WorldEvent).count(),
        db.query(models.Evidence).count(),
    )

    assert counts_after == counts_before
    assert {node.entity_type for node in snapshot.nodes} >= {"signal", "pattern", "belief"}
    assert any(edge.relation_type == "derived_from" for edge in snapshot.edges)
    assert any(edge.relation_type == "informed_by" for edge in snapshot.edges)
    assert any(ref.entity_id == evidence.id for ref in snapshot.evidence_refs)
    assert any(ref.relation.startswith("event:") for ref in snapshot.event_refs)
    public_node_ids = {node.id for node in snapshot.nodes}
    assert all(
        edge.from_entity_id in public_node_ids and edge.to_entity_id in public_node_ids
        for edge in snapshot.edges if edge.graph_source == "substrate"
    )

    client, cleanup = _client(db)
    try:
        response = client.get("/public/network")
        assert response.status_code == 200, response.text
        assert response.json()["edges"]
    finally:
        cleanup()


def test_public_network_uses_connection_adapter_only_until_relation_is_projected(db):
    need = models.DomainRecord(
        kind="job", title="Public test need", detail="An open request.",
        close_token_hash="test-hash", status="open",
    )
    provider = models.Provider(
        name="Verified network provider", country="Nepal", public_visible=True,
        is_active=True, verification_status="verified",
    )
    db.add_all([need, provider])
    db.flush()
    projected = models.NetworkConnection(
        left_kind="domain_record", left_id=need.id,
        right_kind="provider", right_id=provider.id,
        relation_type="offered_by", epistemic_state="hypothesized",
        state="candidate", reason="A visible projected edge.",
        agreement_gap="No agreement is implied.", public_visible=True,
    )
    unprojected = models.NetworkConnection(
        left_kind="domain_record", left_id=need.id,
        right_kind="provider", right_id=provider.id,
        relation_type="possible_match", epistemic_state="possible",
        state="candidate", reason="A visible legacy adapter edge.",
        agreement_gap="No agreement is implied.", public_visible=True,
    )
    hidden = models.NetworkConnection(
        left_kind="domain_record", left_id=need.id,
        right_kind="provider", right_id=provider.id,
        relation_type="possible_match", epistemic_state="hypothesized",
        state="candidate", reason="A private edge between public endpoints.",
        agreement_gap="No agreement is implied.", public_visible=False,
    )
    hidden_evidence = models.Evidence(
        source="private operator note",
        content="Private evidence must not be included in the public graph.",
    )
    db.add_all([projected, hidden, hidden_evidence])
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=hidden_evidence.id,
        network_connection_id=hidden.id,
        relation_type="derived_from",
        relation_key=f"public-network-hidden-evidence:{hidden.id}",
    ))
    db.commit()

    network_substrate_adapter.sync_network_connections(db)
    db.commit()
    # Insert this row after the adapter cycle to exercise migration fallback.
    db.add(unprojected)
    db.commit()
    counts_before = (db.query(models.SubstrateEntity).count(), db.query(models.WorldRelation).count())
    snapshot = public_network.build_public_network(db, limit=100)
    counts_after = (db.query(models.SubstrateEntity).count(), db.query(models.WorldRelation).count())

    assert counts_after == counts_before
    projected_edges = [edge for edge in snapshot.edges if edge.source_ref and edge.source_ref.entity_id == projected.id]
    assert len(projected_edges) == 1
    assert projected_edges[0].graph_source == "substrate"
    assert projected_edges[0].id == f"relation:{projected.relation_id}"
    legacy_edges = [edge for edge in snapshot.edges if edge.source_ref and edge.source_ref.entity_id == unprojected.id]
    assert len(legacy_edges) == 1
    assert legacy_edges[0].graph_source == "legacy_adapter"
    assert all(ref.entity_id != hidden_evidence.id for ref in snapshot.evidence_refs)
    assert all(edge.source_ref.entity_id != hidden.id for edge in snapshot.edges if edge.source_ref)
    assert not any(edge.relation_type == "possible_match" and edge.graph_source == "substrate"
                   for edge in snapshot.edges if edge.source_ref is None)
