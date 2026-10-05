"""Bounded proposal-only cognitive tasks over existing research records."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app import models
from app.services import cognitive_provider, world_graph

_PROPOSAL_LIST_ADAPTER = TypeAdapter(list[cognitive_provider.CognitiveProposal])
_MAX_EVIDENCE_ID_FIELD_CHARS = 4_096


def create_cognitive_task(
    db: Session,
    research_task_id: int,
    *,
    priority: int = 0,
) -> models.WorkerTask:
    """Queue or reuse one cognitive proposal task for an existing research task."""
    if type(research_task_id) is not int or research_task_id <= 0:
        raise cognitive_provider.CognitiveTaskInputError("research_task_id must be a positive integer")
    if db.get(models.ResearchTask, research_task_id) is None:
        raise cognitive_provider.CognitiveTaskInputError("research task does not exist")

    idempotency_key = f"cognitive-research-task:v1:{research_task_id}"
    existing = db.query(models.WorkerTask).filter_by(idempotency_key=idempotency_key).one_or_none()
    if existing is not None:
        return existing

    task = models.WorkerTask(
        idempotency_key=idempotency_key,
        worker_type="cognitive",
        task_name="propose_research_followups",
        status="queued",
        priority=priority,
        inputs={"research_task_id": research_task_id},
    )
    db.add(task)
    db.flush()
    return task


def _context_for_task(
    db: Session,
    worker_task: models.WorkerTask,
) -> tuple[models.ResearchTask, cognitive_provider.CognitiveTaskContext]:
    inputs = worker_task.inputs
    if not isinstance(inputs, dict) or set(inputs) != {"research_task_id"}:
        raise cognitive_provider.CognitiveTaskInputError(
            "cognitive task inputs must contain only research_task_id"
        )
    research_task_id = inputs.get("research_task_id")
    if type(research_task_id) is not int or research_task_id <= 0:
        raise cognitive_provider.CognitiveTaskInputError("research_task_id must be a positive integer")
    research_task = db.get(models.ResearchTask, research_task_id)
    if research_task is None:
        raise cognitive_provider.CognitiveTaskInputError("research task does not exist")

    objective = (research_task.objective or research_task.query or "").strip()
    if not objective:
        raise cognitive_provider.CognitiveTaskInputError("research task has no objective")
    if len(objective) > cognitive_provider.MAX_COGNITIVE_OBJECTIVE_CHARS:
        raise cognitive_provider.CognitiveTaskBoundsError(
            f"research objective exceeds {cognitive_provider.MAX_COGNITIVE_OBJECTIVE_CHARS} characters"
        )

    raw_evidence_ids = (research_task.evidence_ids or "").strip()
    if len(raw_evidence_ids) > _MAX_EVIDENCE_ID_FIELD_CHARS:
        raise cognitive_provider.CognitiveTaskBoundsError("research evidence reference field is too large")
    if not raw_evidence_ids:
        evidence_ids: list[int] = []
        evidence_refs_truncated = False
    else:
        tokens = [item.strip() for item in raw_evidence_ids.split(",", maxsplit=cognitive_provider.MAX_COGNITIVE_EVIDENCE_IDS)]
        evidence_refs_truncated = len(tokens) > cognitive_provider.MAX_COGNITIVE_EVIDENCE_IDS
        selected_tokens = tokens[: cognitive_provider.MAX_COGNITIVE_EVIDENCE_IDS]
        if any(not token.isdecimal() or int(token) <= 0 for token in selected_tokens):
            raise cognitive_provider.CognitiveTaskInputError(
                "research evidence references must be positive persisted evidence IDs"
            )
        evidence_ids = [int(token) for token in selected_tokens]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise cognitive_provider.CognitiveTaskInputError("research evidence references must be unique")
        persisted_ids = {
            row[0]
            for row in db.query(models.Evidence.id)
            .filter(models.Evidence.id.in_(evidence_ids))
            .all()
        }
        if persisted_ids != set(evidence_ids):
            raise cognitive_provider.CognitiveTaskInputError(
                "research task references evidence that is not persisted"
            )

    return research_task, cognitive_provider.CognitiveTaskContext(
        research_task_id=research_task.id,
        objective=objective,
        evidence_ids=tuple(evidence_ids),
        evidence_refs_truncated=evidence_refs_truncated,
    )


def _validated_proposals(
    raw_proposals: Sequence[Mapping[str, Any]],
    context: cognitive_provider.CognitiveTaskContext,
) -> list[cognitive_provider.CognitiveProposal]:
    if not isinstance(raw_proposals, (list, tuple)):
        raise cognitive_provider.CognitiveProposalValidationError(
            "provider output must be a bounded proposal list"
        )
    if not raw_proposals or len(raw_proposals) > context.max_proposals:
        raise cognitive_provider.CognitiveProposalValidationError(
            f"provider must return between one and {context.max_proposals} proposals"
        )
    try:
        proposals = _PROPOSAL_LIST_ADAPTER.validate_python(raw_proposals)
    except ValidationError as exc:
        raise cognitive_provider.CognitiveProposalValidationError(
            "provider output did not satisfy the proposal-only schema"
        ) from exc

    allowed_evidence_ids = set(context.evidence_ids)
    for proposal in proposals:
        if any(evidence_id not in allowed_evidence_ids for evidence_id in proposal.evidence_ids):
            raise cognitive_provider.CognitiveProposalValidationError(
                "proposal cites evidence outside the linked research evidence set"
            )
    return proposals


def _context_digest(context: cognitive_provider.CognitiveTaskContext) -> str:
    canonical = json.dumps(
        {
            "research_task_id": context.research_task_id,
            "objective": context.objective,
            "evidence_ids": context.evidence_ids,
            "evidence_refs_truncated": context.evidence_refs_truncated,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_research_event(
    db: Session,
    research_task: models.ResearchTask,
    event_type: str,
    details: dict[str, Any],
) -> None:
    db.add(
        models.ResearchTaskEvent(
            task_id=research_task.id,
            event_type=event_type,
            step_name="evaluate",
            details=details,
        )
    )
    db.flush()


def _record_failure(
    db: Session,
    research_task: models.ResearchTask,
    worker_task: models.WorkerTask,
    event_type: str,
    provider_name: str,
    error_code: str,
) -> None:
    _record_research_event(
        db,
        research_task,
        event_type,
        {
            "worker_task_id": worker_task.id,
            "provider": provider_name,
            "error_code": error_code,
        },
    )
    # The worker manager rolls back the handler transaction when the handler
    # raises. A failure record that dies with that rollback is not a record:
    # commit it here so the fail-closed trace survives by design. The failure
    # paths raise immediately after, so no other handler writes are affected.
    db.commit()


def run_cognitive_task(
    db: Session,
    worker_task: models.WorkerTask,
    *,
    provider: cognitive_provider.CognitiveProvider | None = None,
) -> dict[str, Any]:
    """Produce validated proposals without mutating research truth or executing work."""
    research_task, context = _context_for_task(db, worker_task)
    configured_provider = provider
    provider_name = (
        getattr(configured_provider, "name", "injected")
        if configured_provider is not None
        else db_provider_name()
    )
    if configured_provider is None:
        try:
            configured_provider = cognitive_provider.get_cognitive_provider()
        except cognitive_provider.CognitiveProviderUnavailable:
            _record_failure(
                db,
                research_task,
                worker_task,
                "cognitive_provider_unavailable",
                provider_name,
                "provider_unavailable",
            )
            raise

    if configured_provider.mode not in {"MOCK", "TEST", "EXTERNAL"}:
        raise cognitive_provider.CognitiveProviderError("provider mode is invalid")
    if not configured_provider.name.strip() or not configured_provider.version.strip():
        raise cognitive_provider.CognitiveProviderError("provider identity is incomplete")

    try:
        proposals = _validated_proposals(configured_provider.propose(context), context)
    except cognitive_provider.CognitiveProposalValidationError:
        _record_failure(
            db,
            research_task,
            worker_task,
            "cognitive_proposal_rejected",
            configured_provider.name,
            "invalid_proposal",
        )
        raise
    except cognitive_provider.CognitiveProviderError:
        _record_failure(
            db,
            research_task,
            worker_task,
            "cognitive_provider_failed",
            configured_provider.name,
            "provider_execution_failed",
        )
        raise

    proposal_dicts = [proposal.model_dump(mode="json") for proposal in proposals]
    provenance = {
        "worker_task_id": worker_task.id,
        "research_task_id": research_task.id,
        "provider": configured_provider.name,
        "provider_version": configured_provider.version,
        "provider_mode": configured_provider.mode,
        "proposal_classification": "HYPOTHESIS",
        "context_sha256": _context_digest(context),
        "evidence_ids": list(context.evidence_ids),
        "evidence_refs_truncated": context.evidence_refs_truncated,
        "proposal_count": len(proposals),
    }
    event_key = f"cognitive-worker-proposals:v1:{worker_task.id}"
    event_payload = {
        **provenance,
        "proposal_sha256": [
            hashlib.sha256(
                json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            for item in proposal_dicts
        ],
    }
    substrate_event = (
        db.query(models.WorldEvent)
        .filter_by(idempotency_key=event_key)
        .one_or_none()
    )
    serialized_event_payload = json.dumps(
        event_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if substrate_event is None:
        world_graph.seed_core_types(db)
        db.add(
            models.WorldEvent(
                event_type="cognitive_proposals_generated",
                payload=serialized_event_payload,
                source="cognitive_worker",
                idempotency_key=event_key,
            )
        )
    elif substrate_event.payload != serialized_event_payload:
        raise cognitive_provider.CognitiveProviderError(
            "existing cognitive proposal event conflicts with this task result"
        )

    _record_research_event(
        db,
        research_task,
        "cognitive_proposals_generated",
        provenance,
    )
    db.flush()
    return {
        "result_type": "cognitive_proposals",
        "status": "PROPOSED",
        "execution_allowed": False,
        "research_task_id": research_task.id,
        "proposals": proposal_dicts,
        "provenance": provenance,
    }


def db_provider_name() -> str:
    """Return the configured selector for safe unavailable-provider provenance."""
    from app.config import settings

    return settings.COGNITIVE_PROVIDER.strip().lower()


def cognitive_handler(db: Session, worker_task: models.WorkerTask) -> dict[str, Any]:
    return run_cognitive_task(db, worker_task)
