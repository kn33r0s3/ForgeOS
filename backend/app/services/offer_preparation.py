"""Owner-operated offer preparation over the existing Product substrate.

This is deliberately a hypothesis builder, not a lead, CRM, outreach, or
payment system. It uses capabilities already present in Forge's local tool
registry and leaves delivery, price, value, and authorization questions
explicit for owner review.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.services import product_engine


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _capability_inventory() -> list[dict]:
    # Keep this path lightweight and deterministic. The offline provider is
    # part of the existing Forge runtime and requires no network credential.
    # Optional providers remain unresolved until their own configured path is
    # explicitly selected and checked.
    return [
        {
            "name": "offline-mock",
            "category": "reasoning",
            "status": "currently_available",
            "authorization": "built_in_local_provider",
            "capabilities": ["completion", "fallback", "summarization"],
        }
    ]


def create_offer_draft(
    db: Session,
    *,
    problem: str,
    target_customer: str | None = None,
    data_scope: str = "REAL",
) -> models.Product:
    clean_problem = problem.strip()
    customer = (target_customer or "business experiencing this problem").strip()
    inventory = _capability_inventory()
    available = [item for item in inventory if item["status"] == "currently_available"]
    names = [item["name"] for item in available]
    brief = {
        "problem_statement": clean_problem,
        "target_business": customer,
        "current_workflow": "Unknown; owner must confirm the customer's current process.",
        "proposed_workflow": (
            "Use ForgeOS to structure the problem, apply an available local reasoning "
            "capability, and return an owner-reviewed workflow recommendation."
        ),
        "capabilities_used": available,
        "implementation_scope": [
            "Understand and structure the stated business problem",
            "Produce a bounded workflow recommendation and next-step checklist",
            "Owner manually reviews and performs any customer-facing delivery",
        ],
        "exclusions": [
            "No automatic external outreach",
            "No promise of a customer result, savings, ROI, or payment",
            "No deployment of third-party automation without explicit owner/customer authorization",
        ],
        "assumptions": [
            "The customer can explain the current workflow and desired outcome",
            "The owner can perform or arrange any implementation not already available locally",
        ],
        "delivery_time_estimate": "UNRESOLVED — owner estimate required",
        "cost_assumptions": "UNRESOLVED — no delivery cost has been recorded",
        "price_hypothesis": "UNRESOLVED — do not treat a draft price as WTP evidence",
        "value_hypothesis": "UNRESOLVED — require customer-specific baseline and outcome evidence",
        "unresolved_questions": [
            "What exact workflow should change?",
            "What systems and access may the customer authorize?",
            "What small paid pilot would demonstrate value?",
        ],
        "authorization_requirements": [
            "Owner approval before any external contact or publication",
            "Customer authorization before accessing their systems or data",
        ],
        "next_action": "Owner review: edit the scope, price hypothesis, and delivery estimate before presenting anything.",
        "capability_names": names,
    }
    product = product_engine.create_product(
        db,
        name=f"Owner offer draft: {clean_problem[:120]}",
        offer="Owner-reviewed workflow analysis and implementation plan for the stated business problem.",
        target_customer=customer,
        pricing="UNRESOLVED — owner must set a price hypothesis",
        mvp_scope="Problem understanding, workflow outline, capability match, and manual delivery checklist.",
        hypothesis="A bounded workflow intervention may be useful; customer need, WTP, cost, and outcome remain unverified.",
        launch_state="not_launched",
        data_scope=data_scope,
    )
    product.offer_brief_json = json.dumps(brief, ensure_ascii=False)
    product.approval_status = "PENDING_REVIEW"
    db.commit()
    db.refresh(product)
    return product


def fixed_npr_price_paisa(pricing: str | None) -> int | None:
    """Accept only explicit fixed one-time NPR contracts, never fuzzy price prose."""
    match = re.fullmatch(
        r"\s*NPR\s*([0-9]{1,8})(?:\.([0-9]{1,2}))?\s+one[- ]time\s*",
        pricing or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    rupees = int(match.group(1))
    fraction = (match.group(2) or "").ljust(2, "0")
    amount = rupees * 100 + int(fraction or "0")
    return amount if amount > 0 else None


def _state_event(db: Session, product: models.Product, *, change: str, before: str, after: str) -> None:
    from app.services import world_graph

    world_graph.create_event(
        db,
        event_type="state_changed",
        source="offer_preparation",
        payload={
            "domain": "product",
            "product_id": product.id,
            "change": change,
            "from": before,
            "to": after,
        },
        idempotency_key=f"product:{product.id}:{change}:{uuid.uuid4().hex}",
    )


def prepare_existing_product_for_review(
    db: Session,
    product_id: int,
) -> models.Product | None:
    """Attach an owner-reviewable brief to the existing Product; never duplicate it."""
    product = product_engine.get_product(db, product_id)
    if product is None:
        return None
    if product.data_scope != "REAL":
        raise ValueError("A public offer review requires a REAL-scope product.")
    if product.opportunity_id is None:
        raise ValueError("Link the product to its originating opportunity before review.")
    opportunity = db.get(models.Opportunity, product.opportunity_id)
    if opportunity is None:
        raise ValueError("The originating opportunity no longer exists.")
    if product.launch_state in {"public", "piloting"} or product.status in {"launched", "iterating"}:
        raise ValueError("Pause a launched product before preparing a new review.")
    amount_paisa = fixed_npr_price_paisa(product.pricing)
    if amount_paisa is None:
        raise ValueError('Set a fixed one-time price such as "NPR 5000 one-time" before review.')

    brief = {
        "kind": "existing_product_owner_review",
        "product_id": product.id,
        "opportunity_id": opportunity.id,
        "problem_statement": opportunity.problem,
        "target_customer": product.target_customer or opportunity.target_customer,
        "offer": product.offer,
        "delivery_scope": product.mvp_scope or "UNRESOLVED — owner must define exact delivery scope.",
        "fixed_price": {"currency": "NPR", "amount_paisa": amount_paisa, "billing": "one_time"},
        "price_hypothesis": "An owner-set offer price is not evidence that a customer agreed to pay it.",
        "value_hypothesis": opportunity.economic_evidence_summary or "Customer value remains unverified until a real delivery/outcome is recorded.",
        "exclusions": [
            "No customer is claimed from this brief.",
            "No payment is claimed before provider verification.",
            "No automatic outreach, publication, or fulfillment is authorized by this brief.",
        ],
        "authorization_requirements": [
            "Owner approval before public offer publication.",
            "Customer authorization before accessing their systems or data.",
        ],
        "next_action": "Owner review: confirm offer, exact price, delivery scope, exclusions, and customer-specific promises.",
    }
    prior = product.approval_status
    product.offer_brief_json = json.dumps(brief, ensure_ascii=False, sort_keys=True)
    product.approval_status = "PENDING_REVIEW"
    product.approval_note = None
    product.approved_at = None
    product.updated_at = _now()
    _state_event(db, product, change="offer_review_prepared", before=prior, after="PENDING_REVIEW")
    db.commit()
    db.refresh(product)
    return product


def set_offer_approval(
    db: Session,
    product_id: int,
    *,
    status: str,
    note: str | None = None,
) -> models.Product | None:
    product = product_engine.get_product(db, product_id)
    if product is None:
        return None
    if not product.offer_brief_json:
        raise ValueError("offer approval requires an offer draft")
    previous = product.approval_status
    product.approval_status = status
    product.approval_note = (note or "").strip() or None
    product.approved_at = _now() if status == "APPROVED" else None
    if status != "APPROVED" and product.launch_state == "public":
        product.launch_state = "paused"
        product.status = "validating"
    product.updated_at = _now()
    _state_event(db, product, change="offer_approval_changed", before=previous, after=status)
    db.commit()
    db.refresh(product)
    return product


def brief(product: models.Product) -> dict | None:
    if not product.offer_brief_json:
        return None
    try:
        value = json.loads(product.offer_brief_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
