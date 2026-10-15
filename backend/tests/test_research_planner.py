from sqlalchemy import event

from app import models
from app.services import research_planner


def test_unrelated_questions_get_general_subquestions_and_only_cleared_sources(db):
    questions = [
        models.ResearchQuestion(
            question="What are the measured postharvest losses for smallholder farmers in Nepal?"
        ),
        models.ResearchQuestion(
            question="Do independent bicycle repair shops lose customers because of missed appointments?"
        ),
    ]
    db.add_all(questions)
    db.commit()

    plans = [research_planner.build_research_plan(db, question) for question in questions]
    planned_tasks = [
        research_planner.plan_tasks_for_question(db, question)
        for question in questions
    ]

    assert len(plans[0]["orchestration_requirements"]) == 5
    assert len(plans[1]["subquestions"]) == 5
    assert all(plan["subquestions"] != plans[1 - index]["subquestions"] for index, plan in enumerate(plans))
    assert all("not external evidence" in plan["assumptions"][0] for plan in plans)
    assert all(
        next(source for source in plan["candidate_sources"] if source["source"] == "crossref")["available"]
        for plan in plans
    )
    assert all(
        not next(source for source in plan["candidate_sources"] if source["source"] == "web_search")["available"]
        for plan in plans
    )
    assert all(
        not next(source for source in plan["candidate_sources"] if source["source"] == "direct_web")["available"]
        for plan in plans
    )
    assert len(planned_tasks[0]) == 3
    assert {task.source for task in planned_tasks[0]} == {
        "openalex",
        "world_bank_indicators",
    }
    assert len(planned_tasks[1]) == 1
    assert planned_tasks[1][0].source == "crossref"
    assert any(
        item["capable_sources"]
        for item in plans[0]["requirements"]
        if item["id"] == "scholarly_evidence"
    )
    assert next(
        item
        for item in plans[1]["requirements"]
        if item["id"] == "bibliographic_discovery"
    )["capable_sources"]
    assert all(
        not next(item for item in plan["requirements"] if item["id"] == "buyer_willingness_to_pay")[
            "capable_sources"
        ]
        for plan in plans
    )


def test_prior_external_evidence_is_reused_as_unverified_context(db):
    signal = models.Signal(
        source="crossref",
        source_type="external",
        content="Measured postharvest loss among smallholder farmers in Nepal.",
        title="Postharvest loss measurement",
        canonical_url="https://doi.org/10.1234/postharvest",
        retrieved_at=models.utcnow(),
    )
    db.add(signal)
    db.flush()
    evidence = models.Evidence(
        signal_id=signal.id,
        source=signal.source,
        content=signal.content,
        canonical_url=signal.canonical_url,
    )
    question = models.ResearchQuestion(
        question="What evidence measures postharvest loss among smallholder farmers?"
    )
    db.add_all([evidence, question])
    db.commit()

    plan = research_planner.build_research_plan(db, question)

    assert plan["known_observations"]
    observation = plan["known_observations"][0]
    assert observation["evidence_id"] == evidence.id
    assert observation["url"] == signal.canonical_url
    assert observation["epistemic_status"] == "prior_observation_unverified"




def test_tokens_support_devanagari_romanized_nepali_short_terms_and_unicode_normalization():
    devanagari = research_planner._tokens("नेपालको कृषि बजारमा QR भुक्तानी")
    assert {"नेपालको", "कृषि", "बजारमा", "qr", "भुक्तानी"} <= devanagari
    assert "qr" in research_planner._tokens("Nepali QR payments")
    assert {"nepal", "krishi", "bazar", "qr"} <= research_planner._tokens("Nepal ko krishi bazar QR")
    assert not ({"the", "and", "to", "मा", "र", "को", "ko", "ra"} &
                research_planner._tokens("the and to मा र को ko ra"))
    # CJK/Japanese/Korean runs use bigrams so longer source text can overlap a query.
    assert {"世界", "物流"} <= (
        research_planner._tokens("世界物流") & research_planner._tokens("世界经济物流")
    )
    assert research_planner._tokens("नेपाल  कृषि") == research_planner._tokens("नेपाल कृषि")


