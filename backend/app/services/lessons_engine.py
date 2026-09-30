"""Lessons Memory — ForgeOS's durable "what it has actually learned".

This is the recall/consolidation half of the learning loop, and it makes
ForgeOS learn the way the operator's assistant does:

  - **consolidate()**  — when a real LearningEvent is recorded, file it into a
    durable, themed Lesson (dedupe by theme key, bump hit_count/last_seen,
    merge prediction errors). Mirrors filing a fact into a memory page.
  - **recall()**       — surface relevant Lessons when reasoning about an
    opportunity or decision, so *past reality* informs what ForgeOS pursues
    next instead of being computed from a fresh signal pool every time.

Honesty guarantee: a Lesson is NEVER fabricated. It only exists if a real
LearningEvent produced it, and a LearningEvent only exists if a real ACTUAL
outcome was recorded (see learning_engine / outcome_learning). Themed lessons
are the merged record of those real events, never invented claims.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models

# Words that carry real signal for consolidating lessons about an opportunity
# / market. Used only to build a stable dedupe theme key (deterministic — no
# LLM, works with AI_PROVIDER=mock). A lesson with none of these falls back to
# a "general" key rather than being dropped.
THEME_WORDS = [
    "pricing", "price", "revenue", "customer", "demand", "no-show", "reply",
    "response", "conversion", "lead", "outreach", "interview", "pilot",
    "willingness", "pay", "cost", "churn", "retention", "acquisition",
    "free", "trial", "discount", "onboarding", "support", "service",
    "marketplace", "gig", "content", "ad", "ads", "seo", "social",
    "referral", "partner", "response-rate", "eps", "offering", "positioning",
]


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Theme extraction (deterministic, honest)
# ---------------------------------------------------------------------------

def _theme_key_from(event: models.LearningEvent, lesson_text: str,
                    opportunity: Optional[models.Opportunity] = None) -> str:
    """Build a stable, coarse theme key from the lesson + linked opportunity.

    Picks theme words found in the concatenated text (lowercased). If the
    opportunity has a customer/problem worth naming, the key becomes
    "<word>:<customer-word>" so distinct market lessons don't collapse into
    one page. Deterministic and cheap — no model call.
    """
    text = f"{lesson_text} {event.prediction or ''} {event.actual or ''}".lower()
    found = [w for w in THEME_WORDS if w in text]
    # opportunity context sharpens the theme
    opp_word = ""
    if opportunity:
        hint = f"{opportunity.target_customer or ''} {opportunity.problem or ''}".lower()
        for w in THEME_WORDS:
            if w and w in hint:
                opp_word = w
                break
        else:
            # fall back to a content word from the problem if any
            m = re.findall(r"[a-z]{5,}", hint)
            if m:
                opp_word = m[0]
    if found:
        base = found[0]
    elif opp_word:
        base = opp_word
    else:
        base = "general"
    key = f"{base}:{opp_word}" if opp_word and opp_word != base else base
    return key


# ---------------------------------------------------------------------------
# Consolidate — file a LearningEvent into a durable Lesson
# ---------------------------------------------------------------------------

def consolidate_learning_event(db: Session, event: models.LearningEvent,
                               lesson_text: Optional[str] = None, *, commit: bool = True) -> models.Lesson:
    """Upsert a LearningEvent into a themed Lesson (dedupe by theme key).

    If no theme exists yet, creates one. If one exists, merges: hit_count++,
    last_seen updated, prediction_error averaged in, event id appended to
    provenance. Returns the (existing or new) Lesson.
    """
    text = (lesson_text or event.lesson or "").strip() or (event.actual or "")
    opportunity = (
        db.query(models.Opportunity).filter_by(id=event.opportunity_id).first()
        if event.opportunity_id else None
    )
    key = _theme_key_from(event, text, opportunity)

    # If the event names an opportunity, try to attach that context to the key.
    lesson = (
        db.query(models.Lesson)
        .filter_by(theme_key=key, active=True, data_scope=event.data_scope)
        .order_by(models.Lesson.last_seen.desc())
        .first()
    )
    if lesson and str(event.id) in (lesson.source_learning_event_ids or "").split(","):
        return lesson
    now = utcnow()
    if lesson is None:
        title = _make_title(event, key)
        lesson = models.Lesson(
            theme_key=key,
            title=title,
            summary=text,
            opportunity_id=event.opportunity_id,
            belief_id=event.belief_id,
            product_id=event.product_id,
            error_type=event.error_type,
            prediction_error_avg=float(event.prediction_error or 0.0),
            hit_count=1,
            source_learning_event_ids=str(event.id),
            first_seen=now,
            last_seen=now,
            active=True,
            data_scope=event.data_scope,
            created_at=now,
            updated_at=now,
        )
        db.add(lesson)
    else:
        # merge: average the prediction error, append provenance, update timestamps
        prev_avg = lesson.prediction_error_avg or 0.0
        prev_n = max(lesson.hit_count, 1)
        new_err = float(event.prediction_error or 0.0)
        lesson.prediction_error_avg = (prev_avg * prev_n + new_err) / (prev_n + 1)
        lesson.hit_count += 1
        ids = [s for s in (lesson.source_learning_event_ids or "").split(",") if s]
        if str(event.id) not in ids:
            ids.append(str(event.id))
        lesson.source_learning_event_ids = ",".join(ids)
        # keep the more recent summary, but never overwrite a known lesson
        # with a weaker one when the new text is just the generic fallback
        if text and not _is_generic(text):
            lesson.summary = text
        lesson.error_type = event.error_type or lesson.error_type
        if event.opportunity_id and not lesson.opportunity_id:
            lesson.opportunity_id = event.opportunity_id
        lesson.last_seen = now
        lesson.updated_at = now

    try:
        db.commit() if commit else db.flush()
    except Exception:
        db.rollback()
        raise
    return lesson


def _is_generic(text: str) -> bool:
    lowered = text.lower()
    return "causal explanation remains uncertain" in lowered or "uncertain unless" in lowered


def _make_title(event: models.LearningEvent, key: str) -> str:
    """A short headline derived from the lesson text / error type."""
    text = (event.lesson or event.actual or "").strip() or "self-contained lesson"
    snippet = text[:80].rstrip()
    if event.error_type == "confirmed":
        return f"Confirmed: {snippet}"
    if event.error_type == "overestimate":
        return f"We overestimated: {snippet}"
    if event.error_type == "underestimate":
        return f"We underestimated: {snippet}"
    if event.error_type == "qualitative_miss":
        return f"Missed the mark: {snippet}"
    return f"Lesson ({key}): {snippet}"


# ---------------------------------------------------------------------------
# Recall — surface lessons that should inform a new reasoning pass
# ---------------------------------------------------------------------------

def recall_lessons(db: Session, *, opportunity_id: Optional[int] = None,
                   limit: int = 8, include_inactive: bool = False, data_scope: str = "REAL") -> list[models.Lesson]:
    """Return the most relevant active Lessons for a given context.

    Relevance is honest and simple: lessons directly tied to this opportunity
    (or to the same theme key) that were seen most recently rank first.
    Used at reasoning time so past reality shapes the next decision.
    """
    q = db.query(models.Lesson).filter(models.Lesson.data_scope == data_scope)
    if not include_inactive:
        q = q.filter(models.Lesson.active == True)  # noqa: E712
    if opportunity_id is not None:
        # rank: same-opportunity lessons first, then by recency
        opp = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
        all_lessons = q.order_by(models.Lesson.last_seen.desc()).limit(80).all()
        same = [l for l in all_lessons if l.opportunity_id == opportunity_id]
        # theme-match via the opportunity's own words
        hint = f"{opp.target_customer or ''} {opp.problem or ''}".lower() if opp else ""
        themed = [
            l for l in all_lessons
            if l.id not in {s.id for s in same}
            and any(w in l.theme_key for w in THEME_WORDS if w and w in hint)
        ]
        ranked = (same + themed + [l for l in all_lessons if l.id not in {
            s.id for s in same + themed
        }])[:limit]
        return ranked
    return q.order_by(models.Lesson.last_seen.desc()).limit(limit).all()


def assist_decision(db: Session, *, opportunity_id: Optional[int] = None,
                    rationale: Optional[str] = None, data_scope: str = "REAL") -> dict:
    """Produce the 'recalled context' an opportunity/decision should see.

    Returns the recalled lessons plus a short structured note adding the past
    reality to the decision rationale. Honest: notes lessons verbatim with
    their hit_count, never a fabricated 'the market proved X'.
    """
    lessons = recall_lessons(db, opportunity_id=opportunity_id, limit=6, data_scope=data_scope)
    notes = []
    for l in lessons:
        notes.append(
            f"past-lesson {l.id} ({l.theme_key}{' x%s' % l.hit_count if l.hit_count > 1 else ''}): {l.summary[:160]}"
        )
    return {
        "recalled_lessons": [{
            "id": l.id, "theme_key": l.theme_key, "title": l.title,
            "summary": l.summary, "hit_count": l.hit_count,
            "prediction_error_avg": l.prediction_error_avg,
            "error_type": l.error_type, "last_seen": l.last_seen,
            "opportunity_id": l.opportunity_id, "belief_id": l.belief_id,
            "product_id": l.product_id,
            "source_learning_event_ids": l.source_learning_event_ids,
            "first_seen": l.first_seen, "active": l.active,
            "created_at": l.created_at, "updated_at": l.updated_at,
            "data_scope": l.data_scope,
        } for l in lessons],
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Feed-forward wiring
# ---------------------------------------------------------------------------

def run_lessons_cycle(db: Session) -> dict:
    """One pass of the Lessons Memory across the existing learning backlog.

    Re-consolidates any LearningEvent that is not yet part of a Lesson, so a
    lesson learned via the API/experiment path gets filed even if it predates
    the Lessons Memory feature. Idempotent. Returns counts.
    """
    existing_event_ids: set[int] = set()
    for lesson in db.query(models.Lesson).all():
        for s in (lesson.source_learning_event_ids or "").split(","):
            if s:
                try:
                    existing_event_ids.add(int(s))
                except ValueError:
                    pass
    events = db.query(models.LearningEvent).order_by(models.LearningEvent.created_at.asc()).all()
    made = 0
    for ev in events:
        if ev.id in existing_event_ids:
            continue
        consolidate_learning_event(db, ev)
        made += 1
    return {"events_total": len(events), "new_lessons_or_merges": made, "lessons_total": db.query(models.Lesson).count()}
