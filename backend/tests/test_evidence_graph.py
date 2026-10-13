import pytest
from fastapi import HTTPException

from app import models, schemas
from app.api import opportunities as opportunities_api
from app.services import evidence_graph, opportunity_engine
from app.services.observer_engine import ObserverEngine


def test_claim_evidence_graph_is_persistent_and_deduplicated(db):
    observer = ObserverEngine(db)
    signal = observer.observe(
        "Small contractors lose hours manually scheduling repairs.",
        source="rss",
        metadata={
            "url": "https://example.test/repair/1",
            "external_id": "repair-1",
            "title": "Repair scheduling pain",
        },
    )
    evidence = db.query(models.Evidence).filter_by(signal_id=signal.id).one()
    opportunity = opportunity_engine.opportunity_from_idea(
        db, "Small contractors lose hours manually scheduling repairs."
    )
    claim, created = evidence_graph.create_or_get_claim(
        db,
        "Small contractors experience a recurring scheduling problem.",
        opportunity_id=opportunity.id,
        provenance={"signal_id": signal.id},
    )

    edge, edge_created = evidence_graph.link_evidence(
        db, evidence, claim=claim, relation_type="supports"
    )
    duplicate_edge, duplicate_created = evidence_graph.link_evidence(
        db, evidence, claim=claim, relation_type="supports"
    )

    assert created is True
    assert edge_created is True
    assert duplicate_created is False
    assert duplicate_edge.id == edge.id
    assert edge.idempotency_key == edge.relation_key
    assert db.query(models.Claim).count() == 1
    assert db.query(models.EvidenceRelationship).count() == 1
    assert db.get(models.Claim, claim.id).epistemic_state == "supported"

    for relation_type in ("duplicates", "derived_from", "translated_from", "summarizes", "updates", "supersedes"):
        evidence_graph.link_evidence(db, evidence, claim=claim, relation_type=relation_type)
    assert {
        edge.relation_type
        for edge in db.query(models.EvidenceRelationship).filter_by(evidence_id=evidence.id).all()
    } == {"supports", "duplicates", "derived_from", "translated_from", "summarizes", "updates", "supersedes"}

    claim_id, edge_id = claim.id, edge.id
    db.expunge_all()
    restored_claim = db.get(models.Claim, claim_id)
    restored_edge = db.get(models.EvidenceRelationship, edge_id)
    assert restored_claim.statement.startswith("Small contractors")
    assert restored_edge.relation_type == "supports"