def test_prior_external_evidence_matches_devanagari_and_short_terms(db):
    text = "नेपालको कृषि बजार QR भुक्तानी"
    signal = models.Signal(
        source="public_web",
        source_type="external",
        content=f"{text} सम्बन्धी सार्वजनिक अवलोकन।",
        title=text,
        canonical_url="https://example.test/nepali-market",
        retrieved_at=models.utcnow(),
    )
    db.add(signal)
    db.flush()
    evidence = models.Evidence(
        signal_id=signal.id,
        source=signal.source,
        content=signal.content,
        canonical_url=signal.canonical_url,
    )
    db.add(evidence)
    db.commit()

    observations = research_planner._prior_observations(db, text, limit=5)

    assert len(observations) == 1
    assert observations[0]["signal_id"] == signal.id
    assert observations[0]["evidence_id"] == evidence.id
    assert observations[0]["matched_term_fraction"] == 1.0
    assert observations[0]["weighted_match_score"] == 1.0
    assert observations[0]["ranking_method"] == "inverse_document_frequency_weighted_lexical"
    assert observations[0]["epistemic_status"] == "prior_observation_unverified"
    assert observations[0]["matching_is_not_semantic_relevance"] is True



def test_prior_observations_rank_distinctive_terms_above_common_overlap(db):
    question = "Nepal agriculture QR outage"
    signals = []
    # Several recent records share three broad terms but not the decisive term.
    for index in range(12):
        signal = models.Signal(
            source="public_web",
            source_type="external",
            content="Nepal agriculture QR",
            title=f"Nepal agriculture QR record {index}",
            canonical_url=f"https://example.test/common-{index}",
            retrieved_at=models.utcnow(),
        )
        db.add(signal)
        db.flush()
        db.add(models.Evidence(
            signal_id=signal.id,
            source=signal.source,
            content=signal.content,
            canonical_url=signal.canonical_url,
        ))
        signals.append(signal)

    distinctive = models.Signal(
        source="public_web",
        source_type="external",
        content="Nepal outage",
        title="Nepal outage",
        canonical_url="https://example.test/distinctive-outage",
        retrieved_at=models.utcnow(),
    )
    db.add(distinctive)
    db.flush()
    distinctive_evidence = models.Evidence(
        signal_id=distinctive.id,
        source=distinctive.source,
        content=distinctive.content,
        canonical_url=distinctive.canonical_url,
    )
    db.add(distinctive_evidence)
    db.commit()

    observations = research_planner._prior_observations(db, question, limit=5)

    assert observations
    assert observations[0]["signal_id"] == distinctive.id
    assert observations[0]["evidence_id"] == distinctive_evidence.id
    assert observations[0]["matched_term_fraction"] == 0.5
    assert observations[0]["weighted_match_score"] > observations[1]["weighted_match_score"]
    assert observations[0]["matching_is_not_semantic_relevance"] is True



def test_prior_observations_skip_evidence_less_top_hits_to_fill_limit(db):
    question = "Nepal outage"

    for index in range(5):
        db.add(models.Signal(
            source="public_web",
            source_type="external",
            content="Nepal outage reported",
            title=f"Nepal outage result {index}",
            canonical_url=f"https://example.test/no-evidence-{index}",
            retrieved_at=models.utcnow(),
        ))

    eligible = models.Signal(
        source="public_web",
        source_type="external",
        content="Nepal outage reported",
        title="Nepal outage with linked evidence",
        canonical_url="https://example.test/eligible-evidence",
        retrieved_at=models.utcnow(),
    )
    db.add(eligible)
    db.flush()
    evidence = models.Evidence(
        signal_id=eligible.id,
        source=eligible.source,
        content=eligible.content,
        canonical_url=eligible.canonical_url,
    )
    db.add(evidence)
    db.commit()

    evidence_selects = {"count": 0}

    def count_evidence_selects(conn, cursor, statement, parameters, context, executemany):
        normalized_sql = " ".join(statement.casefold().split())
        if normalized_sql.startswith("select") and " from evidence" in normalized_sql:
            evidence_selects["count"] += 1

    event.listen(db.get_bind(), "before_cursor_execute", count_evidence_selects)
    try:
        observations = research_planner._prior_observations(db, question, limit=1)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count_evidence_selects)

    assert len(observations) == 1
    assert evidence_selects["count"] == 1
    assert observations[0]["signal_id"] == eligible.id
    assert observations[0]["evidence_id"] == evidence.id
    assert observations[0]["epistemic_status"] == "prior_observation_unverified"

