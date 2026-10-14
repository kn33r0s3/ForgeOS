"""Minimal repair-shop vertical slice built on existing ForgeOS primitives.

This module adds only customer/work-item context. Decisions, experiments/actions,
evidence, outcomes, learning, and product revenue remain existing ForgeOS records.
No external customer contact or payment is performed here directly;
approve_customer_status only enqueues an SMS delivery in the integration outbox
(dispatched by a separate worker, never implicitly).
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app import evidence_source, models
from app.models import utcnow
from app.services import execution_engine


WORK_ITEM_STATES = {
    "INTAKE", "EVIDENCE_CAPTURED", "TRIAGE_PROPOSED", "APPROVAL_REQUIRED",
    "APPROVED", "STATUS_DRAFT", "STATUS_APPROVED", "CUSTOMER_RESPONDED",
    "PAYMENT_PENDING", "PAYMENT_CONFIRMED", "PAYMENT_FAILED", "OUTCOME_RECORDED",
    "LEARNING_RECORDED", "CLOSED",
}




def _scope(value: str) -> str:
    value = value.upper()
    if value not in {"REAL", "SANDBOX"}:
        raise ValueError("data_scope must be REAL or SANDBOX")
    return value


def _item(db: Session, work_item_id: int) -> models.RepairWorkItem:
    item = db.get(models.RepairWorkItem, work_item_id)
    if not item:
        raise ValueError("Repair work item not found")
    return item


def _transition(
    db: Session,
    item: models.RepairWorkItem,
    next_state: str,
    *,
    event_type: str,
    actor: str,
    reason: Optional[str] = None,
    evidence_ids: Optional[list[int]] = None,
    metadata: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
) -> models.WorkItemEvent:
    if next_state not in WORK_ITEM_STATES:
        raise ValueError(f"Unknown work-item state: {next_state}")
    if idempotency_key:
        existing = db.query(models.WorkItemEvent).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing
    event = models.WorkItemEvent(
        work_item_id=item.id,
        actor=actor,
        event_type=event_type,
        previous_state=item.status,
        next_state=next_state,
        reason=reason,
        evidence_ids=",".join(str(value) for value in evidence_ids or []) or None,
        metadata_json=metadata,
        idempotency_key=idempotency_key,
        created_at=utcnow(),
    )
    item.status = next_state
    item.updated_at = utcnow()
    db.add(event)
    db.flush()
    return event


def create_work_item(
    db: Session,
    *,
    customer_name: str,
    contact_identifier: Optional[str],
    consent_state: str,
    asset_label: str,
    reported_problem: str,
    data_scope: str = "SANDBOX",
    actor: str = "operator",
    idempotency_key: Optional[str] = None,
) -> models.RepairWorkItem:
    scope = _scope(data_scope)
    if not customer_name.strip() or not asset_label.strip() or not reported_problem.strip():
        raise ValueError("customer_name, asset_label, and reported_problem are required")
    if idempotency_key:
        existing_event = db.query(models.WorkItemEvent).filter_by(idempotency_key=idempotency_key).first()
        if existing_event:
            return _item(db, existing_event.work_item_id)
    customer = models.Customer(
        name=customer_name.strip(),
        contact_identifier=contact_identifier.strip() if contact_identifier else None,
        consent_state=consent_state,
        data_scope=scope,
    )
    item = models.RepairWorkItem(
        customer=customer,
        asset_label=asset_label.strip(),
        reported_problem=reported_problem.strip(),
        status="INTAKE",
        data_scope=scope,
    )
    db.add(item)
    db.flush()
    _transition(
        db, item, "INTAKE", event_type="WORK_ITEM_CREATED", actor=actor,
        reason="Reported problem captured as an observed intake record.",
        metadata={"epistemic_state": "OBSERVED", "data_scope": scope},
        idempotency_key=idempotency_key,
    )
    db.commit()
    db.refresh(item)
    return item


def attach_evidence(
    db: Session,
    work_item_id: int,
    *,
    content: str,
    source: str = "manual",
    data_scope: str = "SANDBOX",
    actor: str = "operator",
    idempotency_key: Optional[str] = None,
) -> models.Evidence:
    item = _item(db, work_item_id)
    scope = _scope(data_scope)
    if item.data_scope != scope:
        raise ValueError("Evidence scope must match work-item scope")
    if idempotency_key:
        event = db.query(models.WorkItemEvent).filter_by(idempotency_key=idempotency_key).first()
        if event and event.evidence_ids:
            return db.get(models.Evidence, int(event.evidence_ids.split(",")[0]))
    evidence = models.Evidence(
        content=content.strip(), source=source, direction="supports",
        provenance=json.dumps({"work_item_id": item.id, "actor": actor, "scope": scope}),
        collection_status="collected",
        idempotency_key=(
            f"repair-work-item-evidence:{item.id}:{idempotency_key}"
            if idempotency_key else None
        ),
    )
    db.add(evidence)
    db.flush()
    relationship = models.EvidenceRelationship(
        evidence_id=evidence.id,
        relation_type="supports",
        relation_key=f"repair_work_item:{item.id}:evidence:{evidence.id}",
        idempotency_key=f"repair-work-item-evidence-link:{item.id}:{evidence.id}",
    )
    db.add(relationship)
    _transition(
        db, item, "EVIDENCE_CAPTURED", event_type="EVIDENCE_ATTACHED", actor=actor,
        reason="Evidence captured with local provenance.", evidence_ids=[evidence.id],
        metadata={"epistemic_state": "OBSERVED", "source": source},
        idempotency_key=idempotency_key,
    )
    db.commit()
    db.refresh(evidence)
    return evidence


def create_triage(
    db: Session,
    work_item_id: int,
    *,
    rationale: str,
    expected_outcome: str,
    confidence: float,
    actor: str = "operator",
    idempotency_key: Optional[str] = None,
) -> dict:
    item = _item(db, work_item_id)
    if item.status not in {"INTAKE", "EVIDENCE_CAPTURED"}:
        raise ValueError("Triage requires an intake or evidence-captured work item")
    if idempotency_key:
        existing = db.query(models.WorkItemEvent).filter_by(idempotency_key=idempotency_key).first()
        if existing and item.decision_id:
            return {"decision": db.get(models.Decision, item.decision_id), "experiment": db.get(models.Experiment, item.experiment_id)}
    opportunity = models.Opportunity(
        problem=item.reported_problem,
        target_customer="independent repair shop",
        solution="auditable intake, status, and payment workflow",
        business_model="service",
        offer="one repair-shop work item workflow",
        validation_plan="Complete one real paid workflow and measure time saved or communication quality.",
        status="validating",
        uncertainty=100.0,
    )
    db.add(opportunity)
    db.flush()
    decision = models.Decision(
        opportunity_id=opportunity.id,
        title="Repair-shop triage decision",
        rationale=rationale,
        expected_outcome=expected_outcome,
        confidence_at_decision=confidence,
        status="proposed",
    )
    db.add(decision)
    db.flush()
    action = execution_engine.create_action(
        db,
        opportunity_id=opportunity.id,
        action_type="service_delivery",
        description="Perform the approved repair-shop workflow and record reality.",
        expected_result=expected_outcome,
        required_inputs="Human operator approval and real work-item evidence",
        domain="revenue",
        data_scope=item.data_scope,
    )
    if not action:
        raise ValueError("Unable to create the existing ForgeOS execution action")
    item.opportunity_id = opportunity.id
    item.decision_id = decision.id
    item.experiment_id = action.id
    _transition(
        db, item, "APPROVAL_REQUIRED", event_type="TRIAGE_PROPOSED", actor=actor,
        reason=rationale, metadata={"epistemic_state": "INFERRED", "confidence": confidence},
        idempotency_key=idempotency_key,
    )
    db.commit()
    db.refresh(decision)
    db.refresh(action)
    return {"decision": decision, "experiment": action}


def propose_customer_status(db: Session, work_item_id: int, *, body: str, actor: str = "operator") -> models.CustomerCommunication:
    item = _item(db, work_item_id)
    if item.status not in {"APPROVAL_REQUIRED", "APPROVED", "CUSTOMER_RESPONDED"}:
        raise ValueError("Customer status requires a triage decision")
    communication = models.CustomerCommunication(work_item_id=item.id, body=body.strip(), status="DRAFT")
    db.add(communication)
    _transition(db, item, "STATUS_DRAFT", event_type="CUSTOMER_STATUS_DRAFTED", actor=actor, reason="Prepared for human review.")
    db.commit()
    db.refresh(communication)
    return communication


def approve_customer_status(db: Session, communication_id: int, *, actor: str = "operator") -> models.CustomerCommunication:
    communication = db.get(models.CustomerCommunication, communication_id)
    if not communication:
        raise ValueError("Customer communication not found")
    if communication.status != "DRAFT":
        raise ValueError("Only a draft communication can be approved")
    
    item = _item(db, communication.work_item_id)
    if not item.customer.contact_identifier:
        raise ValueError("Cannot approve delivery: customer has no contact_identifier (phone number)")

    communication.status = "APPROVED"
    
    from app.services import integration_outbox
    delivery = integration_outbox.enqueue(
        db,
        integration_name="twilio",
        operation="send_sms",
        idempotency_key=f"repair_communication_{communication.id}",
        request={"to": item.customer.contact_identifier, "body": communication.body}
    )
    communication.integration_delivery_id = delivery.id
    
    _transition(db, item, "STATUS_APPROVED", event_type="CUSTOMER_STATUS_APPROVED", actor=actor, reason="Approved and queued for external SMS delivery.")
    db.commit()
    db.refresh(communication)
    return communication


def record_customer_response(db: Session, communication_id: int, *, accepted: bool, response: str, actor: str = "operator") -> models.CustomerCommunication:
    communication = db.get(models.CustomerCommunication, communication_id)
    if not communication:
        raise ValueError("Customer communication not found")
    if communication.status not in {"APPROVED", "SENT"}:
        raise ValueError("Customer response requires an approved or sent communication")
    communication.status = "CUSTOMER_RESPONDED"
    communication.customer_response = response.strip()
    item = _item(db, communication.work_item_id)
    _transition(db, item, "CUSTOMER_RESPONDED", event_type="CUSTOMER_RESPONDED", actor=actor, reason="Response entered by operator; acceptance is not payment.", metadata={"accepted": accepted})
    db.commit()
    db.refresh(communication)
    return communication


def record_verified_payment(
    db: Session,
    work_item_id: int,
    *,
    amount: float,
    unit: str,
    provider: str,
    provider_reference: str,
    actor: str = "operator",
    data_scope: str = "SANDBOX",
    idempotency_key: Optional[str] = None,
) -> models.Outcome:
    item = _item(db, work_item_id)
    scope = _scope(data_scope)
    if item.data_scope != scope:
        raise ValueError("Payment scope must match work-item scope")
    if scope == "REAL":
        raise ValueError(
            "REAL repair-shop payments must use the existing provider-verified payment-intent "
            "and fulfillment path; a manually supplied provider reference cannot establish verified revenue."
        )
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Payment amount must be a positive finite amount")
    if not provider.strip() or not provider_reference.strip():
        raise ValueError("Verified payment requires provider and provider_reference")
    if idempotency_key:
        existing = db.query(models.WorkItemEvent).filter_by(idempotency_key=idempotency_key).first()
        if existing and existing.metadata_json and existing.metadata_json.get("outcome_id"):
            return db.get(models.Outcome, existing.metadata_json["outcome_id"])
    outcome = models.Outcome(
        action_id=item.action_id,
        experiment_id=item.experiment_id,
        decision_id=item.decision_id,
        outcome_type="ACTUAL_REVENUE",
        actual_value=amount,
        unit=unit,
        source=provider,
        verification_state="VERIFIED",
        notes=f"Provider reference: {provider_reference}; entered by {actor}.",
        data_scope=scope,
        source_kind=(
            evidence_source.REAL if scope == "REAL" else evidence_source.MOCK
        ),
    )
    db.add(outcome)
    db.flush()
    item.status = "PAYMENT_CONFIRMED"
    _transition(
        db, item, "PAYMENT_CONFIRMED", event_type="PAYMENT_CONFIRMED", actor=actor,
        reason="Actual payment evidence recorded; this is not a test transaction.",
        metadata={"outcome_id": outcome.id, "provider": provider, "provider_reference": provider_reference, "epistemic_state": "ACTUAL"},
        idempotency_key=idempotency_key,
    )
    db.commit()
    db.refresh(outcome)
    return outcome




def _payment_intent_snapshot(intent: models.OpPaymentIntent) -> dict:
    """Expose non-sensitive status fields for a linked canonical payment attempt."""
    return {
        "id": intent.id,
        "product_id": intent.product_id,
        "provider": intent.provider,
        "status": intent.status,
        "amount_paisa": intent.amount_paisa,
        "currency": intent.currency,
        "data_scope": intent.data_scope,
        "fulfilled": intent.fulfilled_at is not None,
        "fulfilled_at": intent.fulfilled_at.isoformat() if intent.fulfilled_at else None,
        "outcome_id": intent.outcome_id,
    }


def _payment_intent_link_key(payment_intent_id: int) -> str:
    return f"repair-payment-intent-link:{payment_intent_id}"


def _payment_intent_fulfillment_key(payment_intent_id: int) -> str:
    return f"repair-payment-intent-fulfilled:{payment_intent_id}"


def link_verified_payment_intent(
    db: Session,
    work_item_id: int,
    payment_intent_id: int,
    *,
    actor: str = "operator",
) -> dict:
    """Link a REAL repair work item to an existing, provider-verified payment intent.

    This operation never initiates checkout or writes revenue. The existing
    OpPaymentIntent and Outcome remain canonical; WorkItemEvent stores only the
    relationship and its audit trail.
    """
    item = _item(db, work_item_id)
    if item.data_scope != "REAL":
        raise ValueError("Only REAL repair work items can link REAL payment intents.")

    intent = db.get(models.OpPaymentIntent, payment_intent_id)
    if intent is None:
        raise ValueError("Payment intent not found.")
    if intent.data_scope != "REAL":
        raise ValueError("Only REAL provider payment intents can be linked to repair work.")
    if intent.status != "VERIFIED":
        raise ValueError("Only provider-verified payment intents can be linked to a repair work item.")
    if not intent.provider_reference:
        raise ValueError("Verified payment intent has no provider transaction reference.")

    link_key = _payment_intent_link_key(intent.id)
    existing_link = db.query(models.WorkItemEvent).filter_by(idempotency_key=link_key).one_or_none()
    if existing_link is not None and existing_link.work_item_id != item.id:
        raise ValueError("Payment intent is already linked to another repair work item.")

    product = db.get(models.Product, intent.product_id)
    if product is None or product.data_scope != "REAL":
        raise ValueError("Payment intent must reference an existing REAL product.")
    if item.product_id not in (None, product.id):
        raise ValueError("Repair work item is already linked to a different product.")
    if item.opportunity_id is None or item.opportunity_id != product.opportunity_id:
        raise ValueError("Payment product must belong to the repair work item's canonical opportunity.")
    if item.status in {"INTAKE", "EVIDENCE_CAPTURED", "TRIAGE_PROPOSED"}:
        raise ValueError("Repair work item must be triaged before a payment intent can be linked.")

    if existing_link is not None:
        metadata = existing_link.metadata_json or {}
        if metadata.get("payment_intent_id") != intent.id or metadata.get("product_id") != product.id:
            raise ValueError("Existing payment-intent link provenance conflicts with canonical records.")
    else:
        # Do not attach another unresolved attempt to the same work item. Only a
        # provider-confirmed FAILED/CANCELLED attempt permits a fresh intent;
        # disputed/refunded states require reconciliation.
        prior_links = (
            db.query(models.WorkItemEvent)
            .filter_by(work_item_id=item.id, event_type="PAYMENT_INTENT_LINKED")
            .order_by(models.WorkItemEvent.id.asc())
            .all()
        )
        for prior_event in prior_links:
            prior_metadata = prior_event.metadata_json or {}
            prior_id = prior_metadata.get("payment_intent_id")
            if not isinstance(prior_id, int):
                raise ValueError("Existing payment-intent link has incomplete provenance; reconcile before retrying.")
            prior_intent = db.get(models.OpPaymentIntent, prior_id)
            if prior_intent is None:
                raise ValueError("A linked payment-intent record is missing; reconcile before linking another attempt.")
            if prior_intent.fulfilled_at is not None or prior_intent.status not in {"FAILED", "CANCELLED"}:
                raise ValueError("Another payment attempt is unresolved or verified for this work item.")

    item.product_id = product.id
    if existing_link is None:
        next_state = (
            item.status
            if item.status in {"OUTCOME_RECORDED", "LEARNING_RECORDED", "CLOSED"}
            else "PAYMENT_PENDING"
        )
        existing_link = _transition(
            db,
            item,
            next_state,
            event_type="PAYMENT_INTENT_LINKED",
            actor=actor,
            reason="Linked to the canonical provider-verified payment intent; revenue still requires owner-confirmed fulfillment.",
            metadata={
                "payment_intent_id": intent.id,
                "product_id": product.id,
                "provider": intent.provider,
                "provider_status": intent.status,
                "amount_paisa": intent.amount_paisa,
                "currency": intent.currency,
                "data_scope": "REAL",
                "epistemic_state": "VERIFIED_PAYMENT_PENDING_FULFILLMENT",
            },
            idempotency_key=link_key,
        )

    # Recovery case: fulfillment may have occurred before this relationship was
    # repaired. Bring the work-item audit current without duplicating revenue.
    if intent.fulfilled_at is not None:
        record_provider_payment_fulfillment(db, intent.id)
    db.commit()
    db.refresh(item)
    return {
        "work_item_id": item.id,
        "work_item_status": item.status,
        "link_event_id": existing_link.id,
        "payment_intent": _payment_intent_snapshot(intent),
    }


def record_provider_payment_fulfillment(
    db: Session,
    payment_intent_id: int,
) -> models.WorkItemEvent | None:
    """Mirror canonical fulfillment into a linked work item's audit, never revenue."""
    intent = db.get(models.OpPaymentIntent, payment_intent_id)
    if intent is None:
        raise RuntimeError("Linked provider payment intent disappeared during fulfillment.")
    link_event = (
        db.query(models.WorkItemEvent)
        .filter_by(idempotency_key=_payment_intent_link_key(intent.id))
        .one_or_none()
    )
    if link_event is None:
        return None
    link_metadata = link_event.metadata_json or {}
    if link_metadata.get("payment_intent_id") != intent.id:
        raise RuntimeError("Repair work-item payment link does not match its idempotency identity.")

    item = db.get(models.RepairWorkItem, link_event.work_item_id)
    product = db.get(models.Product, intent.product_id)
    outcome = db.get(models.Outcome, intent.outcome_id) if intent.outcome_id else None
    if item is None or product is None or outcome is None:
        raise RuntimeError("Linked provider fulfillment is missing its work item, product, or canonical Outcome.")
    if (
        intent.status != "VERIFIED"
        or intent.data_scope != "REAL"
        or intent.fulfilled_at is None
        or not intent.provider_reference
    ):
        raise RuntimeError("Repair work-item completion requires a provider-verified and owner-fulfilled REAL intent.")
    if (
        item.data_scope != "REAL"
        or item.product_id != product.id
        or item.opportunity_id != product.opportunity_id
        or product.data_scope != "REAL"
        or link_metadata.get("product_id") != product.id
    ):
        raise RuntimeError("Linked repair work item does not match the canonical payment product/opportunity.")

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
        raise RuntimeError("Repair fulfillment refuses an Outcome that differs from canonical verified payment evidence.")

    fulfillment_key = _payment_intent_fulfillment_key(intent.id)
    existing = db.query(models.WorkItemEvent).filter_by(idempotency_key=fulfillment_key).one_or_none()
    if existing is not None:
        metadata = existing.metadata_json or {}
        if (
            existing.work_item_id != item.id
            or metadata.get("payment_intent_id") != intent.id
            or metadata.get("outcome_id") != outcome.id
        ):
            raise RuntimeError("Existing repair payment-fulfillment event conflicts with canonical payment records.")
        return existing

    next_state = item.status
    if item.status in {
        "APPROVAL_REQUIRED", "APPROVED", "STATUS_DRAFT", "STATUS_APPROVED",
        "CUSTOMER_RESPONDED", "PAYMENT_PENDING", "PAYMENT_FAILED",
    }:
        next_state = "PAYMENT_CONFIRMED"
    return _transition(
        db,
        item,
        next_state,
        event_type="PAYMENT_INTENT_FULFILLED",
        actor="payment_intent_engine",
        reason="The canonical payment intent is provider-verified and owner-confirmed fulfilled; linked revenue remains in the existing Outcome ledger.",
        metadata={
            "payment_intent_id": intent.id,
            "product_id": product.id,
            "outcome_id": outcome.id,
            "provider": intent.provider,
            "amount_paisa": intent.amount_paisa,
            "currency": intent.currency,
            "fulfilled_at": intent.fulfilled_at.isoformat(),
            "data_scope": "REAL",
            "epistemic_state": "ACTUAL",
        },
        idempotency_key=fulfillment_key,
    )


