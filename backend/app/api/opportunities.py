"""API routes for listing generated opportunities and logging experiments."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

from app.database import get_db
from app import schemas, models
from app.services import opportunity_engine
from app.services import evidence_graph
from app.services import multi_judge
from app.services import opportunity_monitor
from app.services import option_space, outcome_learning, experiment_service
from app.services import experiment_action_service
from app.services import economic_validation
from app.schemas.experiment import ExperimentAuthorize, ExperimentOutcomeCreate, ExperimentProposalCreate

router = APIRouter(tags=["opportunities"])


class ExperimentOutcomeBody(BaseModel):
    actual: str = Field(..., min_length=1)
    success: Optional[bool] = None
    source: str = "manual"
    actual_value: Optional[float] = None
    unit: Optional[str] = None
    lesson: Optional[str] = None


class NeedEconomicAssessmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solution_hypothesis: str = Field(..., min_length=1, max_length=2000)
    capability_id: Optional[int] = Field(default=None, ge=1)
    cost_assumption: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    price_assumption: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    evidence_by_assumption: dict[str, list[int]] = Field(default_factory=dict)
    fulfillment_constraints: list[str] = Field(default_factory=list, max_length=30)
    unresolved_uncertainties: list[str] = Field(default_factory=list, max_length=30)
    experiment_definition: str = Field(..., min_length=1, max_length=3000)
    experiment_tests_willingness_to_pay: bool = False


@router.get("/opportunities", response_model=list[schemas.OpportunityOut])
def get_opportunities(limit: int = 200, db: Session = Depends(get_db)):
    """List discovered opportunities, highest score first."""
    return opportunity_engine.list_opportunities(db, limit=limit)


@router.post("/needs/{need_id}/economic-validation")
def assess_need_economic_validation(
    need_id: int,
    payload: NeedEconomicAssessmentBody,
    db: Session = Depends(get_db),
):
    try:
        return economic_validation.assess_need_economics(
            db,
            need_id,
            solution_hypothesis=payload.solution_hypothesis,
            capability_id=payload.capability_id,
            cost_assumption=payload.cost_assumption,
            price_assumption=payload.price_assumption,
            evidence_by_assumption=payload.evidence_by_assumption,
            fulfillment_constraints=payload.fulfillment_constraints,
            unresolved_uncertainties=payload.unresolved_uncertainties,
            experiment_definition=payload.experiment_definition,
            experiment_tests_willingness_to_pay=payload.experiment_tests_willingness_to_pay,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/opportunities/{opportunity_id}/monitor")
def monitor_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    result = opportunity_monitor.monitor_opportunity(db, opportunity_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return result


@router.get("/opportunities/{opportunity_id}/options")
def get_opportunity_options(opportunity_id: int, db: Session = Depends(get_db)):
    return option_space.evaluate_option_space(db, opportunity_id)


@router.post("/opportunities/{opportunity_id}/options/decision")
def create_option_decision(opportunity_id: int, db: Session = Depends(get_db)):
    return option_space.create_decision_from_options(db, opportunity_id)


@router.get("/opportunities/{opportunity_id}/evidence-graph", response_model=schemas.OpportunityEvidenceGraph)
def get_opportunity_evidence_graph(opportunity_id: int, db: Session = Depends(get_db)):
    graph = evidence_graph.trace_opportunity(db, opportunity_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return graph


@router.post("/opportunities/{opportunity_id}/claims", response_model=schemas.ClaimOut)
def create_opportunity_claim(
    opportunity_id: int,
    payload: schemas.ClaimCreate,
    db: Session = Depends(get_db),
):
    opportunity = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    claim, _ = evidence_graph.create_or_get_claim(
        db,
        payload.statement,
        epistemic_state=payload.epistemic_state,
        opportunity_id=opportunity_id,
        decision_id=payload.decision_id,
        experiment_id=payload.experiment_id,
        outcome_id=payload.outcome_id,
    )
    if payload.evidence_id is not None:
        evidence = db.query(models.Evidence).filter_by(id=payload.evidence_id).first()
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")
        evidence_graph.link_evidence(
            db,
            evidence,
            claim=claim,
            relation_type=payload.relation_type,
        )
    return claim


@router.post("/opportunities/{opportunity_id}/judge", response_model=schemas.JudgmentRunOut)
def judge_opportunity(
    opportunity_id: int,
    payload: schemas.JudgeRequest,
    db: Session = Depends(get_db),
):
    opportunity = db.query(models.Opportunity).filter_by(id=opportunity_id).first()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    judgments = multi_judge.run_judgments(
        db,
        question=payload.question,
        evidence_ids=payload.evidence_ids,
        opportunity_id=opportunity_id,
        claim_id=payload.claim_id,
    )
    comparison = multi_judge.compare_judgments(
        db,
        question=payload.question,
        judgment_ids=[judgment.id for judgment in judgments],
        evidence_ids=payload.evidence_ids,
        claim_id=payload.claim_id,
    )
    return {"judgments": judgments, "comparison": comparison}


@router.post("/experiments/proposed", response_model=schemas.ExperimentRead)
def create_proposed_experiment(payload: ExperimentProposalCreate, db: Session = Depends(get_db)):
    """Create a research-first Experiment without requiring an Opportunity row."""
    try:
        return experiment_service.create_proposed(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/authorize", response_model=schemas.ExperimentRead)
def authorize_experiment(experiment_id: int, payload: ExperimentAuthorize, db: Session = Depends(get_db)):
    """Approve or reject a research-first Experiment before execution can proceed."""
    try:
        return experiment_service.authorize_experiment(db, experiment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/execute", response_model=schemas.ExperimentRead)
def execute_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """Fail-closed: only an explicitly approved Experiment may be executed."""
    try:
        return experiment_service.execute_experiment(db, experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/outcome", response_model=schemas.ExperimentRead)
def record_experiment_outcome(experiment_id: int, payload: ExperimentOutcomeCreate, db: Session = Depends(get_db)):
    """Record a real rejection, interest, or payment outcome. Revenue is only valid for payment outcomes."""
    try:
        return experiment_service.record_outcome(db, experiment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/action", response_model=schemas.ExperimentActionRead)
def propose_experiment_action(experiment_id: int, db: Session = Depends(get_db)):
    try:
        return experiment_action_service.propose_action(db, experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/action/approve", response_model=schemas.ExperimentActionRead)
def approve_experiment_action(experiment_id: int, db: Session = Depends(get_db)):
    try:
        return experiment_action_service.approve_action(db, experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/action/execute", response_model=schemas.ExperimentActionRead)
def execute_experiment_action(experiment_id: int, db: Session = Depends(get_db)):
    try:
        return experiment_action_service.execute_action(db, experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments/{experiment_id}/action/outcome")
def record_experiment_action_outcome(
    experiment_id: int,
    payload: schemas.ExperimentActionOutcomeCreate,
    db: Session = Depends(get_db),
):
    try:
        return experiment_action_service.record_actual_response(
            db,
            experiment_id,
            **payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/experiments", response_model=schemas.ExperimentOut)
def create_experiment(payload: schemas.ExperimentCreate, db: Session = Depends(get_db)):
    """Log a real-world test/action taken against an opportunity, and what was learned."""
    opp = db.query(models.Opportunity).filter(models.Opportunity.id == payload.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    experiment = models.Experiment(
        opportunity_id=payload.opportunity_id,
        action=payload.action,
        result=payload.result,
        lesson=payload.lesson,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("/experiments", response_model=list[schemas.ExperimentOut])
def get_experiments(opportunity_id: Optional[int] = None, db: Session = Depends(get_db)):
    """List logged experiments, optionally filtered by opportunity."""
    query = db.query(models.Experiment)
    if opportunity_id is not None:
        query = query.filter(models.Experiment.opportunity_id == opportunity_id)
    return query.order_by(models.Experiment.created_at.desc()).all()


@router.post("/experiments/{experiment_id}/actual-outcome")
def record_actual_outcome(
    experiment_id: int, payload: ExperimentOutcomeBody, db: Session = Depends(get_db)
):
    try:
        return outcome_learning.record_experiment_outcome(
            db,
            experiment_id,
            actual=payload.actual,
            success=payload.success,
            source=payload.source,
            actual_value=payload.actual_value,
            unit=payload.unit,
            lesson=payload.lesson,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
