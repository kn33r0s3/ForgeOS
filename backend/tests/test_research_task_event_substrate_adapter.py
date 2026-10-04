import hashlib
import json

from app import models
from app.services import (
    forge_loop,
    research_task_event_substrate_adapter as adapter,
    research_task_engine,
    world_graph,
)


def _failed_research_task(db, *, question_suffix=""):
    question = models.ResearchQuestion(
        question=(
            "What public evidence addresses this bounded research objective?"
            f"{question_suffix}"
        )
    )
    db.add(question)
    db.commit()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="crossref",
        query="bounded bibliographic metadata query",
        objective=question.question,
    )
    research_task_engine.fail_task(
        db,
        task,
        "TEST: source unavailable; no result was collected",
    )
    return question, task


def test_lifecycle_events_are_projected_with_safe_provenance_and_truthful_failure(db):
    question, task = _failed_research_task(db)
    source_events = (
        db.query(models.ResearchTaskEvent)
        .filter_by(task_id=task.id)
        .order_by(models.ResearchTaskEvent.id.asc())
        .all()
    )

    result = adapter.sync_research_task_events(db)

    assert result == {
        "events_seen": len(source_events),
        "events_projected": len(source_events),
        "unresolved_events": 0,
    }
    question_entity = world_graph.find_canonical_entity(
        db,
        "research_question",
        question.id,
    )
    assert question_entity is not None
    for source_event in source_events:
        canonical = db.query(models.WorldEvent).filter_by(
            idempotency_key=(
                f"research-task-event:{source_event.id}:state-changed-v1"
            )
        ).one()
        payload = json.loads(canonical.payload)
        details_json = json.dumps(
            source_event.details or {},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        assert canonical.event_type == "state_changed"
        assert canonical.entity_id == question_entity.id
        assert payload["subject_kind"] == "research_task"
        assert payload["task_ref"] == {
            "table": "research_tasks",
            "id": task.id,
        }
        assert payload["source_ref"] == {
            "table": "research_task_events",
            "id": source_event.id,
        }
        assert payload["lifecycle_event"] == source_event.event_type
        assert payload["source_details_sha256"] == hashlib.sha256(
            details_json.encode("utf-8")
        ).hexdigest()
        assert payload["payload_copied"] is False
        assert "source unavailable" not in canonical.payload

    failed_event = next(row for row in source_events if row.event_type == "failed")
    failure_projection = db.query(models.WorldEvent).filter_by(
        idempotency_key=f"research-task-event:{failed_event.id}:state-changed-v1"
    ).one()
    assert json.loads(failure_projection.payload)["lifecycle_event"] == "failed"
    assert task.status == "failed"
    assert task.evidence_ids == ""
    assert db.query(models.Evidence).count() == 0
    assert db.query(models.Action).count() == 0

    repeated = adapter.sync_research_task_events(db)
    assert repeated == {
        "events_seen": 0,
        "events_projected": 0,
        "unresolved_events": 0,
    }
    projected_keys = {
        row[0]
        for row in db.query(models.WorldEvent.idempotency_key)
        .filter(models.WorldEvent.idempotency_key.isnot(None))
        .all()
    }
    assert all(
        f"research-task-event:{source_event.id}:state-changed-v1" in projected_keys
        for source_event in source_events
    )


def test_event_projection_is_bounded_and_retries_without_starvation(db):
    _question, task = _failed_research_task(db)
    for index in range(3):
        db.add(
            models.ResearchTaskEvent(
                task_id=task.id,
                event_type=f"bounded_transition_{index}",
                details={"index": index},
            )
        )
    db.commit()
    total = db.query(models.ResearchTaskEvent).filter_by(task_id=task.id).count()

    projected = 0
    for _ in range(total):
        batch = adapter.sync_research_task_events(db, limit=1)
        assert batch["events_seen"] == 1
        assert batch["events_projected"] == 1
        projected += batch["events_projected"]

    assert projected == total
    source_event_ids = [
        row[0]
        for row in db.query(models.ResearchTaskEvent.id)
        .filter_by(task_id=task.id)
        .all()
    ]
    projected_keys = {
        row[0]
        for row in db.query(models.WorldEvent.idempotency_key)
        .filter(models.WorldEvent.idempotency_key.isnot(None))
        .all()
    }
    assert all(
        f"research-task-event:{event_id}:state-changed-v1" in projected_keys
        for event_id in source_event_ids
    )
    assert len(source_event_ids) == total


def test_task_id_scope_projects_only_selected_research_lifecycle(db):
    _question, selected_task = _failed_research_task(db)
    _other_question, other_task = _failed_research_task(
        db,
        question_suffix=" Another test-only research question.",
    )
    other_event_ids = {
        row.id
        for row in db.query(models.ResearchTaskEvent).filter_by(task_id=other_task.id).all()
    }

    result = adapter.sync_research_task_events(db, task_id=selected_task.id)

    assert result["events_seen"] > 0
    assert result["events_projected"] == result["events_seen"]
    assert result["unresolved_events"] == 0
    assert all(
        db.query(models.WorldEvent).filter_by(
            idempotency_key=f"research-task-event:{event_id}:state-changed-v1"
        ).count() == 0
        for event_id in other_event_ids
    )


def test_inactive_event_type_stays_unresolved(db):
    _question, _task = _failed_research_task(db)
    world_graph.seed_core_types(db)
    event_type = db.query(models.TypeRegistry).filter_by(
        category="event_type",
        type_name="state_changed",
    ).one()
    world_graph.set_type_status(
        db,
        event_type,
        "deprecated",
        actor="test_agent",
        rationale="Verify research events respect type activation state.",
        evidence_ref="backend/tests/test_research_task_event_substrate_adapter.py",
    )

    result = adapter.sync_research_task_events(db)

    assert result["events_seen"] > 0
    assert result["events_projected"] == 0
    assert result["unresolved_events"] == result["events_seen"]
    assert db.query(models.WorldEvent).filter(
        models.WorldEvent.idempotency_key.like("research-task-event:%")
    ).count() == 0


def test_canonical_forge_cycle_projects_research_task_lifecycle(db):
    _question, task = _failed_research_task(db)

    summary = forge_loop.run_cycle(db)

    assert "substrate_adapters" not in summary["stage_errors"]
    assert summary["substrate_research_task_events_projected"] > 0
    assert summary["substrate_research_task_events_unresolved"] == 0
    projected_keys = {
        row[0]
        for row in db.query(models.WorldEvent.idempotency_key)
        .filter(models.WorldEvent.idempotency_key.isnot(None))
        .all()
    }
    source_event_ids = [
        row[0]
        for row in db.query(models.ResearchTaskEvent.id)
        .filter_by(task_id=task.id)
        .all()
    ]
    assert all(
        f"research-task-event:{event_id}:state-changed-v1" in projected_keys
        for event_id in source_event_ids
    )
