"""
API routes that drive Forge's core analysis loop:

  POST /analyze        -> acknowledge a problem and start bounded background research
  GET  /analyze/{id}/status -> read persisted progress for that research question
  POST /patterns/run    -> re-scan all stored signals and (re)detect patterns
  GET  /patterns        -> list currently detected patterns
  POST /patterns/{id}/opportunity -> generate an Opportunity from a specific pattern
  GET  /stats           -> dashboard totals
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models
from app.config import settings
from app.services import pattern_engine, evidence_graph
from app.services.observer_engine import ObserverEngine

router = APIRouter(tags=["analyze"])


def execute_research_task_in_background(task_id: int) -> None:
    """Execute one persisted, source-governed research task after acknowledgement."""
    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        return

    from app.services import collector_runner, research_planner
    from app.database import SessionLocal

    with SessionLocal() as db:
        task = (
            db.query(models.ResearchTask)
            .filter_by(id=task_id, status="planned")
            .one_or_none()
        )
        if task is None:
            return
        question_id = task.question_id
        collector_runner.execute_task(db, task)
        question = db.get(models.ResearchQuestion, question_id)
        if question is not None:
            research_planner.plan_tasks_for_question(db, question)


@router.post("/analyze", response_model=schemas.AnalyzeResponse)
def analyze_idea(
    payload: schemas.AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start the real research pipeline for a user-submitted problem.

    This route still accepts input and records it as a Signal, but it does NOT
    create a fresh Opportunity on the basis of a raw idea alone. The public flow
    creates a ResearchQuestion tied to a claim and returns its current persisted
    state. One planned, source-governed ResearchTask runs after acknowledgement;
    no Opportunity is justified by the raw idea alone.
    """
    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        raise HTTPException(status_code=503, detail="Legacy intelligence is disabled.")

    from app.services import research_planner

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

    reserved_task = research_planner.reserve_task_for_acknowledgement(db, question)
    if reserved_task is not None and reserved_task.status == "planned":
        background_tasks.add_task(
            execute_research_task_in_background,
            reserved_task.id,
        )
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
    claim_evidence_ids = {edge.evidence_id for edge in claim_evidence}
    persisted_claim_evidence_ids = set()
    if claim_evidence_ids:
        persisted_claim_evidence_ids = {
            row[0]
            for row in db.query(models.Evidence.id)
            .filter(models.Evidence.id.in_(claim_evidence_ids))
            .all()
        }
    evidence_count = len(persisted_claim_evidence_ids)
    persisted_evidence_ids = set()
    if evidence_ids:
        persisted_evidence_ids = {
            row[0]
            for row in db.query(models.Evidence.id)
            .filter(models.Evidence.id.in_(set(evidence_ids)))
            .all()
        }
    evidence_quality = "LIMITED"
    if evidence_count == 0 and persisted_evidence_ids:
        evidence_count = len(persisted_evidence_ids)

    states = {task.status for task in tasks}
    has_pending_tasks = bool(states & {"planned", "running"})
    has_unresolved_tasks = bool(states & {"failed", "needs_research"})
    research_plan = question.research_plan or research_planner.acknowledgement_plan(
        question, tasks
    )
    if research_plan.get("status") == "research_complete":
        research_status = "research_complete"
    elif research_plan.get("status") == "research_terminal_unresolved":
        research_status = "research_terminal_unresolved"
    elif states & {"failed"} and not has_pending_tasks:
        research_status = "research_failed"
    elif states & {"needs_research"} or states == {"completed"}:
        research_status = "research_needs_evidence"
    elif evidence_count > 0:
        research_status = "research_in_progress"
    else:
        research_status = "research_started"

    unknowns = [
        f'{requirement["question"]} — '
        f'{requirement.get("terminal_reason") or requirement.get("status", "unresolved")}'
        for requirement in research_plan.get("requirements", [])
        if requirement.get("status") != "satisfied"
    ]
    unknowns.extend(research_plan["unknowns"])
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

    if research_status == "research_terminal_unresolved":
        findings_summary = (
            f"The bounded research loop reached a terminal state after {len(tasks)} task(s), but "
            f"{len(research_plan.get('unresolved_requirements', []))} evidence requirement(s) remain unresolved. "
            "Collected bibliographic records are leads only; no opportunity or market claim is validated."
        )
    elif evidence_count:
        findings_summary = (
            f"Persisted {evidence_count} attributable evidence record(s); "
            f"{sum(task.status in {'planned', 'running'} for task in tasks)} task(s) remain queued or running. "
            "These are research leads, not validated demand or answers to unrelated requirements."
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
        research_status_url=f"/analyze/{question.id}/status",
        evidence_count=evidence_count,
        findings_summary=findings_summary,
        research_plan=research_plan,
        research_sources=research_sources,
    )


