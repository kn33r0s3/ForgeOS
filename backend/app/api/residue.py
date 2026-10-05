"""Residue engine API (owner-guarded)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, security
from app.database import get_db
from app.services import residue_engine

router = APIRouter(prefix="/residue", tags=["residue"])


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)


class JourneyIn(BaseModel):
    perspective: str  # BUYER | CIRCLE
    consulted_who_where: str
    what_was_said: str
    what_was_checked: str
    what_almost_stopped: str
    what_decided_it: str
    consent_given: bool = False


class ReviewIn(BaseModel):
    notes: str = ""


@router.post("/journeys")
def record_journey(payload: JourneyIn, request: Request, db: Session = Depends(get_db)):
    """Record a buyer-side purchase journey. Consent required.
    No private chat content — only the person's own account."""
    _owner(request)
    try:
        ev = residue_engine.record_purchase_journey(
            db,
            perspective=payload.perspective,
            consulted_who_where=payload.consulted_who_where,
            what_was_said=payload.what_was_said,
            what_was_checked=payload.what_was_checked,
            what_almost_stopped=payload.what_almost_stopped,
            what_decided_it=payload.what_decided_it,
            consent_given=payload.consent_given,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": ev.id,
        "perspective": ev.perspective,
        "journey_count": residue_engine.count_journeys(db),
    }


@router.get("/journeys")
def list_journeys(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    rows = (
        db.query(models.Evidence)
        .filter(models.Evidence.perspective.in_(("BUYER", "CIRCLE")))
        .filter(models.Evidence.source == "owner-console intake")
        .order_by(models.Evidence.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "perspective": r.perspective,
            "claim": r.claim,
            "journey": json.loads(r.content) if r.content else {},
            "recorded_at": r.recorded_at,
        }
        for r in rows
    ]


@router.get("/flags")
def list_flags(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    flags = (
        db.query(models.ResidueFlag)
        .filter(models.ResidueFlag.reviewed == False)  # noqa: E712
        .order_by(models.ResidueFlag.id.desc())
        .all()
    )
    return [
        {
            "id": f.id,
            "evidence_id": f.evidence_id,
            "observation_perspective": f.observation_perspective,
            "hypothesis_perspectives": json.loads(f.hypothesis_perspectives),
            "flagged_at": f.flagged_at,
            "claim": f.evidence.claim if f.evidence else None,
        }
        for f in flags
    ]


@router.post("/scan")
def scan(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    flagged = residue_engine.scan_all(db)
    return {"flagged": len(flagged)}


@router.post("/flags/{flag_id}/review")
def review_flag(flag_id: int, payload: ReviewIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    flag = db.get(models.ResidueFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found.")
    flag.reviewed = True
    flag.review_notes = payload.notes
    db.commit()
    return {"id": flag.id, "reviewed": True}


@router.get("/experiment-status")
def experiment_status(request: Request, db: Session = Depends(get_db)):
    """'Where is the sale decided?' — outcome stays blank until >=10 accounts."""
    _owner(request)
    count = residue_engine.count_journeys(db)
    return {"journey_count": count, "threshold": 10, "outcome_recorded": count >= 10}
