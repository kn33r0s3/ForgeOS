"""
OBSERVER MODULE (legacy entry point)
======================================

This module backs the original POST /signals endpoint. It now
delegates the actual processing to app.services.observer_engine.
ObserverEngine, so signals created through /signals, /observer/observe,
a real collector (collector_runner.py), or the Knowledge Mining Engine
all end up identically shaped (tagged, typed, importance-scored,
reliability-snapshotted) in the Signals table — the Pattern Engine sees
one consistent pool of signals no matter which door they came in.
"""

from sqlalchemy.orm import Session

from app import models
from app.services.observer_engine import ObserverEngine
from typing import Optional


def record_signal(db: Session, content: str, source: str = "manual", category: Optional[str] = None) -> models.Signal:
    """Store one piece of observed information as a Signal row, fully
    processed by the Observer Engine. If a category is explicitly
    supplied (the old /signals API allows this), it overrides the
    auto-detected one."""
    signal = ObserverEngine(db).observe(content, source=source)
    if category:
        signal.category = category
        db.commit()
        db.refresh(signal)
    return signal


def list_signals(
    db: Session,
    limit: int = 200,
    *,
    include_user_requests: bool = True,
) -> list[models.Signal]:
    query = db.query(models.Signal)
    if not include_user_requests:
        query = query.filter(models.Signal.source != "user_request")
    return query.order_by(models.Signal.timestamp.desc()).limit(limit).all()
