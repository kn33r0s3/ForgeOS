"""Hami Autonomy - Step 1: idempotency record store (C2).

Deterministic keys plus the durable lifecycle for the execution gate
(plan sections 3a and 1b-C2). Backed by the existing durable store:
the ``IdempotencyRecord`` model in ``app.models`` (table
``idempotency_records``), created by the same ``Base.metadata.create_all``
that creates every other table - no new database.

Key: ``sha256(operation + "|" + principal + "|" + canonical_scope +
"|" + sha256(canonical_payload))``, hex-encoded. Canonical means JSON
with sorted keys, no timestamps, no random values. Two identical
requests produce the same key; two different payloads produce different
keys. The key is computed by the gate (E4), never trusted from the
caller.

Lifecycle: ``started`` -> ``completed`` / ``failed`` / ``abandoned``.
A ``started`` record younger than its lease means the operation is
in progress - the gate refuses a duplicate. A stale ``started`` record
(older than its lease) is marked ``abandoned`` and the operation may
run once, under a new attempt number. Mutating functions commit, so a
``completed`` record is durable before the gate returns its result.

Never store payloads containing secrets - step-1 payloads contain none
by construction.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models


def _canonical_json(payload: dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, no timestamps, no random values."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_idempotency_key(
    operation: str,
    principal: str,
    scope: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """Deterministic idempotency key for one (operation, principal, scope, payload)."""
    canonical_scope = scope.strip()
    canonical_payload = _canonical_json(payload or {})
    payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    material = f"{operation}|{principal}|{canonical_scope}|{payload_hash}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lookup(db: Session, key: str) -> Optional[models.IdempotencyRecord]:
    """Return the record for ``key``, or None when this is a first attempt."""
    return db.query(models.IdempotencyRecord).filter_by(key=key).one_or_none()


def record_started(
    db: Session,
    *,
    key: str,
    operation: str,
    principal: str,
    scope: str,
    payload: dict[str, Any] | None = None,
    attempt: int = 1,
    lease_seconds: int = 600,
) -> models.IdempotencyRecord:
    """Create a ``started`` record for a new attempt under ``key``.

    Lease defaults to 10 minutes (OP-03 test runs use 30 minutes -
    pass ``lease_seconds=1800``). Commits before returning.
    """
    payload = payload or {}
    record = models.IdempotencyRecord(
        key=key,
        operation=operation,
        principal=principal,
        scope_hash=_hash(scope.strip()),
        payload_hash=_hash(_canonical_json(payload)),
        status="started",
        attempt=attempt,
        result=None,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=lease_seconds),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def record_completed(
    db: Session, key: str, result: dict[str, Any]
) -> Optional[models.IdempotencyRecord]:
    """Mark ``key`` completed and store the result BEFORE the gate returns it."""
    record = lookup(db, key)
    if record is None:
        return None
    record.status = "completed"
    record.result = result
    db.commit()
    db.refresh(record)
    return record


def record_failed(
    db: Session, key: str, reason: str
) -> Optional[models.IdempotencyRecord]:
    """Mark ``key`` failed with the reason stored in the result blob."""
    record = lookup(db, key)
    if record is None:
        return None
    record.status = "failed"
    record.result = {"error": reason}
    db.commit()
    db.refresh(record)
    return record


def mark_abandoned(
    db: Session, record: models.IdempotencyRecord
) -> models.IdempotencyRecord:
    """Mark a stale ``started`` record abandoned so the operation may run once."""
    record.status = "abandoned"
    db.commit()
    db.refresh(record)
    return record


def record_restarted(
    db: Session, record: models.IdempotencyRecord, *, attempt: int, lease_seconds: int = 600
) -> models.IdempotencyRecord:
    """Re-open a ``failed`` (or ``abandoned``) record for a new attempt
    under the SAME key. The gate calls this instead of ``record_started``
    when a record already exists for the key - ``record_started`` does a
    plain INSERT and would crash on the key's UNIQUE constraint.
    Commits before returning."""
    record.status = "started"
    record.attempt = attempt
    record.result = None
    record.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
    db.commit()
    db.refresh(record)
    return record


def is_stale(record: models.IdempotencyRecord, now: Optional[datetime] = None) -> bool:
    """True when a ``started`` record is older than its lease."""
    if record.status != "started":
        return False
    if record.lease_expires_at is None:
        return False
    moment = now or datetime.now(timezone.utc)
    expires = record.lease_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment >= expires
