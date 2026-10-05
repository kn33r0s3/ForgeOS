"""Operating Model v4 API (owner-guarded). Scoreboard is GET-only."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, security
from app.database import get_db
from app.services import operating_v4

router = APIRouter(prefix="/opv4", tags=["operating-v4"])


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)


class BetIn(BaseModel):
    claim: str
    constraint: str
    test: str
    kill_criterion: str
    decision_rule: str
    skeptic_case: str
    owner_time: Optional[str] = None
    attention: Optional[str] = None
    energy: Optional[str] = None
    money_at_risk: Optional[str] = None
    trust_at_risk: Optional[str] = None
    deadline: Optional[datetime] = None
    assumption_ids: Optional[list[int]] = None


class BetDecisionIn(BaseModel):
    decision: str
    notes: Optional[str] = None


class ProofIn(BaseModel):
    level: int
    source_type: Optional[str] = None
    verifier: Optional[str] = None


class VerificationIn(BaseModel):
    deployed_sha: str
    fetched_content: str
    test_counts: str
    passed: bool
    source: str = "ci"


class FrontierIn(BaseModel):
    month: str
    alternative_frontier: str
    comparison: str
    verdict: Optional[str] = None


class AssumptionStatusIn(BaseModel):
    status: str


class EvidenceLinkIn(BaseModel):
    evidence_ref: str


class BeliefIn(BaseModel):
    belief_text: str
    assumption_id: Optional[int] = None


class OrientationIn(BaseModel):
    observer_who: str
    observer_from_where: str
    means: str
    local_knowledge: str
    beliefs: list[BeliefIn] = []


class DiagnosisNodeIn(BaseModel):
    node_text: str
    evidence: str = ""
    binding_status: str


class DiagnosisIn(BaseModel):
    situation: str
    nodes: list[DiagnosisNodeIn]


@router.get("/bets")
def list_bets(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    bets = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == "bet")
        .order_by(models.SubstrateEntity.id.desc())
        .all()
    )
    return [
        {"id": b.id, "display_name": b.display_name, **json.loads(b.attributes or "{}")}
        for b in bets
    ]


@router.post("/bets")
def create_bet(payload: BetIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        b = operating_v4.create_bet(
            db,
            claim=payload.claim,
            constraint=payload.constraint,
            test=payload.test,
            kill_criterion=payload.kill_criterion,
            decision_rule=payload.decision_rule,
            skeptic_case=payload.skeptic_case,
            owner_time=payload.owner_time,
            attention=payload.attention,
            energy=payload.energy,
            money_at_risk=payload.money_at_risk,
            trust_at_risk=payload.trust_at_risk,
            deadline=payload.deadline,
            assumption_ids=payload.assumption_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": b.id}


@router.post("/bets/{bet_id}/decide")
def decide_bet(bet_id: int, payload: BetDecisionIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        operating_v4.decide_bet(db, bet_id, payload.decision, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": bet_id, "decision": payload.decision}


@router.post("/evidence/{evidence_id}/proof")
def set_proof(evidence_id: int, payload: ProofIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        ev = operating_v4.set_proof_level(
            db, evidence_id, payload.level, payload.source_type, payload.verifier
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": ev.id, "proof_level": ev.proof_level}


@router.get("/scoreboard")
def get_scoreboard(request: Request, db: Session = Depends(get_db)):
    """Read-only. Agents read; they do not write."""
    _owner(request)
    return operating_v4.scoreboard(db)


@router.post("/verifications")
def record_verification(payload: VerificationIn, request: Request, db: Session = Depends(get_db)):
    """Append-only. No update or delete endpoint exists."""
    _owner(request)
    try:
        rec = operating_v4.record_verification(
            db, payload.deployed_sha, payload.fetched_content,
            payload.test_counts, payload.passed, payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": rec.id}


@router.get("/verifications")
def list_verifications(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return [
        {
            "id": r.id,
            "deployed_sha": r.deployed_sha,
            "test_counts": r.test_counts,
            "passed": r.passed,
            "recorded_at": r.recorded_at,
            "source": r.source,
        }
        for r in db.query(models.DeployVerification).order_by(models.DeployVerification.id.desc()).limit(20).all()
    ]


@router.post("/dormancy/enter")
def enter_dormancy(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    s = operating_v4.enter_dormancy(db)
    return {"dormant": s.is_dormant}


@router.post("/dormancy/exit")
def exit_dormancy(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        s = operating_v4.exit_dormancy(db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"dormant": s.is_dormant}


@router.post("/frontier")
def record_frontier(payload: FrontierIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        fc = operating_v4.record_frontier_challenge(
            db, payload.month, payload.alternative_frontier, payload.comparison, payload.verdict
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": fc.id, "month": fc.month}


@router.get("/frontier")
def get_frontier(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    return {
        "frontier": operating_v4.FROZEN_FRONTIER,
        "frozen_from": operating_v4.FRONTIER_START,
        "day_90": operating_v4.FRONTIER_DAY_90,
    }


@router.post("/gates/seed")
def seed_gates(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    created = operating_v4.seed_frontier_gates(db)
    return {"seeded": len(created)}


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


@router.get("/assumptions")
def list_assumptions(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    return [
        {"id": a.id, **json.loads(a.attributes or "{}")}
        for a in operating_v4.rank_assumptions(db)
    ]


@router.post("/assumptions/seed")
def seed_assumptions(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    created = operating_v4.seed_assumptions(db)
    return {"seeded": len(created)}


@router.post("/assumptions/{assumption_id}/status")
def set_assumption_status(
    assumption_id: int, payload: AssumptionStatusIn,
    request: Request, db: Session = Depends(get_db),
):
    _owner(request)
    import json

    try:
        a = operating_v4.set_assumption_status(db, assumption_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": a.id, **json.loads(a.attributes or "{}")}


@router.post("/assumptions/{assumption_id}/evidence-links")
def add_evidence_link(
    assumption_id: int, payload: EvidenceLinkIn,
    request: Request, db: Session = Depends(get_db),
):
    _owner(request)
    import json

    try:
        a = operating_v4.add_evidence_link(db, assumption_id, payload.evidence_ref)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": a.id, **json.loads(a.attributes or "{}")}


@router.get("/orientations")
def list_orientations(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    return [
        {"id": o.id, **json.loads(o.attributes or "{}")}
        for o in operating_v4.list_orientations(db)
    ]


@router.post("/orientations")
def create_orientation(
    payload: OrientationIn, request: Request, db: Session = Depends(get_db)
):
    _owner(request)
    import json

    try:
        o = operating_v4.record_orientation(
            db,
            observer_who=payload.observer_who,
            observer_from_where=payload.observer_from_where,
            means=payload.means,
            local_knowledge=payload.local_knowledge,
            beliefs=[b.model_dump() for b in payload.beliefs],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": o.id, **json.loads(o.attributes or "{}")}


@router.get("/diagnoses")
def list_diagnoses(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    return [
        {"id": d.id, **json.loads(d.attributes or "{}")}
        for d in operating_v4.list_diagnoses(db)
    ]


@router.post("/diagnoses")
def create_diagnosis(
    payload: DiagnosisIn, request: Request, db: Session = Depends(get_db)
):
    _owner(request)
    import json

    try:
        d = operating_v4.diagnose_constraints(
            db,
            situation=payload.situation,
            nodes=[n.model_dump() for n in payload.nodes],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id, **json.loads(d.attributes or "{}")}
