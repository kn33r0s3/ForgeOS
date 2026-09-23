"""
SOURCE MANAGER
===============

Tracks source reliability (`Source` table) so evidence from different
sources is weighted differently instead of trusted equally. Signal ≠
Truth — a random Reddit complaint and an arXiv paper shouldn't count
the same. reliability_score is not static: it moves over time as
Predictions resolve (see reality_memory.py) — that's the "learn from
being wrong" feedback loop.

The SourceCollector interface itself lives in collectors/base.py, not
here — see that file for why.
"""

from sqlalchemy.orm import Session
from typing import Optional

from app import models


# Starting reliability estimates. These are deliberately rough — the
# point is that sources are NOT treated equally, not that these exact
# numbers are correct. reliability_score moves over time based on
# whether each source's evidence held up under resolved Predictions
# (see reality_memory.py's _adjust_source_reliability). `url` is each
# source's default feed/endpoint where one applies — collectors read
# it via get_source_url() so the endpoint lives in one place (the DB),
# not hardcoded across every collector file.
DEFAULT_SOURCES = [
    {"name": "manual", "type": "human", "reliability_score": 90.0, "lifespan": "permanent", "url": None},
    {"name": "arxiv", "type": "research", "reliability_score": 88.0, "lifespan": "permanent",
     "url": "http://export.arxiv.org/api/query"},
    {"name": "paper", "type": "research", "reliability_score": 85.0, "lifespan": "permanent", "url": None},
    {"name": "github", "type": "code", "reliability_score": 80.0, "lifespan": "long",
     "url": "https://api.github.com/search/issues"},
    {"name": "book", "type": "human", "reliability_score": 75.0, "lifespan": "permanent", "url": None},
    {"name": "reddit", "type": "discussion", "reliability_score": 65.0, "lifespan": "medium",
     "url": "https://www.reddit.com/search.json"},
    {"name": "rss", "type": "media", "reliability_score": 55.0, "lifespan": "short", "url": None},
    # kept for backward compatibility with any already-planned ResearchTask
    # rows tagged "news" from before rss.py absorbed that functionality —
    # collector_runner.py maps both "news" and "rss" to the same RSSCollector.
    {"name": "news", "type": "media", "reliability_score": 55.0, "lifespan": "short", "url": None},
    {"name": "web", "type": "general", "reliability_score": 40.0, "lifespan": "variable", "url": None},
]


def seed_default_sources(db: Session) -> None:
    """Insert the default Source rows if they don't already exist.
    Called on app/worker startup — safe to call every time (no-op once seeded)."""
    for entry in DEFAULT_SOURCES:
        exists = db.query(models.Source).filter(models.Source.name == entry["name"]).first()
        if exists:
            continue
        db.add(models.Source(**entry))
    db.commit()


def get_reliability(db: Session, source_name: str) -> float:
    """Return the current tracked reliability score for a source name,
    or a neutral 50.0 default for an unseen/unknown source."""
    source = db.query(models.Source).filter(models.Source.name == source_name).first()
    return source.reliability_score if source else 50.0


def get_source_url(db: Session, source_name: str) -> Optional[str]:
    """Return the tracked default endpoint/feed URL for a source, if
    any. Lets a collector's default endpoint be reconfigured via the
    Source table instead of being hardcoded in the collector file."""
    source = db.query(models.Source).filter(models.Source.name == source_name).first()
    return source.url if source else None


def list_sources(db: Session) -> list[models.Source]:
    return db.query(models.Source).order_by(models.Source.reliability_score.desc()).all()



def adjust_reliability(db: Session, source_name: str, delta: float) -> float:
    """Evidence-based reliability nudge. Clamped to [0, 100].

    Used by learning when predictions tied to a source's evidence resolve.
    """
    source = db.query(models.Source).filter(models.Source.name == source_name).first()
    if not source:
        return 50.0
    source.reliability_score = round(max(0.0, min(100.0, (source.reliability_score or 50.0) + delta)), 1)
    db.commit()
    return source.reliability_score
