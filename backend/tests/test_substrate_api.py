undefined

def test_global_frontier_is_cross_domain_diversified_and_read_only(substrate_client, db):
    # This question is intentionally not a Bet or commercial opportunity.
    question = models.ResearchQuestion(
        question="What interventions reduce groundwater salinity in coastal wetlands?",
        status="open",
        priority_score=87.0,
    )
    db.add(question)
    db.flush()
    task = models.ResearchTask(
        question_id=question.id,
        source="crossref",
        query="groundwater salinity coastal wetlands",
        status="planned",
        objective="Find attributable research on coastal groundwater salinity.",
    )
    db.add(task)
    world_graph.create_capability(
        db,
        capability_type="workflow",
        name="TEST coastal observation integration",
        description="TEST-only example of an unverified observation capability.",
        owner_agent="test-agent",
        attributes={"provides": ["observation.coastal_groundwater"]},
    )
    db.commit()

    # Exercise real persisted open-world findings as part of the same projection.
    report = __import__(
        "app.services.discovery_engine", fromlist=["run_discovery"]
    ).run_discovery(db, methods=["ignorance_map"], persist=True)
    db.commit()
    assert report["surfaced"]

    before = {
        model.__name__: db.query(model).count()
        for model in (
            models.SubstrateEntity, models.WorldRelation, models.WorldEvent,
            models.Evidence, models.ForgeCapability, models.ResearchQuestion,
            models.ResearchTask, models.Outcome, models.Opportunity,
        )
    }
    response = substrate_client.get("/forge/substrate/discovery/frontier", params={"limit": 12})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["read_only"] is True
    assert body["selection_method"] == "round_robin_by_record_kind"
    assert len(body["items"]) <= 12
    assert body["candidate_count_scanned"] >= len(body["items"])
    assert "not a measure of total world value" in body["boundary"]

    refs = {item["record_type"] for item in body["items"]}
    assert "research_question" in refs
    assert "research_task" in refs
    assert "capability" in refs
    assert "discovery_finding" in refs
    assert any(
        item["record_type"] == "research_question"
        and "groundwater salinity" in item["title"]
        for item in body["items"]
    )
    # This projection must not create a Bet, commercial opportunity, task,
    # finding, event, evidence record, or any other side effect on read.
    after = {
        model.__name__: db.query(model).count()
        for model in (
            models.SubstrateEntity, models.WorldRelation, models.WorldEvent,
            models.Evidence, models.ForgeCapability, models.ResearchQuestion,
            models.ResearchTask, models.Outcome, models.Opportunity,
        )
    }
    assert after == before
