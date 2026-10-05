import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services import capability_substrate_adapter as adapter, tool_registry, world_graph


class CountingTool:
    def __init__(self, metadata):
        self.capability = metadata
        self.availability_checks = 0
        self.executions = 0

    def is_available(self):
        self.availability_checks += 1
        return True

    def execute(self, payload, **kwargs):
        self.executions += 1
        return payload


def _registry(*, reliability=0.4, category="research"):
    tool = CountingTool(tool_registry.ToolCapability(
        name="evidence-reader",
        category=category,
        input_types=("query", "text"),
        output_types=("evidence",),
        cost="free",
        latency="network",
        reliability=reliability,
        languages=("en", "ne"),
        media_support=("text",),
        availability="optional_public_source",
        capabilities=("collect", "normalize"),
    ))
    return tool_registry.ToolRegistry([tool]), tool


def test_runtime_tools_project_as_proposed_and_repeat_without_execution(db):
    registry, tool = _registry()

    first = adapter.sync_runtime_tool_capabilities(db, registry)
    second = adapter.sync_runtime_tool_capabilities(db, registry)

    capability = db.query(models.ForgeCapability).filter_by(
        name="runtime-tool:evidence-reader"
    ).one()
    assert first == {"created": 1, "refreshed": 0, "unchanged": 0, "events_created": 1, "invalid": 0}
    assert second == {"created": 0, "refreshed": 0, "unchanged": 1, "events_created": 0, "invalid": 0}
    assert capability.capability_type == "tool"
    assert capability.status == "proposed"
    assert capability.spec_ref == "tool_registry:evidence-reader"
    attributes = json.loads(capability.attributes)
    assert attributes["source_registry"] == "runtime_tool_registry"
    assert attributes["source_name"] == "evidence-reader"
    assert attributes["languages"] == ["en", "ne"]
    assert tool.availability_checks == 0
    assert tool.executions == 0
    assert db.query(models.ForgeCapability).count() == 1
    assert db.query(models.WorldEvent).filter_by(event_type="capability_source_refreshed").count() == 1


def test_metadata_refresh_preserves_canonical_capability_lifecycle(db):
    registry, _ = _registry()
    adapter.sync_runtime_tool_capabilities(db, registry)
    capability = db.query(models.ForgeCapability).filter_by(
        name="runtime-tool:evidence-reader"
    ).one()
    # Non-starved: lifecycle tests verify mechanics, not operating discipline.
    world_graph.create_event(
        db, event_type="outreach.sent", source="test", payload={},
    )
    db.commit()
    world_graph.begin_capability_build(db, capability)
    world_graph.mark_capability_tested(
        db,
        capability,
        test_ref="backend/tests/test_capability_substrate_adapter.py",
        command="pytest backend/tests/test_capability_substrate_adapter.py",
        exit_code=0,
        output_excerpt="passed",
        provenance={"actor": "test", "revision": "bf8546ed26f9179e8522726e966a984fc1dd83c6"},
    )
    world_graph.activate_capability(db, capability)
    db.commit()

    changed_registry, tool = _registry(reliability=0.7, category="collection")
    result = adapter.sync_runtime_tool_capabilities(db, changed_registry)

    db.refresh(capability)
    assert result == {"created": 0, "refreshed": 1, "unchanged": 0, "events_created": 1, "invalid": 0}
    assert capability.status == "active"
    assert capability.test_ref == "backend/tests/test_capability_substrate_adapter.py"
    assert json.loads(capability.attributes)["reliability"] == 0.7
    refresh = db.query(models.WorldEvent).filter_by(
        event_type="capability_source_refreshed"
    ).order_by(models.WorldEvent.id.desc()).first()
    payload = json.loads(refresh.payload)
    assert payload["previous_snapshot_sha256"]
    assert payload["snapshot_sha256"]
    assert payload["lifecycle_status"] == "active"
    assert tool.availability_checks == 0
    assert tool.executions == 0


def test_runtime_capability_projection_survives_restart(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'capabilities.sqlite'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    first_session = SessionLocal()
    registry, _ = _registry()
    adapter.sync_runtime_tool_capabilities(first_session, registry)
    first_session.commit()
    first_session.close()

    restarted = SessionLocal()
    result = adapter.sync_runtime_tool_capabilities(restarted, registry)
    restarted.commit()

    assert result == {"created": 0, "refreshed": 0, "unchanged": 1, "events_created": 0, "invalid": 0}
    capability = restarted.query(models.ForgeCapability).one()
    assert capability.name == "runtime-tool:evidence-reader"
    assert capability.status == "proposed"
    assert restarted.query(models.WorldEvent).filter_by(
        event_type="capability_source_refreshed"
    ).count() == 1
    restarted.close()
    engine.dispose()
