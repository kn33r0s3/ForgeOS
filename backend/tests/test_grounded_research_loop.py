from datetime import date, datetime, timezone
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import (
    experiment_service,
    opportunity_engine,
    research_planner,
    research_task_engine,
    source_clearance_registry,
)
from app.services import evidence_graph
from app.services.research_evidence_assessment import assess_source_record


def _planned_question(db, text="Do independent repair shops have appointment-status communication pain?"):
    question = models.ResearchQuestion(question=text)
    db.add(question)
    db.commit()
    db.refresh(question)
    research_planner.plan_tasks_for_question(db, question)
    db.refresh(question)
    return question


def test_zero_result_and_failed_tasks_never_satisfy_research(db):
    question = _planned_question(db)
    task = (
        db.query(models.ResearchTask)
        .filter_by(question_id=question.id, source="crossref")
        .one()
    )

    research_task_engine.finish_task(db, task, signal_ids=[], evidence_ids=[])
    research_planner.plan_tasks_for_question(db, question)

    assert task.status in {"planned", "needs_research"}
    assert question.research_plan["status"] != "research_complete"
    assert next(
        row for row in question.research_plan["requirements"]
        if row["id"] == "bibliographic_discovery"
    )["status"] != "satisfied"

    task = db.get(models.ResearchTask, task.id)
    task.status = "failed"
    task.attempts = task.max_attempts
    db.commit()
    research_planner.plan_tasks_for_question(db, question)
    assert question.research_plan["status"] != "research_complete"


def test_unrelated_evidence_does_not_satisfy_bibliographic_requirement(db):
    question = _planned_question(db)
    task = (
        db.query(models.ResearchTask)
        .filter_by(question_id=question.id, source="crossref")
        .one()
    )
    assert task.results["research_requirement_id"] == "bibliographic_discovery"
    evidence = models.Evidence(
        source="unrelated",
        content="This is an unrelated observation.",
        canonical_url="https://example.test/unrelated",
        retrieved_at=datetime.now(timezone.utc),
    )
    db.add(evidence)
    db.flush()
    task.status = "completed"
    task.evidence_ids = str(evidence.id)
    task.results = {**task.results, "source_results": []}
    db.commit()

    research_planner.plan_tasks_for_question(db, question)
    requirement = next(
        row for row in question.research_plan["requirements"]
        if row["id"] == "bibliographic_discovery"
    )

    assert requirement["status"] == "terminal_unresolved"
    assert requirement["terminal_reason"] == "metadata_leads_do_not_establish_content_relevance_or_answer_the_claim"


def test_partial_crossref_lead_creates_idempotent_narrow_follow_up(db):
    question = _planned_question(db)
    task = (
        db.query(models.ResearchTask)
        .filter_by(question_id=question.id, source="crossref")
        .one()
    )
    evidence = models.Evidence(
        source="crossref",
        content="Crossref metadata record: Appointment scheduling in hospitals.",
        title="Appointment scheduling in hospitals",
        canonical_url="https://doi.org/10.1234/hospital",
        external_id="10.1234/hospital",
        retrieved_at=datetime.now(timezone.utc),
        provenance=json.dumps({"metadata_only": True}),
    )
    db.add(evidence)
    db.flush()
    task.status = "completed"
    task.evidence_ids = str(evidence.id)
    task.results = {
        **task.results,
        "source_results": [
            {
                "evidence_id": evidence.id,
                "title": evidence.title,
                "url": evidence.canonical_url,
            }
        ],
    }
    db.commit()

    followups = research_planner.plan_tasks_for_question(db, question)
    again = research_planner.plan_tasks_for_question(db, question)

    assert len(followups) == 1
    assert again == []
    followup = followups[0]
    assert followup.results["follow_up_of_task_id"] == task.id
    assert followup.results["follow_up_depth"] == 1
    assert "Appointment scheduling in hospitals" in followup.query
    assert question.research_plan["status"] == "research_in_progress"


def test_source_capabilities_are_requirement_scoped_and_expiry_checked():
    assert source_clearance_registry.capabilities_for_requirement(
        "problem_incidence",
        today=date(2026, 9, 27),
    ) == ()
    assert source_clearance_registry.capabilities_for_requirement(
        "public_rule_text",
        today=date(2026, 9, 27),
    ) == ()
    crossref = source_clearance_registry.capabilities_for_requirement(
        "bibliographic_discovery",
        today=date(2026, 9, 27),
    )
    assert [entry.registry_id for entry in crossref] == ["crossref-public-works-metadata"]
    assert crossref[0].allowed_operation == "search_bibliographic_metadata"
    assert "abstract" not in crossref[0].allowed_fields


def test_metadata_assessment_is_attributed_but_not_semantic_or_claim_support():
    assessment = assess_source_record(
        "Do independent repair shops have appointment-status communication pain?",
        title="Appointment status in hospitals",
        content="A bibliographic metadata record.",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        retrieved_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        source_identity="10.1234/hospital",
        canonical_url="https://doi.org/10.1234/hospital",
        provenance={
            "metadata_only": True,
            "source_registry_id": "crossref-public-works-metadata",
        },
    )

    assert assessment["assessment_state"] == "metadata_only_lead"
    assert assessment["provenance"]["source_identity"] == "10.1234/hospital"
    assert assessment["semantic_relevance"] == "unassessed"
    assert assessment["claim_support"] == "not_inferred"
    assert assessment["source_reliability"] == "unassessed"


