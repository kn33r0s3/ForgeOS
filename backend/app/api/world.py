"""World / Source Intelligence API — permitted text only, claims unverified."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.security import require_owner_api_key
from app.services.source_intelligence import process_permitted_text

router = APIRouter(prefix="/world", tags=["world-intelligence"])


class IngestBody(BaseModel):
    content_text: str = Field(..., min_length=1)
    source_uri: Optional[str] = None
    source_type: str = "transcript"
    language_original: Optional[str] = None
    title: Optional[str] = None
    access_basis: str = "user_provided"


@router.post("/ingest")
def api_ingest(body: IngestBody, request: Request, db: Session = Depends(get_db)):
    # Owner-only: this writes user-provided documents, claims and ideas into
    # the production database. Unauthenticated writes must not be possible
    # (cycle-37/47/53/61/62/64 guard pattern).
    require_owner_api_key(request)
    return process_permitted_text(
        db,
        body.content_text,
        source_uri=body.source_uri,
        source_type=body.source_type,
        language_original=body.language_original,
        title=body.title,
        access_basis=body.access_basis,
    )


@router.get("/claims")
def list_claims(request: Request, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    # Owner-only: claims are user-provided text that may contain pasted PII.
    require_owner_api_key(request)
    rows = db.query(models.WorldClaim).order_by(models.WorldClaim.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "claim_text": r.claim_text[:300],
            "claim_type": r.claim_type,
            "domain": r.domain,
            "verification_status": r.verification_status,
        }
        for r in rows
    ]


@router.get("/ideas")
def list_ideas(request: Request, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    # Owner-only: ideas derive from user-provided text.
    require_owner_api_key(request)
    rows = db.query(models.WorldIdea).order_by(models.WorldIdea.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "idea_text": r.idea_text[:400],
            "domain": r.domain,
            "status": r.status,
        }
        for r in rows
    ]


@router.get("/principles")
def principles():
    return {
        "mass_scrape": False,
        "claim_is_not_truth": True,
        "llm_is_not_evidence": True,
        "access_basis_required": True,
        "business_path": "claim → investigate demand/competition/economics → experiment",
        "learning_path": "observation → evidence → pattern → hypothesis → experiment → outcome → belief update",
    }
