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


def _evidence_citation(evidence: models.Evidence) -> dict[str, Any] | None:
    if not evidence.canonical_url:
        return None
    try:
        provenance = json.loads(evidence.provenance) if evidence.provenance else {}
    except (TypeError, json.JSONDecodeError):
        provenance = {}
    if not isinstance(provenance, dict):
        provenance = {}
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


def synthesize_research_plan(
    db: Session,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Cite only persisted evidence; collection completion never means conclusion."""
    requirements = {
        row.get("id"): row
        for row in plan.get("requirements", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    contradictions = explicit_contradiction_edges(
        db,
        sorted(
            {
                evidence_id
                for requirement in requirements.values()
                for evidence_id in requirement.get("evidence_ids", [])
                if isinstance(evidence_id, int)
            }
        ),
    )
    contradiction_evidence_ids = {row["evidence_id"] for row in contradictions}

    synthesized = []
    for node in plan.get("orchestration_requirements", []):
        if not isinstance(node, dict):
            continue
        requirement_id = node.get("requirement_id")
        related = [
            requirements[value]
            for value in node.get("related_requirement_ids", [])
            if value in requirements
        ]
        evidence_ids = sorted(
            {
                evidence_id
                for requirement in related
                for evidence_id in requirement.get("evidence_ids", [])
                if isinstance(evidence_id, int)
            }
        )
        citations = [
            citation
            for evidence_id in evidence_ids
            if (evidence := db.get(models.Evidence, evidence_id)) is not None
            if (citation := _evidence_citation(evidence)) is not None
        ]
        if requirement_id in _COMMERCIAL_REQUIREMENTS:
            state = "unresolved"
            statement = (
                "Direct customer, buyer, or transaction evidence is required; "
                "public-source observations cannot resolve this commercial gap."
            )
        elif citations:
            state = (
                "contradicted"
                if any(
                    citation["evidence_id"] in contradiction_evidence_ids
                    for citation in citations
                )
                else "supported"
                if any(
                    item.get("status") == "satisfied"
                    and item.get("id") != "bibliographic_discovery"
                    for item in related
                )
                else "partially_supported"
            )
            statement = (
                f"{len(citations)} persisted source observation(s) are cited for this "
                "bounded requirement; they do not validate broader claims."
            )
        else:
            state = "unresolved"
            statement = (
                "No persisted evidence with a provenance URL currently supports this "
                "bounded requirement."
            )
        synthesized.append(
            {
                "requirement_id": requirement_id,
                "state": state,
                "statement": statement,
                "citations": citations,
                "coexisting_observations": citations,
                "explicit_contradiction_edges": [
                    edge
                    for edge in contradictions
                    if edge["evidence_id"] in evidence_ids
                ],
                "unresolved_dimensions": list(node.get("unresolved_dimensions", [])),
                "commercial_gate_locked": requirement_id in _COMMERCIAL_REQUIREMENTS,
            }
        )
    return {
        "state": (
            "unresolved"
            if not synthesized
            else "partially_supported"
            if any(row["state"] in {"supported", "partially_supported", "contradicted"} for row in synthesized)
            else "unresolved"
        ),
        "conclusions_are_not_claim_truth_transitions": True,
        "requirements": synthesized,
        "explicit_contradiction_edges": contradictions,
        "commercial_validation": {
            "state": "unresolved",
            "opportunity_gate_unlocked": False,
            "required_evidence": "direct_customer_or_transaction_evidence",
        },
    }
