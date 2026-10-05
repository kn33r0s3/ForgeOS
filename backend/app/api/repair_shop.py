from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import require_owner_api_key
from app.services import repair_shop

router = APIRouter(prefix="/repair-shop", tags=["repair-shop"])


def _error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 404 if "not found" in message.lower() else 409
    return HTTPException(status_code=status, detail=message)


def _detail(db: Session, work_item_id: int) -> dict:
    detail = repair_shop.get_work_item_detail(db, work_item_id)
    return {
        "work_item": detail["work_item"],
        "customer": detail["customer"],
        "events": detail["events"],
        "communications": detail["communications"],
        "evidence": detail["evidence"],
        "decision": detail["decision"].__dict__ if detail["decision"] else None,
        "experiment": detail["experiment"].__dict__ if detail["experiment"] else None,
        "outcomes": [row.__dict__ for row in detail["outcomes"]],
        "learning_events": [row.__dict__ for row in detail["learning_events"]],
    }


@router.post("/work-items", response_model=schemas.RepairWorkItemOut, status_code=201)
def create_work_item(body: schemas.RepairWorkItemCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return repair_shop.create_work_item(db, **body.model_dump())
    except ValueError as exc:
        raise _error(exc) from exc


@router.get("/work-items", response_model=list[schemas.RepairWorkItemOut])
def list_work_items(request: Request, data_scope: schemas.Literal["REAL", "SANDBOX"] = "SANDBOX", db: Session = Depends(get_db)):
    require_owner_api_key(request)
    return repair_shop.list_work_items(db, data_scope=data_scope)


@router.get("/work-items/{work_item_id}", response_model=schemas.RepairWorkItemDetail)
def get_work_item(work_item_id: int, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return _detail(db, work_item_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/work-items/{work_item_id}/evidence", response_model=schemas.EvidenceOut, status_code=201)
def attach_evidence(work_item_id: int, body: schemas.RepairEvidenceCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return repair_shop.attach_evidence(db, work_item_id, **body.model_dump())
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/work-items/{work_item_id}/triage")
def create_triage(work_item_id: int, body: schemas.RepairTriageCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        result = repair_shop.create_triage(db, work_item_id, **body.model_dump())
        return {"decision": result["decision"].__dict__, "experiment": result["experiment"].__dict__}
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/work-items/{work_item_id}/communications", response_model=schemas.RepairCommunicationOut, status_code=201)
def propose_status(work_item_id: int, body: schemas.CustomerStatusCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return repair_shop.propose_customer_status(db, work_item_id, **body.model_dump())
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/communications/{communication_id}/approve", response_model=schemas.RepairCommunicationOut)
def approve_status(communication_id: int, request: Request, body: schemas.RepairScope = schemas.RepairScope(), db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return repair_shop.approve_customer_status(db, communication_id, actor="operator")
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/communications/{communication_id}/response", response_model=schemas.RepairCommunicationOut)
def record_response(communication_id: int, body: schemas.CustomerResponseCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        return repair_shop.record_customer_response(db, communication_id, **body.model_dump())
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/work-items/{work_item_id}/payment", status_code=201)
def record_payment(work_item_id: int, body: schemas.RepairPaymentCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        outcome = repair_shop.record_verified_payment(db, work_item_id, **body.model_dump())
        return {"outcome": outcome.__dict__, "truth": "ACTUAL_REVENUE only after verified provider evidence"}
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/work-items/{work_item_id}/outcome", status_code=201)
def record_outcome(work_item_id: int, body: schemas.RepairOutcomeCreate, request: Request, db: Session = Depends(get_db)):
    require_owner_api_key(request)
    try:
        outcome, learning = repair_shop.record_work_outcome(db, work_item_id, **body.model_dump())
        return {"outcome": outcome.__dict__, "learning_event": learning.__dict__}
    except ValueError as exc:
        raise _error(exc) from exc
