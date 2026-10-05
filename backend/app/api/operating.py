"""Operating Model v2 API (owner-guarded)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, security
from app.database import get_db
from app.services import operating_model

router = APIRouter(prefix="/operating", tags=["operating"])


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)


class StatusIn(BaseModel):
    status: str


class EvidenceLinkIn(BaseModel):
    evidence_ref: str


class OrientationIn(BaseModel):
    observer_who: str
    observer_from_where: str
    means: str
    local_knowledge: str
    beliefs: list  # [[belief_text, assumption_id | null], ...]


class DiagnosisNodeIn(BaseModel):
    node_text: str
    evidence: Optional[str] = None
    binding_status: str = "not_binding_now"


class DiagnosisIn(BaseModel):
    situation: str
    nodes: list[DiagnosisNodeIn]


class ProbeIn(BaseModel):
    assumption_id: int
    probe_type: str
    affordable_loss: str
    kill_criterion: str


class ProbeDecisionIn(BaseModel):
    decision: str
    result: Optional[str] = None


class CapabilityIn(BaseModel):
    name: str
    description: Optional[str] = None
    event_id: int
    evidence_id: int


# --- Assumptions ---


@router.get("/assumptions")
def list_assumptions(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    import json

    return [
        {
            "id": a.id,
            "statement": a.statement,
            "status": a.status,
            "deal_killer": a.deal_killer,
            "cost_to_test": a.cost_to_test,
            "cheapest_test": a.cheapest_test,
            "evidence_links": json.loads(a.evidence_links or "[]"),
            "milestone": a.milestone,
            "source_note": a.source_note,
        }
        for a in operating_model.rank_assumptions(db)
    ]


@router.post("/assumptions/seed")
def seed_assumptions(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    created = operating_model.seed_assumptions(db)
    return {"seeded": len(created)}


@router.post("/assumptions/{assumption_id}/status")
def set_status(assumption_id: int, payload: StatusIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        a = operating_model.set_assumption_status(db, assumption_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": a.id, "status": a.status}


@router.post("/assumptions/{assumption_id}/evidence")
def add_evidence(assumption_id: int, payload: EvidenceLinkIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        a = operating_model.add_evidence_link(db, assumption_id, payload.evidence_ref)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": a.id}


# --- Orientation ---


@router.get("/orientations")
def list_orientations(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    orientations = db.query(models.Orientation).order_by(models.Orientation.version.desc()).all()
    out = []
    for o in orientations:
        beliefs = (
            db.query(models.OrientationBelief)
            .filter(models.OrientationBelief.orientation_id == o.id)
            .all()
        )
        out.append(
            {
                "id": o.id,
                "version": o.version,
                "observer_who": o.observer_who,
                "observer_from_where": o.observer_from_where,
                "means": o.means,
                "local_knowledge": o.local_knowledge,
                "created_at": o.created_at,
                "beliefs": [
                    {"belief_text": b.belief_text, "assumption_id": b.assumption_id}
                    for b in beliefs
                ],
            }
        )
    return out


@router.post("/orientations")
def create_orientation(payload: OrientationIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        o = operating_model.record_orientation(
            db,
            observer_who=payload.observer_who,
            observer_from_where=payload.observer_from_where,
            means=payload.means,
            local_knowledge=payload.local_knowledge,
            beliefs=[(b[0], b[1] if len(b) > 1 else None) for b in payload.beliefs],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": o.id, "version": o.version}


# --- Constraint diagnosis ---


@router.get("/diagnoses")
def list_diagnoses(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    diagnoses = db.query(models.ConstraintDiagnosis).order_by(models.ConstraintDiagnosis.id.desc()).all()
    out = []
    for d in diagnoses:
        nodes = (
            db.query(models.DiagnosisNode)
            .filter(models.DiagnosisNode.diagnosis_id == d.id)
            .all()
        )
        out.append(
            {
                "id": d.id,
                "situation": d.situation,
                "created_at": d.created_at,
                "nodes": [
                    {"node_text": n.node_text, "evidence": n.evidence, "binding_status": n.binding_status}
                    for n in nodes
                ],
            }
        )
    return out


@router.post("/diagnoses")
def create_diagnosis(payload: DiagnosisIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        d = operating_model.diagnose_constraints(
            db,
            situation=payload.situation,
            nodes=[(n.node_text, n.evidence, n.binding_status) for n in payload.nodes],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": d.id}


# --- Probes ---


@router.get("/probes")
def list_probes(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    probes = db.query(models.Probe).order_by(models.Probe.id.desc()).all()
    return [
        {
            "id": p.id,
            "assumption_id": p.assumption_id,
            "assumption": p.assumption.statement if p.assumption else None,
            "probe_type": p.probe_type,
            "affordable_loss": p.affordable_loss,
            "kill_criterion": p.kill_criterion,
            "started_at": p.started_at,
            "ended_at": p.ended_at,
            "result": p.result,
            "decision": p.decision,
        }
        for p in probes
    ]


@router.post("/probes")
def create_probe(payload: ProbeIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        p = operating_model.record_probe(
            db,
            assumption_id=payload.assumption_id,
            probe_type=payload.probe_type,
            affordable_loss=payload.affordable_loss,
            kill_criterion=payload.kill_criterion,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": p.id}


@router.post("/probes/{probe_id}/decide")
def decide_probe(probe_id: int, payload: ProbeDecisionIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        p = operating_model.decide_probe(db, probe_id, payload.decision, payload.result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": p.id, "decision": p.decision}


# --- Capabilities ---


@router.get("/capabilities")
def list_capabilities(request: Request, db: Session = Depends(get_db)):
    _owner(request)
    caps = db.query(models.Capability).order_by(models.Capability.id.asc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "event_id": c.event_id,
            "evidence_id": c.evidence_id,
            "verified_at": c.verified_at,
        }
        for c in caps
    ]


@router.post("/capabilities")
def create_capability(payload: CapabilityIn, request: Request, db: Session = Depends(get_db)):
    _owner(request)
    try:
        c = operating_model.record_capability(
            db,
            name=payload.name,
            event_id=payload.event_id,
            evidence_id=payload.evidence_id,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": c.id}
