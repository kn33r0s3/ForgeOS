
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_owner_api_key
from app.services.rare_signal_engine import detect_rare_signals, trigger_research_for_rare_signals

router = APIRouter(prefix="/intelligence/rare-signals", tags=["rare-signals"])


def serialize(assessment):
    return {
        "id": assessment.id,
        "cluster_key": assessment.cluster_key,
        "label": assessment.label,
        "signal_ids": [int(value) for value in assessment.signal_ids.split(",") if value.strip().isdigit()],
        "frequency": assessment.frequency,
        "prior_frequency": assessment.prior_frequency,
        "recent_frequency": assessment.recent_frequency,
        "velocity": assessment.velocity,
        "acceleration": assessment.acceleration,
        "source_diversity": assessment.source_diversity,
        "novelty": assessment.novelty,
        "specificity": assessment.specificity,
        "pain_intensity": assessment.pain_intensity,
        "solution_scarcity": assessment.solution_scarcity,
        "economic_relevance": assessment.economic_relevance,
        "freshness": assessment.freshness,
        "recurrence": assessment.recurrence,
        "geographic_spread": assessment.geographic_spread,
        "language_spread": assessment.language_spread,
        "score": assessment.score,
        "status": assessment.status,
        "explanation": assessment.explanation,
        "pattern_id": assessment.pattern_id,
        "opportunity_id": assessment.opportunity_id,
        "research_question_id": assessment.research_question_id,
        "first_seen": assessment.first_seen,
        "last_seen": assessment.last_seen,
        "updated_at": assessment.updated_at,
    }


@router.post("/detect")
def detect(request: Request, min_score: float = 35.0, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    assessments = detect_rare_signals(db, min_score=min_score)
    trigger_research_for_rare_signals(db, assessments)
    return [serialize(assessment) for assessment in assessments]
