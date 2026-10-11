from __future__ import annotations
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, AnyHttpUrl

from app.config import settings
from app.security import require_owner_api_key
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


@router.get("/status")
def payment_configuration_status(request: Request):
    """Return credential-presence flags only; never call a payment provider here."""
    require_owner_api_key(request)
    esewa_merchant_code_configured = bool(settings.ESEWA_MERCHANT_CODE.strip())
    esewa_signing_secret_configured = bool(settings.ESEWA_SECRET_KEY.strip())
    khalti_secret_key_configured = bool(settings.KHALTI_SECRET_KEY.strip())
    return {
        "scope": "configuration_only",
        "provider_connectivity_checked": False,
        "transaction_state_checked": False,
        "providers": {
            "esewa": {
                "merchant_code_configured": esewa_merchant_code_configured,
                "signing_secret_configured": esewa_signing_secret_configured,
                "required_credentials_present": (
                    esewa_merchant_code_configured and esewa_signing_secret_configured
                ),
            },
            "khalti": {
                "secret_key_configured": khalti_secret_key_configured,
                "required_credentials_present": khalti_secret_key_configured,
            },
        },
        "not_established": [
            "provider availability or merchant approval",
            "transaction completion or settlement",
            "live payment collection or verified revenue",
        ],
    }

@router.post("/esewa/checkout")
def esewa_checkout(request: Request, body: EsewaCheckoutRequest):
    require_owner_api_key(request)
    try:
        return nepal_payments.esewa_checkout(**body.model_dump())
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.post("/esewa/lookup")
def esewa_lookup(request: Request, body: EsewaLookupRequest):
    require_owner_api_key(request)
    try:
        result = nepal_payments.esewa_lookup(**body.model_dump())
        return {"provider": "esewa", "verified": result.get("status") == "COMPLETE", "response": result}
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.get("/esewa/callback")
def esewa_callback(data: str = Query(min_length=20)):
    """Verify the browser return without requiring an owner key.

    The provider redirects the payer's browser here, so it cannot carry Hami's
    private owner API key. This endpoint is read-only: it validates the signed
    provider payload and checks status/amount/merchant with eSewa's server API.
    It deliberately does not create orders, mark revenue, or trigger fulfillment.
    """
    try:
        payload = nepal_payments.verify_esewa_response(data)
        callback_status = str(payload.get("status", ""))
        transaction_uuid = str(payload.get("transaction_uuid", ""))
        merchant_code = str(payload.get("product_code", ""))
        total_amount = Decimal(str(payload.get("total_amount", "")))
        if not total_amount.is_finite() or total_amount <= 0 or not transaction_uuid:
            raise ValueError("invalid eSewa callback transaction fields")
        configured_merchant = settings.ESEWA_MERCHANT_CODE
        if not configured_merchant or merchant_code != configured_merchant:
            raise ValueError("eSewa callback merchant mismatch")

        lookup: dict = {}
        if callback_status == "COMPLETE":
            lookup = nepal_payments.esewa_lookup(
                amount_npr=total_amount,
                transaction_uuid=transaction_uuid,
            )

        lookup_amount = lookup.get("totalAmount", lookup.get("total_amount"))
        amount_matches = False
        if lookup_amount is not None:
            try:
                amount_matches = Decimal(str(lookup_amount)) == total_amount
            except Exception:
                amount_matches = False
        lookup_merchant = lookup.get("scd", lookup.get("product_code"))
        verified = (
            callback_status == "COMPLETE"
            and lookup.get("status") == "COMPLETE"
            and amount_matches
            and lookup_merchant == configured_merchant
        )
        return {
            "provider": "esewa",
            "verified": verified,
            "response": {
                "status": callback_status,
                "transaction_uuid": transaction_uuid,
                "total_amount": format(total_amount, "f"),
                "transaction_code": payload.get("transaction_code"),
                "provider_status": lookup.get("status"),
                "provider_reference": lookup.get("refId"),
            },
        }
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.post("/khalti/initiate")
def khalti_initiate(request: Request, body: KhaltiInitiateRequest):
    require_owner_api_key(request)
    try:
        return {"provider": "khalti", **nepal_payments.khalti_initiate(**body.model_dump())}
    except Exception as exc:
        raise _provider_error(exc) from exc

@router.post("/khalti/lookup")
def khalti_lookup(request: Request, body: KhaltiLookupRequest):
    require_owner_api_key(request)
    try:
        result = nepal_payments.khalti_lookup(**body.model_dump())
        return {"provider": "khalti", "verified": result.get("status") == "Completed", "response": result}
    except Exception as exc:
        raise _provider_error(exc) from exc
