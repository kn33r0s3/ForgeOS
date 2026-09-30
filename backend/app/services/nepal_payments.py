"""Real Nepal payment provider adapters.

These adapters never fabricate a successful payment. They only create a
provider checkout request or perform provider lookup; callers must verify the
provider response before recording a paid outcome.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.config import settings


def _require(value: str, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={**headers, "Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise RuntimeError("payment provider returned a non-object response")
    return body


def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise RuntimeError("payment provider returned a non-object response")
    return body


def _npr(value: Decimal | int | float | str) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValueError("amount must be greater than zero")
    return format(amount, "f")


def esewa_checkout(*, amount_npr: Decimal | int | float | str, transaction_uuid: str, success_url: str, failure_url: str) -> dict[str, str]:
    merchant = _require(settings.ESEWA_MERCHANT_CODE, "ESEWA_MERCHANT_CODE")
    secret = _require(settings.ESEWA_SECRET_KEY, "ESEWA_SECRET_KEY")
    total = _npr(amount_npr)
    signed = f"total_amount={total},transaction_uuid={transaction_uuid},product_code={merchant}"
    signature = base64.b64encode(hmac.new(secret.encode(), signed.encode(), hashlib.sha256).digest()).decode()
    return {
        "form_url": settings.ESEWA_FORM_URL,
        "amount": total,
        "tax_amount": "0",
        "product_service_charge": "0",
        "product_delivery_charge": "0",
        "total_amount": total,
        "transaction_uuid": transaction_uuid,
        "product_code": merchant,
        "success_url": success_url,
        "failure_url": failure_url,
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
    }


def esewa_lookup(*, amount_npr: Decimal | int | float | str, transaction_uuid: str) -> dict[str, Any]:
    merchant = _require(settings.ESEWA_MERCHANT_CODE, "ESEWA_MERCHANT_CODE")
    query = urllib.parse.urlencode({"product_code": merchant, "total_amount": _npr(amount_npr), "transaction_uuid": transaction_uuid})
    return _get_json(f"{settings.ESEWA_STATUS_URL}?{query}", {})


def verify_esewa_response(encoded_data: str) -> dict[str, Any]:
    """Decode and verify eSewa's base64 callback before treating it as evidence."""
    secret = _require(settings.ESEWA_SECRET_KEY, "ESEWA_SECRET_KEY")
    try:
        payload = json.loads(base64.b64decode(encoded_data, validate=True).decode("utf-8"))
        fields = payload["signed_field_names"].split(",")
        signed = ",".join(f"{field}={payload[field]}" for field in fields)
        expected = base64.b64encode(hmac.new(secret.encode(), signed.encode(), hashlib.sha256).digest()).decode()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid eSewa callback payload") from exc
    if not hmac.compare_digest(expected, str(payload.get("signature", ""))):
        raise ValueError("eSewa callback signature mismatch")
    return payload


def khalti_initiate(*, amount_npr: Decimal | int | float | str, purchase_order_id: str, purchase_order_name: str, return_url: str, website_url: str) -> dict[str, Any]:
    secret = _require(settings.KHALTI_SECRET_KEY, "KHALTI_SECRET_KEY")
    paisa = int((Decimal(str(amount_npr)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if paisa < 1000:
        raise ValueError("Khalti amount must be at least NPR 10")
    return _post_json(
        f"{settings.KHALTI_API_BASE_URL.rstrip('/')}/epayment/initiate/",
        {"return_url": return_url, "website_url": website_url, "amount": paisa, "purchase_order_id": purchase_order_id, "purchase_order_name": purchase_order_name},
        {"Authorization": f"Key {secret}"},
    )


def khalti_lookup(*, pidx: str) -> dict[str, Any]:
    secret = _require(settings.KHALTI_SECRET_KEY, "KHALTI_SECRET_KEY")
    return _post_json(f"{settings.KHALTI_API_BASE_URL.rstrip('/')}/epayment/lookup/", {"pidx": pidx}, {"Authorization": f"Key {secret}"})
