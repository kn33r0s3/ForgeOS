"""
API routes for the Observer Engine — Forge's "eyes".

    POST /observer/observe   -> submit raw information from any source,
                                  get back the fully-scored Signal
    GET  /observer/signals    -> most important observed signals
                                   (importance_score desc)
    GET  /observer/stats       -> Dashboard Observer section numbers

These sit alongside (not instead of) the original POST/GET /signals
endpoints in signals.py — both write into the same Signals table via
the same ObserverEngine, so nothing downstream (Pattern Engine,
Opportunity Engine) needs to know which route a signal came in through.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app import security
from app.services.observer_engine import ObserverEngine

router = APIRouter(prefix="/observer", tags=["observer"])


@router.post("/observe", response_model=schemas.SignalOut)
def observe(request: Request, payload: schemas.ObserveRequest, db: Session = Depends(get_db)):
    """Submit one piece of raw information. The Observer Engine
    normalizes it, tags it, classifies its type, scores its importance
    (0-100), and stores it as a Signal — all synchronously, no external
    API calls required."""
    security.require_owner_api_key(request)
    engine = ObserverEngine(db)
    return engine.observe(payload.content, source=payload.source)


@router.get("/signals", response_model=list[schemas.SignalOut])
def get_important_signals(
    request: Request,
    limit: int = 50,
    min_importance: float = 0.0,
    db: Session = Depends(get_db),
):
    """Owner-only raw signal listing; public callers use evidence-backed Feed projections."""
    security.require_owner_api_key(request)
    engine = ObserverEngine(db)
    return engine.list_signals(
        limit=limit,
        min_importance=min_importance,
        include_user_requests=True,
    )


@router.get("/recent", response_model=list[schemas.SignalOut])
def get_recent_signals(
    request: Request,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Owner-only raw signal history; public discovery uses the Feed projection."""
    security.require_owner_api_key(request)
    engine = ObserverEngine(db)
    return engine.recent_signals(
        limit=limit,
        include_user_requests=True,
    )


@router.get("/stats", response_model=schemas.ObserverStatsOut)
def get_observer_stats(db: Session = Depends(get_db)):
    """Total observations, how many were high-importance (>=70), and
    the average importance score — the Dashboard Observer summary."""
    engine = ObserverEngine(db)
    return engine.stats()