def test_claim_state_cannot_be_promoted_by_claim_creation_argument(db):
    with pytest.raises(ValueError, match="only creates observed claims"):
        evidence_graph.create_or_get_claim(
            db,
            "A claim cannot become supported from a state string alone.",
            epistemic_state="supported",
        )
    assert db.query(models.Claim).count() == 0

    claim, created = evidence_graph.create_or_get_claim(
        db, "A claim cannot become supported from a state string alone."
    )
    assert created is True
    assert claim.epistemic_state == "observed"

    with pytest.raises(ValueError, match="only creates observed claims"):
        evidence_graph.create_or_get_claim(
            db,
            claim.statement,
            epistemic_state="contested",
        )
    with pytest.raises(ValueError, match="matching evidence relationship"):
        evidence_graph.set_claim_state(db, claim, "supported")
    with pytest.raises(ValueError, match="dedicated verified-outcome"):
        evidence_graph.set_claim_state(db, claim, "verified")

    evidence = models.Evidence(
        source="TEST reviewed assessment",
        content="TEST separately assessed evidence for the claim.",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    evidence_graph.link_evidence(db, evidence, claim=claim, relation_type="supports")
    assert claim.epistemic_state == "supported"
    with pytest.raises(ValueError, match="cannot be downgraded"):
        evidence_graph.set_claim_state(db, claim, "observed")
    db.refresh(claim)
    assert claim.epistemic_state == "supported"


def test_owner_claim_api_requires_evidence_for_semantic_state_and_checks_before_write(db, monkeypatch):
    opportunity = models.Opportunity(
        problem="TEST claim API must preserve epistemic evidence boundaries."
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    monkeypatch.setattr(opportunities_api, "require_owner_api_key", lambda _request: None)

    unsupported_without_evidence = schemas.ClaimCreate(
        statement="TEST unsupported state must not persist",
        epistemic_state="supported",
        relation_type="supports",
    )
    with pytest.raises(HTTPException) as no_evidence_error:
        opportunities_api.create_opportunity_claim(
            opportunity.id, unsupported_without_evidence, object(), db
        )
    assert no_evidence_error.value.status_code == 422
    assert db.query(models.Claim).count() == 0

    nonexistent_evidence = schemas.ClaimCreate(
        statement="TEST missing evidence must not leave a partial claim",
        epistemic_state="supported",
        evidence_id=987654321,
        relation_type="supports",
    )
    with pytest.raises(HTTPException) as missing_evidence_error:
        opportunities_api.create_opportunity_claim(
            opportunity.id, nonexistent_evidence, object(), db
        )
    assert missing_evidence_error.value.status_code == 404
    assert db.query(models.Claim).count() == 0

    evidence = models.Evidence(
        source="TEST owner-reviewed source",
        content="TEST source reviewed for this specific claim.",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    supported_payload = schemas.ClaimCreate(
        statement="TEST this claim has an explicit reviewed supporting relation",
        epistemic_state="supported",
        evidence_id=evidence.id,
        relation_type="supports",
    )
    claim = opportunities_api.create_opportunity_claim(
        opportunity.id, supported_payload, object(), db
    )
    assert claim.epistemic_state == "supported"
    edge = db.query(models.EvidenceRelationship).filter_by(
        claim_id=claim.id, evidence_id=evidence.id
    ).one()
    assert edge.relation_type == "supports"


def test_provenance_keyed_evidence_creation_is_idempotent(db):
    first, first_created = evidence_graph.get_or_create_evidence(
        db,
        provenance_hash="feed:bulletin:42",
        source="public bulletin",
        content="A source observation with preserved provenance.",
        provenance={"url": "https://example.gov/bulletin/42"},
    )
    repeated, repeated_created = evidence_graph.get_or_create_evidence(
        db,
        provenance_hash="feed:bulletin:42",
        source="public bulletin",
        content="A source observation with preserved provenance.",
        provenance={"url": "https://example.gov/bulletin/42"},
    )

    assert first_created is True
    assert repeated_created is False
    assert repeated.id == first.id
    assert first.idempotency_key == "evidence-provenance:feed:bulletin:42"
    assert db.query(models.Evidence).filter_by(idempotency_key=first.idempotency_key).count() == 1
    with pytest.raises(ValueError, match="provenance hash collision"):
        evidence_graph.get_or_create_evidence(
            db,
            provenance_hash="feed:bulletin:42",
            source="public bulletin",
            content="Different content cannot reuse the same provenance identity.",
            provenance={"url": "https://example.gov/bulletin/42"},
        )


def test_duplicate_source_address_is_restored_onto_the_original(db):
    original = models.Signal(
        source="rss",
        content="A stored article about a local parts shortage.",
        source_type="external",
        canonical_url=None,
    )
    db.add(original)
    db.commit()
    duplicate = models.Signal(
        source="rss",
        content=original.content,
        source_type="external",
        canonical_url="https://example.test/parts-shortage",
        is_duplicate_of=original.id,
    )
    db.add(duplicate)
    db.commit()
    assert evidence_graph.restore_source_addresses(db, limit=10) == 1
    db.refresh(original)
    assert original.canonical_url == "https://example.test/parts-shortage"
    assert evidence_graph.restore_source_addresses(db, limit=10) == 0


def test_unclaimed_external_signal_becomes_an_observation(db):
    observer = ObserverEngine(db)
    signal = observer.observe(
        "A paper reports a measurement. Forge has not checked it.",
        source="arxiv",
        metadata={"url": "https://example.test/paper", "title": "A measurement"},
    )
    linked = evidence_graph.link_unclaimed_observations(db, limit=5)
    assert len(linked) == 1
    claim = db.query(models.Claim).one()
    assert claim.epistemic_state == "observed"
    assert "not checked" in claim.statement
    again = evidence_graph.link_unclaimed_observations(db, limit=5)
    assert again == []
    assert db.query(models.Claim).count() == 1
    assert signal.canonical_url == "https://example.test/paper"


def test_distinct_external_signals_link_to_claims_but_unaddressed_signal_stays_private(db):
    observer = ObserverEngine(db)
    first = observer.observe(
        "A Kathmandu repair shop reports missed appointments during monsoon season.",
        source="rss",
        metadata={"url": "https://example.test/one", "title": "One"},
    )
    second = observer.observe(
        "A software maintainer reports that release notes are difficult to coordinate across repositories.",
        source="github",
        metadata={"url": "https://example.test/two", "title": "Two"},
    )
    private = observer.observe(
        "An unaddressed report mentions an internal scheduling concern.",
        source="manual",
        metadata={"title": "No source address"},
    )

    linked = evidence_graph.link_unclaimed_observations(db, limit=20)

    assert len(linked) == 2
    assert len({claim_id for claim_id in linked}) == 2
    assert first.canonical_url and second.canonical_url
    assert private.canonical_url is None


def test_contradiction_changes_claim_state_without_fabricating_confidence(db):
    observer = ObserverEngine(db)
    supporting_signal = observer.observe(
        "Contractors manually schedule repairs every week.",
        source="rss",
        metadata={"url": "https://example.test/support", "external_id": "support"},
    )
    contradicting_signal = observer.observe(
        "Contractors use an automated scheduler and do not manually schedule repairs.",
        source="github",
        metadata={"url": "https://example.test/contradict", "external_id": "contradict"},
    )
    support = db.query(models.Evidence).filter_by(signal_id=supporting_signal.id).one()
    contradiction = db.query(models.Evidence).filter_by(signal_id=contradicting_signal.id).one()
    claim, _ = evidence_graph.create_or_get_claim(db, "Contractors manually schedule repairs.")

    evidence_graph.link_evidence(db, support, claim=claim, relation_type="supports")
    evidence_graph.link_evidence(db, contradiction, claim=claim, relation_type="contradicts")

    persisted = db.get(models.Claim, claim.id)
    assert persisted.epistemic_state == "contested"
    assert persisted.confidence is None
    assert db.query(models.EvidenceRelationship).filter_by(claim_id=claim.id).count() == 2



def test_new_support_does_not_erase_existing_contradiction(db):
    observer = ObserverEngine(db)
    supporting_signal = observer.observe(
        "TEST source states the claim is true.",
        source="reviewed-support",
        metadata={"url": "https://example.test/legacy-support"},
    )
    contradicting_signal = observer.observe(
        "TEST earlier source states the claim is false.",
        source="reviewed-contradiction",
        metadata={"url": "https://example.test/legacy-contradiction"},
    )
    support = db.query(models.Evidence).filter_by(signal_id=supporting_signal.id).one()
    contradiction = db.query(models.Evidence).filter_by(signal_id=contradicting_signal.id).one()
    claim, _ = evidence_graph.create_or_get_claim(db, "TEST a claim with legacy contradiction.")

    # Simulate an older/inconsistent graph row that predates the guarded
    # transition logic. New support must reconcile with, not erase, that fact.
    db.add(models.EvidenceRelationship(
        evidence_id=contradiction.id,
        claim_id=claim.id,
        relation_type="contradicts",
        relation_key="legacy-contradiction-edge",
        idempotency_key="legacy-contradiction-edge",
    ))
    db.commit()

    evidence_graph.link_evidence(db, support, claim=claim, relation_type="supports")

    db.refresh(claim)
    assert claim.epistemic_state == "contested"
    assert db.query(models.EvidenceRelationship).filter_by(
        claim_id=claim.id, relation_type="contradicts"
    ).count() == 1
    assert db.query(models.EvidenceRelationship).filter_by(
        claim_id=claim.id, relation_type="supports"
    ).count() == 1


def test_opportunity_trace_explains_why_it_exists(db):
    observer = ObserverEngine(db)
    signal = observer.observe(
        "Small contractors lose hours manually scheduling repairs.",
        source="rss",
        metadata={"url": "https://example.test/trace", "external_id": "trace"},
    )
    evidence = db.query(models.Evidence).filter_by(signal_id=signal.id).one()
    opportunity = opportunity_engine.opportunity_from_idea(db, "Small contractors lose hours scheduling repairs")
    claim, _ = evidence_graph.create_or_get_claim(
        db,
        "Small contractors lose productive time to repair scheduling.",
        opportunity_id=opportunity.id,
    )
    evidence_graph.link_evidence(db, evidence, claim=claim, relation_type="supports")

    trace = evidence_graph.trace_opportunity(db, opportunity.id)

    assert trace is not None
    assert trace["opportunity"].id == opportunity.id
    assert trace["claims"][0].epistemic_state == "supported"
    assert trace["why"][0]["evidence"][0]["canonical_url"] == "https://example.test/trace"


def test_evidence_links_to_decision_experiment_and_outcome(db):
    observer = ObserverEngine(db)
    signal = observer.observe(
        "Contractors manually schedule repairs every week.",
        source="rss",
        metadata={"url": "https://example.test/closed-loop", "external_id": "closed-loop"},
    )
    evidence = db.query(models.Evidence).filter_by(signal_id=signal.id).one()
    opportunity = opportunity_engine.opportunity_from_idea(db, "Contractors manually schedule repairs")
    decision = models.Decision(
        opportunity_id=opportunity.id,
        title="Test scheduling demand",
        rationale="The evidence indicates a recurring problem.",
    )
    db.add(decision)
    db.flush()
    experiment = models.Experiment(
        opportunity_id=opportunity.id,
        action="Interview contractors",
        hypothesis="Contractors will confirm the scheduling problem.",
    )
    db.add(experiment)
    db.flush()
    outcome = models.Outcome(
        experiment_id=experiment.id,
        decision_id=decision.id,
        outcome_type="QUALITATIVE",
        qualitative_result="Two contractors confirmed the problem.",
        source="interview",
    )
    db.add(outcome)
    db.commit()

    evidence_graph.link_evidence(db, evidence, opportunity_id=opportunity.id, relation_type="derived_from")
    evidence_graph.link_evidence(db, evidence, decision_id=decision.id, relation_type="updates")
    evidence_graph.link_evidence(db, evidence, experiment_id=experiment.id, relation_type="summarizes")
    evidence_graph.link_evidence(db, evidence, outcome_id=outcome.id, relation_type="supports")

    edges = db.query(models.EvidenceRelationship).filter_by(evidence_id=evidence.id).all()
    assert {edge.opportunity_id for edge in edges if edge.opportunity_id} == {opportunity.id}
    assert {edge.decision_id for edge in edges if edge.decision_id} == {decision.id}
    assert {edge.experiment_id for edge in edges if edge.experiment_id} == {experiment.id}
    assert {edge.outcome_id for edge in edges if edge.outcome_id} == {outcome.id}
