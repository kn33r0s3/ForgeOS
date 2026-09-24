from app import models
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
