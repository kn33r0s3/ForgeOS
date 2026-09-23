"""Provider-neutral registry for Forge intelligence tools.

Tools describe what they can do before they are invoked. Providers remain
owned by their existing services; this module only adapts and selects them.
Optional tools may be unavailable without making the registry unusable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Protocol
import hashlib


@dataclass(frozen=True)
class ToolCapability:
    name: str
    category: str
    input_types: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()
    cost: str = "unknown"
    latency: str = "unknown"
    reliability: float = 0.0
    languages: tuple[str, ...] = ()
    media_support: tuple[str, ...] = ()
    availability: str = "unknown"
    capabilities: tuple[str, ...] = ()


class IntelligenceTool(Protocol):
    capability: ToolCapability

    def is_available(self) -> bool:
        ...

    def execute(self, payload: Any, **kwargs: Any) -> Any:
        ...


class ToolUnavailableError(RuntimeError):
    """Raised when a selected tool cannot be used at execution time."""


class ProviderAdapter:
    """Adapt an existing provider factory to the intelligence-tool contract."""

    def __init__(
        self,
        capability: ToolCapability,
        provider_factory: Callable[[], Any],
        *,
        availability_check: Callable[[], bool] | None = None,
    ) -> None:
        self.capability = capability
        self._provider_factory = provider_factory
        self._availability_check = availability_check

    def is_available(self) -> bool:
        if self._availability_check is not None:
            try:
                return bool(self._availability_check())
            except Exception:
                return False
        try:
            self._provider_factory()
            return True
        except Exception:
            return False

    def execute(self, payload: Any, **kwargs: Any) -> Any:
        try:
            provider = self._provider_factory()
        except Exception as exc:
            raise ToolUnavailableError(str(exc)) from exc
        try:
            return provider.complete(str(payload), system=kwargs.get("system", ""))
        except Exception as exc:
            raise ToolUnavailableError(str(exc)) from exc


class CollectorToolAdapter:
    """Expose an existing SourceCollector through the P0 registry."""

    def __init__(self, name: str, collector_factory: Callable[[], Any], source_type: str):
        self._collector_factory = collector_factory
        self.capability = ToolCapability(
            name=name,
            category="collection",
            input_types=("query", "text"),
            output_types=("evidence", "metadata"),
            cost="free",
            latency="network",
            reliability=0.5,
            media_support=("text",),
            availability="optional_public_source",
            capabilities=("collect", "normalize", source_type),
        )

    def is_available(self) -> bool:
        try:
            self._collector_factory()
            return True
        except Exception:
            return False

    def execute(self, payload: Any, **kwargs: Any) -> Any:
        collector = self._collector_factory()
        return collector.collect(str(payload) if payload else None)


@dataclass
class ToolSelection:
    tool: IntelligenceTool
    reason: str


class ToolRegistry:
    """In-memory registry with deterministic capability-based selection."""

    def __init__(self, tools: Iterable[IntelligenceTool] = ()) -> None:
        self._tools: dict[str, IntelligenceTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: IntelligenceTool) -> IntelligenceTool:
        name = tool.capability.name.strip()
        if not name:
            raise ValueError("tool capability name is required")
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> IntelligenceTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown intelligence tool: {name}") from exc

    def list_capabilities(self) -> list[ToolCapability]:
        return [self._tools[name].capability for name in sorted(self._tools)]

    def find(
        self,
        *,
        category: str | None = None,
        capability: str | None = None,
        input_type: str | None = None,
        output_type: str | None = None,
        media_type: str | None = None,
    ) -> list[IntelligenceTool]:
        matches: list[IntelligenceTool] = []
        for tool in self._tools.values():
            metadata = tool.capability
            if category and metadata.category != category:
                continue
            if capability and capability not in metadata.capabilities:
                continue
            if input_type and input_type not in metadata.input_types:
                continue
            if output_type and output_type not in metadata.output_types:
                continue
            if media_type and media_type not in metadata.media_support:
                continue
            matches.append(tool)
        return sorted(matches, key=lambda item: item.capability.name)

    def select(
        self,
        *,
        category: str | None = None,
        capability: str | None = None,
        input_type: str | None = None,
        output_type: str | None = None,
        media_type: str | None = None,
        preferred: Iterable[str] = (),
        fallback: str | None = None,
        db: Any = None,
        exploration_key: str = "",
        explore: bool = True,
    ) -> ToolSelection:
        candidates = self.find(
            category=category,
            capability=capability,
            input_type=input_type,
            output_type=output_type,
            media_type=media_type,
        )
        preferred_names = list(preferred)
        learned = {}
        if db is not None:
            from app.services import tool_usefulness
            learned = {
                tool.capability.name: tool_usefulness.tool_summary(db, tool.capability.name)
                for tool in candidates
            }

        def rank(tool):
            summary = learned.get(tool.capability.name, {})
            learned_score = tool_usefulness.learned_score(summary) if summary else None
            return (
                0 if tool.capability.name in preferred_names else 1,
                -(learned_score if learned_score is not None else tool.capability.reliability),
                summary.get("attempts", 0),
                tool.capability.name,
            )

        ranked = sorted(candidates, key=rank)
        if explore and len(ranked) > 1 and exploration_key:
            should_explore = int(hashlib.sha256(exploration_key.encode()).hexdigest()[:8], 16) % 5 == 0
            if should_explore:
                ranked = sorted(ranked, key=lambda tool: (learned.get(tool.capability.name, {}).get("attempts", 0), tool.capability.name))
        for tool in ranked:
            if tool.is_available():
                return ToolSelection(tool=tool, reason="highest-ranked available match")
        if fallback is not None:
            fallback_tool = self.get(fallback)
            if fallback_tool.is_available():
                return ToolSelection(tool=fallback_tool, reason="requested tools unavailable; fallback selected")
        raise ToolUnavailableError("no available intelligence tool matches the request")


def default_registry() -> ToolRegistry:
    """Build the default registry from existing AI providers.

    Importing is intentionally lazy so optional OpenAI dependencies and a
    stopped Ollama daemon never prevent Forge from starting.
    """
    from app.services import ai_engine

    registry = ToolRegistry()
    from app.services.youtube_intelligence import YouTubeIntelligenceTool

    registry.register(YouTubeIntelligenceTool())
    from app.services.collectors.arxiv import ArxivCollector
    from app.services.collectors.github import GithubCollector
    from app.services.collectors.reddit import RedditCollector
    from app.services.collectors.rss import RSSCollector
    from app.services.collectors.web import WebCollector
    for name, factory, source_type in (
        ("reddit", RedditCollector, "discussion"),
        ("github", GithubCollector, "code"),
        ("rss", RSSCollector, "media"),
        ("arxiv", ArxivCollector, "research"),
        ("web", WebCollector, "web"),
    ):
        registry.register(CollectorToolAdapter(name, factory, source_type))
    registry.register(
        ProviderAdapter(
            ToolCapability(
                name="local-qwen3-coder",
                category="reasoning",
                input_types=("text", "prompt"),
                output_types=("text", "analysis"),
                cost="local",
                latency="variable",
                reliability=0.8,
                languages=("en",),
                media_support=("text",),
                availability="optional",
                capabilities=("completion", "reasoning", "code", "summarization"),
            ),
            ai_engine.OllamaProvider,
            availability_check=lambda: ai_engine.settings.AI_PROVIDER == "ollama",
        )
    )
    registry.register(
        ProviderAdapter(
            ToolCapability(
                name="offline-mock",
                category="reasoning",
                input_types=("text", "prompt"),
                output_types=("text", "analysis"),
                cost="free",
                latency="low",
                reliability=0.4,
                languages=("en",),
                media_support=("text",),
                availability="always",
                capabilities=("completion", "fallback", "summarization"),
            ),
            ai_engine.MockProvider,
        )
    )
    if ai_engine.settings.OPENAI_API_KEY:
        registry.register(
            ProviderAdapter(
                ToolCapability(
                    name="openai-completion",
                    category="reasoning",
                    input_types=("text", "prompt"),
                    output_types=("text", "analysis"),
                    cost="paid",
                    latency="network",
                    reliability=0.8,
                    languages=("en",),
                    media_support=("text",),
                    availability="optional",
                    capabilities=("completion", "reasoning", "summarization"),
                ),
                ai_engine.OpenAIProvider,
                availability_check=lambda: ai_engine.settings.AI_PROVIDER == "openai",
            )
        )
    return registry
