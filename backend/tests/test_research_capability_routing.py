import json

import pytest

from app import models
from app.database import Base
from app.services import (
    capability_discovery,
    research_planner,
    research_task_engine,
    research_task_event_substrate_adapter,
    source_clearance_registry,
    tool_usefulness,
    world_graph,
)


def test_planner_discovers_and_persists_existing_cleared_capability(db):
    tables_before = set(Base.metadata.tables)
    question = models.ResearchQuestion(
        question="What published solutions address independent bicycle repair shop needs?"
    )
    db.add(question)
    db.commit()

    plan = research_planner.build_research_plan(db, question)
    requirement = next(
        row for row in plan["requirements"] if row["id"] == "bibliographic_discovery"
    )
    candidate = requirement["selected_capability"]

    assert candidate["source"] == "crossref"
    assert candidate["registry_id"] == "crossref-public-works-metadata"
    assert candidate["capability_state"] == "untested"
    assert candidate["truth_state"] == "hypothesized"
    assert candidate["authorization_status"].endswith("required")
    assert candidate["cost"] == "unknown"
    capability = db.get(models.ForgeCapability, candidate["capability_id"])
    assert capability is not None
    assert capability.status == "proposed"
    cap_data = json.loads(capability.attributes)["capability_discovery"]
    assert cap_data["record_kind"] == "registered_source_capability"
    assert cap_data["source_registry_id"] == candidate["registry_id"]
    assert cap_data["request_authorization_required"] is True
    assert cap_data["cost"] == "unknown"
    reused = capability_discovery.discover_candidates(
        db, question, requirement
    )
    assert [row.id for row in reused] == [capability.id]
    assert "web_search" not in {
        item["source"] for item in requirement["candidate_capabilities"]
    }
    assert set(Base.metadata.tables) == tables_before

    tasks = research_planner.plan_tasks_for_question(db, question)
    task = next(row for row in tasks if row.source == "crossref")
    selection = task.results["capability_selection"]
    assert selection["capability_id"] == capability.id
    assert selection["authorization_status"] == candidate["authorization_status"]
    selected_event = db.query(models.WorldEvent).filter_by(
        idempotency_key=(
            f"research-capability-selection:{task.idempotency_key}"
        )
    ).one()
    event_payload = json.loads(selected_event.payload)
    assert event_payload["lifecycle_event"] == "research_capability_selected"
    assert event_payload["capability_id"] == capability.id
    assert event_payload["source_registry_id"] == candidate["registry_id"]
    assert event_payload["truth_state"] == "hypothesized"
    assert event_payload["authorization_status"] == candidate["authorization_status"]
    assert event_payload["cost"] == "unknown"
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.Outcome).count() == 0
    source_capabilities_before = db.query(models.ForgeCapability).filter(
        models.ForgeCapability.name.like("source-capability-%")
    ).count()
    source_capability_events_before = db.query(models.WorldEvent).filter_by(
        source="research_capability_discovery",
        event_type="capability_source_refreshed",
    ).count()
    repeated_plan = research_planner.build_research_plan(db, question)
    assert repeated_plan["question_id"] == question.id
    assert db.query(models.ForgeCapability).filter(
        models.ForgeCapability.name.like("source-capability-%")
    ).count() == source_capabilities_before
    assert db.query(models.WorldEvent).filter_by(
        source="research_capability_discovery",
        event_type="capability_source_refreshed",
    ).count() == source_capability_events_before
    selected_event.payload = "{}"
    db.flush()
    with pytest.raises(world_graph.SubstrateError, match="key collision"):
        research_planner._record_capability_selection(
            db,
            question=question,
            task=task,
            requirement_id="bibliographic_discovery",
            selection=selection,
            task_identity=task.idempotency_key,
        )


