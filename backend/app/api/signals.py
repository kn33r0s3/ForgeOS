"""API routes for observing/storing and listing signals."""

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import observer
from app.services import demand_understanding

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=schemas.SignalOut)
def create_signal(
    payload: schemas.SignalCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Store a new observed signal (e.g. a customer complaint, a market note)."""
    if payload.purpose == "demand_understanding":
        content = payload.content.strip()
        if not content:
            raise HTTPException(status_code=422, detail="content must not be blank")
        if len(content) > 5000:
            raise HTTPException(status_code=422, detail="demand-understanding content exceeds 5000 characters")
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
                        "request_boundary": "POST /signals",
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
        return signal

    signal = observer.record_signal(
        db, content=payload.content, source=payload.source, category=payload.category
    )
    return signal


@router.get("", response_model=list[schemas.SignalOut])
def get_signals(limit: int = 200, db: Session = Depends(get_db)):
    """List stored signals, most recent first."""
    return observer.list_signals(db, limit=limit)
