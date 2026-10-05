"""Scout + Draft + Approval Queue API (owner-guarded).

NO autonomous sending exists on any of these routes. Drafts are prepared;
the OWNER sends from their own account and marks SENT.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import security
from app.database import get_db
from app.services import scout

router = APIRouter(prefix="/scout", tags=["scout"])


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)


class CandidateIn(BaseModel):
    display_name: str
    source_url: str
    public_contact_route: str
    observed_signals: Optional[dict] = None


class SignalIn(BaseModel):
    signal_type: str
    detail: str
    confidence: float = 0.7


class DraftIn(BaseModel):
    observed_fact: str


class DraftEditIn(BaseModel):
    message_en: Optional[str] = None
    message_ne: Optional[str] = None


class SentIn(BaseModel):
    channel: str
    sent_by: str = "owner"


class ReplyIn(BaseModel):
    summary: str


class DoNotContactIn(BaseModel):
    reason: str


class CapIn(BaseModel):
    daily_cap: int


@router.get("/candidates")
def list_candidates(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return [
        {
            "id": e.id,
            "display_name": e.display_name,
            "identity_state": e.identity_state,
            "score": score,
        }
        for e, score in scout.rank_candidates(db)
    ]


@router.post("/candidates")
def create_candidate(payload: CandidateIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    e = scout.register_candidate(
        db,
        display_name=payload.display_name,
        source_url=payload.source_url,
        public_contact_route=payload.public_contact_route,
        observed_signals=payload.observed_signals,
    )
    return {"id": e.id, "display_name": e.display_name}


@router.post("/candidates/{entity_id}/signals")
def add_signal(entity_id: int, payload: SignalIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    ev = scout.record_signal(db, entity_id, payload.signal_type, payload.detail, payload.confidence)
    return {"id": ev.id, "score": scout.score_candidate(db, entity_id)}


@router.post("/candidates/{entity_id}/draft")
def create_draft(entity_id: int, payload: DraftIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        d = scout.generate_draft(db, entity_id, payload.observed_fact)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id, "status": d.status}


@router.get("/drafts")
def approval_queue(request: Request, db: Session = Depends(get_db)):
    """The owner approval queue: DRAFT and APPROVED items awaiting action."""
    _owner(request)
    from app import models

    drafts = (
        db.query(models.OutreachDraft)
        .filter(models.OutreachDraft.status.in_(["DRAFT", "APPROVED"]))
        .order_by(models.OutreachDraft.id.asc())
        .all()
    )
    return [
        {
            "id": d.id,
            "candidate_entity_id": d.candidate_entity_id,
            "observed_fact": d.observed_fact,
            "message_en": d.message_en,
            "message_ne": d.message_ne,
            "status": d.status,
        }
        for d in drafts
    ]


@router.post("/drafts/{draft_id}/edit")
def edit_draft(draft_id: int, payload: DraftEditIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    from app import models

    d = db.get(models.OutreachDraft, draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found.")
    if d.status not in ("DRAFT", "APPROVED"):
        raise HTTPException(status_code=422, detail="Only DRAFT/APPROVED drafts can be edited.")
    if payload.message_en:
        d.message_en = payload.message_en
    if payload.message_ne:
        d.message_ne = payload.message_ne
    db.commit()
    return {"id": d.id, "status": d.status}


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: int, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        d = scout.approve_draft(db, draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id, "status": d.status}


@router.post("/drafts/{draft_id}/skip")
def skip_draft(draft_id: int, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        d = scout.skip_draft(db, draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id, "status": d.status}


@router.post("/drafts/{draft_id}/sent")
def mark_sent(draft_id: int, payload: SentIn, request: Request, db: Session = Depends(get_db)):
    """Owner confirms THEY sent the message from their own account.
    This endpoint never sends anything itself."""
    _owner(request)
    try:
        d = scout.mark_sent(db, draft_id, payload.channel, payload.sent_by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id, "status": d.status, "sent_at": d.sent_at}


@router.post("/drafts/{draft_id}/reply")
def record_reply(draft_id: int, payload: ReplyIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        d = scout.record_reply(db, draft_id, payload.summary)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id, "reply_received": d.reply_received}


@router.get("/do-not-contact")
def list_dnc(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    from app import models

    return [
        {"entity_id": r.candidate_entity_id, "reason": r.reason}
        for r in db.query(models.DoNotContact).all()
    ]


@router.post("/do-not-contact/{entity_id}")
def add_dnc(entity_id: int, payload: DoNotContactIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    from app import models

    if scout.is_do_not_contact(db, entity_id):
        return {"entity_id": entity_id, "already": True}
    r = models.DoNotContact(candidate_entity_id=entity_id, reason=payload.reason)
    db.add(r)
    db.commit()
    return {"entity_id": entity_id, "added": True}


@router.get("/config")
def get_config(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return {"daily_cap": scout.get_daily_cap(db), "sent_today": scout.sends_today(db)}


@router.post("/config")
def set_config(payload: CapIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    from app import models

    cfg = db.query(models.OutreachConfig).first()
    if not cfg:
        cfg = models.OutreachConfig()
        db.add(cfg)
    cfg.daily_cap = payload.daily_cap
    db.commit()
    return {"daily_cap": cfg.daily_cap}


@router.get("/experiments")
def registry(request: Request, db: Session = Depends(get_db)):
    """Experiments registry with kind + five fields."""
    _owner(request)
    import json

    from app import models

    exps = (
        db.query(models.Experiment)
        .filter(models.Experiment.experiment_kind.isnot(None))
        .order_by(models.Experiment.id.asc())
        .all()
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "kind": e.experiment_kind,
            "status": e.status,
            "five_fields": json.loads(e.five_fields_json) if e.five_fields_json else None,
        }
        for e in exps
    ]


@router.post("/experiments/seed")
def seed_experiments(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    created = scout.seed_registry_experiments(db)
    return {"seeded": len(created)}
