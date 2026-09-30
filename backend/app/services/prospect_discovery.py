"""Opportunity-scoped, fail-closed prospect-source eligibility handoff."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import source_clearance_registry, world_graph


PROSPECT_DISCOVERY_REQUIREMENT = "authorized_prospect_discovery"
MAX_CANDIDATES = 10
_DEFAULT_QUALIFICATION_QUESTIONS = (
    "What source evidence establishes that the entity fits the scoped business profile?",
    "What evidence establishes that the entity experiences the Need?",
    "What evidence identifies the relevant decision role without inferring it from an entity name?",
    "What direct response evidence, if any, supports interest? Discovery alone cannot answer this.",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _testable_context(
    db: Session, opportunity_id: int
) -> tuple[
    models.Opportunity,
    models.SubstrateEntity,
    models.SubstrateEntity,
    models.OpportunityEvent,
    dict[str, Any],
]:
    opportunity = db.get(models.Opportunity, opportunity_id)
    if opportunity is None:
        raise ValueError("Opportunity does not exist")

    latest_assessment = (
        db.query(models.OpportunityEvent)
        .filter_by(
            opportunity_id=opportunity.id,
            event_type="economic_validation_assessed",
        )
        .order_by(models.OpportunityEvent.id.desc())
        .first()
    )
    if latest_assessment is None:
        raise ValueError("prospect discovery requires an economic assessment for this Opportunity")
    try:
        assessment = json.loads(latest_assessment.details or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("latest Opportunity economic assessment is unreadable") from exc
    if assessment.get("assessment_state") != "testable":
        raise ValueError("prospect discovery requires a currently testable economic assessment")

    opportunity_entity = world_graph.find_canonical_entity(
        db, "opportunity", opportunity.id, source_system="opportunities"
    )
    need_id = assessment.get("need_id")
    need = db.get(models.SubstrateEntity, need_id) if isinstance(need_id, int) else None
    if (
        opportunity_entity is None
        or need is None
        or need.entity_type != "need"
        or db.query(models.WorldRelation)
        .filter_by(
            from_entity_id=opportunity_entity.id,
            to_entity_id=need.id,
            relation_type="derived_from",
        )
        .first()
        is None
    ):
        raise ValueError("testable economic assessment must retain its substrate Opportunity-to-Need link")
    return opportunity, opportunity_entity, need, latest_assessment, assessment


def evaluate_prospect_discovery_readiness(
    db: Session,
    opportunity_id: int,
    *,
    target_profile: str,
    geographic_scope: str,
    max_candidates: int = 5,
    requested_source_registry_ids: list[str] | None = None,
    qualification_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Audit exact source clearances for an economic hypothesis without fetching.

    The current registry contains no source authorized for
    ``authorized_prospect_discovery``. This operation therefore records a
    bounded source-eligibility result and qualification handoff, never a
    candidate or external request.
    """
    opportunity, opportunity_entity, need, latest_assessment, assessment = _testable_context(
        db, opportunity_id
    )
    profile = " ".join((target_profile or "").split())
    geography = " ".join((geographic_scope or "").split())
    if not profile or len(profile) > 1000:
        raise ValueError("target_profile must contain 1 to 1000 characters")
    if not geography or len(geography) > 160:
        raise ValueError("geographic_scope must contain 1 to 160 characters")
    if (
        isinstance(max_candidates, bool)
        or not isinstance(max_candidates, int)
        or not 1 <= max_candidates <= MAX_CANDIDATES
    ):
        raise ValueError(f"max_candidates must be between 1 and {MAX_CANDIDATES}")

    questions = tuple(
        " ".join(question.split())
        for question in (
            qualification_questions or list(_DEFAULT_QUALIFICATION_QUESTIONS)
        )
        if question and question.strip()
    )
    if len(questions) > 10 or any(len(question) > 300 for question in questions):
        raise ValueError("qualification_questions must contain at most 10 questions of 300 characters")
    if not questions:
        raise ValueError("at least one qualification question is required")

    current_date = datetime.now(timezone.utc).date()
    registry_entries = source_clearance_registry.source_clearances()
    eligible_entries = source_clearance_registry.capabilities_for_requirement(
        PROSPECT_DISCOVERY_REQUIREMENT,
        today=current_date,
    )
    eligible_ids = {entry.registry_id for entry in eligible_entries}
    requested_ids = sorted(set(requested_source_registry_ids or []))
    if len(requested_ids) > 10 or any(
        not isinstance(source_id, str) or not source_id.strip()
        for source_id in requested_ids
    ):
        raise ValueError("requested_source_registry_ids must contain at most 10 non-empty IDs")
    unauthorized_ids = sorted(set(requested_ids) - eligible_ids)
    if unauthorized_ids:
        raise PermissionError(
            "requested source registry entries are not currently cleared for authorized prospect discovery: "
            + ", ".join(unauthorized_ids)
        )

    inventory = []
    for entry in registry_entries:
        current = entry.reviewed_on <= current_date <= entry.valid_through
        authorized_for_purpose = entry.registry_id in eligible_ids
        inventory.append(
            {
                "registry_id": entry.registry_id,
                "collector": entry.collector,
                "url": entry.url,
                "reviewed_on": entry.reviewed_on.isoformat(),
                "valid_through": entry.valid_through.isoformat(),
                "current_clearance": current,
                "authorized_for_prospect_discovery": authorized_for_purpose,
                "allowed_operation": entry.allowed_operation,
                "allowed_need": entry.allowed_need,
                "supports_requirements": list(entry.supports_requirements),
                "categories": list(entry.categories),
                "allowed_fields": list(entry.allowed_fields),
                "minimum_interval_seconds": entry.min_interval_seconds,
                "evidence_references": list(entry.evidence_references),
                "disposition": (
                    "eligible_for_purpose_review"
                    if authorized_for_purpose
                    else (
                        "clearance_expired"
                        if not current
                        else "not_authorized_for_prospect_discovery"
                    )
                ),
            }
        )

    existing_directory = {
        "surfaces": ["/public/providers", "/public/services"],
        "disposition": "excluded_as_prospect_source",
        "reason": (
            "These are provider-authored service listings intended for public service discovery. "
            "public_visible and verified status does not grant consent to repurpose provider contact "
            "fields for buyer/client prospecting."
        ),
        "contact_fields_read": False,
        "external_request_made": False,
    }
    criteria = {
        "opportunity_id": opportunity.id,
        "need_id": need.id,
        "economic_assessment_event_id": latest_assessment.id,
        "target_profile": profile,
        "geographic_scope": geography,
        "max_candidates": max_candidates,
        "requested_source_registry_ids": requested_ids,
        "qualification_questions": list(questions),
    }
    handoff_key = _digest(criteria)
    eligible_sources = [
        {
            "registry_id": entry.registry_id,
            "url": entry.url,
            "collector": entry.collector,
        }
        for entry in eligible_entries
    ]
    if not eligible_sources:
        state = "blocked_no_authorized_source"
        boundary = (
            "Only the reviewed source-clearance registry was checked. No source data was queried; "
            "this result does not establish that no prospects exist in the world."
        )
    else:
        state = "blocked_no_prospect_adapter"
        boundary = (
            "A source is purpose-cleared but no prospect-specific adapter is implemented; "
            "no source data was queried."
        )
    source_snapshot_key = _digest(inventory)
    payload = {
        "discovery_state": state,
        "opportunity_id": opportunity.id,
        "opportunity_entity_id": opportunity_entity.id,
        "need_id": need.id,
        "economic_assessment_event_id": latest_assessment.id,
        "economic_assessment_state": assessment["assessment_state"],
        "criteria": criteria,
        "bounded_search": {
            "maximum_candidates": max_candidates,
            "geographic_scope": geography,
            "source_requirement": PROSPECT_DISCOVERY_REQUIREMENT,
            "eligible_sources": eligible_sources,
            "source_registry_inventory": inventory,
            "source_data_queried": False,
            "external_requests_made": 0,
        },
        "existing_directory_review": existing_directory,
        "candidate_entity_ids": [],
        "candidate_count": 0,
        "potential_prospect_count": 0,
        "qualification_handoff": {
            "state": "blocked_before_candidate",
            "qualification_questions": list(questions),
            "qualification_evidence_needed": [
                "source-attributed evidence establishing the entity's relevance to this Opportunity and Need",
                "identity corroboration before any identity promotion",
                "separate evidence for need fit and decision-role qualification",
            ],
            "qualification_started": False,
            "interested_party_created": False,
            "customer_created": False,
            "outreach_eligible": False,
            "outreach_authorization_required": True,
            "outreach_authorized": False,
            "action_created": False,
            "authorization_path": [
                "POST /experiments/{experiment_id}/authorize",
                "POST /experiments/{experiment_id}/action",
                "POST /experiments/{experiment_id}/action/approve",
                "POST /experiments/{experiment_id}/action/execute",
            ],
        },
        "inference_boundary": boundary,
    }
    key = (
        f"prospect-discovery-evaluation:{opportunity.id}:"
        f"{handoff_key}:{source_snapshot_key}"
    )
    world_graph.seed_core_types(db)
    event = world_graph.create_event(
        db,
        event_type="prospect_discovery_evaluated",
        entity_id=opportunity_entity.id,
        source="prospect_discovery_source_audit",
        payload=payload,
        idempotency_key=key,
    )
    evidence = world_graph.create_evidence(
        db,
        subject_kind="entity",
        subject_id=opportunity_entity.id,
        claim=(
            "The current configured source-clearance registry contains no active source "
            "authorized for this Opportunity's prospect-discovery purpose."
            if state == "blocked_no_authorized_source"
            else (
                "A currently cleared prospect source exists, but no matching prospect adapter "
                "was executed by this readiness audit."
            )
        ),
        support_level="possible",
        source="source_clearance_registry",
        provenance={
            "source_registry_id": "runtime_source_clearances",
            "source_reviewed_at": event.occurred_at.replace(
                tzinfo=timezone.utc
            ).isoformat(),
            "source_data_queried": False,
            "external_requests_made": 0,
            "opportunity_id": opportunity.id,
            "opportunity_entity_id": opportunity_entity.id,
            "need_id": need.id,
            "economic_assessment_event_id": latest_assessment.id,
            "criteria": criteria,
            "eligible_source_registry_ids": sorted(eligible_ids),
            "reviewed_source_registry_ids": [
                entry["registry_id"] for entry in inventory
            ],
            "source_scope_and_restrictions": inventory,
            "existing_directory_review": existing_directory,
            "event_idempotency_key": key,
            "inference_boundary": boundary,
        },
        confidence=0.25,
        idempotency_key=f"{key}:evidence",
    )
    db.commit()
    return {
        "event_id": event.id,
        "evaluated_at": event.occurred_at.replace(tzinfo=timezone.utc).isoformat(),
        "evidence_id": evidence.id,
        "opportunity_id": opportunity.id,
        "need_id": need.id,
        **payload,
    }
