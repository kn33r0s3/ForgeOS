"""Durable payment intent state machine for public Hami offers.

Provider callbacks are only pointers. A server-side provider lookup must confirm
the stored order, merchant, exact amount, final status and transaction reference
before a REAL/VERIFIED revenue outcome is written to the existing Product.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app import evidence_source, models
from app.config import settings
from app.services import action_engine, nepal_payments, offer_preparation, orchestrator, product_engine, world_graph

_TERMINAL = {"VERIFIED", "FAILED", "CANCELLED", "DISPUTED", "REFUNDED"}


class PaymentReconciliationRequired(RuntimeError):
    """A provider reports a refund that conflicts with a previously verified payment.

    The existing ledger is intentionally left untouched for owner review.
    """


def checkout_enabled() -> bool:
    return bool(settings.FORGEOS_PUBLIC_CHECKOUT_ENABLED)


def _public_origin() -> str:
    raw = (settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    parts = urlsplit(raw)
    local_http = parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1"}
    if (
        not parts.hostname or parts.username or parts.password or parts.query or parts.fragment
        or parts.path not in ("", "/")
        or not (parts.scheme == "https" or local_http)
    ):
        raise RuntimeError("PUBLIC_APP_URL must be an explicit HTTPS origin before payment redirects are enabled.")
    return raw


def payment_result_url(public_ref: str) -> str:
    return _public_origin() + "/payment-result?intent=" + public_ref


def _trusted_https_url(value: str, *, allowed_domains: set[str], allow_subdomains: bool = False, required_path: str | None = None) -> bool:
    """Reject malformed, credential-bearing, non-HTTPS, and off-provider URLs."""
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port = parts.port
    except (TypeError, ValueError):
        return False
    if (
        parts.scheme != "https" or not host or parts.username or parts.password
        or parts.fragment or port not in (None, 443)
        or (required_path is not None and parts.path != required_path)
    ):
        return False
    if allow_subdomains:
        return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)
    return host in allowed_domains


def _trusted_esewa_form_url(value: str) -> bool:
    return _trusted_https_url(
        value,
        allowed_domains={"epay.esewa.com.np", "rc-epay.esewa.com.np"},
        required_path="/api/epay/main/v2/form",
    )


def _trusted_khalti_payment_url(value: str) -> bool:
    return _trusted_https_url(value, allowed_domains={"khalti.com"}, allow_subdomains=True)


def _has_provider_credentials(provider: str) -> bool:
    if provider == "esewa":
        return bool(settings.ESEWA_MERCHANT_CODE.strip() and settings.ESEWA_SECRET_KEY.strip())
    if provider == "khalti":
        return bool(settings.KHALTI_SECRET_KEY.strip())
    return False


def _fixed_price(product: models.Product) -> int:
    amount = offer_preparation.fixed_npr_price_paisa(product.pricing)
    if amount is None:
        raise ValueError('Public checkout requires a fixed one-time NPR price such as "NPR 5000 one-time".')
    return amount


def _eligible_product(db: Session, product_id: int) -> models.Product:
    product = db.get(models.Product, product_id)
    if product is None:
        raise ValueError("Published offer not found.")
    if not (
        product.data_scope == "REAL"
        and product.status in {"launched", "iterating"}
        and product.launch_state == "public"
        and product.approval_status == "APPROVED"
        and product.approved_at is not None
        and product.offer_brief
        and product.opportunity_id is not None
    ):
        raise ValueError("This offer is not currently approved for public checkout.")
    confirmed, willing = orchestrator.validation_counts(db, product.opportunity_id, "REAL")
    if (
        confirmed < orchestrator.DEFAULT_Y_CONFIRM_PROBLEM
        or willing < orchestrator.DEFAULT_Z_WILLING_TO_PAY
    ):
        raise ValueError("Verified REAL demand no longer meets the public checkout gate.")
    _fixed_price(product)
    return product


def public_offers(db: Session) -> list[dict]:
    """Return a minimal public DTO; never include contact records or review JSON."""
    durable_for_public_checkout = not os.getenv("VERCEL") or db.get_bind().dialect.name == "postgresql"
    enabled = (
        checkout_enabled()
        and bool(settings.FORGE_BOT_CONTACT_HMAC_KEY.strip())
        and durable_for_public_checkout
    )
    rows = (
        db.query(models.Product)
        .filter(
            models.Product.data_scope == "REAL",
            models.Product.status.in_(("launched", "iterating")),
            models.Product.launch_state == "public",
            models.Product.approval_status == "APPROVED",
            models.Product.approved_at.isnot(None),
        )
        .order_by(models.Product.updated_at.desc(), models.Product.id.desc())
        .all()
    )
    result: list[dict] = []
    for product in rows:
        try:
            _eligible_product(db, product.id)
            amount_paisa = _fixed_price(product)
        except (ValueError, RuntimeError):
            continue
        providers = [
            provider for provider in ("esewa", "khalti")
            if enabled and _has_provider_credentials(provider)
            and (provider != "khalti" or amount_paisa >= 1000)
        ]
        from app.services.public_feed import sanitize_public_text
        result.append({
            "id": product.id,
            "name": sanitize_public_text(product.name),
            "offer": sanitize_public_text(product.offer),
            "pricing": sanitize_public_text(product.pricing),
            "currency": "NPR",
            "amount_paisa": amount_paisa,
            "checkout_enabled": bool(providers),
            "providers": providers,
        })
    return result


def _transition(
    db: Session,
    intent: models.OpPaymentIntent,
    status: str,
    *,
    note: str | None = None,
    provider_payment_id: str | None = None,
    provider_reference: str | None = None,
    checkout_url: str | None = None,
    outcome_id: int | None = None,
    commit: bool = True,
) -> models.OpPaymentIntent:
    if status == intent.status:
        for attr, candidate in (
            ("provider_payment_id", provider_payment_id),
            ("provider_reference", provider_reference),
            ("checkout_url", checkout_url),
            ("outcome_id", outcome_id),
        ):
            current = getattr(intent, attr)
            if candidate is not None and current not in (None, candidate):
                raise ValueError(f"Conflicting {attr} for payment intent.")
            if candidate is not None:
                setattr(intent, attr, candidate)
        if note is not None:
            intent.status_note = note[:500]
        if commit:
            intent.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(intent)
        return intent
    if intent.status in _TERMINAL:
        raise ValueError("A terminal payment intent is immutable.")
    previous = intent.status
    intent.status = status
    intent.updated_at = datetime.now(timezone.utc)
    if note is not None:
        intent.status_note = note[:500]
    for attr, candidate in (
        ("provider_payment_id", provider_payment_id),
        ("provider_reference", provider_reference),
        ("checkout_url", checkout_url),
        ("outcome_id", outcome_id),
    ):
        current = getattr(intent, attr)
        if candidate is not None and current not in (None, candidate):
            raise ValueError(f"Conflicting {attr} for payment intent.")
        if candidate is not None:
            setattr(intent, attr, candidate)
    world_graph.create_event(
        db,
        event_type="state_changed",
        source="payment_intent_engine",
        payload={
            "domain": "payment_intent",
            "payment_intent_id": intent.id,
            "product_id": intent.product_id,
            "provider": intent.provider,
            "from": previous,
            "to": status,
            "amount_paisa": intent.amount_paisa,
            "currency": intent.currency,
        },
        idempotency_key=f"payment-intent:{intent.id}:{previous}:{status}:{uuid.uuid4().hex}",
    )
    if commit:
        db.commit()
        db.refresh(intent)
    return intent


def _public_payload(intent: models.OpPaymentIntent, product: models.Product) -> dict:
    from app.services.public_feed import sanitize_public_text
    return {
        "intent": intent.public_ref,
        "offer_id": intent.product_id,
        "provider": intent.provider,
        "status": intent.status,
        "amount_paisa": intent.amount_paisa,
        "amount_npr": format(Decimal(intent.amount_paisa) / Decimal(100), "f"),
        "currency": "NPR",
        "product_name": sanitize_public_text(product.name),
        "fulfilled": intent.fulfilled_at is not None,
    }


def get_public_intent(db: Session, public_ref: str) -> dict:
    intent = db.query(models.OpPaymentIntent).filter_by(public_ref=public_ref).one_or_none()
    if intent is None:
        raise ValueError("Payment intent not found.")
    product = db.get(models.Product, intent.product_id)
    if product is None:
        raise ValueError("Payment intent product not found.")
    return _public_payload(intent, product)


def _checkout_details(intent: models.OpPaymentIntent) -> dict:
    origin = _public_origin()
    root = origin + "/api/payments"
    if intent.provider == "esewa":
        callback = f"{root}/esewa/callback?intent={intent.public_ref}"
        fields = nepal_payments.esewa_checkout(
            amount_npr=Decimal(intent.amount_paisa) / Decimal(100),
            transaction_uuid=intent.merchant_order_id,
            success_url=callback,
            failure_url=callback,
        )
        form_url = str(fields.pop("form_url", ""))
        if not _trusted_esewa_form_url(form_url):
            raise RuntimeError("eSewa checkout URL is not an approved HTTPS eSewa form endpoint.")
        return {"type": "form_post", "url": form_url, "fields": fields}
    if intent.provider == "khalti":
        if not intent.checkout_url or not _trusted_khalti_payment_url(intent.checkout_url):
            raise RuntimeError("Khalti checkout URL is not an approved HTTPS Khalti payment endpoint.")
        return {"type": "redirect", "url": intent.checkout_url}
    raise ValueError("Unsupported payment provider.")


def create_checkout(
    db: Session,
    *,
    product_id: int,
    provider: str,
    idempotency_key: str,
) -> dict:
    if not checkout_enabled():
        raise RuntimeError("Public checkout is disabled.")
    if provider not in {"esewa", "khalti"}:
        raise ValueError("Unsupported payment provider.")
    if not isinstance(idempotency_key, str) or not 16 <= len(idempotency_key) <= 128 or idempotency_key.strip() != idempotency_key:
        raise ValueError("Idempotency-Key must be 16–128 non-whitespace characters.")
    # Idempotency is request-scoped across provider/body parameters. A client
    # reusing the same key for a different product or provider must collide and
    # be rejected below rather than accidentally creating a second payment.
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    existing = db.query(models.OpPaymentIntent).filter_by(idempotency_key_hash=digest).one_or_none()
    if existing is not None:
        if existing.product_id != product_id or existing.provider != provider:
            raise ValueError("Idempotency key conflicts with another checkout request.")
        if existing.status in {"FAILED", "CANCELLED", "DISPUTED", "REFUNDED"}:
            raise ValueError("This idempotency key already has a terminal attempt; use a new key only for a genuinely new attempt.")
        product = db.get(models.Product, existing.product_id)
        if product is None:
            raise ValueError("Payment intent product not found.")
        checkout = None if existing.status == "VERIFIED" else _checkout_details(existing)
        return {**_public_payload(existing, product), "checkout": checkout, "reused": True}

    product = _eligible_product(db, product_id)
    if not _has_provider_credentials(provider):
        raise RuntimeError(f"{provider} credentials are not configured.")
    if not settings.FORGE_BOT_CONTACT_HMAC_KEY.strip():
        raise RuntimeError("Privacy-preserving checkout rate limiting is not configured.")
    origin = _public_origin()
    amount_paisa = _fixed_price(product)
    if provider == "khalti" and amount_paisa < 1000:
        raise ValueError("Khalti payments require a minimum total of NPR 10.")
    intent = models.OpPaymentIntent(
        public_ref=secrets.token_urlsafe(32),
        product_id=product.id,
        provider=provider,
        status="CREATED",
        amount_paisa=amount_paisa,
        currency="NPR",
        merchant_order_id=f"hami-{provider}-{uuid.uuid4().hex}",
        idempotency_key_hash=digest,
        data_scope="REAL",
    )
    db.add(intent)
    db.flush()
    world_graph.create_event(
        db,
        event_type="state_changed",
        source="payment_intent_engine",
        payload={
            "domain": "payment_intent",
            "payment_intent_id": intent.id,
            "product_id": product.id,
            "provider": provider,
            "from": None,
            "to": "CREATED",
            "amount_paisa": amount_paisa,
            "currency": "NPR",
        },
        idempotency_key=f"payment-intent:{intent.id}:created",
    )
    db.commit()
    db.refresh(intent)

    try:
        if provider == "khalti":
            callback = f"{origin}/api/payments/khalti/callback?intent={intent.public_ref}"
            response = nepal_payments.khalti_initiate(
                amount_npr=Decimal(amount_paisa) / Decimal(100),
                purchase_order_id=intent.merchant_order_id,
                purchase_order_name=product.name[:200],
                return_url=callback,
                website_url=origin + "/",
            )
            pidx = str(response.get("pidx", ""))
            payment_url = str(response.get("payment_url", ""))
            if not pidx or not _trusted_khalti_payment_url(payment_url):
                raise RuntimeError("Khalti initiation did not return a valid payment ID and approved HTTPS URL.")
            _transition(db, intent, "INITIATED", provider_payment_id=pidx, checkout_url=payment_url)
        else:
            # eSewa's checkout request is a signed form, not a server-side
            # transaction creation call. The durable Hami intent precedes it.
            _transition(db, intent, "INITIATED")
        return {
            **_public_payload(intent, product),
            "checkout": _checkout_details(intent),
            "reused": False,
        }
    except Exception:
        db.rollback()
        current = db.query(models.OpPaymentIntent).filter_by(id=intent.id).one_or_none()
        if current is not None and current.status not in _TERMINAL:
            _transition(
                db, current, "FAILED",
                note="Provider initiation failed; no verified payment was recorded.",
            )
        raise


_REFUND_STATUSES = {"FULL_REFUND", "PARTIAL_REFUND", "REFUNDED"}


def _raise_reconciliation_on_verified_refund(
    intent: models.OpPaymentIntent, provider: str, provider_status: str
) -> None:
    """Never mutate a verified payment ledger automatically when a refund is reported."""
    if intent.status == "VERIFIED" and (provider_status or "").strip().upper() in _REFUND_STATUSES:
        raise PaymentReconciliationRequired(
            f"{provider} reports a refund for a previously verified payment; "
            "owner reconciliation is required."
        )


def _nonverified_state(
    db: Session, intent: models.OpPaymentIntent, provider_status: str, note: str
) -> models.OpPaymentIntent:
    normalized = (provider_status or "").strip().upper()
    if normalized in {"CANCELLED", "CANCELED", "USER CANCELLED", "USER CANCELED"}:
        target = "CANCELLED"
    elif normalized in {"FAILED", "FULL_REFUND", "PARTIAL_REFUND", "REFUNDED"}:
        target = "REFUNDED" if "REFUND" in normalized else "FAILED"
    else:
        target = "PENDING"
    if intent.status == target or intent.status == "VERIFIED":
        return intent
    return _transition(db, intent, target, note=note)


def _record_verified_payment(
    db: Session, intent: models.OpPaymentIntent, *, provider_reference: str
) -> models.OpPaymentIntent:
    """Mark payment as verified only; realization waits for owner-confirmed fulfillment."""
    if not provider_reference or len(provider_reference) > 200:
        return _transition(db, intent, "DISPUTED", note="Provider did not return a usable transaction reference.")
    if intent.status == "VERIFIED":
        if intent.provider_reference != provider_reference:
            raise ValueError("Verified payment callback conflicts with the stored transaction.")
        return intent
    if intent.status in {"FAILED", "CANCELLED", "DISPUTED", "REFUNDED"}:
        raise ValueError("A terminal non-payment intent cannot be promoted to a verified payment.")
    product = db.get(models.Product, intent.product_id)
    if product is None or product.data_scope != "REAL":
        return _transition(db, intent, "DISPUTED", note="Payment intent no longer links to a REAL product.")
    return _transition(
        db, intent, "VERIFIED",
        note="Provider status, merchant, amount and transaction reference verified server-side; awaiting owner-confirmed fulfillment.",
        provider_reference=provider_reference,
    )




_RECOVERABLE_LOCAL_STATES = {"CREATED", "INITIATED", "PENDING", "FAILED", "CANCELLED"}
_KHALTI_TERMINAL_RECOVERY = {
    "EXPIRED": "CANCELLED",
    "USER CANCELED": "CANCELLED",
    "USER CANCELLED": "CANCELLED",
    "CANCELED": "CANCELLED",
    "CANCELLED": "CANCELLED",
    "FAILED": "FAILED",
}
_ESEWA_TERMINAL_RECOVERY = {
    "NOT_FOUND": "CANCELLED",
    "CANCELED": "CANCELLED",
    "CANCELLED": "CANCELLED",
    "FAILED": "FAILED",
}
_RECOVERY_REFUND_STATUSES = {
    "REFUNDED", "FULL_REFUND", "PARTIAL_REFUND", "PARTIALLY REFUNDED",
}


def _recovery_payload(
    db: Session,
    intent: models.OpPaymentIntent,
    *,
    checked: bool,
    retry_allowed: bool,
    message: str,
    provider_status: str | None = None,
) -> dict:
    product = db.get(models.Product, intent.product_id)
    if product is None:
        raise ValueError("Payment intent product not found.")
    return {
        **_public_payload(intent, product),
        "retry_allowed": retry_allowed,
        "recovery": {
            "checked": checked,
            "retry_allowed": retry_allowed,
            "provider_status": (provider_status or "")[:64] or None,
            "message": message,
        },
    }


def _recovery_mismatch(
    db: Session, intent: models.OpPaymentIntent, *, note: str
) -> dict:
    if intent.status in {"FAILED", "CANCELLED"}:
        raise PaymentReconciliationRequired(
            "Provider details conflict with this terminal payment state; owner reconciliation is required."
        )
    if intent.status in _TERMINAL:
        return _recovery_payload(
            db, intent, checked=True, retry_allowed=False,
            message="This payment requires owner reconciliation. Another attempt remains blocked.",
        )
    _transition(db, intent, "DISPUTED", note=note)
    return _recovery_payload(
        db, intent, checked=True, retry_allowed=False,
        message="Provider details did not match the stored attempt. Owner reconciliation is required.",
    )


def _reconcile_payment_intent(
    db: Session, intent: models.OpPaymentIntent
) -> dict:
    if intent.status == "VERIFIED":
        return _recovery_payload(
            db, intent, checked=False, retry_allowed=False,
            message="This payment is already verified. A new attempt is not allowed from this status page.",
        )
    if intent.status in {"DISPUTED", "REFUNDED"}:
        return _recovery_payload(
            db, intent, checked=False, retry_allowed=False,
            message="This payment requires owner reconciliation. Hami will not unlock another attempt automatically.",
        )
    if intent.status not in _RECOVERABLE_LOCAL_STATES:
        return _recovery_payload(
            db, intent, checked=False, retry_allowed=False,
            message="This payment state is not eligible for automatic recovery.",
        )

    if intent.provider == "khalti":
        if not intent.provider_payment_id:
            raise PaymentReconciliationRequired(
                "Khalti did not return a stored payment reference, so Hami cannot confirm a terminal provider state. Owner reconciliation is required."
            )
        lookup = nepal_payments.khalti_lookup(pidx=intent.provider_payment_id)
        lookup_pidx = str(lookup.get("pidx", ""))
        lookup_status = str(lookup.get("status", "")).strip()
        normalized = lookup_status.upper()
        try:
            amount_paisa = int(lookup.get("total_amount", -1))
        except (TypeError, ValueError):
            amount_paisa = -1
        lookup_order = str(lookup.get("purchase_order_id") or "")
        if (
            lookup_pidx != intent.provider_payment_id
            or amount_paisa != intent.amount_paisa
            or (lookup_order and lookup_order != intent.merchant_order_id)
        ):
            return _recovery_mismatch(
                db, intent, note="Khalti recovery lookup returned a different payment, order, or amount."
            )

        if lookup.get("refunded") is True or normalized in _RECOVERY_REFUND_STATUSES:
            if intent.status in {"FAILED", "CANCELLED"}:
                raise PaymentReconciliationRequired(
                    "Khalti reports a refund while Hami has a different terminal state; owner reconciliation is required."
                )
            _transition(db, intent, "REFUNDED", note="Khalti server-side lookup reports a refund.")
            return _recovery_payload(
                db, intent, checked=True, retry_allowed=False,
                provider_status=lookup_status,
                message="Khalti reports a refund. Hami will not unlock a new attempt automatically.",
            )

        if normalized == "COMPLETED":
            reference = str(lookup.get("transaction_id") or "")
            if not reference:
                return _recovery_mismatch(
                    db, intent, note="Khalti reported completion without a transaction reference."
                )
            if intent.status in {"FAILED", "CANCELLED"}:
                raise PaymentReconciliationRequired(
                    "Khalti reports a completed payment for an attempt Hami previously marked terminal; owner reconciliation is required."
                )
            _record_verified_payment(db, intent, provider_reference=reference)
            return _recovery_payload(
                db, intent, checked=True, retry_allowed=False,
                provider_status=lookup_status,
                message="Khalti confirms a completed payment. Hami marked it verified; fulfillment still requires owner confirmation.",
            )

        terminal_target = _KHALTI_TERMINAL_RECOVERY.get(normalized)
        if terminal_target:
            if intent.status in {"CREATED", "INITIATED", "PENDING"}:
                _transition(
                    db, intent, terminal_target,
                    note=f"Khalti server-side lookup confirmed terminal status {lookup_status}.",
                )
            return _recovery_payload(
                db, intent, checked=True, retry_allowed=True,
                provider_status=lookup_status,
                message="Khalti confirmed that this attempt ended without a completed payment. Starting a new attempt is now allowed.",
            )

        if intent.status in {"FAILED", "CANCELLED"}:
            raise PaymentReconciliationRequired(
                "Khalti still reports a pending or unrecognized state for an attempt Hami marked terminal; owner reconciliation is required."
            )
        _nonverified_state(
            db, intent, lookup_status,
            "Khalti server-side lookup did not confirm a completed or terminal failed payment.",
        )
        return _recovery_payload(
            db, intent, checked=True, retry_allowed=False,
            provider_status=lookup_status,
            message="Khalti has not confirmed a terminal failed or cancelled state. Keep this attempt and check again later.",
        )

    if intent.provider == "esewa":
        lookup = nepal_payments.esewa_lookup(
            amount_npr=Decimal(intent.amount_paisa) / Decimal(100),
            transaction_uuid=intent.merchant_order_id,
        )
        lookup_status = str(lookup.get("status", "")).strip()
        normalized = lookup_status.upper()
        raw_amount = lookup.get("totalAmount")
        if raw_amount is None:
            raw_amount = lookup.get("total_amount")
        lookup_merchant = str(lookup.get("scd") or lookup.get("product_code") or "")
        lookup_uuid = str(lookup.get("transaction_uuid") or "")
        lookup_reference = str(lookup.get("refId") or lookup.get("ref_id") or "")

        # eSewa NOT_FOUND responses may contain only status. The server-side
        # lookup request binds that response to this stored amount/order/merchant.
        if normalized == "NOT_FOUND":
            if (
                (lookup_merchant and lookup_merchant != settings.ESEWA_MERCHANT_CODE)
                or (lookup_uuid and lookup_uuid != intent.merchant_order_id)
            ):
                return _recovery_mismatch(
                    db, intent, note="eSewa NOT_FOUND response contradicted the stored merchant or order."
                )
            if raw_amount is not None:
                try:
                    found_amount_paisa = int((Decimal(str(raw_amount)) * Decimal(100)).quantize(Decimal("1")))
                except Exception:
                    found_amount_paisa = -1
                if found_amount_paisa != intent.amount_paisa:
                    return _recovery_mismatch(
                        db, intent, note="eSewa NOT_FOUND response contradicted the stored amount."
                    )
        else:
            try:
                amount_paisa = int((Decimal(str(raw_amount)) * Decimal(100)).quantize(Decimal("1")))
            except Exception:
                amount_paisa = -1
            if (
                amount_paisa != intent.amount_paisa
                or not settings.ESEWA_MERCHANT_CODE
                or lookup_merchant != settings.ESEWA_MERCHANT_CODE
                or (lookup_uuid and lookup_uuid != intent.merchant_order_id)
            ):
                return _recovery_mismatch(
                    db, intent, note="eSewa recovery lookup returned a different merchant, order, or amount."
                )

        if normalized in _RECOVERY_REFUND_STATUSES:
            if intent.status in {"FAILED", "CANCELLED"}:
                raise PaymentReconciliationRequired(
                    "eSewa reports a refund while Hami has a different terminal state; owner reconciliation is required."
                )
            _transition(db, intent, "REFUNDED", note="eSewa server-side lookup reports a refund.")
            return _recovery_payload(
                db, intent, checked=True, retry_allowed=False,
                provider_status=lookup_status,
                message="eSewa reports a refund. Hami will not unlock a new attempt automatically.",
            )

        if normalized == "COMPLETE":
            if not lookup_reference:
                return _recovery_mismatch(
                    db, intent, note="eSewa reported completion without a transaction reference."
                )
            if intent.status in {"FAILED", "CANCELLED"}:
                raise PaymentReconciliationRequired(
                    "eSewa reports a completed payment for an attempt Hami previously marked terminal; owner reconciliation is required."
                )
            _record_verified_payment(db, intent, provider_reference=lookup_reference)
            return _recovery_payload(
                db, intent, checked=True, retry_allowed=False,
                provider_status=lookup_status,
                message="eSewa confirms a completed payment. Hami marked it verified; fulfillment still requires owner confirmation.",
            )

        terminal_target = _ESEWA_TERMINAL_RECOVERY.get(normalized)
        if terminal_target:
            if intent.status in {"CREATED", "INITIATED", "PENDING"}:
                _transition(
                    db, intent, terminal_target,
                    note=f"eSewa server-side lookup confirmed terminal status {lookup_status}.",
                )
            return _recovery_payload(
                db, intent, checked=True, retry_allowed=True,
                provider_status=lookup_status,
                message="eSewa confirmed that this attempt ended without a completed payment. Starting a new attempt is now allowed.",
            )

        if intent.status in {"FAILED", "CANCELLED"}:
            raise PaymentReconciliationRequired(
                "eSewa still reports a pending, ambiguous or unrecognized state for an attempt Hami marked terminal; owner reconciliation is required."
            )
        _nonverified_state(
            db, intent, lookup_status,
            "eSewa server-side lookup has not confirmed a completed or terminal failed payment.",
        )
        return _recovery_payload(
            db, intent, checked=True, retry_allowed=False,
            provider_status=lookup_status,
            message="eSewa has not confirmed a terminal failed or cancelled state. Keep this attempt and check again later.",
        )

    raise ValueError("Unsupported payment provider.")


def reconcile_public_intent(db: Session, public_ref: str) -> dict:
    """Reconcile a checkout using a high-entropy public reference and provider lookup."""
    intent = db.query(models.OpPaymentIntent).filter_by(public_ref=public_ref).one_or_none()
    if intent is None:
        raise ValueError("Payment intent not found.")
    return _reconcile_payment_intent(db, intent)


def reconcile_checkout_by_key(
    db: Session, *, product_id: int, idempotency_key: str
) -> dict:
    """Reconcile a checkout error even when the browser never received its public reference."""
    if (
        not isinstance(idempotency_key, str)
        or not 16 <= len(idempotency_key) <= 128
        or idempotency_key.strip() != idempotency_key
    ):
        raise ValueError("Invalid checkout idempotency key.")
    product = db.get(models.Product, product_id)
    if product is None:
        raise ValueError("Checkout product not found.")

    # Match the exact SHA-256 digest create_checkout stores. The digest is
    # intentionally global to the raw client key: create_checkout rejects its
    # reuse with a different product/provider after it finds an existing row.
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    intent = db.query(models.OpPaymentIntent).filter_by(
        idempotency_key_hash=digest
    ).one_or_none()
    if intent is None:
        return {
            "intent": None,
            "offer_id": product.id,
            "provider": None,
            "status": "NO_ATTEMPT",
            "retry_allowed": True,
            "recovery": {
                "checked": False,
                "retry_allowed": True,
                "provider_status": None,
                "message": "Hami has no persisted payment attempt for this key. It is safe to start a new attempt.",
            },
        }
    if intent.product_id != product_id:
        raise ValueError("Checkout attempt was not found.")
    return _reconcile_payment_intent(db, intent)


def pending_fulfillment_intents(db: Session) -> list[dict]:
    """Return only provider-verified, not-yet-fulfilled REAL payments for the owner."""
    intents = (
        db.query(models.OpPaymentIntent)
        .filter(
            models.OpPaymentIntent.data_scope == "REAL",
            models.OpPaymentIntent.status == "VERIFIED",
            models.OpPaymentIntent.fulfilled_at.is_(None),
        )
        .order_by(models.OpPaymentIntent.created_at.asc(), models.OpPaymentIntent.id.asc())
        .all()
    )
    results: list[dict] = []
    for intent in intents:
        product = db.get(models.Product, intent.product_id)
        if product is None or product.data_scope != "REAL":
            continue
        results.append({
            "id": intent.id,
            "product_id": product.id,
            "product_name": product.name,
            "provider": intent.provider,
            "status": intent.status,
            "amount_paisa": intent.amount_paisa,
            "amount_npr": format(Decimal(intent.amount_paisa) / Decimal(100), "f"),
            "currency": intent.currency,
            "provider_reference": intent.provider_reference,
            "created_at": intent.created_at.isoformat() if intent.created_at else None,
            "outcome_id": intent.outcome_id,
        })
    return results


def _fulfillment_result(db: Session, intent: models.OpPaymentIntent) -> dict:
    product = db.get(models.Product, intent.product_id)
    event = (
        db.query(models.CustomerEvent)
        .filter_by(outcome_id=intent.outcome_id)
        .order_by(models.CustomerEvent.id.asc())
        .first()
        if intent.outcome_id is not None else None
    )
    return {
        "id": intent.id,
        "product_id": intent.product_id,
        "product_name": product.name if product else "Unknown product",
        "provider": intent.provider,
        "status": intent.status,
        "amount_paisa": intent.amount_paisa,
        "amount_npr": format(Decimal(intent.amount_paisa) / Decimal(100), "f"),
        "currency": intent.currency,
        "fulfilled": intent.fulfilled_at is not None,
        "fulfilled_at": intent.fulfilled_at.isoformat() if intent.fulfilled_at else None,
        "outcome_id": intent.outcome_id,
        "customer_event_id": event.id if event else None,
    }


def fulfill_verified_intent(db: Session, intent_id: int) -> dict:
    """Owner confirmation records one REAL revenue outcome and one linked paid-customer event."""
    intent = (
        db.query(models.OpPaymentIntent)
        .filter_by(id=intent_id)
        .with_for_update()
        .one_or_none()
    )
    if intent is None:
        raise ValueError("Payment intent not found.")
    if intent.status != "VERIFIED":
        raise ValueError("Only provider-verified payments can be marked fulfilled.")
    if intent.data_scope != "REAL":
        raise ValueError("Only REAL payment intents can be fulfilled into business revenue.")
    product = db.get(models.Product, intent.product_id)
    if product is None or product.data_scope != "REAL":
        raise ValueError("Payment intent no longer links to a REAL product.")
    if not intent.provider_reference:
        raise ValueError("Verified payment has no provider transaction reference.")

    if intent.fulfilled_at is not None:
        if intent.outcome_id is None:
            raise RuntimeError("Fulfilled payment intent is missing its linked revenue outcome.")
        return _fulfillment_result(db, intent)

    try:
        outcome = db.get(models.Outcome, intent.outcome_id) if intent.outcome_id else None
        if outcome is None:
            outcome = action_engine.record_outcome(
                db,
                outcome_type="ACTUAL_REVENUE",
                product_id=product.id,
                actual_value=float(Decimal(intent.amount_paisa) / Decimal(100)),
                unit="NPR",
                qualitative_result=f"Owner-confirmed fulfillment of provider-verified payment intent #{intent.id}.",
                source=f"{intent.provider}_provider_lookup:{intent.provider_reference}",
                success=True,
                data_scope="REAL",
                source_kind=evidence_source.REAL,
                verification_state="VERIFIED",
                idempotency_key=f"payment-intent-{intent.id}-fulfilled-revenue",
                commit=False,
            )
        expected_amount = float(Decimal(intent.amount_paisa) / Decimal(100))
        if not (
            outcome.product_id == product.id
            and outcome.outcome_type == "ACTUAL_REVENUE"
            and outcome.actual_value == expected_amount
            and outcome.unit == "NPR"
            and outcome.data_scope == "REAL"
            and outcome.source_kind == evidence_source.REAL
            and outcome.verification_state == "VERIFIED"
        ):
            raise ValueError("Existing outcome does not match this verified payment intent.")

        intent.outcome_id = outcome.id
        customer_event = (
            db.query(models.CustomerEvent)
            .filter_by(outcome_id=outcome.id)
            .order_by(models.CustomerEvent.id.asc())
            .first()
        )
        if customer_event is None:
            customer_event = product_engine.create_customer_event(
                db,
                product_id=product.id,
                opportunity_id=product.opportunity_id,
                segment="public checkout",
                stage="paid_customer",
                event_type="purchase",
                notes=f"Owner-confirmed fulfillment for payment intent #{intent.id}; no buyer contact details collected.",
                outcome_id=outcome.id,
                data_scope="REAL",
                commit=False,
            )
        intent.fulfilled_at = datetime.now(timezone.utc)
        intent.updated_at = intent.fulfilled_at
        world_graph.create_event(
            db,
            event_type="state_changed",
            source="payment_intent_engine",
            payload={
                "domain": "payment_intent",
                "payment_intent_id": intent.id,
                "product_id": product.id,
                "provider": intent.provider,
                "from": "VERIFIED_UNFULFILLED",
                "to": "FULFILLED",
                "amount_paisa": intent.amount_paisa,
                "currency": intent.currency,
                "outcome_id": outcome.id,
                "customer_event_id": customer_event.id,
            },
            idempotency_key=f"payment-intent:{intent.id}:fulfilled",
        )
        # Keep any linked repair work-item audit in the same transaction.
        # The existing intent/Outcome remain the only payment/revenue ledger.
        from app.services import repair_shop
        db.flush()
        repair_shop.record_provider_payment_fulfillment(db, intent.id)
        db.commit()
        db.refresh(intent)
    except Exception:
        db.rollback()
        raise
    return _fulfillment_result(db, intent)

def finalize_esewa_callback(
    db: Session, *, public_ref: str, encoded_data: str
) -> models.OpPaymentIntent:
    intent = db.query(models.OpPaymentIntent).filter_by(public_ref=public_ref).one_or_none()
    if intent is None:
        raise ValueError("Payment intent not found.")
    if intent.provider != "esewa":
        raise ValueError("Payment provider does not match this intent.")
    payload = nepal_payments.verify_esewa_response(encoded_data)
    status = str(payload.get("status", ""))
    transaction_uuid = str(payload.get("transaction_uuid", ""))
    merchant = str(payload.get("product_code", ""))
    try:
        amount_paisa = int((Decimal(str(payload.get("total_amount", ""))) * Decimal(100)).quantize(Decimal("1")))
    except Exception as exc:
        raise ValueError("Invalid eSewa transaction amount.") from exc
    if (
        transaction_uuid != intent.merchant_order_id
        or merchant != settings.ESEWA_MERCHANT_CODE
        or amount_paisa != intent.amount_paisa
    ):
        _transition(db, intent, "DISPUTED", note="Signed callback identity, merchant, or amount mismatched this intent.")
        raise ValueError("eSewa transaction does not match this payment intent.")
    _raise_reconciliation_on_verified_refund(intent, "eSewa", status)
    if status != "COMPLETE":
        return _nonverified_state(db, intent, status, "eSewa signed callback is not a completed payment.")
    lookup = nepal_payments.esewa_lookup(
        amount_npr=Decimal(intent.amount_paisa) / Decimal(100),
        transaction_uuid=intent.merchant_order_id,
    )
    lookup_status = str(lookup.get("status", ""))
    lookup_amount = lookup.get("totalAmount", lookup.get("total_amount"))
    lookup_merchant = lookup.get("scd", lookup.get("product_code"))
    reference = str(lookup.get("refId", ""))
    try:
        lookup_amount_paisa = int((Decimal(str(lookup_amount)) * Decimal(100)).quantize(Decimal("1")))
    except Exception:
        lookup_amount_paisa = -1
    if lookup_status.strip().upper() in _REFUND_STATUSES:
        _raise_reconciliation_on_verified_refund(intent, "eSewa", lookup_status)
        if (
            lookup_amount_paisa == intent.amount_paisa
            and lookup_merchant == settings.ESEWA_MERCHANT_CODE
        ):
            return _nonverified_state(
                db, intent, lookup_status, "eSewa server lookup reports a refund."
            )
        return _transition(
            db, intent, "DISPUTED",
            note="eSewa server lookup reported a refund but identity, amount, or merchant did not match.",
        )
    if (
        lookup_status != "COMPLETE" or lookup_amount_paisa != intent.amount_paisa
        or lookup_merchant != settings.ESEWA_MERCHANT_CODE or not reference
    ):
        return _transition(
            db, intent, "DISPUTED",
            note="eSewa server lookup did not confirm callback status, amount, merchant and reference.",
        )
    return _record_verified_payment(db, intent, provider_reference=reference)


def finalize_khalti_callback(
    db: Session, *, public_ref: str, pidx: str
) -> models.OpPaymentIntent:
    intent = db.query(models.OpPaymentIntent).filter_by(public_ref=public_ref).one_or_none()
    if intent is None:
        raise ValueError("Payment intent not found.")
    if intent.provider != "khalti" or intent.provider_payment_id != pidx:
        raise ValueError("Khalti payment ID does not match this intent.")
    lookup = nepal_payments.khalti_lookup(pidx=pidx)
    lookup_pidx = str(lookup.get("pidx", ""))
    status = str(lookup.get("status", ""))
    reference = str(lookup.get("transaction_id", ""))
    try:
        amount_paisa = int(lookup.get("total_amount", -1))
    except (TypeError, ValueError):
        amount_paisa = -1
    if lookup_pidx != pidx:
        return _transition(db, intent, "DISPUTED", note="Khalti lookup returned a different payment ID.")
    if lookup.get("refunded") is True:
        if intent.status == "VERIFIED":
            raise PaymentReconciliationRequired(
                "Khalti reports a refund for a previously verified payment; owner reconciliation is required."
            )
        return _nonverified_state(db, intent, "REFUNDED", "Khalti lookup reports a refunded payment.")
    if status != "Completed":
        return _nonverified_state(db, intent, status, "Khalti lookup did not confirm a completed payment.")
    if amount_paisa != intent.amount_paisa or not reference:
        return _transition(db, intent, "DISPUTED", note="Khalti lookup amount or transaction reference mismatched this intent.")
    return _record_verified_payment(db, intent, provider_reference=reference)
