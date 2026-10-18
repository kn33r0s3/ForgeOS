"""
LEARNING ENGINE
================

Compares EXPECTED vs ACTUAL outcomes and records structured LearningEvents.

This is not decorative "lesson learned" text. It:
  1. Records prediction error when measurable
  2. Applies shared knowledge changes only when an explicitly REAL learning event
     is linked to a verified REAL Outcome for the same canonical Experiment
  3. Keeps legacy BeliefExperiment reports HYPOTHESIS-only until a canonical,
     evidence-backed outcome path exists
  4. Never fabricates actuals — only records what was provided

States of knowledge remain labeled:
  ESTIMATED / EXPECTED  vs  ACTUAL / OBSERVED
"""

from __future__ import annotations

import math

from typing import Optional

from sqlalchemy.orm import Session

from app import evidence_source, models
from app.models import utcnow
from app.services import belief_engine




def record_learning_from_experiment(
    db: Session,
    experiment_id: int,
    *,
    prediction: str,
    actual: str,
    lesson: str,
    prediction_error: Optional[float] = None,
    error_type: Optional[str] = None,
    confidence_delta: Optional[float] = None,
    product_id: Optional[int] = None,
    data_scope: str = "REAL",
    source_kind: str = evidence_source.MOCK,
    commit: bool = True,
) -> models.LearningEvent:
    """Create a LearningEvent from a completed Experiment (opportunity test)."""
    exp = db.query(models.Experiment).filter_by(id=experiment_id).first()
    if not exp:
        raise ValueError(f"Experiment {experiment_id} not found")
    source_kind = evidence_source.validate(source_kind)
    if exp.data_scope != data_scope:
        raise ValueError("Learning scope must match experiment")
    if source_kind == evidence_source.REAL:
        verified_outcome = (
            db.query(models.Outcome.id)
            .filter(
                models.Outcome.experiment_id == experiment_id,
                *evidence_source.verified_real_outcome_filters(models.Outcome),
            )
            .first()
        )
        if verified_outcome is None:
            raise ValueError("REAL learning requires linked verified REAL outcome evidence")

    event = models.LearningEvent(
        experiment_id=experiment_id,
        opportunity_id=exp.opportunity_id,
        prediction=prediction,
        actual=actual,
        prediction_error=prediction_error,
        error_type=error_type,
        lesson=lesson,
        confidence_delta=confidence_delta,
        product_id=product_id,
        data_scope=data_scope,
        source_kind=source_kind,
        belief_update_applied=False,
    )
    db.add(event)

    # Persist lesson on the experiment if not already set
    if not exp.lesson:
        exp.lesson = lesson
    if exp.result is None:
        exp.result = actual

    try:
        db.flush()
        from app.services import lessons_engine
        lessons_engine.consolidate_learning_event(db, event, commit=False)
        if commit:
            db.commit()
    except Exception:
        db.rollback()
        raise

    return event


def record_learning_from_belief_experiment(
    db: Session,
    belief_experiment_id: int,
    *,
    prediction: str,
    actual: str,
    lesson: str,
    confidence_delta: float,
) -> models.LearningEvent:
    """Record an unverified BeliefExperiment report without applying it.

    The legacy BeliefExperiment table has no canonical verified-Outcome link.
    Therefore this event is HYPOTHESIS-only: it cannot update shared Belief
    confidence, source reliability, opportunity scores, or reusable causal
    knowledge. A later verified outcome must use the canonical Experiment /
    Outcome path. The recorded hypothesis and result are immutable.
    """
    bexp = db.query(models.BeliefExperiment).filter_by(id=belief_experiment_id).first()
    if not bexp:
        raise ValueError(f"BeliefExperiment {belief_experiment_id} not found")
    if bexp.status != "completed" or not (bexp.result or "").strip():
        raise ValueError("A completed BeliefExperiment result must be recorded before learning")
    if (prediction or "").strip() != (bexp.hypothesis or "").strip():
        raise ValueError("Learning prediction must match the experiment's pre-recorded hypothesis")
    if (actual or "").strip() != (bexp.result or "").strip():
        raise ValueError("Learning actual must match the persisted reported result")
    if not (lesson or "").strip():
        raise ValueError("A learning note is required")
    if bexp.confidence_change is None or not math.isfinite(float(bexp.confidence_change)):
        raise ValueError("BeliefExperiment has no finite reported confidence assessment")
    if (
        isinstance(confidence_delta, bool)
        or not isinstance(confidence_delta, (int, float))
        or not math.isfinite(float(confidence_delta))
        or not math.isclose(float(confidence_delta), float(bexp.confidence_change), rel_tol=0.0, abs_tol=1e-9)
    ):
        raise ValueError("Confidence assessment must match the value recorded with the result")

    existing = (
        db.query(models.LearningEvent)
        .filter_by(belief_experiment_id=belief_experiment_id)
        .order_by(models.LearningEvent.id.asc())
        .first()
    )
    if existing is not None:
        if (
            existing.prediction == bexp.hypothesis
            and existing.actual == bexp.result
            and existing.lesson == lesson.strip()
            and existing.source_kind == evidence_source.HYPOTHESIS
            and existing.confidence_delta is None
            and not existing.belief_update_applied
        ):
            return existing
        raise ValueError(
            "A learning record already exists for this BeliefExperiment; preserve history instead of duplicating it"
        )

    event = models.LearningEvent(
        belief_experiment_id=belief_experiment_id,
        belief_id=bexp.belief_id,
        prediction=bexp.hypothesis,
        actual=bexp.result,
        lesson=lesson.strip(),
        prediction_error=None,
        error_type=None,
        confidence_delta=None,
        belief_update_applied=False,
        data_scope="REAL",
        source_kind=evidence_source.HYPOTHESIS,
    )
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise
    return event


