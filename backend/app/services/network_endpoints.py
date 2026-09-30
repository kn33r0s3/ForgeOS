"""Typed adapters from a network endpoint reference to its canonical record.

The adapter map is deliberately an application extension point. Endpoint
kinds are canonical record adapters, not rows in a second entity/type registry.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app import models


class EndpointResolutionError(ValueError):
    """A relation endpoint kind or id cannot be resolved to a canonical row."""


ENDPOINT_ADAPTERS: dict[str, type] = {
    "signal": models.Signal,
    "pattern": models.Pattern,
    "belief": models.Belief,
    "claim": models.Claim,
    "research_question": models.ResearchQuestion,
    "opportunity": models.Opportunity,
    "provider": models.Provider,
    "service_listing": models.ServiceListing,
    "domain_record": models.DomainRecord,
    "booking_request": models.BookingRequest,
    "outcome": models.Outcome,
    "customer": models.Customer,
    "experiment": models.Experiment,
    "decision": models.Decision,
    "action": models.Action,
    "learning_event": models.LearningEvent,
    "product": models.Product,
    "repair_work_item": models.RepairWorkItem,
    "network_connection": models.NetworkConnection,
}

ENDPOINT_ALIASES = {
    "post": "domain_record",
    "knowledge": "claim",
    "service": "service_listing",
}
_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


def canonical_endpoint_type(value: str | None, *, strict: bool = True) -> str | None:
    kind = (value or "").strip().casefold()
    kind = ENDPOINT_ALIASES.get(kind, kind)
    if not _KIND_PATTERN.fullmatch(kind) or kind not in ENDPOINT_ADAPTERS:
        if strict:
            raise EndpointResolutionError(f"unknown canonical endpoint kind: {value!r}")
        return None
    return kind


def resolve_endpoint(db: Session, kind: str, entity_id: int) -> tuple[str, object]:
    """Return the canonical kind and stored row, failing closed on missing ids."""
    canonical_kind = canonical_endpoint_type(kind)
    if isinstance(entity_id, bool) or not isinstance(entity_id, int) or entity_id < 1:
        raise EndpointResolutionError("canonical endpoint id must be a positive integer")
    record = db.get(ENDPOINT_ADAPTERS[canonical_kind], entity_id)
    if record is None:
        raise EndpointResolutionError(
            f"canonical endpoint {canonical_kind} #{entity_id} was not found"
        )
    return canonical_kind, record
