from app import models
from app.services import forge_loop, public_feed
from app.services.observer_engine import ObserverEngine


def test_canonical_cycle_links_external_evidence_into_public_network(db):
    texts = [
        "At least 12 restaurants in Kathmandu still take phone orders and write them on paper tickets. Managers report 3-5 wrong dishes per busy night, losing roughly NPR 8000-15000 each weekend.",
        "Restaurant managers in Kathmandu report that paper kitchen tickets get lost every Friday night. One owner counted 7 lost tickets last week, leading to angry customers who refused to pay for 4 orders.",
        "Three cafe owners near Thamel still use handwritten order pads. Staff make mistakes on 15 percent of orders according to their own count. Customers complain about wrong dishes at least twice per week.",
        "A restaurant owner in Lazimpat said they lose about NPR 12000 every weekend because phone orders are miswritten and kitchen tickets are illegible. They tried hiring more staff but the paper process remains the bottleneck.",
        "Small restaurants need a simple digital order system. Manual phone-to-paper process creates constant operational friction: 5 restaurants interviewed last month all reported the same problem of lost tickets and misheard phone orders.",
    ]
    observer = ObserverEngine(db)
    signals = [
        observer.observe(
            text,
            source="pytest-external-fixture",
            metadata={
                "source_type": "external",
                "canonical_url": f"https://evidence.example.test/notice/{index}",
                "provenance": {"fixture": "pytest; no network fetch occurred"},
            },
        )
        for index, text in enumerate(texts, start=1)
    ]
    source_evidence_ids = {
        signal.id: db.query(models.Evidence.id)
        .filter_by(signal_id=signal.id)
        .order_by(models.Evidence.id.desc())
        .first()[0]
        for signal in signals
    }
    need = models.DomainRecord(
        kind="job",
        title="A work item without a recorded counterparty",
        detail="This fixture checks the internal network pass without adding a real person.",
        status="open",
        close_token_hash="test-token-hash",
    )
    db.add(need)
    db.commit()

    summary = forge_loop.run_cycle(db)

    claims = db.query(models.Claim).order_by(models.Claim.id).all()
    assert len(claims) == len(signals)
    assert set(summary["claims_linked"]) == {claim.id for claim in claims}
    for signal in signals:
        evidence = db.get(models.Evidence, source_evidence_ids[signal.id])
        relationship = db.query(models.EvidenceRelationship).filter_by(
            evidence_id=evidence.id,
            relation_type="derived_from",
        ).one()
        assert relationship.id is not None
        claim = db.get(models.Claim, relationship.claim_id)
        assert claim.epistemic_state == "observed"
    assert summary["network_connection_ids"] == []
    assert summary["patterns_found"] >= 1
    assert summary["beliefs_updated"] >= 1
    assert summary["opportunities_discovered"] >= 1
    assert summary["opportunity_questions_linked"] >= 1
    assert db.query(models.ResearchQuestion).filter(
        models.ResearchQuestion.question.like(f"Gap: open job #{need.id}%")
    ).one().status == "open"
    linked_claim_ids = {
        row[0]
        for row in db.query(models.ResearchQuestion.source_claim_id)
        .filter(models.ResearchQuestion.source_claim_id.isnot(None))
        .all()
    }
    assert linked_claim_ids & {claim.id for claim in claims}

    feed = public_feed.build_public_feed(db)
    feed_refs = {(item.entity_type, item.entity_id) for item in feed}
    assert all(("claim", claim.id) in feed_refs for claim in claims)
    assert any(item.entity_type == "pattern" for item in feed)
    assert any(item.entity_type == "belief" for item in feed)
    opportunity_item = next(item for item in feed if item.entity_type == "opportunity")
    assert any(
        relation.entity_type == "claim" and relation.entity_id in linked_claim_ids
        for relation in opportunity_item.relations
    )

    repeated = forge_loop.run_cycle(db)
    assert repeated["claims_linked"] == []
    assert repeated["opportunity_questions_linked"] == 0
    assert db.query(models.Claim).count() == len(signals)
    assert db.query(models.ResearchQuestion).filter(
        models.ResearchQuestion.source_claim_id.in_(linked_claim_ids)
    ).count() == len(linked_claim_ids)
