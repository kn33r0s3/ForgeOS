import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import (
    capability_discovery,
    collector_runner,
    research_planner,
    source_clearance_registry,
    source_manager,
)
from app.services.collectors.base import SourceCollector


def _unserved_requirement(db, question_text="What is the local crop loss incidence in Nepal?"):
    question = models.ResearchQuestion(question=question_text)
    db.add(question)
    db.commit()
    requirement = {
        "id": "local_crop_loss",
        "question": "What local crop loss incidence is documented?",
        "required_evidence_type": "primary_agriculture_observation",
        "original_research_question": question.question,
        "geographic_qualification": "Nepal",
        "population_qualification": "smallholder farmers",
        "unresolved_dimensions": ["season", "crop", "local_applicability"],
    }
    return question, requirement


def test_unserved_requirement_persists_one_gap_and_bounded_candidates(db):
    question, requirement = _unserved_requirement(db)

    gap = capability_discovery.ensure_capability_gap(db, question, requirement)
    candidates = capability_discovery.discover_candidates(
        db, question, requirement, max_candidates=99
    )
    repeated = capability_discovery.discover_candidates(db, question, requirement)
    db.commit()

    assert gap.id == capability_discovery.ensure_capability_gap(
        db, question, requirement
    ).id
    assert len(candidates) == capability_discovery.MAX_CANDIDATES_PER_GAP
    assert [row.id for row in repeated] == [row.id for row in candidates]
    data = json.loads(gap.attributes)["capability_discovery"]
    assert data["record_kind"] == "research_capability_gap"
    assert data["clearance_status"] == "not_cleared"
    assert data["required_scope"]["geographic_scope"] == "Nepal"
    assert data["required_scope"]["temporal_scope"] is None
    assert all(
        json.loads(row.attributes)["capability_discovery"]["lifecycle"] == "candidate"
        and row.status == "proposed"
        for row in candidates
    )
    gap_evidence = db.query(models.Evidence).filter_by(
        idempotency_key=(
            "capability-gap-evidence:"
            + json.loads(gap.attributes)["capability_discovery"]["idempotency_key"]
        )
    ).one()
    assert gap_evidence.support_level == "possible"
    assert json.loads(gap_evidence.provenance)["claim_boundary"].startswith(
        "This records the bounded registry search"
    )
    assert db.query(models.WorldEvent).filter_by(
        event_type="capability_gap_recorded"
    ).count() == 1
    assert db.query(models.WorldEvent).filter_by(
        event_type="capability_gap_candidates_discovered"
    ).count() == 1
    assert db.query(models.Signal).count() == 0
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Decision).count() == 0


def test_candidate_review_requires_registered_source_and_does_not_activate(db, monkeypatch):
    question, requirement = _unserved_requirement(db)
    candidate = capability_discovery.discover_candidates(
        db, question, requirement, max_candidates=1
    )[0]

    with __import__("pytest").raises(ValueError):
        capability_discovery.review_candidate(
            db,
            candidate.id,
            source_registry_id="invented-source",
            actor="reviewer",
            rationale="Not enough.",
            provenance_references=["review:test"],
        )
    assert candidate.status == "proposed"