def test_source_route_ranking_reuses_measured_successful_capability(
    db, monkeypatch
):
    entries = {
        item.collector: item
        for item in source_clearance_registry.source_clearances()
        if item.collector in {"crossref", "openalex"}
    }
    assert set(entries) == {"crossref", "openalex"}
    monkeypatch.setattr(
        capability_discovery,
        "active_cleared_sources",
        lambda _db, _requirement: (
            entries["openalex"],
            entries["crossref"],
        ),
    )
    tool_usefulness.record_usage(
        db,
        tool_name="collector:crossref",
        source="crossref",
        source_type="collector",
        query="test usage history",
        research_task_id=None,
        claim_id=None,
        result_count=2,
        useful_result_count=2,
        novel_result_count=2,
        verified_result_count=0,
        duplicate_result_count=0,
        corroborated_evidence_count=0,
        contradicted_claim_count=0,
        freshness=100.0,
        latency_ms=50.0,
        success=True,
        result_ids=[101, 102],
    )

    ranked = capability_discovery.ranked_source_capabilities(
        db, "bibliographic_discovery"
    )

    assert [item["source"] for item in ranked] == ["crossref", "openalex"]
    assert ranked[0]["capability_state"] == "tested"
    assert ranked[0]["observed_usage"]["attempts"] == 1
    assert ranked[0]["observed_usage"]["successes"] == 1
    assert ranked[0]["observed_usage"]["learned_score"] == 1.0
    assert ranked[0]["selection_reason"].startswith("ordered using persisted")
    tested_record = db.get(models.ForgeCapability, ranked[0]["capability_id"])
    tested_data = json.loads(tested_record.attributes)["capability_discovery"]
    assert tested_data["execution_state"] == "tested"
    assert tested_data["truth_state"] == "tested"
    assert "supported" not in tested_data.values()
    assert ranked[1]["capability_state"] == "untested"
    assert ranked[1]["truth_state"] == "hypothesized"
    assert all(item["authorization_status"].endswith("required") for item in ranked)
    assert all(item["cost"] == "unknown" for item in ranked)
    assert all(item["capability_id"] for item in ranked)


def test_failed_capability_execution_is_projected_without_claiming_success(db):
    question = models.ResearchQuestion(question="Can this source answer the query?")
    db.add(question)
    db.commit()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="crossref",
        query="bounded metadata query",
        objective=question.question,
    )
    world_graph.seed_core_types(db)
    capability = models.ForgeCapability(
        capability_type="integration",
        name="test-source-capability",
        description="Test-only source capability.",
        status="proposed",
        owner_agent="test",
        attributes="{}",
    )
    db.add(capability)
    db.flush()
    task.results = {
        **task.results,
        "source_registry_id": "crossref-public-works-metadata",
        "capability_selection": {
            "capability_id": capability.id,
            "registry_id": "crossref-public-works-metadata",
            "capability_state": "untested",
            "truth_state": "hypothesized",
            "authorization_status": (
                "request_time_source_authorization_and_rate_reservation_required"
            ),
            "cost": "unknown",
        },
    }
    db.add(
        models.ResearchTaskEvent(
            task_id=task.id,
            event_type="failed",
            details={"failure_kind": "network_error", "result_count": 0},
        )
    )
    tool_usefulness.record_usage(
        db,
        tool_name="collector:crossref",
        source="crossref",
        source_type="collector",
        query=task.query,
        research_task_id=task.id,
        claim_id=None,
        result_count=0,
        useful_result_count=0,
        novel_result_count=0,
        verified_result_count=0,
        duplicate_result_count=0,
        corroborated_evidence_count=0,
        contradicted_claim_count=0,
        freshness=None,
        latency_ms=25.0,
        success=False,
        failure_kind="network_error",
        cost=None,
        result_ids=[],
    )

    projection = research_task_event_substrate_adapter.sync_research_task_events(db)

    assert projection["events_projected"] >= 1
    failure = next(
        event
        for event in db.query(models.ResearchTaskEvent).filter_by(task_id=task.id)
        if event.event_type == "failed"
    )
    canonical = db.query(models.WorldEvent).filter_by(
        idempotency_key=f"research-task-event:{failure.id}:state-changed-v1"
    ).one()
    payload = json.loads(canonical.payload)
    assert payload["lifecycle_event"] == "failed"
    assert payload["capability_ref"] == {
        "table": "capabilities",
        "id": capability.id,
    }
    assert payload["source_registry_id"] == "crossref-public-works-metadata"
    assert payload["observed_execution"]["success"] is False
    assert payload["observed_execution"]["failure_kind"] == "network_error"
    assert payload["observed_execution"]["result_count"] == 0
    assert payload["observed_execution"]["cost"] is None
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.Outcome).count() == 0
