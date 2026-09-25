"""
Reddit collector — uses Reddit's public search JSON endpoint, which
doesn't require API credentials for read access. Stdlib only
(urllib/json), no praw dependency, to keep Forge lightweight.

Rate limits and endpoint behavior are Reddit's to change at any time;
this is a best-effort integration, not a guaranteed-stable one. A
production version should move to OAuth + the official API.
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.services.collectors.base import SourceCollector
from typing import Optional

USER_AGENT = "ForgeOS/0.1 (research collector; https://github.com/)"
TIMEOUT_SECONDS = 10

# Used when collect() is called with no query (autonomous/default mode
# — e.g. the Background Forge Worker waking up on its own). Small,
# generic pain-point search terms that fit Forge's mission, so it has
# something worth observing even before any Curiosity-driven question
# exists yet.
DEFAULT_QUERIES = [
    "small business problem",
    "startup pain point",
    "customers complain",
]


class RedditCollector(SourceCollector):
    source_name = "reddit"
    source_type = "discussion"

    def collect(self, query: Optional[str] = None) -> list[dict]:
        self.require_cleared_source()
        queries = [query] if query else DEFAULT_QUERIES
        items: list[dict] = []
        for term in queries:
            items.extend(self._search(term))
        return items

    def _search(self, query: str) -> list[dict]:
        self.require_cleared_source()
        url = (
            "https://www.reddit.com/search.json?"
            + urllib.parse.urlencode({"q": query, "limit": 10, "sort": "relevance"})
        )
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Reddit collector failed for query '{query}': {exc}") from exc

        items = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            body = post.get("selftext", "")
            content = f"{title}. {body}".strip()
            if not content:
                continue

            created_utc = post.get("created_utc")
            timestamp = (
                datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
                if created_utc
                else None
            )

            items.append(
                {
                    "content": content[:1000],
                    "title": title,
                    "external_id": post.get("name") or str(post.get("id")) if post.get("id") else None,
                    "timestamp": timestamp,
                    "metadata": {
                        "subreddit": post.get("subreddit"),
                        "score": post.get("score"),
                        "url": post.get("url"),
                        "query": query,
                    },
                }
            )
        return items
