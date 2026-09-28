import json
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import (
    collector_runner,
    research_planner,
    research_synthesis_engine,
    source_manager,
    source_clearance_registry,
)
from app.services.collectors.base import SourceCollector


QUESTION = (
    "Determine whether there is a credible opportunity to reduce postharvest losses "
    "affecting smallholder farmers in Nepal"
)


def _freeze_clearance_date(monkeypatch):
    original = source_clearance_registry.capabilities_for_requirement
    review_date = date(2026, 9, 27)

    def capabilities(requirement, *, today=None):
        return original(requirement, today=today or review_date)

    monkeypatch.setattr(
        source_clearance_registry,
        "capabilities_for_requirement",
        capabilities,
    )


def test_decomposition_and_capability_routing_are_requirement_scoped(db, monkeypatch):
    _freeze_clearance_date(monkeypatch)
    question = models.ResearchQuestion(question=QUESTION)
    db.add(question)
    db.commit()

    plan = research_planner.build_research_plan(db, question)
    nodes = {row["requirement_id"]: row for row in plan["orchestration_requirements"]}
    assert set(nodes) == {
        "phenomenon_existence",
        "affected_population",
        "geographic_boundary",
        "reporting_velocity",
        "documented_interventions",
        "commercial_validation_gap",
    }
    assert nodes["phenomenon_existence"]["geographic_qualification"] == "Nepal"
    assert nodes["phenomenon_existence"]["population_qualification"] == "smallholder farmers"
    assert nodes["commercial_validation_gap"]["candidate_sources"] == []
    assert nodes["commercial_validation_gap"]["epistemic_state"] == "unresolved"

    routed = {
        source
        for node in nodes.values()
        for source in (candidate["source"] for candidate in node["candidate_sources"])
    }
    assert {"openalex", "crossref", "world_bank_indicators", "gdelt_doc"} <= routed
    assert all(
        candidate["registry_id"]
        for node in nodes.values()
        for candidate in node["candidate_sources"]
    )


def test_planner_creates_bounded_multisource_tasks_and_runner_executes_sequentially(
    db, monkeypatch
):
    _freeze_clearance_date(monkeypatch)
    question = models.ResearchQuestion(question=QUESTION)
    db.add(question)
    db.commit()

    plan = research_planner.build_research_plan(db, question)
    scholarly_requirement = next(
        item for item in plan["requirements"] if item["id"] == "scholarly_evidence"
    )
    assert scholarly_requirement["capable_sources"]
    intervention_requirement = next(
        item for item in plan["requirements"] if item["id"] == "documented_intervention"
    )
    assert intervention_requirement["capable_sources"]
    tasks = research_planner.plan_tasks_for_question(db, question)
    assert len(tasks) == research_planner.MAX_TASKS_PER_QUESTION
    assert {task.source for task in tasks} >= {
        "crossref",
        "openalex",
        "world_bank_indicators",
        "gdelt_doc",
    }
    openalex_tasks = [task for task in tasks if task.source == "openalex"]
    linked_openalex_requirements = {
        requirement_id
        for task in openalex_tasks
        for requirement_id in task.results["research_requirement_ids"]
    }
    assert {"scholarly_evidence", "documented_intervention"} <= set(
        linked_openalex_requirements
    )
    assert all(
        task.results["original_research_question"] == QUESTION
        and task.results["source_type"] == task.source
        and task.results["geographic_qualification"] == "Nepal"
        and task.results["population_qualification"] == "smallholder farmers"
        for task in tasks
    )
    assert all(task.results["search_mode"] in {"keyword", "semantic"} for task in openalex_tasks)
    assert all(    "Nepal" in task.results["derived_retrieval_query"] for task in openalex_tasks
    )
    assert question.research_plan["budget"]["tasks_created"] == 5
    assert all(
    requirement["task_ids"]
    for requirement in question.research_plan["requirements"]
    if requirement["status"] == "in_progress")

    execution_order = []

    def execute_task(session, task):
        execution_order.append(task.id)
        evidence = models.Evidence(
            source=task.source,
            title=f"Bounded result from {task.source}",
            content=f"Persisted observation for task {task.id}",
            canonical_url=f"https://evidence.test/{task.source}/{task.id}",
            retrieved_at=models.utcnow(),
            provenance=json.dumps({"source_registry_id": task.results["source_registry_id"]}),
        )
        session.add(evidence)
        session.flush()
        task.status = "completed"
        task.evidence_ids = str(evidence.id)
        task.results = {**task.results, "evidence_ids": [evidence.id]}
        session.commit()
        return {"task_id": task.id, "status": "completed"}

    monkeypatch.setattr(collector_runner, "execute_task", execute_task)
    outcomes = collector_runner.run_pending_tasks(db, limit=5)

    assert execution_order == [task.id for task in tasks]
    assert [outcome["status"] for outcome in outcomes] == ["completed"] * len(tasks)
    assert len({task.evidence_ids for task in tasks}) == len(tasks)
    assert all(task.status == "completed" for task in tasks)
    assert db.query(models.Evidence).count() == 5
    assert question.research_plan["status"] != "research_completed"


