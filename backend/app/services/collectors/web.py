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

import re
import urllib.robotparser
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler

from app.services.collectors.base import SourceCollector
from app.services import source_clearance_registry

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
        policy_urls = {
            policy_url
            for entry in source_clearance_registry.source_clearances()
            for policy_url in (entry.robots_url, entry.terms_url)
        }
        if url not in policy_urls:
            raise PermissionError("Policy URL is not in the source clearance registry")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        opener = urllib.request.build_opener(_AllowedRedirectHandler({url}))
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise RuntimeError("Could not recheck source robots or terms") from exc

    def _verify_live_clearance(self, url: str, source_clearance=None) -> None:
        source_clearance = source_clearance_registry.validate_authorization(
            source_clearance,
            url=url,
            collector=self.source_name,
        )
        if url not in source_clearance.redirect_urls:
            raise RuntimeError("Requested page is not in the source clearance registry")
        robots_url = source_clearance.robots_url
        robots_text = self._fetch_policy_text(robots_url)
        robots = urllib.robotparser.RobotFileParser(robots_url)
        robots.parse(robots_text.splitlines())
        if not robots.can_fetch(USER_AGENT, url):
            raise RuntimeError("Source robots.txt disallows this page")

        policy_html = self._fetch_policy_text(source_clearance.terms_url)
        parser = _VisibleTextExtractor()
        parser.feed(policy_html)
        policy_text = re.sub(r"\s+", " ", parser.text()).lower()
        if not source_clearance.required_terms_phrases or not all(
            phrase.lower() in policy_text for phrase in source_clearance.required_terms_phrases
        ):
            raise RuntimeError("Source terms no longer match the reviewed clearance")

    def collect(
        self,
        query: str,
        *,
        authorization: source_clearance_registry.CollectionAuthorization | None = None,
    ) -> list[dict]:
        entry = source_clearance_registry.validate_authorization(
            authorization,
            url=query,
            collector=self.source_name,
        )
        self._verify_live_clearance(query, authorization)

        request = urllib.request.Request(
            query,
            headers={"User-Agent": USER_AGENT},
        )

        try:
            opener = urllib.request.build_opener(_AllowedRedirectHandler(frozenset(entry.redirect_urls)))
            response_context = opener.open(request, timeout=TIMEOUT_SECONDS)
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
