"""Lessons Memory API.

    GET  /lessons           -> list durable consolidated lessons
    GET  /lessons/recall    -> recall lessons relevant to one opportunity
    POST /lessons/rebuild   -> re-consolidate any un-filed LearningEvents

Nothing here fabricates lessons: every Lesson traces back to a real
LearningEvent, which traces back to a real ACTUAL outcome.
"""

from typing import Optional, Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models
from app.security import require_owner_api_key
from app.services import lessons_engine

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("", response_model=list[schemas.LessonOut])
def list_lessons(request: Request, limit: int = 50, data_scope: Literal["REAL", "SANDBOX"] = "REAL", db: Session = Depends(get_db)):
    """Owner-only: exposes the internal durable-lessons intelligence ledger."""
    require_owner_api_key(request)
    q = (db.query(models.Lesson)
         .filter(models.Lesson.active == True, models.Lesson.data_scope == data_scope)  # noqa: E712
         .order_by(models.Lesson.last_seen.desc())
         .limit(limit))
    return q.all()


@router.get("/recall", response_model=schemas.LessonRecallOut)
def recall(request: Request, opportunity_id: Optional[int] = None, data_scope: Literal["REAL", "SANDBOX"] = "REAL", db: Session = Depends(get_db)):
    """Owner-only: recalls the internal lessons memory for one opportunity."""
    require_owner_api_key(request)
    return lessons_engine.assist_decision(db, opportunity_id=opportunity_id, data_scope=data_scope)


@router.post("/rebuild")
def rebuild(request: Request, db: Session = Depends(get_db)):
    """Owner-only: fold any LearningEvent not yet part of a Lesson into the Lessons Memory."""
    require_owner_api_key(request)
    return lessons_engine.run_lessons_cycle(db)
