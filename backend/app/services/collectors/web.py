"""
Web collector — fetches a single web page and extracts its visible
text, using only stdlib (urllib + html.parser). No requests or
BeautifulSoup dependency.

There is no free general-purpose web *search* API without a key, so
unlike the other collectors, `query` here is treated as a direct URL
to fetch rather than a search term. A future version could add a
proper search layer (e.g. a self-hosted SearXNG instance) in front of
this without changing the SourceCollector interface.
"""

import json
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from app.services.collectors.base import SourceCollector

USER_AGENT = "ForgeOS/0.1 (research collector)"
TIMEOUT_SECONDS = 10
SKIP_TAGS = {"script", "style", "noscript"}


class _VisibleTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def text(self) -> str:
        return " ".join(self._chunks)


class WebCollector(SourceCollector):
    source_name = "web"
    source_type = "general"

    def _collect_reddit(self, query: str) -> list[dict] | None:
        parsed_url = urlsplit(query)
        host = (parsed_url.hostname or "").lower()

        if not host.endswith("reddit.com"):
            return None

        path = parsed_url.path.rstrip("/")
        if not path.endswith(".json"):
            path += ".json"

        json_url = urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                path,
                parsed_url.query,
                "",
            )
        )

        request = urllib.request.Request(
            json_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=TIMEOUT_SECONDS,
            ) as response:
                payload = response.read().decode("utf-8", errors="ignore")
        except Exception:
            # Let the normal HTML path handle the URL. If that only yields a
            # shell page, the existing fail-closed rules will reject it.
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []

        post = None

        if isinstance(data, list) and data:
            listing = data[0]
            if isinstance(listing, dict):
                children = listing.get("data", {}).get("children", [])
                if children and isinstance(children[0], dict):
                    post = children[0].get("data")

        elif isinstance(data, dict):
            children = data.get("data", {}).get("children", [])
            if children and isinstance(children[0], dict):
                post = children[0].get("data")

        if not isinstance(post, dict):
            return []

        title = " ".join(str(post.get("title") or "").split())
        author = " ".join(str(post.get("author") or "").split())
        subreddit = " ".join(
            str(post.get("subreddit_name_prefixed") or "").split()
        )
        body = " ".join(str(post.get("selftext") or "").split())

        parts = []

        if title:
            parts.append(f"Title: {title}")
        if author:
            parts.append(f"Author: u/{author}")
        if subreddit:
            parts.append(f"Subreddit: {subreddit}")
        if body:
            parts.append(f"Body: {body}")

        normalized = " ".join(parts).strip()

        if len(normalized) < 120 or len(normalized.split()) < 20:
            return []

        return [{
            "content": normalized[:1500],
            "timestamp": None,
            "metadata": {
                "url": query,
                "extraction": "reddit_json",
                "source_url": json_url,
            },
        }]

    def collect(self, query: str) -> list[dict]:
        reddit_result = self._collect_reddit(query)
        if reddit_result is not None:
            return reddit_result

        request = urllib.request.Request(
            query,
            headers={"User-Agent": USER_AGENT},
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=TIMEOUT_SECONDS,
            ) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            raise RuntimeError(
                f"Web collector failed for url '{query}': {exc}"
            ) from exc

        parser = _VisibleTextExtractor()
        parser.feed(html)
        text = parser.text()
        normalized = " ".join(text.split())

        # Fail closed: a successful HTTP fetch is not evidence if the page
        # yielded only a generic shell/branding token or otherwise trivial text.
        if not normalized:
            return []

        shell_only = {
            "reddit",
            "hiver",
            "peerspot",
        }

        if normalized.casefold() in shell_only:
            return []

        words = normalized.split()

        # Require enough substantive text to distinguish page content from
        # title/branding/navigation-only responses.
        if len(normalized) < 120 or len(words) < 20:
            return []

        return [{
            "content": normalized[:1500],
            "timestamp": None,
            "metadata": {"url": query},
        }]
