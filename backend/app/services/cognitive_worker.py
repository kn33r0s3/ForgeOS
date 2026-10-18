"""Bounded proposal-only cognitive tasks over existing research records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse, urlunsplit

from sqlalchemy import String, and_, cast, exists, func, literal, or_

from app import evidence_source

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app import models
from app.services import cognitive_provider, world_graph

_PROPOSAL_LIST_ADAPTER = TypeAdapter(list[cognitive_provider.CognitiveProposal])
_MAX_EVIDENCE_ID_FIELD_CHARS = 4_096

# Only structured, deterministic-verifier categories may be remembered and
# passed to a retry. Arbitrary provider output/error text never enters feedback.
_PROPOSAL_FIELDS = frozenset({
    "kind", "title", "rationale", "next_step", "evidence_ids",
    "status", "execution_authorized",
})
_SAFE_FAILURE_SIGNATURES = frozenset({
    "kind:literal_error",
    "title:string_too_short", "title:string_too_long",
    "rationale:string_too_short", "rationale:string_too_long",
    "next_step:string_too_short", "next_step:string_too_long",
    "evidence_ids:too_long", "evidence_ids:list_type",
    "evidence_ids:int_type", "evidence_ids:outside_linked_set",
    "status:literal_error", "execution_authorized:literal_error",
    "proposal:extra_forbidden", "proposal:schema_error",
})


def _safe_validation_failure_signatures(error: ValidationError) -> tuple[str, ...]:
    """Reduce Pydantic errors to a small allow-list; never persist input values."""
    signatures: set[str] = set()
    for item in error.errors(include_url=False):
        location = item.get("loc", ())
        field = next(
            (
                part for part in reversed(location)
                if isinstance(part, str) and part in _PROPOSAL_FIELDS
            ),
            None,
        )
        error_type = str(item.get("type") or "")
        if field is None:
            signature = (
                "proposal:extra_forbidden"
                if error_type == "extra_forbidden"
                else "proposal:schema_error"
            )
        else:
            candidate = f"{field}:{error_type}"
            signature = (
                candidate
                if candidate in _SAFE_FAILURE_SIGNATURES
                else "proposal:schema_error"
            )
        signatures.add(signature)
    return tuple(sorted(signatures & _SAFE_FAILURE_SIGNATURES))[:8] or (
        "proposal:schema_error",
    )


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
        evidence_rows = {
            row.id: row
            for row in db.query(models.Evidence)
            .filter(models.Evidence.id.in_(evidence_ids))
            .all()
        }
        if set(evidence_rows) != set(evidence_ids):
            raise cognitive_provider.CognitiveTaskInputError(
                "research task references evidence that is not persisted"
            )

    # Provider-visible context is deliberately narrower than linked provenance.
    # Only explicitly REAL, public third-party material marked not_required for
    # consent is passed, and only short title/claim/URL fields are exposed.
    # Customer, private first-hand, consent-pending, TEST, MOCK and HYPOTHESIS
    # records remain linkable but their content never enters this model prompt.
    evidence_context: list[dict[str, str]] = []
    available_evidence_ids: list[int] = []
    context_chars = 0
    max_context_chars = 6_000
    for evidence_id in evidence_ids:
        row = evidence_rows[evidence_id]
        url = (row.canonical_url or "").strip()
        parsed_url = urlparse(url)
        if not (
            evidence_source.is_real(row.source_kind)
            and (row.source_type or "").strip().lower() == "third_party"
            and (row.consent_status or "").strip().lower() == "not_required"
            and (row.collection_status or "").strip().lower() == "collected"
            and row.source_identity is None
            and parsed_url.scheme in {"http", "https"}
            and parsed_url.netloc
            and parsed_url.username is None
            and parsed_url.password is None
        ):
            continue
        title = " ".join((row.title or "").split())[:200]
        # Canonical URLs are untrusted input. Never pass query strings,
        # fragments or userinfo-like credential material into the model prompt.
        safe_url = urlunsplit((
            parsed_url.scheme.lower(),
            parsed_url.netloc,
            parsed_url.path or "/",
            "",
            "",
        ))
        claim = " ".join((row.claim or "").split())[:500]
        if not title and not claim:
            continue
        item = {
            "evidence_id": str(row.id),
            "title": title,
            "claim": claim,
            "canonical_url": safe_url[:500],
        }
        item_size = sum(len(value) for value in item.values())
        if context_chars + item_size > max_context_chars:
            break
        evidence_context.append(item)
        available_evidence_ids.append(row.id)
        context_chars += item_size

    return research_task, cognitive_provider.CognitiveTaskContext(
        research_task_id=research_task.id,
        objective=objective,
        evidence_ids=tuple(evidence_ids),
        evidence_refs_truncated=evidence_refs_truncated,
        language_context=cognitive_provider.script_context_hint(objective),
        available_evidence_ids=tuple(available_evidence_ids),
        evidence_context=tuple(evidence_context),
        prior_failure_signatures=_prior_failure_signatures(db, research_task.id),
    )


def _prior_failure_signatures(
    db: Session,
    research_task_id: int,
    *,
    limit: int = 4,
) -> tuple[str, ...]:
    """Load only safe schema-verifier failures from prior attempts of this task."""
    events = (
        db.query(models.ResearchTaskEvent)
        .filter_by(
            task_id=research_task_id,
            event_type="cognitive_proposal_rejected",
        )
        .order_by(
            models.ResearchTaskEvent.created_at.desc(),
            models.ResearchTaskEvent.id.desc(),
        )
        .limit(max(1, min(limit, 8)))
        .all()
    )
    signatures: list[str] = []
    for event in events:
        details = event.details
        if not isinstance(details, dict):
            continue
        values = details.get("failure_signatures")
        if not isinstance(values, list):
            continue
        for value in values:
            if value in _SAFE_FAILURE_SIGNATURES and value not in signatures:
                signatures.append(value)
                if len(signatures) >= 8:
                    return tuple(signatures)
    return tuple(signatures)


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
            "provider output did not satisfy the proposal-only schema",
            failure_signatures=_safe_validation_failure_signatures(exc),
        ) from exc

    allowed_evidence_ids = set(
        context.available_evidence_ids
        if context.available_evidence_ids is not None
        else context.evidence_ids
    )
    for proposal in proposals:
        if any(evidence_id not in allowed_evidence_ids for evidence_id in proposal.evidence_ids):
            raise cognitive_provider.CognitiveProposalValidationError(
                "proposal cites evidence outside the linked research evidence set",
                failure_signatures=("evidence_ids:outside_linked_set",),
            )
    return proposals


def _context_digest(context: cognitive_provider.CognitiveTaskContext) -> str:
    canonical = json.dumps(
        {
            "research_task_id": context.research_task_id,
            "objective": context.objective,
            "evidence_ids": context.evidence_ids,
            "available_evidence_ids": context.available_evidence_ids,
            "evidence_context": context.evidence_context,
            "evidence_refs_truncated": context.evidence_refs_truncated,
            "language_context": context.language_context,
            "prior_failure_signatures": context.prior_failure_signatures,
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
    failure_signatures: Sequence[str] = (),
) -> None:
    details: dict[str, Any] = {
        "worker_task_id": worker_task.id,
        "provider": provider_name,
        "error_code": error_code,
    }
    safe_signatures = [
        item for item in failure_signatures
        if isinstance(item, str) and item in _SAFE_FAILURE_SIGNATURES
    ][:8]
    if safe_signatures:
        details["failure_signatures"] = list(dict.fromkeys(safe_signatures))
    _record_research_event(
        db,
        research_task,
        event_type,
        details,
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

    if configured_provider.mode not in {"MOCK", "TEST", "LOCAL", "SELF_HOSTED", "EXTERNAL"}:
        raise cognitive_provider.CognitiveProviderError("provider mode is invalid")
    if not configured_provider.name.strip() or not configured_provider.version.strip():
        raise cognitive_provider.CognitiveProviderError("provider identity is incomplete")

    provider_evidence_ids = tuple(
        context.available_evidence_ids
        if context.available_evidence_ids is not None
        else context.evidence_ids
    )
    provider_context = replace(
        context,
        evidence_ids=provider_evidence_ids,
        available_evidence_ids=provider_evidence_ids,
    )
    try:
        proposals = _validated_proposals(
            configured_provider.propose(provider_context),
            context,
        )
    except cognitive_provider.CognitiveProposalValidationError as exc:
        _record_failure(
            db,
            research_task,
            worker_task,
            "cognitive_proposal_rejected",
            configured_provider.name,
            "invalid_proposal",
            failure_signatures=getattr(exc, "failure_signatures", ()),
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
    raw_provider_metadata = getattr(configured_provider, "last_call_metadata", {})
    provider_metadata = {}
    if isinstance(raw_provider_metadata, dict):
        for key in ("prompt_eval_tokens", "completion_eval_tokens", "total_duration_ms"):
            value = raw_provider_metadata.get(key)
            if value is None or (type(value) in {int, float} and value >= 0):
                provider_metadata[key] = value
    provenance = {
        "worker_task_id": worker_task.id,
        "research_task_id": research_task.id,
        "provider": configured_provider.name,
        "provider_version": configured_provider.version,
        "provider_mode": configured_provider.mode,
        "provider_metadata": provider_metadata,
        "language_context": context.language_context,
        "prior_failure_signatures": list(context.prior_failure_signatures),
        "proposal_classification": "HYPOTHESIS",
        "context_sha256": _context_digest(context),
        "evidence_ids": list(context.evidence_ids),
        "available_evidence_ids": list(context.available_evidence_ids or ()),
        "evidence_context_count": len(context.evidence_context),
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


def run_pending_cognitive_tasks(
    db: Session,
    *,
    limit: int = 2,
    candidate_limit: int = 80,
) -> dict[str, Any]:
    """Run a bounded proposal batch using local or owner-approved self-hosted Ollama.

    Both provider selections must explicitly choose Ollama. Vercel loopback is
    rejected; a remote HTTPS gateway requires a bearer token and separate owner
    approval for internal task-context transfer. The existing owner agent-run
    gate still applies. Outputs remain PROPOSED: no research truth is mutated,
    no Actions are executed, and no contact, spending, or publication occurs.
    """
    if limit <= 0 or candidate_limit <= 0:
        return {
            "status": "skipped",
            "reason": "non_positive_batch_limit",
            "attempted": 0,
            "completed": 0,
            "outcomes": [],
        }

    from app.config import settings

    if (
        settings.AI_PROVIDER.strip().lower() != "ollama"
        or settings.COGNITIVE_PROVIDER.strip().lower() != "ollama"
    ):
        return {
            "status": "disabled",
            "reason": "explicit_local_ollama_selection_required",
            "attempted": 0,
            "completed": 0,
            "outcomes": [],
        }
    import os
    from app.services import ai_engine

    transport_mode = ai_engine.ollama_transport_mode()
    if transport_mode is None:
        return {
            "status": "unavailable",
            "reason": (
                "local_ollama_is_not_available_in_vercel_runtime"
                if os.getenv("VERCEL")
                else "ollama_transport_not_safely_configured"
            ),
            "attempted": 0,
            "completed": 0,
            "outcomes": [],
        }
    if (
        transport_mode == "SELF_HOSTED"
        and not settings.HAMI_ALLOW_INTERNAL_CONTEXT_TO_SELF_HOSTED_OLLAMA
    ):
        return {
            "status": "blocked",
            "reason": "remote_internal_context_not_authorized",
            "attempted": 0,
            "completed": 0,
            "outcomes": [],
        }

    from app.services import operating_v4

    try:
        operating_v4.check_agent_run_allowed(db)
    except ValueError:
        return {
            "status": "blocked",
            "reason": "owner_agent_run_gate",
            "attempted": 0,
            "completed": 0,
            "outcomes": [],
        }

    now = models.utcnow()
    cap = max(1, min(int(candidate_limit), 200))

    # Filter work that cannot run before limiting the ranked candidate window.
    # Otherwise old completed or max-attempt WorkerTasks can occupy every slot
    # and permanently hide newer questions.
    worker_key = (
        literal("cognitive-research-task:v1:")
        + cast(models.ResearchTask.id, String)
    )
    any_worker = (
        db.query(models.WorkerTask.id)
        .filter(models.WorkerTask.idempotency_key == worker_key)
        .correlate(models.ResearchTask)
        .exists()
    )
    runnable_existing_worker = (
        db.query(models.WorkerTask.id)
        .filter(
            models.WorkerTask.idempotency_key == worker_key,
            models.WorkerTask.status.in_(("queued", "failed", "blocked")),
            or_(
                models.WorkerTask.next_run_at.is_(None),
                models.WorkerTask.next_run_at <= now,
            ),
            or_(
                models.WorkerTask.status != "failed",
                models.WorkerTask.attempts < models.WorkerTask.max_attempts,
            ),
        )
        .correlate(models.ResearchTask)
        .exists()
    )
    worker_is_dispatchable = or_(~any_worker, runnable_existing_worker)

    # Match comma-separated evidence IDs against persisted rows in SQL so
    # restricted/private/TEST/MOCK tasks do not occupy slots before the Python
    # context builder enforces the same provider-visible boundary.
    reference_csv = func.replace(models.ResearchTask.evidence_ids, " ", "")
    evidence_id_text = cast(models.Evidence.id, String)
    reference_matches = or_(
        reference_csv == evidence_id_text,
        reference_csv.like(evidence_id_text + literal(",%")),
        reference_csv.like(literal("%,") + evidence_id_text + literal(",%")),
        reference_csv.like(literal("%,") + evidence_id_text),
    )
    safe_url = func.trim(models.Evidence.canonical_url)
    eligible_public_evidence = (
        db.query(models.Evidence.id)
        .filter(
            reference_matches,
            func.upper(func.trim(models.Evidence.source_kind)) == "REAL",
            func.lower(func.trim(func.coalesce(models.Evidence.source_type, ""))) == "third_party",
            func.lower(func.trim(func.coalesce(models.Evidence.consent_status, ""))) == "not_required",
            func.lower(func.trim(func.coalesce(models.Evidence.collection_status, ""))) == "collected",
            models.Evidence.source_identity.is_(None),
            or_(safe_url.like("https://%"), safe_url.like("http://%")),
            ~safe_url.like("https:///%"),
            ~safe_url.like("http:///%"),
            ~safe_url.like("https://%@%"),
            ~safe_url.like("http://%@%"),
            or_(
                func.length(func.trim(func.coalesce(models.Evidence.title, ""))) > 0,
                func.length(func.trim(func.coalesce(models.Evidence.claim, ""))) > 0,
            ),
        )
        .correlate(models.ResearchTask)
        .exists()
    )

    research_rows = (
        db.query(models.ResearchTask)
        .join(
            models.ResearchQuestion,
            models.ResearchQuestion.id == models.ResearchTask.question_id,
        )
        .filter(
            models.ResearchTask.status == "completed",
            models.ResearchTask.evidence_ids.isnot(None),
            models.ResearchTask.evidence_ids != "",
            worker_is_dispatchable,
            eligible_public_evidence,
        )
        .order_by(
            models.ResearchQuestion.priority_score.desc(),
            models.ResearchTask.updated_at.asc(),
            models.ResearchTask.id.asc(),
        )
        .limit(cap)
        .all()
    )

    eligible: list[tuple[models.ResearchTask, models.WorkerTask | None]] = []
    for research_task in research_rows:
        key = f"cognitive-research-task:v1:{research_task.id}"
        worker_task = (
            db.query(models.WorkerTask)
            .filter_by(idempotency_key=key)
            .one_or_none()
        )
        if worker_task is not None:
            if worker_task.status in {"completed", "running"}:
                continue
            if worker_task.status == "failed" and worker_task.attempts >= worker_task.max_attempts:
                continue
            if worker_task.next_run_at is not None and worker_task.next_run_at > now:
                continue
            if worker_task.status not in {"queued", "failed", "blocked"}:
                continue

        # Check provider-visible evidence before creating/claiming work. This
        # lets metadata-only or restricted rows wait without filling the queue.
        preview = models.WorkerTask(
            worker_type="cognitive",
            task_name="preview_research_followups",
            inputs={"research_task_id": research_task.id},
        )
        try:
            _, context = _context_for_task(db, preview)
        except (
            cognitive_provider.CognitiveTaskInputError,
            cognitive_provider.CognitiveTaskBoundsError,
        ):
            continue
        if not context.available_evidence_ids:
            continue
        eligible.append((research_task, worker_task))

    # Coverage pass: one research question gets a turn before a second task
    # from that same question consumes the finite batch. Remaining slots then
    # follow the same ranked priority order.
    outcomes: list[dict[str, Any]] = []
    attempted_ids: set[int] = set()
    served_question_ids: set[int] = set()
    completed = 0
    coverage_pass = True

    def select_next(unserved_only: bool) -> tuple[models.ResearchTask, models.WorkerTask | None] | None:
        for candidate in eligible:
            research_task, existing_worker = candidate
            if research_task.id in attempted_ids:
                continue
            if unserved_only and research_task.question_id in served_question_ids:
                continue
            return candidate
        return None

    while len(outcomes) < limit:
        selected = select_next(coverage_pass)
        if selected is None and coverage_pass:
            coverage_pass = False
            selected = select_next(False)
        if selected is None:
            break

        research_task, worker_task = selected
        attempted_ids.add(research_task.id)
        served_question_ids.add(research_task.question_id)
        dispatch_pass = "question_coverage" if coverage_pass else "throughput"
        key = f"cognitive-research-task:v1:{research_task.id}"
        try:
            if worker_task is None:
                try:
                    worker_task = create_cognitive_task(db, research_task.id)
                except Exception as exc:
                    # Another invocation may have inserted the unique key
                    # between selection and creation. Roll back, then reuse it.
                    db.rollback()
                    worker_task = (
                        db.query(models.WorkerTask)
                        .filter_by(idempotency_key=key)
                        .one_or_none()
                    )
                    if worker_task is None:
                        raise exc
            if worker_task.status in {"failed", "blocked"}:
                worker_task.status = "queued"
                worker_task.next_run_at = None
                worker_task.error = None
                db.commit()

            claim = db.query(models.WorkerTask).filter(
                models.WorkerTask.id == worker_task.id,
                models.WorkerTask.worker_type == "cognitive",
                models.WorkerTask.status == "queued",
                (models.WorkerTask.next_run_at.is_(None))
                | (models.WorkerTask.next_run_at <= models.utcnow()),
            )
            claimed = claim.update(
                {"status": "running", "updated_at": models.utcnow()},
                synchronize_session=False,
            )
            db.commit()
            if not claimed:
                outcomes.append({
                    "research_task_id": research_task.id,
                    "worker_task_id": worker_task.id,
                    "status": "skipped",
                    "reason": "task_not_claimable",
                    "dispatch_pass": dispatch_pass,
                })
                continue

            db.expire_all()
            worker_task = db.get(models.WorkerTask, worker_task.id)
            if worker_task is None:
                outcomes.append({
                    "research_task_id": research_task.id,
                    "status": "failed",
                    "reason": "claimed_task_disappeared",
                    "dispatch_pass": dispatch_pass,
                })
                continue
            # Recheck safety immediately before the local provider call.
            try:
                operating_v4.check_agent_run_allowed(db)
            except ValueError:
                # A changed owner gate is not a model/provider failure. Return
                # the lease to the queue without spending its retry budget.
                worker_task.status = "queued"
                worker_task.error = None
                worker_task.next_run_at = None
                worker_task.updated_at = models.utcnow()
                db.commit()
                outcomes.append({
                    "research_task_id": research_task.id,
                    "worker_task_id": worker_task.id,
                    "status": "blocked",
                    "reason": "owner_agent_run_gate",
                    "dispatch_pass": dispatch_pass,
                })
                continue
            result = run_cognitive_task(db, worker_task)
            worker_task.outputs = result
            worker_task.status = "completed"
            worker_task.error = None
            worker_task.next_run_at = None
            worker_task.updated_at = models.utcnow()
            db.commit()
            completed += 1
            outcomes.append({
                "research_task_id": research_task.id,
                "worker_task_id": worker_task.id,
                "status": "completed",
                "proposal_count": len(result.get("proposals", [])),
                "provider_mode": result.get("provenance", {}).get("provider_mode"),
                "dispatch_pass": dispatch_pass,
            })
        except Exception as exc:
            db.rollback()
            failed = db.get(models.WorkerTask, worker_task.id) if worker_task is not None else None
            if failed is not None:
                failed.attempts += 1
                failed.error = type(exc).__name__
                failed.updated_at = models.utcnow()
                if failed.attempts >= failed.max_attempts:
                    failed.status = "failed"
                    failed.next_run_at = None
                else:
                    failed.status = "queued"
                    failed.next_run_at = models.utcnow() + timedelta(minutes=min(2 ** failed.attempts, 60))
                db.commit()
            outcomes.append({
                "research_task_id": research_task.id,
                "worker_task_id": worker_task.id if worker_task is not None else None,
                "status": "failed",
                "error_type": type(exc).__name__,
                "dispatch_pass": dispatch_pass,
            })

    failures = sum(1 for item in outcomes if item.get("status") == "failed")
    return {
        "status": "partial" if failures else "ok",
        "attempted": len(outcomes),
        "completed": completed,
        "failed": failures,
        "outcomes": outcomes,
    }


def db_provider_name() -> str:
    """Return the configured selector for safe unavailable-provider provenance."""
    from app.config import settings

    return settings.COGNITIVE_PROVIDER.strip().lower()


def cognitive_handler(db: Session, worker_task: models.WorkerTask) -> dict[str, Any]:
    return run_cognitive_task(db, worker_task)