def test_mocked_multisource_evidence_survives_database_reopen(tmp_path, monkeypatch):
    _freeze_clearance_date(monkeypatch)
    database_path = tmp_path / "orchestration.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    source_manager.seed_default_sources(session)
    question = models.ResearchQuestion(question=QUESTION)
    session.add(question)
    session.commit()
    question_id = question.id
    tasks = research_planner.plan_tasks_for_question(session, question)

    def execute_task(db_session, task):
        evidence = models.Evidence(
            source=task.source,
            title=f"Isolated test record from {task.source}",
            content=f"Mock evidence for research task {task.id}",
            canonical_url=f"https://evidence.test/{task.source}/{task.id}",
            retrieved_at=models.utcnow(),
            provenance=json.dumps(
                {
                    "source_registry_id": task.results["source_registry_id"],
                    "original_research_question": QUESTION,
                    "derived_retrieval_query": task.results["derived_retrieval_query"],
                }
            ),
        )
        db_session.add(evidence)
        db_session.flush()
        task.status = "completed"
        task.evidence_ids = str(evidence.id)
        task.results = {**task.results, "evidence_ids": [evidence.id]}
        db_session.commit()
        return {"task_id": task.id, "status": "completed"}

    monkeypatch.setattr(collector_runner, "execute_task", execute_task)
    outcomes = collector_runner.run_pending_tasks(session, limit=5)
    assert len(outcomes) == 5
    assert session.query(models.Evidence).count() == 5
    persisted_evidence_ids = sorted(int(task.evidence_ids) for task in tasks)
    assert persisted_evidence_ids == [1, 2, 3, 4, 5]
    session.close()
    engine.dispose()

    reopened_engine = create_engine(f"sqlite:///{database_path}")
    reopened_session = sessionmaker(bind=reopened_engine)()
    assert reopened_session.query(models.ResearchTask).filter_by(status="completed").count() == 5
    assert reopened_session.query(models.Evidence).count() == 5
    assert [
        evidence.id
        for evidence in reopened_session.query(models.Evidence)
        .order_by(models.Evidence.id)
        .all()
    ] == persisted_evidence_ids
    assert reopened_session.get(models.ResearchQuestion, question_id).question == QUESTION
    reopened_session.close()
    reopened_engine.dispose()


def test_canonical_runner_carries_planner_context_into_evidence_provenance(
    db, monkeypatch
):
    _freeze_clearance_date(monkeypatch)
    question = models.ResearchQuestion(question=QUESTION)
    db.add(question)
    db.commit()
    task = next(
        task
        for task in research_planner.plan_tasks_for_question(db, question)
        if task.source == "crossref"
    )
    clearance = next(
        entry
        for entry in source_clearance_registry.source_clearances()
        if entry.registry_id == "crossref-public-works-metadata"
    )
    monkeypatch.setattr(
        source_clearance_registry,
        "authorize_request",
        lambda *args, **kwargs: SimpleNamespace(entry=clearance),
    )

    class FakeCrossrefCollector(SourceCollector):
        source_name = "crossref"
        source_type = "scholarly_metadata"

        def collect(self, query, *, authorization=None):
            return [
                {
                    "content": "Crossref metadata record: A bounded test publication.",
                    "title": "A bounded test publication",
                    "canonical_url": "https://doi.org/10.1234/test",
                    "external_id": "10.1234/test",
                    "retrieved_at": models.utcnow().isoformat(),
                    "provenance": {
                        "source_registry_id": clearance.registry_id,
                        "query": query,
                        "metadata_only": True,
                    },
                }
            ]

    monkeypatch.setitem(
        collector_runner.COLLECTORS,
        "crossref",
        FakeCrossrefCollector,
    )

    outcome = collector_runner.execute_task(db, task)
    evidence = (
        db.query(models.Evidence)
        .filter_by(source="crossref", external_id="10.1234/test")
        .one()
    )
    provenance = json.loads(evidence.provenance)

    assert outcome["status"] == "completed"
    assert provenance["original_research_question"] == QUESTION
    assert provenance["derived_retrieval_query"] == task.query
    assert provenance["geographic_qualification"] == "Nepal"
    assert provenance["population_qualification"] == "smallholder farmers"
    assert provenance["source_registry_id"] == clearance.registry_id