def record_work_outcome(
    db: Session,
    work_item_id: int,
    *,
    actual: str,
    success: Optional[bool],
    source: str,
    actor: str = "operator",
) -> tuple[models.Outcome, models.LearningEvent]:
    item = _item(db, work_item_id)
    outcome = models.Outcome(
        action_id=item.action_id,
        experiment_id=item.experiment_id,
        decision_id=item.decision_id,
        outcome_type="QUALITATIVE",
        qualitative_result=actual.strip(),
        source=source,
        success=success,
        verification_state="REPORTED",
        data_scope=item.data_scope,
    )
    db.add(outcome)
    db.flush()
    learning = models.LearningEvent(
        experiment_id=item.experiment_id,
        decision_id=item.decision_id,
        opportunity_id=item.opportunity_id,
        prediction="The approved repair-shop workflow would deliver the expected customer/status outcome.",
        actual=actual.strip(),
        lesson="Compare the expected workflow value with the recorded repair-shop outcome before changing the next decision.",
        error_type="confirmed" if success is True else ("qualitative_miss" if success is False else "unassessed"),
        data_scope=item.data_scope,
        source_kind=outcome.source_kind,
    )
    db.add(learning)
    _transition(db, item, "LEARNING_RECORDED", event_type="OUTCOME_AND_LEARNING_RECORDED", actor=actor, reason="Actual outcome recorded and linked learning event created.", metadata={"outcome_id": outcome.id, "learning_event_id": learning.id, "epistemic_state": "ACTUAL"})
    db.commit()
    db.refresh(outcome)
    db.refresh(learning)
    return outcome, learning


