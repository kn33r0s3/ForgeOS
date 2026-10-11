from __future__ import annotations
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, AnyHttpUrl
from sqlalchemy.orm import Session

from app.config import settings
from app.security import require_owner_api_key
from app.database import get_db
from app.services import nepal_payments, payment_intent_engine, forge_bot_privacy

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


class PublicProductCheckoutRequest(BaseModel):
    provider: Literal["esewa", "khalti"]


class FulfillPaymentIntentRequest(BaseModel):
    confirmed: Literal[True]


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

@router.get("/offers")
def public_payment_offers(db: Session = Depends(get_db)):
    return payment_intent_engine.public_offers(db)


@router.post("/products/{product_id}/checkout")
def create_public_product_checkout(
    product_id: int,
    body: PublicProductCheckoutRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=128),
    db: Session = Depends(get_db),
):
    if not settings.FORGEOS_PUBLIC_CHECKOUT_ENABLED:
        raise HTTPException(status_code=503, detail="Public checkout is disabled.")
    try:
        within_limit = forge_bot_privacy.consume_rate_limited_request(
            db,
            request,
            hmac_key=settings.FORGE_BOT_CONTACT_HMAC_KEY,
            scope="public-product-checkout",
            limit=5,
        )
    except HTTPException:
        raise
    if not within_limit:
        raise HTTPException(status_code=429, detail="Hourly checkout-attempt limit reached.")
    try:
        return payment_intent_engine.create_checkout(
            db, product_id=product_id, provider=body.provider,
            idempotency_key=idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/intent/{public_ref}")
def public_payment_intent_status(
    public_ref: str, response: Response, db: Session = Depends(get_db)
):
    try:
        payload = payment_intent_engine.get_public_intent(db, public_ref)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Payment intent not found.") from exc
    response.headers["Cache-Control"] = "no-store"
    return payload


@router.get("/owner/fulfillment-queue")
def owner_payment_fulfillment_queue(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_owner_api_key(request)
    response.headers["Cache-Control"] = "no-store"
    return payment_intent_engine.pending_fulfillment_intents(db)


@router.post("/owner/intents/{intent_id}/fulfill")
def owner_fulfill_payment_intent(
    intent_id: int,
    request: Request,
    body: FulfillPaymentIntentRequest,
    db: Session = Depends(get_db),
):
    require_owner_api_key(request)
    if body.confirmed is not True:
        raise HTTPException(status_code=422, detail="Explicit owner fulfillment confirmation is required.")
    try:
        return payment_intent_engine.fulfill_verified_intent(db, intent_id)
    except ValueError as exc:
        if str(exc) == "Payment intent not found.":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="Payment fulfillment requires owner reconciliation.") from exc


@router.get("/khalti/callback")
def khalti_public_callback(
    intent: str = Query(min_length=24, max_length=64),
    pidx: str = Query(min_length=4, max_length=200),
    db: Session = Depends(get_db),
):
    try:
        payment_intent_engine.finalize_khalti_callback(db, public_ref=intent, pidx=pidx)
        return RedirectResponse(url=payment_intent_engine.payment_result_url(intent), status_code=303)
    except (RuntimeError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Khalti verification is temporarily unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Payment intent or provider reference not found.") from exc


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
def esewa_callback(
    data: str = Query(min_length=20),
    intent: str | None = Query(default=None, min_length=24, max_length=64),
    db: Session = Depends(get_db),
):
    """Bind browser return to the stored intent and validate provider status server-side."""
    if intent:
        try:
            payment_intent_engine.finalize_esewa_callback(
                db, public_ref=intent, encoded_data=data
            )
            return RedirectResponse(
                url=payment_intent_engine.payment_result_url(intent),
                status_code=303,
            )
        except (RuntimeError, OSError) as exc:
            raise HTTPException(status_code=503, detail="eSewa verification is temporarily unavailable.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="eSewa callback did not match the stored payment intent.") from exc
    # Compatibility path remains read-only for provider diagnostics without a Hami intent.
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
