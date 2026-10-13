"""Grounded bilingual public-content drafts over the existing Hami substrate.

This module drafts from persisted open research questions only. It never makes
network calls, publishes, sends outreach, asserts that a hypothesis is true,
or creates a parallel domain table. Drafts are ENTITYs, their question lineage
is a RELATION, and each generated draft emits an EVENT.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import world_graph

GENERATOR_VERSION = "1"
CREATED_BY = "content_loop"
MAX_DRAFTS_PER_RUN = 3
MAX_QUESTION_LENGTH = 800

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL = re.compile(r"\bhttps?://\S+", re.IGNORECASE)
_SECRET = re.compile(r"\b(?:password|passcode|secret|api[\s_-]?key|access token|private key)\b", re.IGNORECASE)
_DIGITS = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]*){9,}(?!\w)")


def _clean_question(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _contains_private_material(question: str) -> bool:
    if _EMAIL.search(question) or _URL.search(question) or _SECRET.search(question):
        return True
    # Fail closed on long number-like strings that could be phone numbers or
    # identifiers. Public copy must not echo them automatically.
    return bool(_DIGITS.search(question))


def _fingerprint(question_id: int, question: str) -> str:
    basis = f"question-invitation:v{GENERATOR_VERSION}:{question_id}:{question}".encode("utf-8")
    return hashlib.sha256(basis).hexdigest()


def _bilingual_copy(question: str) -> tuple[str, str]:
    english = (
        f"We're exploring an open question: “{question}”\n\n"
        "Hami wants to understand real needs before deciding what to build. "
        "If you have firsthand experience, what should we understand first? "
        "Share only what you're comfortable making public.\n\n"
        "This is a research invitation, not a claim that the problem is common or solved."
    )
    nepali = (
        f"हामी एउटा खुला प्रश्नबारे बुझ्दैछौँ: “{question}”\n\n"
        "के निर्माण गर्ने भन्ने निर्णय गर्नुअघि Hami वास्तविक आवश्यकता बुझ्न चाहन्छ। "
        "तपाईंलाई यसबारे प्रत्यक्ष अनुभव छ भने हामीले पहिले के बुझ्नुपर्छ? "
        "सार्वजनिक रूपमा साझा गर्न सहज हुने कुरा मात्र लेख्नुहोस्।\n\n"
        "यो अनुभव बुझ्नका लागि निमन्त्रणा हो—समस्या व्यापक छ वा समाधान भइसकेको छ भन्ने दाबी होइन।"
    )
    return english, nepali


def run_content_draft_cycle(
    db: Session,
    *,
    max_new_drafts: int = MAX_DRAFTS_PER_RUN,
    candidate_limit: int = 500,
) -> dict[str, Any]:
    """Create up to three new bilingual drafts from the open-world question queue.

    Existing drafts remain untouched and are counted for observability. Draft
    creation is idempotent by source-question ID + content version + question
    text. Unusually sensitive questions are skipped rather than copied to public
    copy. The publisher is explicitly blocked until official channel credentials
    and publication rights have been verified.
    """
    if isinstance(max_new_drafts, bool) or not isinstance(max_new_drafts, int):
        raise ValueError("max_new_drafts must be an integer")
    limit = max(0, min(max_new_drafts, MAX_DRAFTS_PER_RUN))
    candidates = max(1, min(int(candidate_limit), 5000))

    world_graph.seed_core_types(db)
    report: dict[str, Any] = {
        "status": "ok",
        "source_questions_scanned": 0,
        "drafts_generated": 0,
        "existing_drafts": 0,
        "skipped_private_or_sensitive": 0,
        "errors": [],
        "published": 0,
        "publish_status": "blocked",
        "publish_blockers": [
            "no_verified_official_social_publisher",
            "content_publication_permission_not_enabled",
        ],
    }

    questions = (
        db.query(models.ResearchQuestion)
        .filter(models.ResearchQuestion.status.in_(("open", "planned")))
        .order_by(
            models.ResearchQuestion.priority_score.desc(),
            models.ResearchQuestion.id.asc(),
        )
        .limit(candidates)
        .all()
    )

    for row in questions:
        report["source_questions_scanned"] += 1
        question = _clean_question(row.question)
        if (
            not question
            or len(question) > MAX_QUESTION_LENGTH
            or _contains_private_material(question)
        ):
            report["skipped_private_or_sensitive"] += 1
            continue

        fingerprint = _fingerprint(row.id, question)
        source_id = f"rq-{row.id}-v{GENERATOR_VERSION}-{fingerprint[:16]}"
        existing = (
            db.query(models.SubstrateEntity)
            .filter_by(
                entity_type="content_asset",
                source_system="hami_content_loop",
                source_id=source_id,
            )
            .one_or_none()
        )
        if existing is None and report["drafts_generated"] >= limit:
            break

        content_en, content_ne = _bilingual_copy(question)
        attrs = {
            "content_type": "question_invitation",
            "status": "draft",
            "content_en": content_en,
            "content_ne": content_ne,
            "source_record": {"table": "research_questions", "id": row.id},
            "source_question": question,
            "source_fingerprint": fingerprint,
            "source_kind": "HYPOTHESIS",
            "language_codes": ["en", "ne"],
            "publish_status": "blocked",
            "publish_blockers": [
                "no_verified_official_social_publisher",
                "content_publication_permission_not_enabled",
            ],
            "generator_version": GENERATOR_VERSION,
            "truth_note": "Open research question; not evidence of prevalence or a proven result.",
        }

        asset = existing or world_graph.create_entity(
            db,
            entity_type="content_asset",
            display_name=f"Hami research question {row.id}: {question[:170]}",
            attributes=attrs,
            created_by=CREATED_BY,
            identity={
                "source_system": "hami_content_loop",
                "source_id": source_id,
                "provenance": {
                    "source_table": "research_questions",
                    "source_record_id": row.id,
                    "source_question_fingerprint": fingerprint,
                    "generator_version": GENERATOR_VERSION,
                },
            },
        )

        source_entity = world_graph.ensure_canonical_entity(
            db, "research_question", row.id, created_by=CREATED_BY
        )
        world_graph.create_relation(
            db,
            from_entity_id=asset.id,
            to_entity_id=source_entity.id,
            relation_type="derived_from",
            attributes={
                "source_table": "research_questions",
                "source_record_id": row.id,
                "source_fingerprint": fingerprint,
            },
            direction="directed",
            truth_state="hypothesized",
            created_by=CREATED_BY,
            idempotency_key=f"content-draft-source:{fingerprint}",
        )
        world_graph.create_event(
            db,
            event_type="content_draft_created",
            source=CREATED_BY,
            entity_id=asset.id,
            payload={
                "source_table": "research_questions",
                "source_record_id": row.id,
                "source_fingerprint": fingerprint,
                "generator_version": GENERATOR_VERSION,
                "status": "draft",
                "publication_attempted": False,
            },
            idempotency_key=f"content-draft-created:{fingerprint}",
        )

        if existing is None:
            report["drafts_generated"] += 1
        else:
            report["existing_drafts"] += 1

    return report
