"""API routes for observing/storing and listing signals."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import observer

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=schemas.SignalOut)
def create_signal(payload: schemas.SignalCreate, db: Session = Depends(get_db)):
    """Store a new observed signal (e.g. a customer complaint, a market note)."""
    signal = observer.record_signal(
        db, content=payload.content, source=payload.source, category=payload.category
    )
    return signal


@router.get("", response_model=list[schemas.SignalOut])
def get_signals(limit: int = 200, db: Session = Depends(get_db)):
    """List stored signals, most recent first."""
    return observer.list_signals(db, limit=limit)
