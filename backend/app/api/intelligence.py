from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.youtube_intelligence import analyze_youtube
from app.services import tool_usefulness

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class YouTubeRequest(BaseModel):
    url: str = Field(..., min_length=1)


@router.post("/youtube")
def analyze_youtube_url(payload: YouTubeRequest, db: Session = Depends(get_db)):
    try:
        result = analyze_youtube(db, payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    analysis = result["analysis"]
    return {
        "id": analysis.id,
        "status": analysis.status,
        "reused": result["reused"],
        "source_uri": analysis.source_uri,
        "video_id": analysis.external_id,
        "title": analysis.title,
        "channel": analysis.channel,
        "published_at": analysis.published_at,
        "description": analysis.description,
        "duration_seconds": analysis.duration_seconds,
        "language": analysis.language,
        "transcript_source": analysis.transcript_source,
        "transcript_available": bool(analysis.transcript_text),
        "claim_count": len(result["claims"]),
        "error": analysis.error,
    }


@router.get("/youtube/{analysis_id}")
def get_youtube_analysis(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.query(models.MediaAnalysis).filter_by(id=analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Media analysis not found")
    return {
        "id": analysis.id,
        "status": analysis.status,
        "source_uri": analysis.source_uri,
        "video_id": analysis.external_id,
        "title": analysis.title,
        "channel": analysis.channel,
        "published_at": analysis.published_at,
        "description": analysis.description,
        "duration_seconds": analysis.duration_seconds,
        "language": analysis.language,
        "transcript_source": analysis.transcript_source,
        "transcript_text": analysis.transcript_text,
        "transcript_segments": analysis.transcript_segments,
        "document_id": analysis.document_id,
        "error": analysis.error,
    }


@router.get("/performance/tools/{tool_name}")
def get_tool_performance(tool_name: str, db: Session = Depends(get_db)):
    return {"tool": tool_name, "performance": tool_usefulness.tool_summary(db, tool_name)}


@router.get("/performance/sources/{source}")
def get_source_performance(source: str, db: Session = Depends(get_db)):
    return {"source": source, "performance": tool_usefulness.source_summary(db, source)}
