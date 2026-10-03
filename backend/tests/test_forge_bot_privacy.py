import json
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app import models
from app.services import forge_bot_privacy


def _request(visitor_ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/forge-bot/leads",
            "headers": [],
            "client": (visitor_ip, 50000),
        }
    )


def _lead(
    reference: str,
    *,
    created_at: datetime,
    stage: str = "READY_FOR_OWNER_REVIEW",
    opted_out: bool = False,
) -> models.ForgeBotLeadContact:
    return models.ForgeBotLeadContact(
        public_ref=reference,
        email=f"{reference.lower()}@example.test",
        normalized_email=f"{reference.lower()}@example.test",
        preferred_channel="email",
        destination="TEST destination",
        course="TEST course",
        timeline="TEST timeline",
        budget_minimum=1,
        budget_maximum=2,
        stage=stage,
        evidence_class="TEST",
        consent_granted=True,
        opted_out=opted_out,
        created_at=created_at,
    )


def test_daily_maintenance_erases_only_old_unacted_review_records(db):
    now = datetime.now(timezone.utc)
    eligible = _lead("FB-RETENTION-OLD", created_at=now - timedelta(days=31))
    fresh = _lead("FB-RETENTION-FRESH", created_at=now - timedelta(days=29))
    acted = _lead("FB-RETENTION-ACTION", created_at=now - timedelta(days=31))
    opted_out = _lead(
        "FB-RETENTION-OPTED",
        created_at=now - timedelta(days=31),
        stage="OPTED_OUT",
        opted_out=True,
    )
    db.add_all([eligible, fresh, acted, opted_out])
    db.flush()
    db.add(
        models.Action(
            action_type="forge_bot_response",
            objective="TEST response action",
            parameters_json=json.dumps({"inquiry_reference": acted.public_ref}),
            status="APPROVAL_REQUIRED",
        )
    )
    expired_bucket = models.ForgeBotIntakeRateLimit(
        visitor_hash="a" * 64,
        request_count=3,
        expires_at=now - timedelta(seconds=1),
    )
    active_bucket = models.ForgeBotIntakeRateLimit(
        visitor_hash="b" * 64,
        request_count=2,
        expires_at=now + timedelta(minutes=10),
    )
    db.add_all([expired_bucket, active_bucket])
    db.commit()

    result = forge_bot_privacy.run_daily_maintenance(db, now=now)

    assert result == {
        "inquiries_erased": 1,
        "expired_rate_limit_buckets_purged": 1,
    }
    remaining_refs = {
        lead.public_ref for lead in db.query(models.ForgeBotLeadContact).all()
    }
    assert remaining_refs == {fresh.public_ref, acted.public_ref, opted_out.public_ref}
    event = db.query(models.WorldEvent).filter_by(
        event_type="forge_bot_inquiry_erased"
    ).one()
    payload = json.loads(event.payload)
    assert payload == {
        "evidence_class": "TEST",
        "previous_state": "READY_FOR_OWNER_REVIEW",
        "reference": eligible.public_ref,
        "state": "ERASED",
    }
    assert "example.test" not in event.payload
    assert "TEST destination" not in event.payload
    remaining_buckets = db.query(models.ForgeBotIntakeRateLimit).all()
    assert len(remaining_buckets) == 1
    assert remaining_buckets[0].visitor_hash == "b" * 64


def test_hourly_counter_is_atomic_keyed_and_expires(db):
    now = datetime.now(timezone.utc)
    first_visitor = _request("203.0.113.10")
    second_visitor = _request("203.0.113.11")

    for attempt in range(forge_bot_privacy.RATE_LIMIT):
        assert forge_bot_privacy.consume_intake_submission(
            db,
            first_visitor,
            hmac_key="test-only-contact-key",
            now=now,
        )
    assert not forge_bot_privacy.consume_intake_submission(
        db,
        first_visitor,
        hmac_key="test-only-contact-key",
        now=now,
    )
    assert forge_bot_privacy.consume_intake_submission(
        db,
        second_visitor,
        hmac_key="test-only-contact-key",
        now=now,
    )

    buckets = db.query(models.ForgeBotIntakeRateLimit).all()
    assert len(buckets) == 2
    assert all(len(bucket.visitor_hash) == 64 for bucket in buckets)
    assert all("203.0.113." not in bucket.visitor_hash for bucket in buckets)

    assert forge_bot_privacy.consume_intake_submission(
        db,
        first_visitor,
        hmac_key="test-only-contact-key",
        now=now + timedelta(seconds=forge_bot_privacy.RATE_WINDOW_SECONDS + 1),
    )
    reset_bucket = next(
        bucket for bucket in db.query(models.ForgeBotIntakeRateLimit).all()
        if bucket.visitor_hash != buckets[1].visitor_hash
    )
    assert reset_bucket.request_count == 1


def test_vercel_visitor_identity_uses_platform_forwarded_ip(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    first = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-vercel-forwarded-for", b"203.0.113.21")],
            "client": ("127.0.0.1", 50000),
        }
    )
    second = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-vercel-forwarded-for", b"203.0.113.22")],
            "client": ("127.0.0.1", 50000),
        }
    )

    first_hash = forge_bot_privacy._visitor_hash(first, "test-only-contact-key")
    second_hash = forge_bot_privacy._visitor_hash(second, "test-only-contact-key")

    assert first_hash != second_hash
    assert "203.0.113." not in first_hash
    assert "203.0.113." not in second_hash


def test_vercel_refuses_ephemeral_privacy_storage(db, monkeypatch):
    import pytest
    from fastapi import HTTPException

    monkeypatch.setenv("VERCEL", "1")

    if db.get_bind().dialect.name == "postgresql":
        assert forge_bot_privacy.run_daily_maintenance(db) == {
            "inquiries_erased": 0,
            "expired_rate_limit_buckets_purged": 0,
        }
    else:
        with pytest.raises(HTTPException) as error:
            forge_bot_privacy.run_daily_maintenance(db)

        assert error.value.status_code == 503
        assert error.value.detail == (
            "Durable Forge Bot privacy storage requires PostgreSQL."
        )
