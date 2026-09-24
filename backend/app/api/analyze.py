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
from app.services import pattern_engine, research_planner, collector_runner, evidence_graph
from app.services.observer_engine import ObserverEngine

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=schemas.AnalyzeResponse)
def analyze_idea(payload: schemas.AnalyzeRequest, db: Session = Depends(get_db)):
    """Start the real research pipeline for a user-submitted problem.

    This route still accepts input and records it as a Signal, but it does NOT
    create a fresh Opportunity on the basis of a raw idea alone. The public flow
    now creates a ResearchQuestion tied to a claim and executes the existing
    research pipeline (ResearchTask -> collector -> Evidence -> evaluation)
    before any Opportunity can be justified.
    """
    idea = payload.idea.strip()
    observer = ObserverEngine(db)
    signal = observer.observe(content=idea, source="manual")

    claim, _ = evidence_graph.create_or_get_claim(db, idea, epistemic_state="observed")
    question_text = f"Validate whether this problem is real and worth solving: {idea}"
    question = (
        db.query(models.ResearchQuestion)
        .filter(models.ResearchQuestion.question == question_text)
        .order_by(models.ResearchQuestion.id.desc())
        .first()
    )
    if question is None:
        question = models.ResearchQuestion(
            question=question_text,
            priority_score=80.0,
            status="open",
            source_claim_id=claim.id,
        )
        db.add(question)
        db.commit()
        db.refresh(question)

    tasks = research_planner.plan_tasks_for_question(db, question)
    task_results = collector_runner.run_pending_tasks(db, limit=max(1, len(tasks))) if tasks else []

    evidence_ids = []
    for task in db.query(models.ResearchTask).filter(models.ResearchTask.question_id == question.id).all():
        if not task.evidence_ids:
            continue
        evidence_ids.extend(int(value) for value in task.evidence_ids.split(",") if value.isdigit())
    evidence_ids = list(dict.fromkeys(evidence_ids))

    claim_evidence = (
        db.query(models.EvidenceRelationship)
        .filter(models.EvidenceRelationship.claim_id == claim.id)
        .all()
    )
    evidence_count = len({edge.evidence_id for edge in claim_evidence})
    if evidence_count == 0 and evidence_ids:
        evidence_count = len(evidence_ids)

    if task_results and any(result.get("status") == "completed" for result in task_results):
        research_status = "research_completed"
    elif evidence_count > 0:
        research_status = "evidence_found"
    elif any(result.get("status") in {"failed", "needs_research"} for result in task_results):
        research_status = "research_failed"
    else:
        research_status = "research_started"

    unknowns = [
        "Willingness to pay (UNKNOWN until tested)",
        "Frequency / severity across a representative sample (LIMITED evidence)",
        "Existing alternatives and switching costs (UNKNOWN)",
        "True market size (ESTIMATED at best, not measured)",
        "Acquisition path that actually works (UNKNOWN)",
    ]

    evidence_quality = "LIMITED"
    if evidence_count >= 3:
        evidence_quality = "MODERATE"
    if evidence_count >= 8:
        evidence_quality = "STRONG"

    recommended = (
        "Interview or contact 10–20 people in the stated target audience. "
        "Record how many confirm the problem, how severe they rate it, "
        "and whether they would pay for a solution (and at what price). "
        "This produces ACTUAL evidence; research results remain provisional until tested."
    )

    return schemas.AnalyzeResponse(
        opportunity_id=None,
        problem=idea,
        target_customer="Customer segment not yet validated by research",
        market_analysis=(
            "Research has started, but no opportunity is claimed until the problem, target customer, "
            "and willingness-to-pay signals are validated with actual evidence."
        ),
        solution="No solution is claimed yet; research is still validating the problem.",
        business_model="No validated business model is claimed yet.",
        pricing_idea="",
        mvp_plan="",
        validation_plan=(
            "Validate whether the problem is real by interviewing the intended users and checking whether "
            "customers confirm the pain and would pay for a fix."
        ),
        difficulty="unknown",
        score=0.0,
        signal_id=signal.id,
        observation_status="OBSERVED_AS_USER_REPORT",
        evidence_quality=evidence_quality,
        unknowns=unknowns,
        recommended_next_experiment=recommended,
        decision_id=None,
        knowledge_labels={
            "score": "NOT_VALIDATED",
            "pricing_idea": "UNVERIFIED",
            "market_analysis": "RESEARCH_IN_PROGRESS",
            "solution": "NOT_YET_PROVEN",
            "revenue": "NOT_MEASURED",
        },
        research_question_id=question.id,
        research_task_ids=[task.id for task in tasks],
        research_status=research_status,
        evidence_count=evidence_count,
        findings_summary=(
            f"Research has created {len(tasks)} task(s) and collected {evidence_count} evidence item(s) "
            f"for review. No opportunity is claimed until evidence is strong enough to justify it."
        ),
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
