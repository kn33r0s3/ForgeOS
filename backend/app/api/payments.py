from __future__ import annotations
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, AnyHttpUrl

from app.services import nepal_payments

router = APIRouter(prefix="/payments", tags=["payments"])

class EsewaCheckoutRequest(BaseModel):
    amount_npr: Decimal = Field(gt=0, le=100_000_000)
    transaction_uuid: str = Field(min_length=4, max_length=80, pattern=r"^[A-Za-z0-9-]+$")
    success_url: AnyHttpUrl
    failure_url: AnyHttpUrl

class EsewaLookupRequest(BaseModel):
    amount_npr: Decimal = Field(gt=0, le=100_000_000)
    transaction_uuid: str = Field(min_length=4, max_length=80, pattern=r"^[A-Za-z0-9-]+$")

class KhaltiInitiateRequest(BaseModel):
    amount_npr: Decimal = Field(gt=0, le=100_000_000)
    purchase_order_id: str = Field(min_length=4, max_length=80)
    purchase_order_name: str = Field(min_length=1, max_length=200)
    return_url: AnyHttpUrl
    website_url: AnyHttpUrl

class KhaltiLookupRequest(BaseModel):
    pidx: str = Field(min_length=4, max_length=200)


def _provider_error(exc: Exception) -> HTTPException:
    message = str(exc)
    status = 503 if isinstance(exc, (RuntimeError, OSError)) else 422
    return HTTPException(status_code=status, detail=message[:500])

@router.post("/esewa/checkout")
def esewa_checkout(body: EsewaCheckoutRequest):
    try:
        return nepal_payments.esewa_checkout(**body.model_dump())
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.post("/esewa/lookup")
def esewa_lookup(body: EsewaLookupRequest):
    try:
        result = nepal_payments.esewa_lookup(**body.model_dump())
        return {"provider": "esewa", "verified": result.get("status") == "COMPLETE", "response": result}
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.get("/esewa/callback")
def esewa_callback(data: str = Query(min_length=20)):
    try:
        payload = nepal_payments.verify_esewa_response(data)
        return {"provider": "esewa", "verified": payload.get("status") == "COMPLETE", "response": payload}
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.post("/khalti/initiate")
def khalti_initiate(body: KhaltiInitiateRequest):
    try:
        return {"provider": "khalti", **nepal_payments.khalti_initiate(**body.model_dump())}
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.post("/khalti/lookup")
def khalti_lookup(body: KhaltiLookupRequest):
    try:
        result = nepal_payments.khalti_lookup(**body.model_dump())
        return {"provider": "khalti", "verified": result.get("status") == "Completed", "response": result}
    except Exception as exc:
        raise _provider_error(exc) from exc
