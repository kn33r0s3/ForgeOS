"""
Source / World Intelligence — claim & idea extraction from permitted text.

Forge does NOT mass-scrape the internet or copy YouTube blindly.
Input is user-provided or otherwise legitimately accessible text
(transcript, article paste, paper excerpt).

Pipeline:
  text → document → claims → ideas → (optional) trading hypothesis bridge

Claims are UNVERIFIED until investigation/experiments say otherwise.
LLM may assist later; this core uses deterministic heuristics so results
are reproducible without treating model prose as evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_document(
    db: Session,
    content_text: str,
    *,
    source_uri: Optional[str] = None,
    source_type: str = "text",
    language_original: Optional[str] = None,
    title: Optional[str] = None,
    access_basis: str = "user_provided",
) -> models.WorldSourceDocument:
    content_text = (content_text or "").strip()
    if not content_text:
        raise ValueError("content_text required")
    h = _hash(content_text)
    existing = db.query(models.WorldSourceDocument).filter_by(content_hash=h).first()
    if existing:
        return existing
    doc = models.WorldSourceDocument(
        source_uri=source_uri,
        source_type=source_type,
        language_original=language_original,
        language_internal="en",
        title=title,
        content_text=content_text,
        content_hash=h,
        access_basis=access_basis,
        retrieved_at=utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# Simple claim cues — deterministic, language-agnostic enough for EN transcripts
_CLAIM_PATTERNS = [
    (r"(?i)\b(always|never|works when|buy when|sell when|if .+ then)\b.{10,200}", "market_rule"),
    (r"(?i)\b(customers pay|price is|costs? \$?\d+|\$\d+\s*/\s*month)\b.{0,80}", "pricing"),
    (r"(?i)\b(everyone needs|huge demand|nobody solves|underserved)\b.{0,120}", "demand"),
    (r"(?i)\b(\d+%\s*(win rate|return|accuracy)|sharpe|profit)\b.{0,80}", "performance"),
]


def extract_claims(db: Session, document_id: int) -> list[models.WorldClaim]:
    doc = db.query(models.WorldSourceDocument).filter_by(id=document_id).first()
    if not doc:
        raise ValueError("document not found")

    text = doc.content_text
    found: list[models.WorldClaim] = []
    seen = set()

    # Sentence-ish split
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    for part in parts:
        part = part.strip()
        if len(part) < 20 or len(part) > 400:
            continue
        claim_type = "opinion"
        for pat, ctype in _CLAIM_PATTERNS:
            if re.search(pat, part):
                claim_type = ctype
                break
        # Only keep sentences that matched a cue or contain strategy-like language
        if claim_type == "opinion" and not re.search(
            r"(?i)\b(strategy|indicator|rsi|moving average|breakout|momentum|saas|subscription|business)\b",
            part,
        ):
            continue
        key = part.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        domain = "trading" if re.search(
            r"(?i)\b(buy|sell|trade|rsi|momentum|stock|market|forex|market)\b", part
        ) else ("business" if re.search(r"(?i)\b(customer|saas|price|business|revenue)\b", part) else "other")
        row = models.WorldClaim(
            document_id=doc.id,
            claim_text=part,
            claim_type=claim_type,
            domain=domain,
            confidence_extract=0.4 if claim_type == "opinion" else 0.6,
            verification_status="UNVERIFIED",
            structured_json=json.dumps({"extractor": "heuristic_v1"}),
            provenance_note=f"doc:{doc.id} access:{doc.access_basis}",
        )
        db.add(row)
        found.append(row)

    db.commit()
    for r in found:
        db.refresh(r)
    return found


def extract_ideas_from_claims(db: Session, document_id: int) -> list[models.WorldIdea]:
    claims = (
        db.query(models.WorldClaim)
        .filter_by(document_id=document_id)
        .all()
    )
    ideas = []
    for c in claims:
        if c.claim_type in ("market_rule", "performance") and c.domain == "trading":
            idea = models.WorldIdea(
                document_id=document_id,
                claim_ids=str(c.id),
                idea_text=f"Test as trading hypothesis: {c.claim_text}",
                domain="trading",
                status="EXTRACTED",
            )
            db.add(idea)
            ideas.append(idea)
        elif c.claim_type in ("demand", "pricing") and c.domain == "business":
            idea = models.WorldIdea(
                document_id=document_id,
                claim_ids=str(c.id),
                idea_text=f"Investigate business claim (do not trust): {c.claim_text}",
                domain="business",
                status="EXTRACTED",
            )
            db.add(idea)
            ideas.append(idea)
    db.commit()
    for i in ideas:
        db.refresh(i)
    return ideas


def process_permitted_text(
    db: Session,
    content_text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Full local pipeline for one permitted document."""
    doc = ingest_document(db, content_text, **kwargs)
    claims = extract_claims(db, doc.id)
    ideas = extract_ideas_from_claims(db, doc.id)
    return {
        "document_id": doc.id,
        "n_claims": len(claims),
        "n_ideas": len(ideas),
        "claims": [
            {
                "id": c.id,
                "claim_text": c.claim_text,
                "claim_type": c.claim_type,
                "domain": c.domain,
                "verification_status": c.verification_status,
            }
            for c in claims
        ],
        "note": "Extracted claims are UNVERIFIED. Not evidence. Not trades.",
    }
