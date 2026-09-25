"""
SOURCE COLLECTOR — base interface
====================================

Every Forge source (Reddit, GitHub, RSS, arXiv, Web, and anything added
later) implements this contract. Moved here from source_manager.py so
the collectors/ package is self-contained: source_manager.py only owns
Source table bookkeeping (reliability tracking), not the interface
collectors implement — that separation avoids a circular import
between "the registry of collectors" and "the collectors themselves."

    class SomeCollector(SourceCollector):
        source_name = "..."
        source_type = "..."

        def collect(self, query: Optional[str] = None) -> list[dict]:
            ...

`query` is optional by design: when a ResearchTask supplies one
(curiosity-driven collection — see research_planner.py), the collector
searches/filters for that topic. When it's None, the collector falls
back to its own default feed/topic. That's what lets the Background
Forge Worker call every collector with no query at all and still get
real signals — the mechanism behind "Forge wakes up without you
manually feeding it."
"""

from abc import ABC, abstractmethod
from typing import Optional


class SourceCollector(ABC):
    source_name: str
    source_type: str

    def require_cleared_source(self) -> None:
        """Fail before network access unless this collector has active scope."""
        from app.services import source_clearance_registry

        if not source_clearance_registry.collector_is_cleared(self.source_name):
            raise PermissionError(f"Source '{self.source_name}' has no active source-registry clearance")

    @abstractmethod
    def collect(self, query: Optional[str] = None) -> list[dict]:
        """
        Returns observations from reality.

        If `query` is given, search/filter for that topic. If omitted,
        fall back to this collector's own default (a fixed feed list,
        a default category, a small set of standing search terms —
        whatever makes sense for the source). Must return a list of
        raw, source-specific dicts; normalize() below converts them
        into Forge's standard observation shape.
        """
        raise NotImplementedError

    def normalize(self, raw_item: dict) -> dict:
        """Convert one raw item into Forge's standard observation
        shape, ready to hand to ObserverEngine.observe()."""
        from datetime import datetime, timezone
        metadata = dict(raw_item.get("metadata", {}) or {})
        retrieved_at = raw_item.get("retrieved_at") or metadata.get("retrieved_at") or datetime.now(timezone.utc).isoformat()
        canonical_url = (
            raw_item.get("canonical_url")
            or metadata.get("canonical_url")
            or metadata.get("url")
            or metadata.get("link")
        )
        content_text = raw_item.get("content", "")
        metadata["source_type"] = "external"
        metadata["canonical_url"] = canonical_url
        metadata["retrieved_at"] = retrieved_at
        metadata["raw_excerpt"] = content_text[:8192] if content_text else ""

        return {
            "source": self.source_name,
            "source_type": "external",
            "content": content_text,
            "timestamp": raw_item.get("timestamp") or retrieved_at,
            "published_at": raw_item.get("published_at") or raw_item.get("timestamp"),
            "retrieved_at": retrieved_at,
            "title": raw_item.get("title") or metadata.get("title"),
            "canonical_url": canonical_url,
            "external_id": raw_item.get("external_id") or metadata.get("external_id"),
            "provenance": raw_item.get("provenance") or metadata,
            "collection_status": raw_item.get("collection_status", "collected"),
            "metadata": metadata,
        }
