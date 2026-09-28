import json
from hashlib import sha256
from datetime import date
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import (
    collector_runner,
    research_planner,
    research_synthesis_engine,
    research_task_engine,
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
        "geographic_baseline",
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
    assert {"openalex", "world_bank_indicators"} <= routed
    assert all(
        candidate["registry_id"]
        for node in nodes.values()
        for candidate in node["candidate_sources"]
    )


def test_objective_decomposition_adapts_to_agriculture_software_and_logistics(db):
    objectives = {
        "agriculture": (
            "Assess postharvest crop losses among smallholder farmers in Nepal"
        ),
        "software": (
            "Assess whether a SaaS appointment service can help independent clinics"
        ),
        "logistics": (
            "Assess delays and costs along the Nepal freight corridor"
        ),
    }
    requirements_by_domain = {}
    for domain, objective in objectives.items():
        question = models.ResearchQuestion(question=objective)
        db.add(question)
        db.flush()
        plan = research_planner.build_research_plan(db, question)
        requirements_by_domain[domain] = {
            node["requirement_id"]: node
            for node in plan["orchestration_requirements"]
        }

    assert set(requirements_by_domain["agriculture"]) == {
        "phenomenon_existence",
        "affected_population",
        "geographic_baseline",
        "documented_interventions",
        "commercial_validation_gap",
    }
    assert set(requirements_by_domain["software"]) == {
        "problem_prevalence",
        "technical_feasibility",
        "existing_solutions",
        "target_user_segment",
        "commercial_validation_gap",
    }
    assert set(requirements_by_domain["logistics"]) == {
        "operational_bottleneck",
        "geographic_corridor",
        "regulatory_environment",
        "macro_economic_volume",
        "commercial_validation_gap",
    }
    for domain, nodes in requirements_by_domain.items():
        for node in nodes.values():
            assert node["original_research_question"] == objectives[domain]
            assert node["required_evidence_type"]
            assert node["epistemic_state"] == "unresolved"
            assert isinstance(node["candidate_sources"], list)
            assert isinstance(node["unresolved_dimensions"], list)
            assert "geographic_qualification" in node
            assert "population_qualification" in node
    assert "SaaS" in requirements_by_domain["software"]["technical_feasibility"]["objective_subject"]
    assert "freight corridor" in requirements_by_domain["logistics"]["macro_economic_volume"]["objective_subject"]


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
    assert len(tasks) == 3
    assert {task.source for task in tasks} == {"openalex", "world_bank_indicators"}
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
    assert all(
        "Nepal" in task.results["derived_retrieval_query"]
        for task in openalex_tasks
    )
    assert question.research_plan["budget"]["tasks_created"] == 3
    assert all(
        requirement["task_ids"]
        for requirement in question.research_plan["requirements"]
        if requirement["status"] == "in_progress"
    )
    for task in tasks:
        assert task.idempotency_key == sha256(
            "\0".join(
                (
                    str(question.id),
                    task.results["research_requirement_id"],
                    task.source,
                    task.results["search_mode"] or "not_applicable",
                    task.query,
                )
            ).encode("utf-8")
        ).hexdigest()

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
    assert db.query(models.Evidence).count() == 3
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
    task_count = len(tasks)

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
    assert len(outcomes) == task_count
    assert session.query(models.Evidence).count() == task_count
    persisted_evidence_ids = sorted(int(task.evidence_ids) for task in tasks)
    assert persisted_evidence_ids == list(range(1, task_count + 1))
    session.close()
    engine.dispose()

    reopened_engine = create_engine(f"sqlite:///{database_path}")
    reopened_session = sessionmaker(bind=reopened_engine)()
    assert reopened_session.query(models.ResearchTask).filter_by(status="completed").count() == task_count
    assert reopened_session.query(models.Evidence).count() == task_count
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
        if task.source == "openalex"
    )
    clearance = next(
        entry
        for entry in source_clearance_registry.source_clearances()
        if entry.registry_id == "openalex-public-works-cc0"
    )
    monkeypatch.setattr(
        source_clearance_registry,
        "authorize_request",
        lambda *args, **kwargs: SimpleNamespace(entry=clearance),
    )

    class FakeOpenAlexCollector(SourceCollector):
        source_name = "openalex"
        source_type = "scholarly_evidence"

        def collect(self, query, *, search_mode, task_provenance, authorization=None):
            return [
                {
                    "content": "OpenAlex abstract record: A bounded test publication.",
                    "title": "A bounded test publication",
                    "canonical_url": "https://openalex.org/W123456789",
                    "external_id": "https://openalex.org/W123456789",
                    "identity_key": "openalex:test-work",
                    "retrieved_at": models.utcnow().isoformat(),
                    "provenance": {
                        "source_registry_id": clearance.registry_id,
                        "query": query,
                        "search_mode": search_mode,
                        "abstract": "A test abstract.",
                        "abstract_reconstructed": True,
                    },
                }
            ]

    monkeypatch.setitem(
        collector_runner.COLLECTORS,
        "openalex",
        FakeOpenAlexCollector,
    )

    outcome = collector_runner.execute_task(db, task)
    evidence = db.query(models.Evidence).filter_by(source="openalex").one()
    provenance = json.loads(evidence.provenance)

    assert outcome["status"] == "completed"
    assert provenance["original_research_question"] == QUESTION
    assert provenance["derived_retrieval_query"] == task.results["derived_retrieval_query"]
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
                "geographic_qualification": "Nepal",
                "population_qualification": "smallholder farmers",
                "task_failures": [
                    {
                        "task_id": 99,
                        "source": "gdelt_doc",
                        "status": "failed",
                        "errors": ["bounded provider failure"],
                    }
                ],
            },
            {
                "id": "population_baseline",
                "status": "satisfied",
                "evidence_ids": [evidence_rows[1].id],
                "geographic_qualification": "Nepal",
            },
            {
                "id": "bibliographic_discovery",
                "status": "satisfied",
                "evidence_ids": [evidence_rows[2].id],
                "geographic_qualification": "Nepal",
                "population_qualification": "smallholder farmers",
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
                "candidate_sources": [{"source": "openalex"}],
            },
            {
                "requirement_id": "affected_population",
                "related_requirement_ids": ["population_baseline"],
                "unresolved_dimensions": ["customer_impact"],
                "candidate_sources": [{"source": "world_bank_indicators"}],
            },
            {
                "requirement_id": "commercial_validation_gap",
                "related_requirement_ids": ["buyer_willingness_to_pay"],
                "unresolved_dimensions": ["buyer_willingness_to_pay"],
                "candidate_sources": [],
            },
        ],
    }

    synthesis = research_synthesis_engine.synthesize_research_plan(db, plan)
    by_id = {row["requirement_id"]: row for row in synthesis["requirements"]}
    phenomenon = by_id["phenomenon_existence"]
    assert phenomenon["state"] == "contradicted"
    assert phenomenon["citations"] == phenomenon["coexisting_observations"]
    assert phenomenon["task_failures"] == [
        {
            "task_id": 99,
            "source": "gdelt_doc",
            "status": "failed",
            "errors": ["bounded provider failure"],
        }
    ]
    assert {
        citation["evidence_id"] for citation in phenomenon["citations"]
    } == {evidence_rows[0].id, evidence_rows[2].id}
    assert {
        citation["provenance_url"] for citation in phenomenon["citations"]
    } == {evidence_rows[0].canonical_url, evidence_rows[2].canonical_url}
    assert by_id["affected_population"]["citations"][0]["evidence_id"] == evidence_rows[1].id
    commercial_gap = by_id["commercial_validation_gap"]
    assert commercial_gap["state"] == "blocked"
    assert commercial_gap["commercial_gate_locked"] is True
    assert synthesis["commercial_validation"]["state"] == "blocked"
    assert synthesis["commercial_validation"]["opportunity_gate_unlocked"] is False
    assert synthesis["conclusions_are_not_claim_truth_transitions"] is True


