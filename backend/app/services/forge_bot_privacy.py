"""Retention and durable, privacy-preserving Forge Bot intake limits."""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app import models
from app.services import world_graph

RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 3600
RETENTION_DAYS = 30


def _visitor_hash(request: Request, key: str) -> str:
    if os.getenv("VERCEL") and request.headers.get("x-vercel-forwarded-for"):
        identifier = request.headers["x-vercel-forwarded-for"].split(",", 1)[0].strip()
    else:
        identifier = request.client.host if request.client else "unknown"
    if not identifier:
        identifier = "unknown"
    message = f"forge-bot-intake-rate-limit:{identifier}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _require_durable_database(db: Session) -> None:
    if os.getenv("VERCEL") and db.get_bind().dialect.name != "postgresql":
        raise HTTPException(
            status_code=503,
            detail="Durable Forge Bot privacy storage requires PostgreSQL.",
        )


def consume_intake_submission(
    db: Session,
    request: Request,
    *,
    hmac_key: str,
    now: datetime | None = None,
) -> bool:
    """Atomically consume one hourly slot without persisting the visitor identifier."""
    _require_durable_database(db)
    timestamp = now or datetime.now(timezone.utc)
    expires_at = timestamp + timedelta(seconds=RATE_WINDOW_SECONDS)
    visitor_hash = _visitor_hash(request, hmac_key)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgres_insert(models.ForgeBotIntakeRateLimit)
    elif dialect == "sqlite":
        insert = sqlite_insert(models.ForgeBotIntakeRateLimit)
    else:
        raise RuntimeError(f"Unsupported Forge Bot rate-limit database dialect: {dialect}")

    expired = models.ForgeBotIntakeRateLimit.expires_at <= timestamp
    current_count = models.ForgeBotIntakeRateLimit.request_count
    capped_count = case(
        (current_count < RATE_LIMIT + 1, current_count + 1),
        else_=RATE_LIMIT + 1,
    )
    statement = (
        insert.values(
            visitor_hash=visitor_hash,
            request_count=1,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            index_elements=[models.ForgeBotIntakeRateLimit.visitor_hash],
            set_={
                "request_count": case((expired, 1), else_=capped_count),
                "expires_at": case(
                    (expired, expires_at),
                    else_=models.ForgeBotIntakeRateLimit.expires_at,
                ),
            },
        )
        .returning(models.ForgeBotIntakeRateLimit.request_count)
    )
    request_count = db.execute(statement).scalar_one()
    db.commit()
    return request_count <= RATE_LIMIT


def _has_response_action(db: Session, reference: str) -> bool:
    return (
        db.query(models.Action.id)
        .filter(
            models.Action.action_type == "forge_bot_response",
            models.Action.parameters_json.contains(reference),
        )
        .first()
        is not None
    )


def run_daily_maintenance(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Erase old READY_FOR_OWNER_REVIEW inquiries without a response ACTION."""
    _require_durable_database(db)
    timestamp = now or datetime.now(timezone.utc)
    cutoff = timestamp - timedelta(days=RETENTION_DAYS)
    try:
        candidates = (
            db.query(models.ForgeBotLeadContact)
            .filter(
                models.ForgeBotLeadContact.stage == "READY_FOR_OWNER_REVIEW",
                models.ForgeBotLeadContact.opted_out.is_(False),
                models.ForgeBotLeadContact.erased_at.is_(None),
                models.ForgeBotLeadContact.created_at <= cutoff,
            )
            .with_for_update(skip_locked=True)
            .all()
        )
        world_graph.seed_core_types(db)
        erased = 0
        for lead in candidates:
            if _has_response_action(db, lead.public_ref):
                continue
            reference = lead.public_ref
            evidence_class = lead.evidence_class
            db.add(
                models.WorldEvent(
                    event_type="forge_bot_inquiry_erased",
                    source="forge_bot_retention_30_day",
                    payload=json.dumps(
                        {
                            "reference": reference,
                            "evidence_class": evidence_class,
                            "state": "ERASED",
                            "previous_state": "READY_FOR_OWNER_REVIEW",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    idempotency_key=(
                        f"forge-bot-inquiry:{reference}:forge_bot_inquiry_erased"
                    ),
                    occurred_at=timestamp,
                )
            )
            db.delete(lead)
            erased += 1

        purged = (
            db.query(models.ForgeBotIntakeRateLimit)
            .filter(models.ForgeBotIntakeRateLimit.expires_at <= timestamp)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "inquiries_erased": erased,
        "expired_rate_limit_buckets_purged": purged,
    }