@router.get(
    "/analyze/{question_id}/status",
    response_model=schemas.AnalyzeProgressResponse,
)
def get_analyze_status(question_id: int, db: Session = Depends(get_db)):
    """Return current persisted progress without rerunning research."""
    question = db.get(models.ResearchQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="research question not found")

    tasks = (
        db.query(models.ResearchTask)
        .filter(models.ResearchTask.question_id == question.id)
        .order_by(models.ResearchTask.id.asc())
        .populate_existing()
        .all()
    )
    task_evidence_ids = {
        int(value)
        for task in tasks
        for value in (task.evidence_ids or "").split(",")
        if value.isdigit()
    }
    claim_evidence_ids = set()
    if question.source_claim_id is not None:
        claim_evidence_ids = {
            row[0]
            for row in db.query(models.EvidenceRelationship.evidence_id)
            .filter(models.EvidenceRelationship.claim_id == question.source_claim_id)
            .all()
        }
    all_evidence_ids = task_evidence_ids | claim_evidence_ids
    persisted_evidence_ids = set()
    if all_evidence_ids:
        persisted_evidence_ids = {
            row[0]
            for row in db.query(models.Evidence.id)
            .filter(models.Evidence.id.in_(all_evidence_ids))
            .all()
        }
    persisted_claim_evidence_ids = persisted_evidence_ids & claim_evidence_ids
    evidence_count = len(persisted_claim_evidence_ids)
    if not evidence_count:
        evidence_count = len(persisted_evidence_ids & task_evidence_ids)

    research_plan = question.research_plan or {}
    states = {task.status for task in tasks}
    has_pending_tasks = bool(states & {"planned", "running"})
    has_unresolved_tasks = bool(states & {"failed", "needs_research"})
    if research_plan.get("status") == "research_complete":
        research_status = "research_complete"
    elif research_plan.get("status") == "research_terminal_unresolved":
        research_status = "research_terminal_unresolved"
    elif states & {"failed"} and not has_pending_tasks:
        research_status = "research_failed"
    elif states & {"needs_research"} or states == {"completed"}:
        research_status = "research_needs_evidence"
    elif evidence_count > 0:
        research_status = "research_in_progress"
    else:
        research_status = "research_started"

    if "running" in states:
        phase = "researching"
    elif "planned" in states:
        phase = "queued"
    elif research_status == "research_complete":
        phase = "completed"
    elif research_status in {"research_terminal_unresolved", "research_failed"}:
        phase = "blocked"
    elif evidence_count:
        phase = "evidence_found"
    elif research_status == "research_needs_evidence" or has_unresolved_tasks:
        phase = "awaiting_evidence"
    else:
        phase = "not_started"

    source_results = []
    task_progress = []
    for task in tasks:
        results = task.results if isinstance(task.results, dict) else {}
        source_results.extend(
            item
            for item in results.get("source_results", [])
            if isinstance(item, dict) and isinstance(item.get("evidence_id"), int)
        )
        task_ids = {
            int(value)
            for value in (task.evidence_ids or "").split(",")
            if value.isdigit()
        }
        task_progress.append(
            schemas.AnalyzeTaskProgress(
                id=task.id,
                source=task.source,
                status=task.status,
                current_step=task.current_step,
                attempts=task.attempts,
                evidence_count=len(task_ids & persisted_evidence_ids),
                updated_at=task.updated_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )
        )
    return schemas.AnalyzeProgressResponse(
        research_question_id=question.id,
        phase=phase,
        research_status=research_status,
        evidence_count=evidence_count,
        tasks=task_progress,
        research_plan=research_plan,
        research_sources=source_results,
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
    try:
        return opportunity_engine.opportunity_from_pattern(db, pattern)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """Dashboard summary counts — truthful zeros when empty."""
    return schemas.StatsOut(
        total_signals=db.query(models.Signal).count(),
        total_patterns=db.query(models.Pattern).count(),
        total_opportunities=db.query(models.Opportunity).count(),
        total_experiments=db.query(models.Experiment).count(),
    )
