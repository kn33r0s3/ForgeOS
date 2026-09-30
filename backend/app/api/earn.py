"""Nepal-first earning workspace API.

The workspace key is a client-generated opaque token, hashed before storage. It
is a lightweight local-sync boundary, not full authentication. No exact age,
contact identity, OTP, PIN, citizenship number, or payment credential is stored.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

router = APIRouter(prefix="/earn", tags=["earn"])
OfferStatus = Literal["draft", "customer_confirmed", "paid", "failed", "abandoned"]

DEFAULT_NEXT_ACTIONS = {
    "local-service": [
        "Write a one-sentence offer with price in NPR",
        "Message or visit 1–3 real people who might need it",
        "Ask if they would pay that price for a first small job",
        "If yes, deliver a tiny version and request payment",
    ],
    "digital": [
        "Make one small sample",
        "Send it to one real person or business",
        "Ask for a paid mini-job at a clear NPR price",
        "Deliver and collect payment only after agreement",
    ],
    "commerce": [
        "List the exact item and your NPR price",
        "Ask three people if they would pre-order",
        "Only buy stock after at least one real commitment",
        "Record payment only when money is received",
    ],
    "agent": [
        "Name one producer and one possible buyer",
        "Confirm both sides are interested in principle",
        "Agree a clear commission or fee in NPR",
        "Record the outcome only after a real transaction",
    ],
    "skill-work": [
        "Prepare a short proof of skill",
        "Contact one real client or local business",
        "Ask for a small paid trial or a clear no",
        "Log the real response",
    ],
}


class ChecklistItem(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    completed: bool = False


class EarningOfferCreate(BaseModel):
    workspace_key: str = Field(min_length=16, max_length=200)
    pathway: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    skill: str = Field(min_length=1, max_length=240)
    customer: str = Field(min_length=1, max_length=240)
    price_npr: int | None = Field(default=None, ge=0, le=100_000_000)
    age_band: Literal["14_17", "18_plus"]
    next_actions: list[ChecklistItem] | None = Field(default=None, max_length=12)


class EarningOfferStatusUpdate(BaseModel):
    workspace_key: str = Field(min_length=16, max_length=200)
    status: OfferStatus
    outcome_note: str | None = Field(default=None, max_length=2000)


class EarningOfferChecklistUpdate(BaseModel):
    workspace_key: str = Field(min_length=16, max_length=200)
    next_actions: list[ChecklistItem] = Field(min_length=1, max_length=12)


class EarningOfferOut(BaseModel):
    id: int
    pathway: str
    title: str
    skill: str
    customer: str
    price_npr: int | None
    age_band: str
    status: str
    next_actions: list[ChecklistItem]
    outcome_note: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _get_owned(db: Session, offer_id: int, workspace_key: str) -> models.EarningOffer:
    row = db.query(models.EarningOffer).filter_by(
        id=offer_id, workspace_key_hash=_hash_key(workspace_key)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="earning offer not found")
    return row


def _serialize_actions(items: list[ChecklistItem]) -> str:
    return json.dumps([item.model_dump() for item in items], ensure_ascii=False)


def _default_actions(pathway: str) -> list[ChecklistItem]:
    values = DEFAULT_NEXT_ACTIONS.get(pathway, ["Contact one real customer and record the response"])
    return [ChecklistItem(text=value) for value in values]


def _out(row: models.EarningOffer) -> EarningOfferOut:
    try:
        raw = json.loads(row.next_actions_json or "[]")
        actions = [ChecklistItem.model_validate(item) for item in raw]
    except (TypeError, ValueError, json.JSONDecodeError):
        actions = _default_actions(row.pathway)
    if not actions:
        actions = _default_actions(row.pathway)
    return EarningOfferOut(
        id=row.id,
        pathway=row.pathway,
        title=row.title,
        skill=row.skill,
        customer=row.customer,
        price_npr=row.price_npr,
        age_band=row.age_band,
        status=row.status,
        next_actions=actions,
        outcome_note=row.outcome_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/offers", response_model=list[EarningOfferOut])
def list_offers(
    workspace_key: str = Query(min_length=16, max_length=200),
    db: Session = Depends(get_db),
):
    rows = (db.query(models.EarningOffer)
            .filter_by(workspace_key_hash=_hash_key(workspace_key))
            .order_by(models.EarningOffer.created_at.desc()).all())
    return [_out(row) for row in rows]


@router.post("/offers", response_model=EarningOfferOut, status_code=201)
def create_offer(body: EarningOfferCreate, db: Session = Depends(get_db)):
    actions = body.next_actions or _default_actions(body.pathway)
    row = models.EarningOffer(
        workspace_key_hash=_hash_key(body.workspace_key),
        pathway=body.pathway.strip(),
        title=body.title.strip(),
        skill=body.skill.strip(),
        customer=body.customer.strip(),
        price_npr=body.price_npr,
        age_band=body.age_band,
        status="draft",
        next_actions_json=_serialize_actions(actions),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.patch("/offers/{offer_id}/status", response_model=EarningOfferOut)
def update_offer_status(
    offer_id: int,
    body: EarningOfferStatusUpdate,
    db: Session = Depends(get_db),
):
    row = _get_owned(db, offer_id, body.workspace_key)
    allowed = {
        "draft": {"customer_confirmed", "failed", "abandoned"},
        "customer_confirmed": {"paid", "failed", "abandoned"},
        "paid": set(),
        "failed": set(),
        "abandoned": set(),
    }
    if body.status not in allowed.get(row.status, set()):
        raise HTTPException(status_code=409, detail=f"cannot move {row.status} to {body.status}")
    note = (body.outcome_note or "").strip()
    if body.status in {"paid", "failed", "abandoned"} and len(note) < 3:
        raise HTTPException(status_code=422, detail="record a brief honest outcome before closing an offer")
    row.status = body.status
    if note:
        row.outcome_note = note
    db.commit()
    db.refresh(row)
    if body.status in {"paid", "failed", "abandoned"}:
        from app.services import action_engine
        stated_price = float(row.price_npr) if row.price_npr is not None else None
        action_engine.record_domain_event(
            db,
            idempotency_key=f"earning-offer:{row.id}:{body.status}",
            source="earning_offer",
            success=body.status == "paid",
            actual_value=stated_price if body.status == "paid" else None,
            unit="NPR" if body.status == "paid" and stated_price is not None else None,
            qualitative_result=(
                f"Earning offer {row.id} closed as {body.status}. "
                f"Stated price NPR {row.price_npr}. Note: {note}"
            ),
        )
    return _out(row)


@router.put("/offers/{offer_id}/checklist", response_model=EarningOfferOut)
def update_offer_checklist(
    offer_id: int,
    body: EarningOfferChecklistUpdate,
    db: Session = Depends(get_db),
):
    row = _get_owned(db, offer_id, body.workspace_key)
    row.next_actions_json = _serialize_actions(body.next_actions)
    db.commit()
    db.refresh(row)
    return _out(row)