def compare_expected_vs_actual_numeric(
    expected: Optional[float],
    actual: Optional[float],
) -> dict:
    """Structured comparison for numeric predictions (revenue, conversion rate, etc.).

    Returns labels that preserve ESTIMATED vs ACTUAL distinction.
    """
    if expected is None and actual is None:
        return {"status": "UNKNOWN", "error": None, "error_type": None}
    if expected is None:
        return {"status": "ACTUAL_ONLY", "error": None, "error_type": None, "actual": actual}
    if actual is None:
        return {"status": "EXPECTED_ONLY", "error": None, "error_type": None, "expected": expected}

    if expected == 0:
        rel_error = None if actual == 0 else 1.0
    else:
        rel_error = (actual - expected) / abs(expected)

    if rel_error is None or abs(rel_error) < 0.1:
        error_type = "confirmed"
    elif rel_error > 0:
        error_type = "underestimate"  # actual higher than expected
    else:
        error_type = "overestimate"

    return {
        "status": "COMPARED",
        "expected": expected,  # ESTIMATE
        "actual": actual,      # ACTUAL
        "absolute_error": actual - expected,
        "relative_error": round(rel_error, 4) if rel_error is not None else None,
        "error_type": error_type,
    }


def list_learning_events(db: Session, limit: int = 50) -> list[models.LearningEvent]:
    return (
        db.query(models.LearningEvent)
        .order_by(models.LearningEvent.created_at.desc())
        .limit(limit)
        .all()
    )


def apply_learning_to_system(
    db: Session,
    event: models.LearningEvent,
) -> dict:
    """Propagate a LearningEvent into beliefs, sources, and opportunity notes.

    This is the difference between storing a lesson string and actually learning.
    """
    changes = {"belief_updated": False, "source_nudged": False, "opportunity_noted": False}

    if event.data_scope != "REAL" or not evidence_source.is_real(event.source_kind):
        return changes  # TEST/MOCK/HYPOTHESIS never changes shared REAL knowledge.
    if event.experiment_id is None:
        return changes  # A source-kind label without an Outcome link is not proof.
    verified_outcome = (
        db.query(models.Outcome.id)
        .filter(
            models.Outcome.experiment_id == event.experiment_id,
            *evidence_source.verified_real_outcome_filters(models.Outcome),
        )
        .first()
    )
    if verified_outcome is None:
        return changes  # REAL label alone cannot authorize learning.

    # Belief confidence already handled in record_learning_from_belief_experiment
    if event.belief_id and event.confidence_delta and not event.belief_update_applied:
        be = belief_engine.BeliefEngine(db)
        belief = be.get_belief(event.belief_id)
        if belief:
            be.adjust_confidence(
                belief,
                event.confidence_delta,
                reason="learning_event",
                experiment_id=None,
            )
            event.belief_update_applied = True
            db.commit()
            changes["belief_updated"] = True

    # Source reliability: if evidence sources supported a failed prediction, nudge down
    if event.belief_id and event.error_type == "overestimate":
        from app.services import source_manager
        evidence_rows = (
            db.query(models.Evidence)
            .filter(models.Evidence.belief_id == event.belief_id)
            .all()
        )
        nudged = set()
        for ev in evidence_rows:
            src_name = ev.source or "manual"
            if src_name in nudged:
                continue
            try:
                source_manager.adjust_reliability(db, src_name, delta=-1.5)
                nudged.add(src_name)
                changes["source_nudged"] = True
            except Exception:
                # adjust_reliability may not exist — try direct
                src = db.query(models.Source).filter_by(name=src_name).first()
                if src:
                    src.reliability_score = max(0.0, (src.reliability_score or 50) - 1.5)
                    db.commit()
                    changes["source_nudged"] = True
                    nudged.add(src_name)

    if event.opportunity_id and event.lesson:
        opp = db.query(models.Opportunity).filter_by(id=event.opportunity_id).first()
        if opp:
            note = f"[LEARNING {event.created_at}] {event.lesson}"
            existing = opp.validation_plan or ""
            if note not in existing:
                opp.validation_plan = (existing + "\n" + note).strip()
                # Slight score dampening on overestimate
                if event.error_type == "overestimate" and opp.score:
                    opp.score = round(max(0.0, opp.score * 0.95), 1)
                db.commit()
                changes["opportunity_noted"] = True

    return changes
