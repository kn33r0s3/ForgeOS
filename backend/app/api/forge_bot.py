"""Consent-scoped Forge Bot lead intake and private owner summary."""

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/forge-bot", tags=["forge-bot"])
CONSENT_PURPOSE = "respond_to_forge_bot_inquiry"
CONSENT_PROVENANCE = "forge_bot_web_form_v1"
RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 3600
MAX_RATE_LIMIT_BUCKETS = 4096
_rate_lock = threading.Lock()
_submissions_by_ip: dict[str, deque[float]] = defaultdict(deque)


def _enabled() -> bool:
    return bool(
        settings.FORGE_BOT_INTAKE_ENABLED
        and len(settings.FORGE_BOT_CONTACT_HMAC_KEY) >= 32
        and bool(settings.FORGE_API_KEY)
    )


def _normalized_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return "".join(character for character in phone if character in "0123456789")


def _contact_digest(kind: str, value: str | None) -> str | None:
    if not value:
        return None
    key = settings.FORGE_BOT_CONTACT_HMAC_KEY.encode("utf-8")
    message = f"forge-bot:{kind}:{value}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _allow_submission(request: Request) -> bool:
    host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _rate_lock:
        recent = _submissions_by_ip.get(host)
        if recent is None:
            if len(_submissions_by_ip) >= MAX_RATE_LIMIT_BUCKETS:
                stale_before = now - RATE_WINDOW_SECONDS
                for ip in [
                    ip
                    for ip, events in _submissions_by_ip.items()
                    if not events or events[-1] < stale_before
                ]:
                    _submissions_by_ip.pop(ip, None)
                if len(_submissions_by_ip) >= MAX_RATE_LIMIT_BUCKETS:
                    return False
            recent = deque()
            _submissions_by_ip[host] = recent
        while recent and now - recent[0] >= RATE_WINDOW_SECONDS:
            recent.popleft()
        if len(recent) >= RATE_LIMIT:
            return False
        recent.append(now)
        return True