def test_unresolved_requirement_gets_one_deterministic_unqueried_task(db, monkeypatch):
    _freeze_clearance_date(monkeypatch)
    question = models.ResearchQuestion(question=QUESTION)
    db.add(question)
    db.commit()

    prior = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="openalex",
        query="postharvest loss Nepal",
        idempotency_key="prior-openalex-task",
    )
    prior.results = {"source_registry_id": "openalex-public-works-cc0"}
    db.commit()
    requirement = {
        "id": "scholarly_evidence",
        "question": "What scholarly evidence documents postharvest loss?",
        "evidence_kind": "openalex_scholarly_abstract",
        "capable_sources": [
            {
                "source": "openalex",
                "registry_id": "openalex-public-works-cc0",
            },
            {
                "source": "crossref",
                "registry_id": "crossref-public-works-metadata",
            },
        ],
    }

    next_task = research_planner._create_next_unqueried_capability_task(
        db,
        question,
        requirement,
        [prior],
        task_count=1,
    )
    assert next_task is not None
    assert next_task.source == "crossref"
    assert next_task.results["follow_up_of_task_id"] == prior.id
    assert next_task.results["follow_up_depth"] == 1

    repeated = research_planner._create_next_unqueried_capability_task(
        db,
        question,
        requirement,
        [prior],
        task_count=1,
    )
    assert repeated.id == next_task.id
    assert db.query(models.ResearchTask).filter_by(question_id=question.id).count() == 2


