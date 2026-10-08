"""Canonical human-validation API. Reads never prepare or execute work."""
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app import models, security
from app.database import get_db
from app.services import orchestrator, execution_engine, decision_engine

router = APIRouter(prefix="/orchestrate", tags=["orchestrate"])
Scope = Literal["REAL", "SANDBOX"]


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)

class ContactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    identifier: Optional[str] = None
    segment: Optional[str] = None
    stage: Literal["lead", "contacted", "interested", "paid_customer", "churned"] = "lead"
    event_type: Optional[str] = None
    notes: Optional[str] = None

class OutcomeBody(BaseModel):
    actual: str = Field(..., min_length=1)
    success: Optional[bool] = None
    actual_value: Optional[float] = Field(None, ge=0, allow_inf_nan=False)
    unit: Optional[str] = None
    source: str = Field("human_interview", min_length=1)
    conversions: Optional[int] = Field(None, ge=0)
    contacts: Optional[list[ContactPayload]] = None
    data_scope: Scope = "REAL"

class ProductGateBody(BaseModel):
    name: Optional[str] = None
    y_confirm: int = Field(orchestrator.DEFAULT_Y_CONFIRM_PROBLEM, ge=1, le=100)
    z_willing: int = Field(orchestrator.DEFAULT_Z_WILLING_TO_PAY, ge=1, le=100)
    data_scope: Scope = "REAL"


def _experiment(db, oid, scope):
    e = db.query(models.Experiment).filter_by(opportunity_id=oid, action_type="customer_interview", data_scope=scope).order_by(models.Experiment.id.desc()).first()
    if not e:
        raise HTTPException(404, "No validation experiment in selected scope")
    return e


def _flow(db, oid, scope):
    if not db.get(models.Opportunity, oid):
        raise HTTPException(404, "Opportunity not found")
    return orchestrator.promote_opportunity(db, oid, create_missing=False, data_scope=scope)

@router.get("/flow")
def get_flow(request: Request, limit: int = Query(10, ge=1, le=50), data_scope: Scope = "REAL", db: Session = Depends(get_db)):
    _owner(request)
    return {"flow": [_flow(db, o.id, data_scope) for o in orchestrator.ranked_opportunities(db, limit)], "pipeline": orchestrator._flow_snapshot(db)}

@router.get("/flow/{opportunity_id}")
def get_flow_for_opportunity(request: Request, opportunity_id: int, data_scope: Scope = "REAL", db: Session = Depends(get_db)):
    _owner(request)
    return _flow(db, opportunity_id, data_scope)

@router.post("/{opportunity_id}/advance")
def advance_opportunity(request: Request, opportunity_id: int, data_scope: Scope = "REAL", x_interviews: int = Query(10, ge=1, le=100), y_confirm: int = Query(5, ge=1, le=100), z_willing: int = Query(3, ge=1, le=100), price_assumption: Optional[float] = Query(None, ge=0), time_window: str = Query(orchestrator.DEFAULT_TIME_WINDOW, min_length=1, max_length=100), db: Session = Depends(get_db)):
    _owner(request)
    if not db.get(models.Opportunity, opportunity_id):
        raise HTTPException(404, "Opportunity not found")
    if y_confirm > x_interviews or z_willing > x_interviews:
        raise HTTPException(422, "Thresholds cannot exceed interview target")
    return orchestrator.promote_opportunity(db, opportunity_id, data_scope=data_scope, x_interviews=x_interviews, y_confirm=y_confirm, z_willing=z_willing, price_assumption=price_assumption, time_window=time_window)

@router.post("/{opportunity_id}/approve")
def approve_opportunity_action(request: Request, opportunity_id: int, data_scope: Scope = "REAL", db: Session = Depends(get_db)):
    _owner(request)
    e = _experiment(db, opportunity_id, data_scope)
    if e.status not in ("planned", "ready", "in_progress") or not execution_engine.approve_action(db, e.id):
        raise HTTPException(409, "Experiment cannot be approved")
    return _flow(db, opportunity_id, data_scope)

@router.post("/{opportunity_id}/execute")
def mark_human_task_executed(request: Request, opportunity_id: int, data_scope: Scope = "REAL", db: Session = Depends(get_db)):
    _owner(request)
    e = _experiment(db, opportunity_id, data_scope)
    if not execution_engine.mark_human_action_executed(db, e.id):
        raise HTTPException(409, "Approve the human task first; terminal tasks cannot execute")
    return _flow(db, opportunity_id, data_scope)

@router.post("/{opportunity_id}/reject")
def reject_human_task(request: Request, opportunity_id: int, data_scope: Scope = "REAL", db: Session = Depends(get_db)):
    _owner(request)
    e = _experiment(db, opportunity_id, data_scope)
    if e.status == "completed":
        raise HTTPException(409, "Completed history cannot be rejected")
    e.status = "abandoned"
    e.completed_at = orchestrator.utcnow()
    e.result = "Rejected by owner; no business outcome recorded."
    db.commit()
    return _flow(db, opportunity_id, data_scope)

@router.post("/{opportunity_id}/outcome")
def record_opportunity_outcome(request: Request, opportunity_id: int, body: OutcomeBody, db: Session = Depends(get_db)):
    _owner(request)
    e = _experiment(db, opportunity_id, body.data_scope)
    try:
        payload = body.model_dump()
        orchestrator.record_demand_outcome(db, e.id, **payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return _flow(db, opportunity_id, body.data_scope)

@router.post("/{opportunity_id}/product")
def gate_opportunity_to_product(request: Request, opportunity_id: int, body: Optional[ProductGateBody] = None, db: Session = Depends(get_db)):
    _owner(request)
    return orchestrator.create_product_for_validated(db, opportunity_id, **(body or ProductGateBody()).model_dump())

@router.post("/{opportunity_id}/next-decision")
def next_decision(request: Request, opportunity_id: int, data_scope: Scope = "REAL", db: Session = Depends(get_db)):
    _owner(request)
    if not db.get(models.Opportunity, opportunity_id):
        raise HTTPException(404, "Opportunity not found")
    return decision_engine.suggest_next_experiment_decision(db, opportunity_id, data_scope=data_scope)