def test_metadata_only_research_cannot_support_claim_or_create_opportunity(db):
    claim = models.Claim(
        statement="Independent repair shops have appointment-status communication pain.",
        normalized_statement="independent repair shops have appointment status communication pain",
        epistemic_state="observed",
    )
    db.add(claim)
    db.flush()
    question = models.ResearchQuestion(
        question="Can Crossref metadata establish repair shop demand?",
        source_claim_id=claim.id,
    )
    db.add(question)
    db.flush()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="crossref",
        query=question.question,
        claim_id=claim.id,
    )
    evidence = models.Evidence(
        source="crossref",
        content="Crossref metadata record: Repair shops and appointments.",
        provenance=json.dumps({"metadata_only": True}),
    )
    db.add(evidence)
    db.flush()
    research_task_engine.finish_task(
        db,
        task,
        signal_ids=[],
        evidence_ids=[evidence.id],
    )

    assert research_task_engine.evaluate_claim_after_research(
        db, task, [evidence.id]
    ) is None
    assert db.get(models.Claim, claim.id).epistemic_state == "observed"
    assert task.results["claim_support"] == "not_inferred"

    signal = models.Signal(
        source="crossref",
        source_type="external",
        content=(
            "Independent repair shops lose $500 monthly due to appointment no-shows "
            "and would pay for a remedy."
        ),
        provenance=json.dumps({"metadata_only": True}),
    )
    db.add(signal)
    db.flush()
    pattern = models.Pattern(
        title="Research pattern",
        description=signal.content,
        frequency=10,
        confidence_score=99,
        origin_signal_ids=str(signal.id),
    )
    db.add(pattern)
    db.commit()

    assert opportunity_engine.generate_opportunity_from_signal_if_strong(db, signal) is None
    assert opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern) is None
    assert db.query(models.Opportunity).count() == 0


def test_explicit_contradiction_relationship_is_preserved(db):
    claim = models.Claim(
        statement="A claim with contradictory evidence.",
        normalized_statement="a claim with contradictory evidence",
        epistemic_state="contested",
    )
    db.add(claim)
    db.flush()
    evidence = models.Evidence(source="reviewed-source", content="An explicit counter-observation.")
    db.add(evidence)
    db.flush()
    evidence_graph.link_evidence(
        db,
        evidence,
        claim=claim,
        relation_type="contradicts",
    )
    db.commit()

    from app.services.research_evidence_assessment import explicit_contradiction_edges

    assert explicit_contradiction_edges(db, [evidence.id]) == [
        {"evidence_id": evidence.id, "claim_id": claim.id}
    ]


def test_research_plan_and_task_survive_database_restart(tmp_path):
    path = tmp_path / "grounded-research.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    question = models.ResearchQuestion(question="A persisted unfamiliar question.")
    session.add(question)
    session.commit()
    session.refresh(question)
    question.research_plan = {
        "status": "research_terminal_unresolved",
        "requirements": [{"id": "problem_incidence", "status": "terminal_unresolved"}],
    }
    task = research_task_engine.create_task(
        session,
        question_id=question.id,
        source="crossref",
        query="A persisted bounded query.",
    )
    question_id, task_id = question.id, task.id
    session.commit()
    session.close()
    engine.dispose()

    reopened_engine = create_engine(f"sqlite:///{path}")
    reopened = sessionmaker(bind=reopened_engine)()
    persisted_question = reopened.get(models.ResearchQuestion, question_id)
    persisted_task = reopened.get(models.ResearchTask, task_id)

    assert persisted_question.research_plan["status"] == "research_terminal_unresolved"
    assert persisted_task.status == "planned"
    reopened.close()
    reopened_engine.dispose()


def test_two_workers_cannot_claim_the_same_persisted_task(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'worker-claim.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    setup = session_factory()
    question = models.ResearchQuestion(question="One task, two concurrent worker claims.")
    setup.add(question)
    setup.commit()
    setup.refresh(question)
    task = research_task_engine.create_task(
        setup,
        question_id=question.id,
        source="crossref",
        query="one durable task",
    )
    task_id = task.id
    setup.close()

    first_worker = session_factory()
    second_worker = session_factory()
    first_task = first_worker.get(models.ResearchTask, task_id)
    stale_second_task = second_worker.get(models.ResearchTask, task_id)

    assert research_task_engine.begin_task(first_worker, first_task) is True
    assert research_task_engine.begin_task(second_worker, stale_second_task) is False
    persisted = second_worker.get(models.ResearchTask, task_id)
    assert persisted.status == "running"
    assert persisted.attempts == 1

    first_worker.close()
    second_worker.close()
    engine.dispose()


def test_experiment_builder_rejects_collection_or_terminal_unresolved_status():
    payload = {
        "problem": "An unvalidated problem.",
        "target_customer": "Unknown",
        "market_analysis": "Unverified.",
        "solution": "Unknown",
        "business_model": "Unknown",
        "pricing_idea": "",
        "mvp_plan": "",
        "validation_plan": "No external action performed.",
        "difficulty": "unknown",
        "score": 0,
        "research_status": "research_terminal_unresolved",
        "research_plan": {
            "requirements": [
                {"id": "problem_incidence", "status": "terminal_unresolved"}
            ]
        },
    }

    try:
        experiment_service.build_experiment_from_analyze(payload)
    except ValueError as exc:
        assert "all research requirements" in str(exc)
    else:
        raise AssertionError("Unresolved research bypassed the experiment evidence gate")
