"""API routes for observing/storing and listing signals."""

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import observer
from app.services import demand_understanding
from app.services import worker_manager
from app import security

router = APIRouter(prefix="/signals", tags=["signals"])


def _record_demand_request(
    content: str,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None,
    db: Session,
    *,
    request_boundary: str,
    require_idempotency_key: bool = False,
):
    content = content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="content must not be blank")
    if len(content) > 5000:
        raise HTTPException(status_code=422, detail="demand-understanding content exceeds 5000 characters")
    if require_idempotency_key and idempotency_key is None:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    if idempotency_key is not None and not 1 <= len(idempotency_key.strip()) <= 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key must contain 1-128 characters")

    request_key = idempotency_key.strip() if idempotency_key else secrets.token_urlsafe(24)
    request_key_digest = hashlib.sha256(request_key.encode("utf-8")).hexdigest()
    submitted_at = datetime.now(timezone.utc).isoformat()
    signal_identity = demand_understanding.normalized_identity_key(request_key_digest)
    signal = (
        db.query(models.Signal)
        .filter_by(source="user_request", identity_key=signal_identity)
        .one_or_none()
    )
    if signal is not None:
        if signal.content != demand_understanding.normalize_observation_content(content):
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used for different request content",
            )
    else:
        signal = demand_understanding.record_raw_observation(
            db,
            content,
            source="user_request",
            metadata={
                "identity_key": request_key_digest,
                "source_type": "manual",
                "collection_status": "user_submitted",
                "retrieved_at": submitted_at,
                "provenance": {
                    "request_boundary": request_boundary,
                    "purpose": "demand_understanding",
                    "authorization_context": "explicit_user_submission_for_demand_understanding",
                    "idempotency_key_sha256": request_key_digest,
                    "submitted_at": submitted_at,
                    "content_handling": "whitespace-normalized; email and phone patterns redacted",
                },
            },
        )
    task = demand_understanding.enqueue_understanding(db, [signal.id])
    response.headers["X-Demand-Understanding-Task-ID"] = str(task.id)
    response.headers["X-Demand-Understanding-Status-URL"] = (
        f"/signals/demand-understanding/{task.id}"
    )
    background_tasks.add_task(worker_manager.process_demand_task_in_background, task.id)
    return signal


@router.post("", response_model=schemas.SignalOut)
def create_signal(
    payload: schemas.SignalCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Store a new observed signal (e.g. a customer complaint, a market note)."""
    if payload.purpose == "demand_understanding":
        return _record_demand_request(
            payload.content,
            response,
            background_tasks,
            idempotency_key,
            db,
            request_boundary="POST /signals",
        )

    signal = observer.record_signal(
        db, content=payload.content, source=payload.source, category=payload.category
    )
    return signal


@router.post(
    "/public-request",
    response_model=schemas.SignalOut,
    status_code=202,
)
def create_public_demand_request(
    payload: schemas.PublicDemandRequestCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Accept a bounded, anonymous request for demand understanding only."""
    return _record_demand_request(
        payload.content,
        response,
        background_tasks,
        idempotency_key,
        db,
        request_boundary="POST /signals/public-request",
        require_idempotency_key=True,
    )


@router.get("", response_model=list[schemas.SignalOut])
def get_signals(
    request: Request,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """List stored signals, most recent first."""
    return observer.list_signals(
        db,
        limit=limit,
        include_user_requests=security.can_read_private_signals(request),
    )


@router.get(
    "/demand-understanding/{task_id}",
    response_model=schemas.DemandUnderstandingTaskStatus,
)
def get_demand_understanding_status(task_id: int, db: Session = Depends(get_db)):
    """Return persisted progress for one demand-understanding task."""
    task = (
        db.query(models.WorkerTask)
        .filter_by(id=task_id, worker_type="demand_understanding")
        .populate_existing()
        .one_or_none()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="demand-understanding task not found")

    outputs = task.outputs if isinstance(task.outputs, dict) else {}
    phase = {
        "queued": "understanding",
        "running": "understanding",
        "completed": "completed",
        "failed": "blocked",
        "blocked": "blocked",
    }.get(task.status, "unknown")
    if task.status == "queued" and task.next_run_at is not None:
        next_run_at = task.next_run_at
        if next_run_at.tzinfo is None:
            next_run_at = next_run_at.replace(tzinfo=timezone.utc)
        if next_run_at > datetime.now(timezone.utc):
            phase = "retry_wait"
    return schemas.DemandUnderstandingTaskStatus(
        task_id=task.id,
        status=task.status,
        phase=phase,
        interpretation_state=outputs.get("state"),
        need_id=outputs.get("need_id"),
        unresolved_questions=outputs.get("unresolved_questions") or [],
        updated_at=task.updated_at,
        next_run_at=task.next_run_at,
    )
