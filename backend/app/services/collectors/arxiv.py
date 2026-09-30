"""
arXiv collector — uses arXiv's free public Atom API (no key required).
Stdlib only (urllib + xml.etree). This is Forge's highest-reliability
non-manual source (see source_manager.DEFAULT_SOURCES) — peer-adjacent
research papers are much less noisy than social discussion.

  - Autonomous (no query): pulls the most recent papers from a default
    category (cs.AI) — relevant to Forge's business/AI-opportunity
    mission, and gives the Background Forge Worker something real to
    observe with zero human input.
  - Query-driven: full-text search for a specific topic.
"""

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from app.services.collectors.base import SourceCollector
from typing import Optional

USER_AGENT = "ForgeOS/0.1 (research collector)"
TIMEOUT_SECONDS = 15
ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Autonomous/default mode — recent papers in a category relevant to
# Forge's mission. A future version could rotate through multiple
# categories (econ.GN, cs.CY, etc.) instead of always cs.AI.
DEFAULT_SEARCH_QUERY = "cat:cs.AI"


class ArxivCollector(SourceCollector):
    source_name = "arxiv"
    source_type = "research"

    def collect(self, query: Optional[str] = None) -> list[dict]:
        self.require_cleared_source()
        search_query = f"all:{query}" if query else DEFAULT_SEARCH_QUERY
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": 10,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw_xml = response.read()
            root = ET.fromstring(raw_xml)
        except Exception as exc:
            raise RuntimeError(f"arXiv collector failed for query '{query}': {exc}") from exc

        items = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            title = (entry.findtext(f"{ATOM_NS}title") or "").strip().replace("\n", " ")
            summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip().replace("\n", " ")
            if not title:
                continue

            content = f"{title}. {summary}"[:1200]
            items.append(
                {
                    "content": content,
                    "timestamp": entry.findtext(f"{ATOM_NS}published"),
                    "metadata": {
                        "url": entry.findtext(f"{ATOM_NS}id"),
                        "query": query or DEFAULT_SEARCH_QUERY,
                    },
                }
            )
        return items
