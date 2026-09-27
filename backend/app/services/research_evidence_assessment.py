"""Conservative, explainable metadata assessment for research source records."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app import models
from sqlalchemy.orm import Session

_STOP_WORDS = {
    "about", "after", "against", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "should", "some", "than", "that", "their", "there",
    "these", "they", "this", "through", "under", "using", "what", "when",
    "where", "which", "while", "with", "would", "your",
}


def _terms(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", value.casefold())
        if token not in _STOP_WORDS
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assess_source_record(
    query: str,
    *,
    title: str | None,
    content: str | None,
    published_at: datetime | None,
    retrieved_at: datetime | None,
    source_identity: str | None = None,
    canonical_url: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe observable metadata without inferring semantic support."""
    query_terms = _terms(query)
    record_terms = _terms(f"{title or ''} {content or ''}")
    matched_terms = sorted(query_terms & record_terms)

    publication_age_days = None
    if published_at is not None and retrieved_at is not None:
        publication_age_days = (
            _as_utc(retrieved_at) - _as_utc(published_at)
        ).days

    return {
        "assessment_state": (
            "metadata_only_lead"
            if provenance and provenance.get("metadata_only") is True
            else "content_not_reviewed"
        ),
        "provenance": {
            "present": bool(provenance),
            "source_registry_id": (provenance or {}).get("source_registry_id"),
            "retrieval_timestamp": _as_utc(retrieved_at).isoformat() if retrieved_at else None,
            "publication_timestamp": _as_utc(published_at).isoformat() if published_at else None,
            "canonical_url": canonical_url,
            "source_identity": source_identity,
        },
        "keyword_overlap": {
            "method": "case-insensitive exact-token overlap; not semantic relevance",
            "query_term_count": len(query_terms),
            "matched_terms": matched_terms,
            "unmatched_terms": sorted(query_terms - record_terms),
        },
        "publication_age_days": publication_age_days,
        "freshness_basis": (
            "publication date compared with retrieval time"
            if publication_age_days is not None
            else "publication age unavailable because a date is missing"
        ),
        "source_record": "retrieved record; substantive claims not reviewed",
        "source_reliability": "unassessed",
        "semantic_relevance": "unassessed",
        "contradictions": "unassessed",
        "claim_support": "not_inferred",
    }


def explicit_contradiction_edges(
    db: Session,
    evidence_ids: list[int],
) -> list[dict[str, int]]:
    """Return only persisted, explicitly typed contradiction relationships."""
    if not evidence_ids:
        return []
    rows = (
        db.query(models.EvidenceRelationship)
        .filter(
            models.EvidenceRelationship.evidence_id.in_(set(evidence_ids)),
            models.EvidenceRelationship.relation_type == "contradicts",
        )
        .order_by(models.EvidenceRelationship.id)
        .all()
    )
    return [
        {"evidence_id": row.evidence_id, "claim_id": row.claim_id}
        for row in rows
    ]
