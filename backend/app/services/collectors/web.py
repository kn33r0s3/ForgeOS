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
import re
import urllib.robotparser
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler

from app.services.collectors.base import SourceCollector

USER_AGENT = "ForgeOS/0.1 (research collector)"
TIMEOUT_SECONDS = 10
POLICY_URL = "https://www.govinfo.gov/about/policies"
REQUIRED_POLICY_TEXT = (
    "public documents can generally be reprinted without legal restriction",
    "does not authorize any use or appropriation of such copyright material without consent",
)
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


class _AllowedRedirectHandler(HTTPRedirectHandler):
    """Prevent an approved page from redirecting collection elsewhere."""

    def __init__(self, allowed_urls: set[str] | frozenset[str]):
        super().__init__()
        self.allowed_urls = allowed_urls

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urljoin(req.full_url, newurl)
        if destination not in self.allowed_urls:
            raise RuntimeError("Redirect target is not explicitly cleared for collection")
        return super().redirect_request(req, fp, code, msg, headers, destination)


class WebCollector(SourceCollector):
    source_name = "web"
    source_type = "general"

    def _fetch_policy_text(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        opener = urllib.request.build_opener(_AllowedRedirectHandler({url}))
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise RuntimeError("Could not recheck source robots or terms") from exc

    def _verify_live_clearance(self, url: str) -> None:
        robots_url = "https://www.govinfo.gov/robots.txt"
        robots_text = self._fetch_policy_text(robots_url)
        robots = urllib.robotparser.RobotFileParser(robots_url)
        robots.parse(robots_text.splitlines())
        if not robots.can_fetch(USER_AGENT, url):
            raise RuntimeError("Source robots.txt disallows this page")

        policy_html = self._fetch_policy_text(POLICY_URL)
        parser = _VisibleTextExtractor()
        parser.feed(policy_html)
        policy_text = re.sub(r"\s+", " ", parser.text()).lower()
        if not all(phrase in policy_text for phrase in REQUIRED_POLICY_TEXT):
            raise RuntimeError("Source terms no longer match the reviewed clearance")

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

    def collect(
        self,
        query: str,
        *,
        allowed_redirect_urls: set[str] | frozenset[str] | None = None,
    ) -> list[dict]:
        if allowed_redirect_urls is not None:
            if query not in allowed_redirect_urls:
                raise RuntimeError("Requested page is not in the collection allowlist")
            self._verify_live_clearance(query)

        reddit_result = self._collect_reddit(query)
        if reddit_result is not None:
            return reddit_result

        request = urllib.request.Request(
            query,
            headers={"User-Agent": USER_AGENT},
        )

        try:
            opener = (
                urllib.request.build_opener(_AllowedRedirectHandler(allowed_redirect_urls))
                if allowed_redirect_urls is not None
                else None
            )
            response_context = (
                opener.open(request, timeout=TIMEOUT_SECONDS)
                if opener is not None
                else urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
            )
            with response_context as response:
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
