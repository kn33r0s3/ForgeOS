"""Small durable cache for reusable intelligence inputs/results."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models


def utcnow():
    return datetime.now(timezone.utc)


def fingerprint(value: Any) -> str:
    if isinstance(value, str):
        # Whitespace-normalized only: identifiers (e.g. YouTube video IDs)
        # are case-SENSITIVE, so casefolding would collapse distinct keys.
        normalized = " ".join(value.split())
    else:
        normalized = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def cache_identity(object_type: str, value: Any, parameters: Any = None) -> tuple[str, str]:
    input_fingerprint = fingerprint({"value": value, "parameters": parameters})
    return f"{object_type}:{input_fingerprint}", input_fingerprint


def get(
    db: Session,
    *,
    object_type: str,
    value: Any,
    parameters: Any = None,
    allow_stale: bool = False,
) -> tuple[models.IntelligenceCacheEntry | None, bool]:
    key, input_fingerprint = cache_identity(object_type, value, parameters)
    entry = db.query(models.IntelligenceCacheEntry).filter_by(cache_key=key).first()
    if not entry:
        return None, False
    now = utcnow()
    expires = _as_utc(entry.expires_at)
    stale_since = _as_utc(entry.stale_at)
    if (expires and expires <= now) or (stale_since and stale_since <= now):
        # stale_at was previously write-only (put stored it, get never read
        # it); it now drives the stale transition exactly like expires_at.
        if entry.status != "stale":
            entry.status = "stale"
            db.commit()
    if entry.status == "invalidated" or (entry.status == "stale" and not allow_stale):
        return entry, False
    return entry, True


def put(
    db: Session,
    *,
    object_type: str,
    value: Any,
    content: str,
    parameters: Any = None,
    metadata: dict | None = None,
    provider: str | None = None,
    model: str | None = None,
    expires_at: datetime | None = None,
    stale_at: datetime | None = None,
) -> models.IntelligenceCacheEntry:
    key, input_fingerprint = cache_identity(object_type, value, parameters)
    entry = db.query(models.IntelligenceCacheEntry).filter_by(cache_key=key).first()
    if not entry:
        entry = models.IntelligenceCacheEntry(
            cache_key=key,
            object_type=object_type,
            input_fingerprint=input_fingerprint,
        )
        db.add(entry)
    entry.content = content
    entry.metadata_json = metadata or {}
    entry.provider = provider
    entry.model = model
    entry.fetched_at = utcnow()
    entry.expires_at = expires_at
    entry.stale_at = stale_at
    entry.status = "current"
    entry.updated_at = utcnow()
    db.commit()
    db.refresh(entry)
    return entry


def invalidate(db: Session, entry: models.IntelligenceCacheEntry) -> models.IntelligenceCacheEntry:
    entry.status = "invalidated"
    entry.updated_at = utcnow()
    db.commit()
    db.refresh(entry)
    return entry


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
