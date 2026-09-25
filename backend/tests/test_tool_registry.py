import pytest

from app.services.tool_registry import (
    ToolCapability,
    ToolRegistry,
    ToolUnavailableError,
    default_registry,
)


class FakeTool:
    def __init__(self, name, available=True, reliability=0.5):
        self.capability = ToolCapability(
            name=name,
            category="extract",
            input_types=("text",),
            output_types=("claims",),
            reliability=reliability,
            capabilities=("extract",),
        )
        self.available = available

    def is_available(self):
        return self.available

    def execute(self, payload, **kwargs):
        if not self.available:
            raise ToolUnavailableError("unavailable")
        return {"payload": payload}


def test_registration_and_capability_lookup():
    tool = FakeTool("claims-v1")
    registry = ToolRegistry([tool])

    assert registry.get("claims-v1") is tool
    assert registry.list_capabilities()[0].capabilities == ("extract",)
    assert registry.find(category="extract", capability="extract") == [tool]


def test_duplicate_registration_is_rejected():
    registry = ToolRegistry([FakeTool("claims-v1")])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeTool("claims-v1"))


def test_unavailable_provider_and_fallback_selection():
    unavailable = FakeTool("remote-claims", available=False, reliability=0.99)
    fallback = FakeTool("local-claims", available=True, reliability=0.2)
    registry = ToolRegistry([unavailable, fallback])

    selection = registry.select(category="extract", capability="missing", fallback="local-claims")

    assert selection.tool is fallback
    assert "fallback" in selection.reason
    with pytest.raises(ToolUnavailableError):
        unavailable.execute("text")


def test_provider_selection_prefers_available_reliable_tool():
    slower = FakeTool("slow", reliability=0.4)
    better = FakeTool("better", reliability=0.9)
    registry = ToolRegistry([slower, better])

    selection = registry.select(category="extract", capability="extract")

    assert selection.tool is better


def test_default_registry_keeps_mock_fallback_when_ollama_is_not_active():
    registry = default_registry()

    assert registry.get("local-qwen3-coder").capability.category == "reasoning"
    selection = registry.select(
        category="reasoning",
        capability="completion",
        preferred=("local-qwen3-coder",),
        fallback="offline-mock",
    )

    assert selection.tool.capability.name == "offline-mock"
    assert selection.tool.execute("hello")


def test_unapproved_collection_tools_are_unavailable_and_web_rejects_unknown_targets(db):
    registry = default_registry()

    assert not registry.get("reddit").is_available()
    with pytest.raises(ToolUnavailableError, match="not cleared"):
        registry.get("reddit").execute("automation", db=db)
    with pytest.raises(ToolUnavailableError, match="not cleared"):
        registry.get("web").execute("https://example.com/article", db=db)
