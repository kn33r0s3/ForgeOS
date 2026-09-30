"""Owner-operated offer preparation over the existing Product substrate.

This is deliberately a hypothesis builder, not a lead, CRM, outreach, or
payment system. It uses capabilities already present in Forge's local tool
registry and leaves delivery, price, value, and authorization questions
explicit for owner review.
"""

from __future__ import annotations

import json
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
    product.approval_status = status
    product.approval_note = (note or "").strip() or None
    product.approved_at = _now() if status == "APPROVED" else None
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
