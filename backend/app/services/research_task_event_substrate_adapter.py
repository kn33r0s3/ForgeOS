"""Project durable research-task lifecycle events into the canonical substrate."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import String, cast, exists, literal
from sqlalchemy.orm import Session

from app import models
from app.services import world_graph


_KEY_PREFIX = "research-task-event:"
_KEY_SUFFIX = ":state-changed-v1"
_SOURCE = "research_task_event_substrate_adapter"


def _event_key(event_id: int) -> str:
    return f"{_KEY_PREFIX}{event_id}{_KEY_SUFFIX}"


def sync_research_task_events(db: Session, *, limit: int = 250) -> dict[str, int]:
    """Project only lifecycle metadata; source details remain in the task log."""
    world_graph.seed_core_types(db)
    result = {
        "events_seen": 0,
        "events_projected": 0,
        "unresolved_events": 0,
    }
    event_key = (
        literal(_KEY_PREFIX)
        + cast(models.ResearchTaskEvent.id, String)
        + literal(_KEY_SUFFIX)
    )
    already_projected = exists().where(
        models.WorldEvent.idempotency_key == event_key
    )
    rows = (
        db.query(models.ResearchTaskEvent)
        .filter(~already_projected)
        .order_by(models.ResearchTaskEvent.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )

    for source_event in rows:
        result["events_seen"] += 1
        task = db.get(models.ResearchTask, source_event.task_id)
        question = db.get(
            models.ResearchQuestion,
            task.question_id if task is not None else None,
        )
        if task is None or question is None:
            result["unresolved_events"] += 1
            continue
        try:
            question_entity = world_graph.ensure_canonical_entity(
                db,
                "research_question",
                question.id,
                created_by=_SOURCE,
            )
            details = json.dumps(
                source_event.details or {},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            world_graph.create_event(
                db,
                event_type="state_changed",
                entity_id=question_entity.id,
                source=_SOURCE,
                occurred_at=source_event.created_at,
                idempotency_key=_event_key(source_event.id),
                payload={
                    "subject_kind": "research_task",
                    "task_ref": {"table": "research_tasks", "id": task.id},
                    "source_ref": {
                        "table": "research_task_events",
                        "id": source_event.id,
                    },
                    "question_ref": {
                        "table": "research_questions",
                        "id": question.id,
                    },
                    "source": task.source,
                    "lifecycle_event": source_event.event_type,
                    "step_name": source_event.step_name,
                    "source_details_sha256": hashlib.sha256(
                        details.encode("utf-8")
                    ).hexdigest(),
                    "payload_copied": False,
                },
            )
        except world_graph.SubstrateError:
            result["unresolved_events"] += 1
            continue
        result["events_projected"] += 1

    db.flush()
    return result
