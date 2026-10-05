"""Operating Model v3 API (owner-guarded)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, security
from app.database import get_db
from app.services import operating_v3

router = APIRouter(prefix="/opv3", tags=["operating-v3"])


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)


class BetIn(BaseModel):
    claim: str
    test: str
    kill_criterion: str
    decision_rule: str
    affordable_loss_time: Optional[str] = None
    affordable_loss_money: Optional[str] = None
    affordable_loss_trust: Optional[str] = None
    deadline: Optional[datetime] = None
    assumption_ids: Optional[list[int]] = None


class BetDecisionIn(BaseModel):
    decision: str
    notes: Optional[str] = None


class ProofIn(BaseModel):
    level: int
    is_agent_written: bool = False
    is_secondhand: bool = False


class ContributorIn(BaseModel):
    name: str
    notes: Optional[str] = None


class ObservationIn(BaseModel):
    claim: str
    content: str


class HorizonIn(BaseModel):
    name: str
    reason: str


class GateIn(BaseModel):
    day: int
    title: str
    kill_criterion: Optional[str] = None


class GateResultIn(BaseModel):
    result: str


class ReportIn(BaseModel):
    deployed_sha: Optional[str] = None
    fetched_content: Optional[str] = None
    test_counts: Optional[str] = None


# --- Bets ---


@router.get("/bets")
def list_bets(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    return [
        {
            "id": b.id,
            "claim": b.claim,
            "test": b.test,
            "status": b.status,
            "deadline": b.deadline,
            "kill_criterion": b.kill_criterion,
            "decision_rule": b.decision_rule,
            "affordable_loss": {
                "time": b.affordable_loss_time,
                "money": b.affordable_loss_money,
                "trust": b.affordable_loss_trust,
            },
            "assumption_ids": json.loads(b.assumption_ids or "[]"),
        }
        for b in db.query(models.Bet).order_by(models.Bet.id.desc()).all()
    ]


@router.post("/bets")
def create_bet(payload: BetIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        b = operating_v3.create_bet(
            db,
            claim=payload.claim,
            test=payload.test,
            kill_criterion=payload.kill_criterion,
            decision_rule=payload.decision_rule,
            affordable_loss_time=payload.affordable_loss_time,
            affordable_loss_money=payload.affordable_loss_money,
            affordable_loss_trust=payload.affordable_loss_trust,
            deadline=payload.deadline,
            assumption_ids=payload.assumption_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": b.id, "status": b.status}


@router.post("/bets/{bet_id}/decide")
def decide_bet(bet_id: int, payload: BetDecisionIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        b = operating_v3.decide_bet(db, bet_id, payload.decision, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": b.id, "status": b.status}


@router.get("/bet-views")
def bet_views(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return operating_v3.bet_views(db)


# --- Proof ladder ---


@router.post("/evidence/{evidence_id}/proof")
def set_proof(evidence_id: int, payload: ProofIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        ev = operating_v3.set_proof_level(
            db, evidence_id, payload.level, payload.is_agent_written, payload.is_secondhand
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": ev.id, "proof_level": ev.proof_level, "capped": ev.proof_capped_reason}


@router.get("/proof-violations")
def proof_violations(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return operating_v3.flag_proof_violations(db)


# --- Pulse ---


@router.get("/pulse")
def pulse(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return operating_v3.pulse_scoreboard(db)


@router.post("/build-check")
def build_check(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        operating_v3.check_build_allowed(db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"allowed": True}


@router.post("/report-check")
def report_check(payload: ReportIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        operating_v3.validate_report(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"valid": True}


# --- Sensor circle ---


@router.get("/contributors")
def list_contributors(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return [
        {"id": c.id, "name": c.name, "consent_given": c.consent_given, "consent_at": c.consent_at}
        for c in db.query(models.SensorContributor).all()
    ]


@router.post("/contributors")
def add_contributor(payload: ContributorIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    c = operating_v3.add_contributor(db, payload.name, payload.notes)
    return {"id": c.id}


@router.post("/contributors/{contributor_id}/consent")
def record_consent(contributor_id: int, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        c = operating_v3.record_consent(db, contributor_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": c.id, "consent_given": c.consent_given}


@router.post("/contributors/{contributor_id}/observations")
def sensor_observation(contributor_id: int, payload: ObservationIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        ev = operating_v3.record_sensor_observation(db, contributor_id, payload.claim, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": ev.id, "proof_level": ev.proof_level}


# --- Horizon ---


@router.get("/horizon")
def list_horizon(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return [
        {"id": h.id, "name": h.name, "reason_parked": h.reason_parked, "unparked_at": h.unparked_at}
        for h in db.query(models.HorizonDomain).all()
    ]


@router.post("/horizon")
def park(payload: HorizonIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        h = operating_v3.park_domain(db, payload.name, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": h.id}


@router.post("/horizon/{domain_id}/unpark")
def unpark(domain_id: int, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        h = operating_v3.unpark_domain(db, domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": h.id}


# --- Gates ---


@router.get("/gates")
def list_gates(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return [
        {
            "day": g.day,
            "title": g.title,
            "kill_criterion": g.kill_criterion,
            "result": g.result,
            "decided_at": g.decided_at,
        }
        for g in db.query(models.Gate).order_by(models.Gate.day.asc()).all()
    ]


@router.post("/gates")
def upsert_gate(payload: GateIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        g = operating_v3.upsert_gate(db, payload.day, payload.title, payload.kill_criterion)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"day": g.day}


@router.post("/gates/{day}/result")
def gate_result(day: int, payload: GateResultIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        g = operating_v3.record_gate_result(db, day, payload.result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"day": g.day, "result": g.result}
