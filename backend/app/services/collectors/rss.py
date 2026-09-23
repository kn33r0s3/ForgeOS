"""
RSS collector — two modes, both free and keyless:

  - Autonomous (no query): polls a small fixed list of general-purpose
    RSS feeds relevant to Forge's mission. This is what lets the
    Background Forge Worker collect real signals with zero human or
    Curiosity-Engine input — the "Forge wakes up on its own" mechanism.
  - Query-driven: searches Google News' public RSS search endpoint for
    a specific topic (used when a ResearchTask supplies a query).

Stdlib only (urllib + xml.etree), no feedparser dependency. Absorbs
what used to be a separate news_collector.py — a Google News search
result IS an RSS feed, so there was no real reason to keep them as two
concepts; "news" is kept as an alias source name for backward
compatibility with any already-planned ResearchTask rows.

Feed URLs can go stale or change format without notice, same caveat as
every other collector here — this is a best-effort integration.
"""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from app.services.collectors.base import SourceCollector
from typing import Optional

USER_AGENT = "ForgeOS/0.1 (research collector)"
TIMEOUT_SECONDS = 10

# Autonomous/default mode — a small, general-purpose set of business/
# tech feeds. Deliberately short; add more once these are confirmed
# working against a live network.
DEFAULT_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://hnrss.org/frontpage",
]


class RSSCollector(SourceCollector):
    source_name = "rss"
    source_type = "media"

    def collect(self, query: Optional[str] = None) -> list[dict]:
        if query:
            return self._fetch_feed(self._google_news_search_url(query), query=query)

        items: list[dict] = []
        errors: list[str] = []
        for feed_url in DEFAULT_FEEDS:
            try:
                items.extend(self._fetch_feed(feed_url))
            except Exception as exc:
                # One dead default feed shouldn't take down autonomous
                # collection entirely — keep whatever feeds worked.
                errors.append(str(exc))

        if not items and errors:
            raise RuntimeError(f"All default RSS feeds failed: {'; '.join(errors)}")
        return items

    def _google_news_search_url(self, query: str) -> str:
        params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)

    def _fetch_feed(self, feed_url: str, query: Optional[str] = None) -> list[dict]:
        request = urllib.request.Request(feed_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw_xml = response.read()
            root = ET.fromstring(raw_xml)
        except Exception as exc:
            raise RuntimeError(f"RSS collector failed for feed '{feed_url}': {exc}") from exc

        items = []
        for item in root.findall(".//item")[:10]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            items.append(
                {
                    "content": title[:500],
                    "title": title,
                    "external_id": item.findtext("guid") or item.findtext("link"),
                    "timestamp": item.findtext("pubDate"),
                    "metadata": {"link": item.findtext("link"), "feed": feed_url, "query": query},
                }
            )
        return items
