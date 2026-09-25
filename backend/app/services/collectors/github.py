"""
GitHub collector — uses GitHub's public REST search API for issues.
No token required for low-volume, unauthenticated use (rate-limited to
10 requests/min). Stdlib only (urllib/json).
"""

import json
import urllib.parse
import urllib.request

from app.services.collectors.base import SourceCollector
from typing import Optional

USER_AGENT = "ForgeOS/0.1 (research collector)"
TIMEOUT_SECONDS = 10

# Autonomous/default mode (no query supplied) — generic terms relevant
# to Forge's mission (business automation, tooling pain points).
DEFAULT_QUERIES = [
    "customer support automation",
    "small business tool",
]


class GithubCollector(SourceCollector):
    source_name = "github"
    source_type = "code"

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
            "https://api.github.com/search/issues?"
            + urllib.parse.urlencode({"q": query, "per_page": 10})
        )
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"GitHub collector failed for query '{query}': {exc}") from exc

        items = []
        for issue in data.get("items", []):
            title = issue.get("title", "")
            body = (issue.get("body") or "")[:500]
            content = f"{title}. {body}".strip()
            if not content:
                continue

            items.append(
                {
                    "content": content[:1000],
                    "title": title,
                    "external_id": str(issue.get("id")) if issue.get("id") is not None else None,
                    "timestamp": issue.get("created_at"),
                    "metadata": {
                        "repository_url": issue.get("repository_url"),
                        "url": issue.get("html_url"),
                        "query": query,
                    },
                }
            )
        return items
