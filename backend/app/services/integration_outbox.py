"""Durable boundary for optional real-world integrations.

This module never performs network I/O. Adapters enqueue intent locally, then a
separate worker may deliver it. If the worker, network, or vendor is down, the
local record remains recoverable and no business success is fabricated.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session

from app import models

MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enqueue(
    db: Session,
    *,
    integration_name: str,
    operation: str,
    idempotency_key: str,
    request: dict[str, Any] | None = None,
    _forge_bot_decision: Any = None,
) -> models.IntegrationDelivery:
    """Persist an external intent exactly once before any network call."""
    request_data = request or {}
    from app.services import forge_bot_response

    forge_bot_response.enforce_delivery_boundary(
        db,
        integration_name=integration_name,
        operation=operation,
        request=request_data,
        action_decision=_forge_bot_decision,
    )
    existing = db.query(models.IntegrationDelivery).filter_by(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    row = models.IntegrationDelivery(
        integration_name=integration_name,
        operation=operation,
        idempotency_key=idempotency_key,
        request_json=json.dumps(request_data, sort_keys=True, default=str),
        status="QUEUED",
        attempts=0,
        next_attempt_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_succeeded(
    db: Session,
    delivery_id: int,
    response: dict[str, Any] | None = None,
    status: str = "SUCCEEDED",
) -> models.IntegrationDelivery:
    row = db.get(models.IntegrationDelivery, delivery_id)
    if not row:
        raise ValueError("integration delivery not found")
    row.status = status
    row.response_json = json.dumps(response or {}, sort_keys=True, default=str)
    row.last_error = None
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def mark_failed(
    db: Session,
    delivery_id: int,
    error: str,
    permanent: bool = False,
) -> models.IntegrationDelivery:
    row = db.get(models.IntegrationDelivery, delivery_id)
    if not row:
        raise ValueError("integration delivery not found")
    row.attempts += 1
    row.last_error = error[:2000]
    row.updated_at = _now()
    if permanent or row.attempts >= MAX_ATTEMPTS:
        row.status = "FAILED"
        row.next_attempt_at = None
    else:
        row.status = "QUEUED"
        row.next_attempt_at = _now() + timedelta(seconds=BASE_BACKOFF_SECONDS * (2 ** (row.attempts - 1)))
    db.commit()
    db.refresh(row)
    return row


def pending(db: Session, *, limit: int = 50) -> list[models.IntegrationDelivery]:
    now = _now()
    return (
        db.query(models.IntegrationDelivery)
        .filter(models.IntegrationDelivery.status == "QUEUED")
        .filter((models.IntegrationDelivery.next_attempt_at.is_(None)) | (models.IntegrationDelivery.next_attempt_at <= now))
        .order_by(models.IntegrationDelivery.id.asc())
        .limit(limit)
        .all()
    )