def test_linked_claim_evidence_is_reused_by_reference_without_truth_upgrade(db):
    from app.services import research_planner

    claim = models.Claim(
        statement="Repair shops repeatedly reschedule appointments.",
        normalized_statement="repair shops repeatedly reschedule appointments",
        epistemic_state="contested",
    )
    public_signal = models.Signal(
        source="crossref",
        source_type="external",
        content="A study describes scheduling constraints in repair businesses.",
        title="Scheduling constraints",
        canonical_url="https://doi.org/10.1234/scheduling",
        retrieved_at=models.utcnow(),
    )
    restricted_signal = models.Signal(
        source="rss",
        source_type="external",
        content="A participant describes scheduling constraints in repair businesses.",
        title="Participant scheduling account",
        canonical_url="https://example.test/restricted-scheduling",
        retrieved_at=models.utcnow(),
    )
    db.add_all([claim, public_signal, restricted_signal])
    db.flush()

    reusable = models.Evidence(
        signal_id=public_signal.id,
        source="crossref",
        content=public_signal.content,
        title=public_signal.title,
        canonical_url=public_signal.canonical_url,
        source_kind="MOCK",
    )
    restricted = models.Evidence(
        signal_id=restricted_signal.id,
        source="rss",
        content=restricted_signal.content,
        title=restricted_signal.title,
        canonical_url=restricted_signal.canonical_url,
        source_identity="identified-participant",
        consent_status="granted",
        source_kind="REAL",
    )
    db.add_all([reusable, restricted])
    db.flush()
    db.add_all([
        models.EvidenceRelationship(
            evidence_id=reusable.id,
            claim_id=claim.id,
            relation_type="supports",
            relation_key="test-linked-reusable-evidence",
        ),
        models.EvidenceRelationship(
            evidence_id=restricted.id,
            claim_id=claim.id,
            relation_type="supports",
            relation_key="test-linked-restricted-evidence",
        ),
    ])
    question = models.ResearchQuestion(
        question="What further evidence tests appointment rescheduling constraints?",
        source_claim_id=claim.id,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    plan = research_planner.build_research_plan(db, question)
    linked = [
        item for item in plan["known_observations"]
        if item.get("reuse_mode") == "reference_only"
    ]

    assert len(linked) == 1
    assert linked[0]["evidence_id"] == reusable.id
    assert linked[0]["related_claim_id"] == claim.id
    assert linked[0]["recorded_relationship"] == "supports"
    assert linked[0]["source_kind"] == "MOCK"
    assert linked[0]["epistemic_status"] == "linked_claim_context_unverified"
    assert linked[0]["link_is_not_independent_verification"] is True
    assert "content" not in linked[0]
    assert all(item.get("evidence_id") != restricted.id for item in plan["known_observations"])
    assert db.get(models.Claim, claim.id).epistemic_state == "contested"


def test_gap_questions_are_not_planned_for_external_collectors(db):
    gap = models.ResearchQuestion(
        question='Gap: open job #1 "repair" has no recorded counterparty.'
    )
    normal = models.ResearchQuestion(question="What evidence describes repair demand?")
    db.add_all([gap, normal])
    db.commit()

    tasks = research_planner.plan_tasks_for_open_questions(db)

    assert tasks
    assert all(task.question_id == normal.id for task in tasks)
    assert db.query(models.ResearchTask).filter_by(question_id=gap.id).count() == 0
    assert db.get(models.ResearchQuestion, gap.id).status == "open"


def test_gap_questions_do_not_fill_the_planning_limit(db):
    for index in range(20):
        db.add(
            models.ResearchQuestion(
                question=f'Gap: open job #{index} "repair" has no recorded counterparty.',
                priority_score=100.0,
                status="open",
            )
        )
    real = models.ResearchQuestion(
        question="What evidence describes repair demand?",
        priority_score=1.0,
        status="open",
    )
    db.add(real)
    db.commit()

    tasks = research_planner.plan_tasks_for_open_questions(db, limit=20)

    assert tasks
    assert all(task.question_id == real.id for task in tasks)
    assert db.get(models.ResearchQuestion, real.id).status == "planned"
    assert db.query(models.ResearchTask).count() == len(tasks)
