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

    research_planner.plan_tasks_for_question(db, question)
    collector_runner.run_pending_tasks(db, limit=1)
    tasks = (
        db.query(models.ResearchTask)
        .filter(models.ResearchTask.question_id == question.id)
        .order_by(models.ResearchTask.id.asc())
        .all()
    )

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
    evidence_quality = "LIMITED"
    if evidence_count == 0 and evidence_ids:
        evidence_count = len(evidence_ids)

    states = {task.status for task in tasks}
    has_pending_tasks = bool(states & {"planned", "running"})
    has_unresolved_tasks = bool(states & {"failed", "needs_research"})
    task_evidence_count = len(set(evidence_ids))
    all_tasks_collected = bool(tasks) and states == {"completed"} and task_evidence_count > 0
    if all_tasks_collected:
        research_status = "research_completed"
    elif evidence_count > 0:
        research_status = "evidence_found"
    elif states & {"failed"}:
        research_status = "research_failed"
    elif states & {"needs_research"} or states == {"completed"}:
        research_status = "research_needs_evidence"
    else:
        research_status = "research_started"

    research_plan = (
        tasks[0].results.get("research_plan")
        if tasks and isinstance(tasks[0].results, dict)
        else None
    ) or research_planner.build_research_plan(db, question)
    unknowns = list(research_plan["unknowns"])
    if not evidence_count:
        unknowns.insert(0, "No external research evidence has been persisted for this question yet.")

    source_results_by_evidence: dict[int, dict] = {}
    for task in tasks:
        task_results = task.results if isinstance(task.results, dict) else {}
        for source_result in task_results.get("source_results", []):
            if isinstance(source_result, dict) and isinstance(source_result.get("evidence_id"), int):
                source_results_by_evidence[source_result["evidence_id"]] = source_result
    research_sources = list(source_results_by_evidence.values())

    recommended = (
        "After reviewing the cited sources and unresolved questions, the cheapest meaningful validation "
        "is a consent-based conversation with people in the relevant group. Record actual confirmations, "
        "rejections, severity, and any stated willingness to pay. ForgeOS does not contact anyone or "
        "treat a proposed test as an executed experiment."
    )

    if all_tasks_collected:
        findings_summary = (
            f"All {len(tasks)} planned source tasks returned attributable records. This completes "
            "collection only: relevance, factual support, customer demand, willingness to pay, and "
            "commercial viability remain unvalidated."
        )
    elif evidence_count:
        findings_summary = (
            f"Persisted {evidence_count} attributable evidence record(s); "
            f"{sum(task.status in {'planned', 'running'} for task in tasks)} task(s) remain queued or running. "
            "These are research leads, not validated demand."
        )
    elif has_pending_tasks:
        findings_summary = (
            f"{len(tasks)} durable task(s) are planned or running; no external evidence has been persisted yet."
        )
    elif has_unresolved_tasks:
        findings_summary = (
            f"No external evidence was persisted. {len(tasks)} task(s) ended with an access failure or no-result "
            "outcome and remain unverified."
        )
    else:
        findings_summary = "No cleared external source strategy is currently available for this question."

    return schemas.AnalyzeResponse(
        opportunity_id=None,
        problem=idea,
        target_customer="Customer segment not yet identified or validated",
        market_analysis=(
            "No opportunity is claimed. Bibliographic search results can identify research leads, but do not "
            "establish an unmet need, a customer, willingness to pay, or a business case."
        ),
        solution="No solution is claimed yet; research is still validating the problem.",
        business_model="No validated business model is claimed yet.",
        pricing_idea="",
        mvp_plan="",
        validation_plan=recommended,
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
        findings_summary=findings_summary,
        research_plan=research_plan,
        research_sources=research_sources,
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