def get_work_item_detail(db: Session, work_item_id: int) -> dict:
    item = _item(db, work_item_id)
    events = sorted(item.events, key=lambda event: (event.created_at, event.id))
    evidence_ids = []
    for event in events:
        if event.evidence_ids:
            evidence_ids.extend(int(value) for value in event.evidence_ids.split(",") if value)
    evidence = db.query(models.Evidence).filter(models.Evidence.id.in_(sorted(set(evidence_ids)))).all() if evidence_ids else []

    # Provider revenue is product-linked. Include it in this work-item view only
    # when the canonical fulfillment event explicitly references the Outcome.
    outcomes = (
        db.query(models.Outcome)
        .filter(models.Outcome.experiment_id == item.experiment_id)
        .order_by(models.Outcome.id.asc())
        .all()
        if item.experiment_id else []
    )
    outcome_ids = {row.id for row in outcomes}
    payment_intents = []
    seen_intents = set()
    for event in events:
        metadata = event.metadata_json or {}
        if event.event_type == "PAYMENT_INTENT_FULFILLED" and metadata.get("outcome_id") is not None:
            try:
                outcome_id = int(metadata["outcome_id"])
            except (TypeError, ValueError):
                outcome_id = None
            if outcome_id is not None and outcome_id not in outcome_ids:
                outcome = db.get(models.Outcome, outcome_id)
                if outcome is not None:
                    outcomes.append(outcome)
                    outcome_ids.add(outcome.id)
        if event.event_type == "PAYMENT_INTENT_LINKED":
            try:
                intent_id = int(metadata["payment_intent_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if intent_id in seen_intents:
                continue
            intent = db.get(models.OpPaymentIntent, intent_id)
            if intent is not None:
                payment_intents.append(_payment_intent_snapshot(intent))
                seen_intents.add(intent_id)

    return {
        "work_item": item,
        "customer": item.customer,
        "events": events,
        "communications": sorted(item.communications, key=lambda communication: (communication.created_at, communication.id)),
        "evidence": evidence,
        "decision": db.get(models.Decision, item.decision_id) if item.decision_id else None,
        "experiment": db.get(models.Experiment, item.experiment_id) if item.experiment_id else None,
        "outcomes": outcomes,
        "learning_events": db.query(models.LearningEvent).filter(models.LearningEvent.experiment_id == item.experiment_id).order_by(models.LearningEvent.id.asc()).all() if item.experiment_id else [],
        "payment_intents": payment_intents,
    }


def list_work_items(db: Session, data_scope: str = "SANDBOX") -> list[models.RepairWorkItem]:
    return db.query(models.RepairWorkItem).filter(models.RepairWorkItem.data_scope == _scope(data_scope)).order_by(models.RepairWorkItem.created_at.desc()).all()
