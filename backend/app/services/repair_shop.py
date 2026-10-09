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
from typing import Optional

from sqlalchemy.orm import Session

from app import models
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
    )
    db.add(learning)
    _transition(db, item, "LEARNING_RECORDED", event_type="OUTCOME_AND_LEARNING_RECORDED", actor=actor, reason="Actual outcome recorded and linked learning event created.", metadata={"outcome_id": outcome.id, "learning_event_id": learning.id, "epistemic_state": "ACTUAL"})
    db.commit()
    db.refresh(outcome)
    db.refresh(learning)
    return outcome, learning


def get_work_item_detail(db: Session, work_item_id: int) -> dict:
    item = _item(db, work_item_id)
    evidence_ids = []
    for event in item.events:
        if event.evidence_ids:
            evidence_ids.extend(int(value) for value in event.evidence_ids.split(",") if value)
    evidence = db.query(models.Evidence).filter(models.Evidence.id.in_(sorted(set(evidence_ids)))).all() if evidence_ids else []
    return {
        "work_item": item,
        "customer": item.customer,
        "events": sorted(item.events, key=lambda event: (event.created_at, event.id)),
        "communications": sorted(item.communications, key=lambda communication: (communication.created_at, communication.id)),
        "evidence": evidence,
        "decision": db.get(models.Decision, item.decision_id) if item.decision_id else None,
        "experiment": db.get(models.Experiment, item.experiment_id) if item.experiment_id else None,
        "outcomes": db.query(models.Outcome).filter(models.Outcome.experiment_id == item.experiment_id).order_by(models.Outcome.id.asc()).all() if item.experiment_id else [],
        "learning_events": db.query(models.LearningEvent).filter(models.LearningEvent.experiment_id == item.experiment_id).order_by(models.LearningEvent.id.asc()).all() if item.experiment_id else [],
    }


def list_work_items(db: Session, data_scope: str = "SANDBOX") -> list[models.RepairWorkItem]:
    return db.query(models.RepairWorkItem).filter(models.RepairWorkItem.data_scope == _scope(data_scope)).order_by(models.RepairWorkItem.created_at.desc()).all()