def _require_owner_key(request: Request) -> None:
    if not settings.FORGE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Forge Bot owner access is unavailable until FORGE_API_KEY is configured.",
        )
    presented = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(
        presented.encode("utf-8"),
        settings.FORGE_API_KEY.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Valid X-API-Key required.")


@router.get("/config")
def get_forge_bot_config():
    """Return only public contact settings and whether intake is currently enabled."""
    return {
        "intake_enabled": _enabled(),
        "contact_email": settings.FORGE_BOT_CONTACT_EMAIL,
        "booking_url": settings.FORGE_BOT_BOOKING_URL,
        "consent_version": CONSENT_PROVENANCE,
    }


@router.post(
    "/leads",
    response_model=schemas.ForgeBotLeadReceipt,
    status_code=202,
)
def create_forge_bot_lead(
    payload: schemas.ForgeBotLeadCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Store one consented web inquiry without sending or exposing contact data."""
    reference = f"FB-{secrets.token_hex(6).upper()}"
    token = secrets.token_urlsafe(32)
    receipt = schemas.ForgeBotLeadReceipt(
        reference=reference,
        manage_token=token,
        message=(
            "Request received for owner review. No automated reply or booking "
            "was sent. If this was your first submission, keep this one-time "
            "control code private."
        ),
    )
    if not _enabled():
        raise HTTPException(status_code=503, detail="Forge Bot web intake is not enabled.")
    if not payload.consent_granted:
        raise HTTPException(status_code=422, detail="Explicit consent is required.")
    if payload.budget_maximum < payload.budget_minimum:
        raise HTTPException(status_code=422, detail="Budget maximum must be at least minimum.")
    if payload.preferred_channel == "email" and not payload.email:
        raise HTTPException(status_code=422, detail="An email address is required for email contact.")
    if payload.preferred_channel == "phone" and not payload.phone:
        raise HTTPException(status_code=422, detail="A phone number is required for phone contact.")
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=422, detail="Provide an email address or phone number.")
    if payload.website:
        return receipt
    if not _allow_submission(request):
        raise HTTPException(status_code=429, detail="Submission rate limit reached; try again later.")

    normalized_email = payload.email.lower() if payload.email else None
    normalized_phone = _normalized_phone(payload.phone)
    is_test_phone = bool(
        normalized_phone and re.fullmatch(r"(?:1)?20255501[0-9]{2}", normalized_phone)
    )
    evidence_class = "TEST" if (
        (normalized_email and normalized_email.endswith("@example.test"))
        or is_test_phone
    ) else "REAL"
    email_suppression_hmac = _contact_digest("email", normalized_email)
    phone_suppression_hmac = _contact_digest("phone", normalized_phone)
    match_conditions = []
    if normalized_email:
        match_conditions.extend(
            [
                models.ForgeBotLeadContact.normalized_email == normalized_email,
                models.ForgeBotLeadContact.email_suppression_hmac == email_suppression_hmac,
            ]
        )
    if normalized_phone:
        match_conditions.extend(
            [
                models.ForgeBotLeadContact.normalized_phone == normalized_phone,
                models.ForgeBotLeadContact.phone_suppression_hmac == phone_suppression_hmac,
            ]
        )
    existing = db.query(models.ForgeBotLeadContact).filter(or_(*match_conditions)).first()
    if existing is not None:
        # The fixed receipt shape avoids disclosing whether an address is already known.
        return receipt

    row = models.ForgeBotLeadContact(
        public_ref=reference,
        email=payload.email,
        normalized_email=normalized_email,
        phone=payload.phone,
        normalized_phone=normalized_phone,
        email_suppression_hmac=email_suppression_hmac,
        phone_suppression_hmac=phone_suppression_hmac,
        manage_token_hash=_token_hash(token),
        preferred_channel=payload.preferred_channel,
        destination=payload.destination,
        course=payload.course,
        timeline=payload.timeline,
        budget_minimum=payload.budget_minimum,
        budget_maximum=payload.budget_maximum,
        stage="READY_FOR_OWNER_REVIEW",
        evidence_class=evidence_class,
        consent_granted=True,
        consent_at=datetime.now(timezone.utc),
        consent_purpose=CONSENT_PURPOSE,
        consent_provenance=CONSENT_PROVENANCE,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent duplicate submissions are acknowledged without returning
        # the other lead's reference or control token.
        duplicate = (
            db.query(models.ForgeBotLeadContact)
            .filter(or_(*match_conditions))
            .first()
        )
        if duplicate is not None:
            return receipt
        raise
    return receipt


@router.post("/leads/opt-out", status_code=202)
def opt_out_forge_bot_lead(
    payload: schemas.ForgeBotLeadControl,
    db: Session = Depends(get_db),
):
    """Permanently suppress a lead using the private one-time control code."""
    token = payload.manage_token
    row = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(manage_token_hash=_token_hash(token), opted_out=False, erased_at=None)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Control code not found.")
    row.opted_out = True
    row.opted_out_at = datetime.now(timezone.utc)
    row.erased_at = datetime.now(timezone.utc)
    row.email = None
    row.normalized_email = None
    row.phone = None
    row.normalized_phone = None
    row.destination = None
    row.course = None
    row.timeline = None
    row.budget_minimum = None
    row.budget_maximum = None
    row.manage_token_hash = None
    row.stage = "OPTED_OUT"
    row.public_ref = f"FB-SUPP-{secrets.token_hex(8).upper()}"
    db.commit()
    return {
        "status": "opted_out",
        "message": (
            "Contact fields and qualification answers were erased. HMAC-only "
            "suppression tokens remain to prevent re-entry or future contact."
        ),
    }


@router.post("/leads/delete", status_code=204)
def delete_forge_bot_lead(
    payload: schemas.ForgeBotLeadControl,
    db: Session = Depends(get_db),
):
    """Erase a lead record using its private one-time control code."""
    token = payload.manage_token
    row = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(manage_token_hash=_token_hash(token), opted_out=False, erased_at=None)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Control code not found.")
    db.delete(row)
    db.commit()
    return None


@router.get("/leads/summary")
def get_owner_lead_summary(request: Request, db: Session = Depends(get_db)):
    """Return active lead rows only after mandatory owner API-key authorization."""
    _require_owner_key(request)
    rows = (
        db.query(models.ForgeBotLeadContact)
        .filter_by(opted_out=False, erased_at=None)
        .order_by(models.ForgeBotLeadContact.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "reference": row.public_ref,
            "email": row.email,
            "phone": row.phone,
            "preferred_channel": row.preferred_channel,
            "destination": row.destination,
            "course": row.course,
            "timeline": row.timeline,
            "budget_minimum": row.budget_minimum,
            "budget_maximum": row.budget_maximum,
            "stage": row.stage,
            "evidence_class": row.evidence_class,
            "consent_at": row.consent_at,
        }
        for row in rows
    ]
