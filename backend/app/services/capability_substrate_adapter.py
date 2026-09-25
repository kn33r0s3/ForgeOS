"""Project runtime ToolRegistry definitions into the substrate Capability primitive.

ToolRegistry stays authoritative for executable implementations. This adapter
records auditable metadata in ForgeCapability without selecting or invoking a
tool, and leaves each substrate lifecycle at its existing state.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import tool_registry, world_graph


def sync_runtime_tool_capabilities(
    db: Session,
    registry: tool_registry.ToolRegistry | None = None,
) -> dict[str, int]:
    """Idempotently mirror declared tool metadata; never check availability or execute."""
    world_graph.seed_core_types(db)
    source_registry = registry or tool_registry.default_registry()
    result = {"created": 0, "refreshed": 0, "unchanged": 0, "events_created": 0}

    for declared in source_registry.list_capabilities():
        name = (declared.name or "").strip()
        if not name:
            continue
        reliability = float(declared.reliability)
        if not math.isfinite(reliability) or reliability < 0 or reliability > 1:
            raise ValueError(f"tool registry reliability must be between 0 and 1: {name}")
        attributes: dict[str, Any] = {
            "source_registry": "runtime_tool_registry",
            "source_name": name,
            "category": declared.category,
            "input_types": list(declared.input_types),
            "output_types": list(declared.output_types),
            "cost": declared.cost,
            "latency": declared.latency,
            "reliability": reliability,
            "languages": list(declared.languages),
            "media_support": list(declared.media_support),
            "declared_availability": declared.availability,
            "capabilities": list(declared.capabilities),
        }
        description = (
            f"Runtime tool capability in category {declared.category}; "
            f"declared functions: {', '.join(declared.capabilities) or 'unspecified'}."
        )
        projected_name = f"runtime-tool:{name}"
        spec_ref = f"tool_registry:{name}"
        snapshot = json.dumps(
            {
                "name": projected_name,
                "capability_type": "tool",
                "description": description,
                "spec_ref": spec_ref,
                "attributes": attributes,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

        capability = db.query(models.ForgeCapability).filter_by(name=projected_name).one_or_none()
        previous_digest = None
        if capability is None:
            capability = world_graph.create_capability(
                db,
                capability_type="tool",
                name=projected_name,
                description=description,
                owner_agent="runtime_tool_registry_adapter",
                spec_ref=spec_ref,
                attributes=attributes,
            )
            result["created"] += 1
        else:
            previous_snapshot = json.dumps(
                {
                    "name": capability.name,
                    "capability_type": capability.capability_type,
                    "description": capability.description,
                    "spec_ref": capability.spec_ref,
                    "attributes": json.loads(capability.attributes or "{}"),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            previous_digest = hashlib.sha256(previous_snapshot.encode("utf-8")).hexdigest()
            if previous_digest == digest:
                result["unchanged"] += 1
                continue
            capability.description = description
            capability.spec_ref = spec_ref
            capability.attributes = json.dumps(
                attributes, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            result["refreshed"] += 1

        event_key = f"runtime-tool-capability:{name}:{digest}"
        already_recorded = db.query(models.WorldEvent).filter_by(idempotency_key=event_key).first()
        world_graph.create_event(
            db,
            event_type="capability_source_refreshed",
            source="runtime_tool_registry_adapter",
            payload={
                "capability_id": capability.id,
                "source_ref": {"registry": "runtime_tool_registry", "name": name},
                "previous_snapshot_sha256": previous_digest,
                "snapshot_sha256": digest,
                "lifecycle_status": capability.status,
            },
            idempotency_key=event_key,
        )
        result["events_created"] += int(already_recorded is None)

    db.flush()
    return result