def test_synthesis_cites_persisted_records_preserves_conflicts_and_locks_commercial_gap(
    db,
):
    evidence_rows = [
        models.Evidence(
            source="openalex",
            title="Scholarly observation",
            content="Persisted scholarly observation.",
            canonical_url="https://openalex.org/W123",
            retrieved_at=models.utcnow(),
            provenance=json.dumps({"source_registry_id": "openalex-public-works-cc0"}),
        ),
        models.Evidence(
            source="world_bank_indicators",
            title="Macro observation",
            content="Persisted macro observation.",
            canonical_url="https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL",
            retrieved_at=models.utcnow(),
            provenance=json.dumps({"source_registry_id": "world-bank-indicators-v2"}),
        ),
        models.Evidence(
            source="crossref",
            title="Bibliographic lead",
            content="A separate bibliographic observation.",
            canonical_url="https://doi.org/10.1234/example",
            retrieved_at=models.utcnow(),
            provenance=json.dumps(
                {"source_registry_id": "crossref-public-works-metadata"}
            ),
        ),
    ]
    db.add_all(evidence_rows)
    db.flush()
    db.add(
        models.EvidenceRelationship(
            evidence_id=evidence_rows[0].id,
            relation_type="contradicts",
            relation_key=f"test:{evidence_rows[0].id}:contradicts",
        )
    )
    db.commit()
    plan = {
        "requirements": [
            {
                "id": "scholarly_evidence",
                "status": "satisfied",
                "evidence_ids": [evidence_rows[0].id],
            },
            {
                "id": "population_baseline",
                "status": "satisfied",
                "evidence_ids": [evidence_rows[1].id],
            },
            {
                "id": "bibliographic_discovery",
                "status": "satisfied",
                "evidence_ids": [evidence_rows[2].id],
            },
            {
                "id": "buyer_willingness_to_pay",
                "status": "terminal_unresolved",
                "evidence_ids": [],
            },
        ],
        "orchestration_requirements": [
            {
                "requirement_id": "phenomenon_existence",
                "related_requirement_ids": [
                    "scholarly_evidence",
                    "bibliographic_discovery",
                ],
                "unresolved_dimensions": ["local_applicability"],
            },
            {
                "requirement_id": "affected_population",
                "related_requirement_ids": ["population_baseline"],
                "unresolved_dimensions": ["customer_impact"],
            },
            {
                "requirement_id": "commercial_validation_gap",
                "related_requirement_ids": ["buyer_willingness_to_pay"],
                "unresolved_dimensions": ["buyer_willingness_to_pay"],
            },
        ],
    }

    synthesis = research_synthesis_engine.synthesize_research_plan(db, plan)
    by_id = {row["requirement_id"]: row for row in synthesis["requirements"]}
    phenomenon = by_id["phenomenon_existence"]
    assert phenomenon["state"] == "contradicted"
    assert phenomenon["citations"] == phenomenon["coexisting_observations"]
    assert {
        citation["evidence_id"] for citation in phenomenon["citations"]
    } == {evidence_rows[0].id, evidence_rows[2].id}
    assert {
        citation["provenance_url"] for citation in phenomenon["citations"]
    } == {evidence_rows[0].canonical_url, evidence_rows[2].canonical_url}
    assert by_id["affected_population"]["citations"][0]["evidence_id"] == evidence_rows[1].id
    commercial_gap = by_id["commercial_validation_gap"]
    assert commercial_gap["state"] == "unresolved"
    assert commercial_gap["commercial_gate_locked"] is True
    assert synthesis["commercial_validation"]["opportunity_gate_unlocked"] is False
    assert synthesis["conclusions_are_not_claim_truth_transitions"] is True
