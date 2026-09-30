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