def test_empty_evidence_synthesis_stays_unresolved_and_commercially_blocked(db):
    plan = {
        "requirements": [
            {
                "id": "scholarly_evidence",
                "status": "terminal_unresolved",
                "evidence_ids": [],
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
                "related_requirement_ids": ["scholarly_evidence"],
                "unresolved_dimensions": ["local_applicability"],
                "candidate_sources": [{"source": "openalex"}],
            },
            {
                "requirement_id": "commercial_validation_gap",
                "related_requirement_ids": ["buyer_willingness_to_pay"],
                "unresolved_dimensions": ["customer_pain", "buyer_willingness_to_pay"],
                "candidate_sources": [],
            },
        ],
    }

    synthesis = research_synthesis_engine.synthesize_research_plan(db, plan)
    by_id = {row["requirement_id"]: row for row in synthesis["requirements"]}
    assert by_id["phenomenon_existence"]["state"] == "unresolved"
    assert by_id["phenomenon_existence"]["citations"] == []
    assert by_id["commercial_validation_gap"]["state"] == "blocked"
    assert (
        plan["requirements"][1]["resolution_state"]
        == "blocked_external_evidence_required"
    )
    assert synthesis["commercial_validation"]["opportunity_gate_unlocked"] is False


def test_concurrent_deterministic_task_creation_has_one_persisted_task(tmp_path):
    database_path = tmp_path / "concurrent-orchestration.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        question = models.ResearchQuestion(question=QUESTION)
        session.add(question)
        session.commit()
        question_id = question.id

    def create_same_task(_):
        with session_factory() as session:
            task = research_task_engine.create_task(
                session,
                question_id=question_id,
                source="openalex",
                query="postharvest loss smallholder farmers Nepal",
                idempotency_key=sha256(
                    "\0".join(
                        (
                            str(question_id),
                            "phenomenon_existence",
                            "openalex",
                            "semantic",
                            "postharvest loss smallholder farmers Nepal",
                        )
                    ).encode("utf-8")
                ).hexdigest(),
            )
            return task.id

    with ThreadPoolExecutor(max_workers=3) as pool:
        task_ids = list(pool.map(create_same_task, range(3)))

    with session_factory() as session:
        tasks = (
            session.query(models.ResearchTask)
            .filter_by(question_id=question_id)
            .all()
        )
        assert len(set(task_ids)) == 1
        assert len(tasks) == 1
        assert tasks[0].idempotency_key == sha256(
            "\0".join(
                (
                    str(question_id),
                    "phenomenon_existence",
                    "openalex",
                    "semantic",
                    "postharvest loss smallholder farmers Nepal",
                )
            ).encode("utf-8")
        ).hexdigest()
    engine.dispose()
