"""
API routes that drive Forge's core analysis loop:

  POST /analyze        -> turn one free-text idea into structured intelligence + Opportunity
  POST /patterns/run    -> re-scan all stored signals and (re)detect patterns
  GET  /patterns        -> list currently detected patterns
  POST /patterns/{id}/opportunity -> generate an Opportunity from a specific pattern
  GET  /stats           -> dashboard totals
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models
from app.services import pattern_engine, opportunity_engine
from app.services.observer_engine import ObserverEngine
from app.services import decision_engine

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=schemas.AnalyzeResponse)
def analyze_idea(payload: schemas.AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Manual observation entry point.

    1. Stores the text as an Observation (Signal) with provenance = user/manual
    2. Creates an Opportunity (heuristic score — labeled as such)
    3. Lists explicit unknowns
    4. Proposes a low-cost next experiment Decision

    Does NOT claim the score is proof of demand or that estimates are actuals.
    """
    # 1. Observation with provenance
    observer = ObserverEngine(db)
    signal = observer.observe(content=payload.idea, source="manual")

    # 2. Opportunity (downstream of observation)
    opportunity = opportunity_engine.opportunity_from_idea(db, payload.idea)

    # 3. Explicit unknowns — reality-first
    unknowns = [
        "Willingness to pay (UNKNOWN until tested)",
        "Frequency / severity across a representative sample (LIMITED evidence)",
        "Existing alternatives and switching costs (UNKNOWN)",
        "True market size (ESTIMATED at best, not measured)",
        "Acquisition path that actually works (UNKNOWN)",
    ]

    evidence_quality = "LIMITED"
    if signal.quality_score and signal.quality_score >= 70:
        evidence_quality = "MODERATE"
    if signal.quality_score and signal.quality_score >= 85:
        evidence_quality = "MODERATE"  # single user report still not STRONG

    recommended = (
        "Interview or contact 10–20 people in the stated target audience. "
        "Record how many confirm the problem, how severe they rate it, "
        "and whether they would pay for a solution (and at what price). "
        "This produces ACTUAL evidence; the current score is only HEURISTIC."
    )

    # 4. Decision: propose validation experiment
    decision = decision_engine.suggest_next_experiment_decision(db, opportunity.id)

    return schemas.AnalyzeResponse(
        opportunity_id=opportunity.id,
        problem=opportunity.problem,
        target_customer=opportunity.target_customer,
        market_analysis=opportunity.market_analysis or "",
        solution=opportunity.solution,
        business_model=opportunity.business_model,
        pricing_idea=opportunity.pricing_idea or "",
        mvp_plan=opportunity.mvp_plan or "",
        validation_plan=opportunity.validation_plan or "",
        difficulty=opportunity.difficulty or "unknown",
        score=opportunity.score,
        signal_id=signal.id,
        observation_status="OBSERVED_AS_USER_REPORT",
        evidence_quality=evidence_quality,
        unknowns=unknowns,
        recommended_next_experiment=recommended,
        decision_id=decision.id if decision else None,
        knowledge_labels={
            "score": "HEURISTIC",
            "pricing_idea": "ESTIMATED",
            "market_analysis": "INFERRED",
            "solution": "PROPOSED",
            "revenue": "NOT_MEASURED",
        },
    )


@router.post("/patterns/run", response_model=schemas.PatternRunResponse)
def run_patterns(db: Session = Depends(get_db)):
    """Re-scan all stored signals and detect repeated-problem patterns."""
    patterns = pattern_engine.run_pattern_detection(db)
    return schemas.PatternRunResponse(patterns_found=len(patterns), patterns=patterns)


@router.get("/patterns", response_model=list[schemas.PatternOut])
def get_patterns(db: Session = Depends(get_db)):
    """List currently detected patterns, strongest confidence first."""
    return (
        db.query(models.Pattern)
        .order_by(models.Pattern.confidence_score.desc())
        .all()
    )


@router.post("/patterns/{pattern_id}/opportunity", response_model=schemas.OpportunityOut)
def create_opportunity_from_pattern(pattern_id: int, db: Session = Depends(get_db)):
    """Generate (and persist) a full business Opportunity from a specific detected pattern."""
    pattern = db.query(models.Pattern).filter(models.Pattern.id == pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return opportunity_engine.opportunity_from_pattern(db, pattern)


@router.get("/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """Dashboard summary counts — truthful zeros when empty."""
    return schemas.StatsOut(
        total_signals=db.query(models.Signal).count(),
        total_patterns=db.query(models.Pattern).count(),
        total_opportunities=db.query(models.Opportunity).count(),
        total_experiments=db.query(models.Experiment).count(),
    )
