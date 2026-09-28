"""Evidence-bounded economic assessment over existing Opportunity records."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import world_graph


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def assess_need_economics(
    db: Session,
    need_id: int,
    *,
    solution_hypothesis: str,
    capability_id: int | None = None,
    cost_assumption: float | None = None,
    price_assumption: float | None = None,
    evidence_by_assumption: dict[str, list[int]] | None = None,
    fulfillment_constraints: list[str] | None = None,
    unresolved_uncertainties: list[str] | None = None,
    experiment_definition: str,
    experiment_tests_willingness_to_pay: bool,
) -> dict[str, Any]:
    """Record a hypothesis-grade assessment; never creates or executes an Action.

    ``testable`` means a concrete, evidence-referenced test is specified. It
    does not mean the market, capability fit, or willingness to pay is proven.
    """
    need = db.get(models.SubstrateEntity, need_id)
    if need is None or need.entity_type != "need":
        raise ValueError("economic assessment requires an existing Need entity")

    attributes = json.loads(need.attributes or "{}")
    if not isinstance(attributes, dict):
        raise ValueError("Need attributes must be an object")
    unresolved_need = attributes.get("unresolved_questions") or []
    need_understood = (
        attributes.get("epistemic_state") == "hypothesized"
        and not unresolved_need
        and bool(attributes.get("desired_outcome"))
    )

    search_event = (
        db.query(models.WorldEvent)
        .filter_by(entity_id=need.id, event_type="capability_search_performed")
        .order_by(models.WorldEvent.occurred_at.desc(), models.WorldEvent.id.desc())
        .first()
    )
    capability = db.get(models.ForgeCapability, capability_id) if capability_id else None
    capability_active = bool(
        capability is not None
        and capability.status == "active"
        and capability.test_ref
    )

    assumptions = {
        key: sorted({int(evidence_id) for evidence_id in values})
        for key, values in (evidence_by_assumption or {}).items()
    }
    allowed_assumptions = {"capability_fit", "cost", "price", "demand"}
    if set(assumptions) - allowed_assumptions:
        raise ValueError("unsupported economic assumption evidence key")
    evidence_ids = sorted({evidence_id for values in assumptions.values() for evidence_id in values})
    evidence_by_id: dict[int, models.Evidence] = {}
    if evidence_ids:
        evidence_by_id = {
            row.id: row
            for row in db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all()
        }
        missing = sorted(set(evidence_ids) - set(evidence_by_id))
        if missing:
            raise ValueError(f"economic assumption evidence does not exist: {missing}")
        unusable = sorted(
            evidence_id
            for evidence_id, row in evidence_by_id.items()
            if not (row.provenance or row.substrate_provenance)
            or row.support_level in {"unknown", "refuted"}
        )
        if unusable:
            raise ValueError(
                f"economic assumption evidence needs stored provenance and non-refuted support: {unusable}"
            )

    solution = (solution_hypothesis or "").strip()
    experiment = (experiment_definition or "").strip()
    if not solution:
        raise ValueError("solution_hypothesis is required")
    if not experiment:
        raise ValueError("experiment_definition is required")
    for name, value in (("cost_assumption", cost_assumption), ("price_assumption", price_assumption)):
        if value is not None and (value < 0 or not math.isfinite(value)):
            raise ValueError(f"{name} must be finite and nonnegative")

    fit_evidence_ids = assumptions.get("capability_fit", [])
    cost_evidence_ids = assumptions.get("cost", [])
    price_evidence_ids = assumptions.get("price", [])
    unresolved: list[str] = []
    if not need_understood:
        unresolved.append("Need is not sufficiently understood or retains unresolved questions")
    if search_event is None:
        unresolved.append("existing-capability search has not been recorded for this Need")
    if not capability_active:
        unresolved.append("no tested active ForgeCapability is identified")
    elif not fit_evidence_ids:
        unresolved.append("capability fit has no linked evidence reference")
    if cost_assumption is None:
        unresolved.append("cost assumption is unknown")
    elif not cost_evidence_ids:
        unresolved.append("cost assumption has no linked evidence reference")
    if price_assumption is None:
        unresolved.append("price assumption is unknown")
    elif not price_evidence_ids:
        unresolved.append("price assumption has no linked evidence reference")
    if not experiment_tests_willingness_to_pay:
        unresolved.append("proposed experiment does not explicitly test willingness to pay")
    unresolved.extend(
        item.strip()
        for item in (unresolved_uncertainties or [])
        if item and item.strip()
    )
    if not need_understood or search_event is None or not capability_active or not fit_evidence_ids:
        state = "insufficient_evidence"
    elif (
        cost_assumption is not None
        and cost_evidence_ids
        and price_assumption is not None
        and price_evidence_ids
        and experiment_tests_willingness_to_pay
    ):
        state = "testable"
    else:
        state = "economically_uncertain"

    assessment = {
        "assessment_state": state,
        "need_id": need.id,
        "need_identity": need.identity_key,
        "capability_search_event_id": search_event.id if search_event else None,
        "capability_id": capability.id if capability else None,
        "capability_status": capability.status if capability else "unidentified",
        "capability_test_ref": capability.test_ref if capability else None,
        "solution_hypothesis": solution,
        "cost_assumption": {
            "value": cost_assumption,
            "epistemic_status": "estimated" if cost_assumption is not None else "unknown",
            "evidence_ids": cost_evidence_ids,
        },
        "price_assumption": {
            "value": price_assumption,
            "epistemic_status": "estimated" if price_assumption is not None else "unknown",
            "evidence_ids": price_evidence_ids,
        },
        "willingness_to_pay": {
            "status": "unknown",
            "evidence_ids": [],
            "claim_boundary": "No payment or buyer willingness is inferred by this assessment.",
        },
        "capability_fit_evidence_ids": fit_evidence_ids,
        "demand_evidence_ids": assumptions.get("demand", []),
        "evidence_reference_boundary": (
            "Referenced Evidence IDs resolve to stored records with provenance and are not refuted; "
            "semantic support for each assumption has not been independently adjudicated."
        ),
        "fulfillment_constraints": [
            item.strip() for item in (fulfillment_constraints or []) if item and item.strip()
        ],
        "unresolved_uncertainties": list(dict.fromkeys(unresolved)),
        "experiment_definition": experiment,
        "experiment_tests_willingness_to_pay": bool(experiment_tests_willingness_to_pay),
        "authorization_required_before_external_action": True,
        "external_action_authorized": False,
        "action_created": False,
        "assessment_boundary": (
            "Assessment and cited evidence references do not validate capability fit, "
            "market size, buyer status, willingness to pay, fulfillment, or revenue."
        ),
    }
    assessment_key = _digest(assessment)

    world_graph.seed_core_types(db)
    if not need_understood or search_event is None:
        gate_event = world_graph.create_event(
            db,
            event_type="economic_validation_assessed",
            entity_id=need.id,
            source="economic_validation",
            payload=assessment,
            idempotency_key=f"economic-need-gate:{need.id}:{assessment_key}",
        )
        db.commit()
        return {
            "opportunity_id": None,
            "opportunity_event_id": None,
            "gate_event_id": gate_event.id,
            "assessment": assessment,
        }

    opportunity = None
    for prior_event in (
        db.query(models.OpportunityEvent)
        .filter_by(event_type="economic_validation_assessed")
        .order_by(models.OpportunityEvent.id.asc())
        .all()
    ):
        try:
            prior_details = json.loads(prior_event.details or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if prior_details.get("need_id") == need.id:
            opportunity = db.get(models.Opportunity, prior_event.opportunity_id)
            if opportunity is not None:
                break
    if opportunity is None:
        opportunity = models.Opportunity(
            problem=str(attributes.get("desired_outcome") or need.display_name),
            target_customer=None,
            solution=solution,
            business_model=None,
            pricing_idea=None,
            validation_plan=experiment,
            score=0.0,
            status="identified",
            market_confidence=0.0,
            revenue_confidence=0.0,
            uncertainty=100.0,
            estimated_price=price_assumption,
            estimated_startup_cost=cost_assumption,
            expected_value=None,
        )
        db.add(opportunity)
        db.flush()

    event_key = f"economic-assessment:{opportunity.id}:{assessment_key}"
    opportunity_event = (
        db.query(models.OpportunityEvent)
        .filter_by(opportunity_id=opportunity.id, event_key=event_key)
        .one_or_none()
    )
    if opportunity_event is None:
        opportunity_event = models.OpportunityEvent(
            opportunity_id=opportunity.id,
            event_type="economic_validation_assessed",
            event_key=event_key,
            details=json.dumps(assessment, sort_keys=True),
        )
        db.add(opportunity_event)

    opportunity_entity = world_graph.ensure_canonical_entity(
        db,
        "opportunity",
        opportunity.id,
        created_by="economic_validation",
        source_system="opportunities",
    )
    world_graph.create_relation(
        db,
        from_entity_id=opportunity_entity.id,
        to_entity_id=need.id,
        relation_type="derived_from",
        attributes={"need_id": need.id, "opportunity_id": opportunity.id},
        truth_state="hypothesized",
        created_by="economic_validation",
        idempotency_key=f"economic-opportunity-need:{opportunity.id}:{need.id}:v1",
    )
    world_graph.create_event(
        db,
        event_type="economic_validation_assessed",
        entity_id=opportunity_entity.id,
        source="economic_validation",
        payload={"opportunity_id": opportunity.id, **assessment},
        idempotency_key=event_key,
    )
    db.commit()
    return {
        "opportunity_id": opportunity.id,
        "opportunity_event_id": opportunity_event.id,
        "assessment": assessment,
    }
