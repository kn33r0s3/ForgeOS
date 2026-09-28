"""Read-only, evidence-cited synthesis for persisted research plans."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services.research_evidence_assessment import explicit_contradiction_edges

_COMMERCIAL_REQUIREMENTS = frozenset(
    {
        "commercial_validation_gap",
        "customer_pain",
        "buyer_willingness_to_pay",
        "commercial_demand",
        "product_demand",
    }
)
_STANDARD_STATES = frozenset(
    {"supported", "partially_supported", "contradicted", "unresolved", "blocked"}
)


def _provenance(evidence: models.Evidence) -> dict[str, Any]:
    try:
        value = json.loads(evidence.provenance) if evidence.provenance else {}
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _evidence_citation(evidence: models.Evidence) -> dict[str, Any] | None:
    if not evidence.canonical_url:
        return None
    provenance = _provenance(evidence)
    return {
        "evidence_id": evidence.id,
        "source": evidence.source,
        "title": evidence.title,
        "provenance_url": evidence.canonical_url,
        "source_registry_id": provenance.get("source_registry_id"),
        "retrieved_at": (
            evidence.retrieved_at.isoformat() if evidence.retrieved_at else None
        ),
    }


def _matches_qualifications(
    evidence: models.Evidence,
    requirement: dict[str, Any],
) -> bool:
    provenance = _provenance(evidence)
    for requirement_key, provenance_key in (
        ("geographic_qualification", "geographic_qualification"),
        ("population_qualification", "population_qualification"),
    ):
        expected = requirement.get(requirement_key)
        observed = provenance.get(provenance_key)
        if expected and observed and expected.casefold() != str(observed).casefold():
            return False
    return True


def _state_for_requirement(
    requirement: dict[str, Any],
    evidence_ids: list[int],
    citations_by_id: dict[int, dict[str, Any]],
    contradiction_evidence_ids: set[int],
) -> str:
    requirement_id = requirement.get("id")
    if requirement_id in _COMMERCIAL_REQUIREMENTS:
        return "blocked"
    if any(evidence_id in contradiction_evidence_ids for evidence_id in evidence_ids):
        return "contradicted"
    if requirement.get("status") == "satisfied":
        return "supported"
    if any(evidence_id in citations_by_id for evidence_id in evidence_ids):
        return "partially_supported"
    return "unresolved"


def synthesize_research_plan(
    db: Session,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Update scoped requirement states from persisted evidence in linear passes."""
    requirements = [
        row
        for row in plan.get("requirements", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    ]
    requirements_by_id = {row["id"]: row for row in requirements}
    evidence_ids = sorted(
        {
            evidence_id
            for requirement in requirements
            for evidence_id in requirement.get("evidence_ids", [])
            if isinstance(evidence_id, int) and not isinstance(evidence_id, bool)
        }
    )
    evidence_rows = (
        db.query(models.Evidence)
        .filter(models.Evidence.id.in_(evidence_ids))
        .all()
        if evidence_ids
        else []
    )
    evidence_by_id = {row.id: row for row in evidence_rows}
    contradictions = explicit_contradiction_edges(db, evidence_ids)
    contradiction_evidence_ids = {row["evidence_id"] for row in contradictions}
    citations_by_id = {
        row.id: citation
        for row in evidence_rows
        if (citation := _evidence_citation(row)) is not None
    }

    requirement_states: dict[str, str] = {}
    requirement_evidence: dict[str, list[int]] = {}
    for requirement in requirements:
        requirement_id = requirement["id"]
        declared_ids = requirement.get("evidence_ids", [])
        scoped_ids = [
            evidence_id
            for evidence_id in declared_ids
            if evidence_id in evidence_by_id
            and _matches_qualifications(evidence_by_id[evidence_id], requirement)
        ]
        citations = [
            citations_by_id[evidence_id]
            for evidence_id in scoped_ids
            if evidence_id in citations_by_id
        ]
        state = _state_for_requirement(
            requirement,
            scoped_ids,
            citations_by_id,
            contradiction_evidence_ids,
        )
        requirement_states[requirement_id] = state
        requirement_evidence[requirement_id] = scoped_ids
        requirement["epistemic_state"] = state
        requirement["resolution_state"] = (
            "blocked_external_evidence_required" if state == "blocked" else state
        )
        requirement["synthesis_citations"] = citations
        requirement["synthesis_unresolved_dimensions"] = list(
            requirement.get("unresolved_dimensions", [])
        )

    synthesized = []
    for node in plan.get("orchestration_requirements", []):
        if not isinstance(node, dict):
            continue
        requirement_id = node.get("requirement_id")
        related_ids = [
            value
            for value in node.get("related_requirement_ids", [])
            if value in requirement_states
        ]
        related_states = [requirement_states[value] for value in related_ids]
        related_evidence_ids = sorted(
            {
                evidence_id
                for value in related_ids
                for evidence_id in requirement_evidence[value]
            }
        )
        task_failures = [
            failure
            for value in related_ids
            for failure in requirements_by_id[value].get("task_failures", [])
            if isinstance(failure, dict)
        ]
        citations = [
            citations_by_id[evidence_id]
            for evidence_id in related_evidence_ids
            if evidence_id in citations_by_id
        ]
        if requirement_id in _COMMERCIAL_REQUIREMENTS or not node.get("candidate_sources"):
            state = "blocked"
        elif "contradicted" in related_states:
            state = "contradicted"
        elif related_states and all(value == "supported" for value in related_states):
            state = "supported"
        elif any(value in {"supported", "partially_supported"} for value in related_states):
            state = "partially_supported"
        else:
            state = "unresolved"
        node["epistemic_state"] = state
        node["resolution_state"] = (
            "blocked_external_evidence_required"
            if state == "blocked"
            else state
        )
        node["citations"] = citations
        node["explicit_contradiction_edges"] = [
            edge
            for edge in contradictions
            if edge["evidence_id"] in related_evidence_ids
        ]
        node["task_failures"] = task_failures
        node["coexisting_observations"] = citations
        synthesized.append(
            {
                "requirement_id": requirement_id,
                "state": state,
                "statement": (
                    "Public-source evidence cannot establish customer demand, pain, or willingness to pay."
                    if state == "blocked" and requirement_id in _COMMERCIAL_REQUIREMENTS
                    else f"{len(citations)} persisted source observation(s) are cited for this bounded requirement."
                ),
                "citations": citations,
                "coexisting_observations": citations,
                "explicit_contradiction_edges": node["explicit_contradiction_edges"],
                "task_failures": task_failures,
                "unresolved_dimensions": list(node.get("unresolved_dimensions", [])),
                "commercial_gate_locked": requirement_id in _COMMERCIAL_REQUIREMENTS,
            }
        )
    overall_state = (
        "contradicted"
        if any(row["state"] == "contradicted" for row in synthesized)
        else "partially_supported"
        if any(row["state"] in {"supported", "partially_supported"} for row in synthesized)
        else "blocked"
        if synthesized and all(row["state"] == "blocked" for row in synthesized)
        else "unresolved"
    )
    return {
        "state": overall_state,
        "conclusions_are_not_claim_truth_transitions": True,
        "requirements": synthesized,
        "explicit_contradiction_edges": contradictions,
        "commercial_validation": {
            "state": "blocked",
            "opportunity_gate_unlocked": False,
            "required_evidence": "direct_customer_or_transaction_evidence",
        },
    }