def test_concurrent_gap_creation_is_idempotent(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'capability-gaps.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as seed:
        source_manager.seed_default_sources(seed)
        from app.services import world_graph

        world_graph.seed_core_types(seed)
        seed.commit()
        question = models.ResearchQuestion(question="What is local crop incidence?")
        seed.add(question)
        seed.commit()
        question_id = question.id

    def create_gap():
        with factory() as session:
            question = session.get(models.ResearchQuestion, question_id)
            requirement = {
                "id": "local_crop_loss",
                "question": "What local crop loss incidence is documented?",
                "required_evidence_type": "primary_agriculture_observation",
                "original_research_question": question.question,
                "geographic_qualification": "Nepal",
                "population_qualification": "smallholder farmers",
            }
            gap = capability_discovery.ensure_capability_gap(
                session, question, requirement
            )
            session.commit()
            return gap.name

    with ThreadPoolExecutor(max_workers=3) as workers:
        names = list(workers.map(lambda _: create_gap(), range(3)))
    with factory() as session:
        assert len(set(names)) == 1
        assert session.query(models.ForgeCapability).count() == 1
        assert session.query(models.WorldEvent).filter_by(
            event_type="capability_gap_recorded"
        ).count() == 1
        assert session.query(models.Evidence).filter_by(
            source="research_capability_discovery"
        ).count() == 1
    engine.dispose()


def test_cleared_active_candidate_becomes_plannable_and_evidence_keeps_provenance(
    db, monkeypatch
):
    entry = next(
        item
        for item in source_clearance_registry.source_clearances()
        if item.collector == "crossref"
    )
    original_capabilities = source_clearance_registry.capabilities_for_requirement

    def scoped_capabilities(requirement, *, today=None):
        if requirement == "problem_incidence":
            return ()
        return original_capabilities(requirement, today=today or date(2026, 9, 27))

    monkeypatch.setattr(
        source_clearance_registry,
        "capabilities_for_requirement",
        scoped_capabilities,
    )
    question = models.ResearchQuestion(
        question="What is the problem incidence for independent repair shops?"
    )
    db.add(question)
    db.commit()
    plan = research_planner.build_research_plan(db, question)
    requirement = next(
        row for row in plan["requirements"] if row["id"] == "problem_incidence"
    )
    gap = db.get(models.ForgeCapability, requirement["capability_gap_id"])
    candidate = capability_discovery.discover_candidates(
        db, question, requirement, max_candidates=1
    )[0]
    assert not capability_discovery.active_cleared_sources(db, "problem_incidence")

    def now_scoped(requirement_id, *, today=None):
        if requirement_id == "problem_incidence":
            return (entry,)
        return scoped_capabilities(requirement_id, today=today)

    monkeypatch.setattr(
        source_clearance_registry,
        "capabilities_for_requirement",
        now_scoped,
    )
    assert not capability_discovery.active_cleared_sources(db, "problem_incidence")
    capability_discovery.review_candidate(
        db,
        candidate.id,
        source_registry_id=entry.registry_id,
        actor="reviewer",
        rationale="The reviewed registry entry has a bounded operation.",
        provenance_references=["tests/test_capability_discovery.py"],
    )
    capability_discovery.clear_candidate(
        db,
        candidate.id,
        actor="reviewer",
        rationale="Exact existing clearance covers the requirement in this test.",
        provenance_reference="tests/test_capability_discovery.py",
    )
    assert not capability_discovery.active_cleared_sources(
        db, "problem_incidence"
    )
    capability_discovery.activate_candidate(
        db,
        candidate.id,
        test_ref="backend/tests/test_capability_discovery.py",
        command="pytest backend/tests/test_capability_discovery.py",
        exit_code=0,
        output_excerpt="state-machine test passed",
    )
    assert capability_discovery.active_cleared_sources(
        db, "problem_incidence"
    ) == (entry,)
    tasks = research_planner.plan_tasks_for_question(db, question)
    task = next(
        row
        for row in db.query(models.ResearchTask).filter_by(question_id=question.id)
        if row.results.get("research_requirement_id") == "problem_incidence"
    )
    assert task.results["capability_id"] == candidate.id

    class FixtureCollector(SourceCollector):
        source_name = "crossref"

        def collect(self, query, *, authorization=None):
            return [
                {
                    "content": "Metadata observation only.",
                    "title": "Bounded repair study",
                    "canonical_url": "https://doi.org/10.1234/repair",
                    "external_id": "10.1234/repair",
                    "retrieved_at": models.utcnow().isoformat(),
                    "provenance": {"metadata_only": True, "query": query},
                }
            ]

    monkeypatch.setitem(collector_runner.COLLECTORS, "crossref", FixtureCollector)
    monkeypatch.setattr(
        source_clearance_registry,
        "authorize_request",
        lambda *args, **kwargs: SimpleNamespace(entry=entry),
    )
    result = collector_runner.execute_task(db, task)
    db.refresh(question)
    evidence = db.query(models.Evidence).filter(
        models.Evidence.source == "crossref"
    ).one()
    provenance = json.loads(evidence.provenance)
    assert result["status"] == "completed"
    assert provenance["source_registry_id"] == entry.registry_id
    assert provenance["capability_id"] == candidate.id
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Decision).count() == 0
    gap_id = gap.id
    candidate_id = candidate.id
    task_id = task.id
    evidence_id = evidence.id
    bind = db.get_bind()
    db.commit()
    db.close()
    with sessionmaker(bind=bind, expire_on_commit=False)() as reopened:
        persisted_gap = reopened.get(models.ForgeCapability, gap_id)
        persisted_candidate = reopened.get(models.ForgeCapability, candidate_id)
        persisted_task = reopened.get(models.ResearchTask, task_id)
        persisted_evidence = reopened.get(models.Evidence, evidence_id)
        assert persisted_gap is not None
        assert persisted_candidate.status == "active"
        assert json.loads(persisted_candidate.attributes)["capability_discovery"][
            "clearance_status"
        ] == "cleared"
        assert persisted_task.results["capability_id"] == candidate_id
        assert json.loads(persisted_evidence.provenance)["capability_id"] == candidate_id
        print(
            json.dumps(
                {
                    "capability_gap_id": gap_id,
                    "candidate_id": candidate_id,
                    "research_task_id": task_id,
                    "evidence_id": evidence_id,
                    "candidate_lifecycle": "active",
                    "clearance_status": "cleared",
                    "opportunities": reopened.query(models.Opportunity).count(),
                    "decisions": reopened.query(models.Decision).count(),
                },
                sort_keys=True,
            )
        )
