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


# Unmeasured sources share one baseline. A differentiated score is stored
# only after evidence adjusts it. The old startup values below were not
# measurements. `url` is a default endpoint, not a clearance to collect.
UNMEASURED_RELIABILITY = 50.0
INVENTED_SEED_SCORES = {
    "manual": 90.0,
    "arxiv": 88.0,
    "paper": 85.0,
    "github": 80.0,
    "book": 75.0,
    "reddit": 65.0,
    "rss": 55.0,
    "news": 55.0,
    "web": 40.0,
}
DEFAULT_SOURCES = [
    {"name": "manual", "type": "human", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "permanent", "url": None},
    {"name": "arxiv", "type": "research", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "permanent",
     "url": "http://export.arxiv.org/api/query"},
    {"name": "paper", "type": "research", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "permanent", "url": None},
    {"name": "github", "type": "code", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "long",
     "url": "https://api.github.com/search/issues"},
    {"name": "book", "type": "human", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "permanent", "url": None},
    {"name": "reddit", "type": "discussion", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "medium",
     "url": "https://www.reddit.com/search.json"},
    {"name": "rss", "type": "media", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "short", "url": None},
    # kept for backward compatibility with any already-planned ResearchTask
    # rows tagged "news" from before rss.py absorbed that functionality —
    # collector_runner.py maps both "news" and "rss" to the same RSSCollector.
    {"name": "news", "type": "media", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "short", "url": None},
    {"name": "web", "type": "general", "reliability_score": UNMEASURED_RELIABILITY, "lifespan": "variable", "url": None},
]


def seed_default_sources(db: Session) -> None:
    """Insert source names if they are missing.

    A row still sitting on an old invented startup score is returned to
    the unmeasured baseline. A score that has moved off that exact value
    is left as stored.
    """
    changed = False
    for entry in DEFAULT_SOURCES:
        exists = db.query(models.Source).filter(models.Source.name == entry["name"]).first()
        if exists:
            invented = INVENTED_SEED_SCORES.get(exists.name)
            if invented is not None and exists.reliability_score == invented:
                exists.reliability_score = UNMEASURED_RELIABILITY
                changed = True
            continue
        db.add(models.Source(**entry))
        changed = True
    if changed:
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
