"""
GitHub Bounty Adapter for ForgeOS
=================================

Provides zero-dollar autonomous discovery, opportunity structuring,
claim execution, and merge verification for funded GitHub issue bounties
(Algora, Opire, and open bounty labels).

Hard constraints:
- $0 spending: uses public GitHub REST APIs with stdlib urllib.
- Truthful states: fails closed without GITHUB_TOKEN for state mutations.
- Objective verification: PR merge state is verified directly from GitHub API.
- Idempotency: identity_key prevents duplicate opportunity creation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import integration_outbox

logger = logging.getLogger(__name__)

USER_AGENT = "ForgeOS/2.3 (bounty-adapter)"
TIMEOUT_SECONDS = 15

# Regex patterns for detecting bounty amounts in issue titles and bodies
BOUNTY_PATTERNS = [
    re.compile(r"bounty:\s*\$?(\d+(?:\.\d{2})?)", re.IGNORECASE),
    re.compile(r"/bounty\s+\$?(\d+(?:\.\d{2})?)", re.IGNORECASE),
    re.compile(r"@opire-dev\s+create\s+\$?(\d+(?:\.\d{2})?)", re.IGNORECASE),
    re.compile(r"\[bounty\]\s*\[?\$?(\d+(?:\.\d{2})?)\]?", re.IGNORECASE),
    re.compile(r"\$(\d+(?:\.\d{2})?)\s+(?:bounty|reward)", re.IGNORECASE),
    re.compile(r"(?:bounty|reward)\s+of\s+\$?(\d+(?:\.\d{2})?)", re.IGNORECASE),
]


def extract_bounty_amount(text: str) -> Optional[float]:
    """Extract numeric bounty amount from issue title, body, or label."""
    if not text:
        return None
    for pattern in BOUNTY_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                val = float(match.group(1))
                if val > 0:
                    return val
            except ValueError:
                continue
    return None


def detect_bounty_platform(text: str, labels: list[str]) -> str:
    """Identify which bounty platform backs the issue."""
    combined = (text + " " + " ".join(labels)).lower()
    if "opire" in combined:
        return "Opire"
    if "algora" in combined:
        return "Algora"
    if "polar.sh" in combined or "polar" in combined:
        return "Polar"
    return "GitHub Bounty"


def fetch_github_bounties(
    query: str = "label:bounty is:open is:issue",
    limit: int = 10,
    github_token: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Query GitHub public search API for open bounty issues.
    
    Zero-dollar, works unauthenticated (rate-limited to 10 req/min)
    or authenticated via optional token.
    """
    token = github_token or os.getenv("GITHUB_TOKEN", "")
    url = (
        "https://api.github.com/search/issues?"
        + urllib.parse.urlencode({"q": query, "per_page": min(limit, 30), "sort": "updated"})
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="ignore")
        logger.error(f"GitHub search failed HTTP {exc.code}: {err_msg}")
        raise RuntimeError(f"GitHub search API error {exc.code}: {err_msg}") from exc
    except Exception as exc:
        logger.error(f"GitHub search network failure: {exc}")
        raise RuntimeError(f"GitHub search network failure: {exc}") from exc

    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        title = item.get("title", "")
        body = item.get("body") or ""
        labels = [l.get("name", "") for l in item.get("labels", [])]
        combined_text = f"{title}\n{body}"

        amount = extract_bounty_amount(combined_text)
        platform = detect_bounty_platform(combined_text, labels)

        # Parse repo owner and name from repository_url
        repo_url = item.get("repository_url", "")
        repo_parts = repo_url.split("/")[-2:]
        owner = repo_parts[0] if len(repo_parts) == 2 else ""
        repo_name = repo_parts[1] if len(repo_parts) == 2 else ""

        results.append({
            "issue_id": item.get("id"),
            "issue_number": item.get("number"),
            "title": title,
            "body": body[:2000],
            "html_url": item.get("html_url"),
            "owner": owner,
            "repo": repo_name,
            "labels": labels,
            "amount_usd": amount,
            "platform": platform,
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "claim_command": "/try" if platform == "Opire" else "/attempt",
        })

    return results


def ingest_bounties_to_opportunities(
    db: Session,
    bounties: list[dict[str, Any]],
) -> list[models.Opportunity]:
    """Ingest discovered GitHub bounties into ForgeOS opportunities table idempotently."""
    created: list[models.Opportunity] = []
    now = datetime.now(timezone.utc)

    for b in bounties:
        owner = b.get("owner")
        repo = b.get("repo")
        number = b.get("issue_number")
        if not owner or not repo or number is None:
            continue
        # Reject non-integer issue numbers (e.g. "invalid", 0, negative)
        try:
            number = int(number)
            if number <= 0:
                raise ValueError
        except (TypeError, ValueError):
            continue

        identity_key = f"github_bounty:{owner}/{repo}#{number}"
        existing = db.query(models.Opportunity).filter_by(identity_key=identity_key).first()
        if existing:
            # If bounty amount was updated, record it
            if b.get("amount_usd") and existing.estimated_price != b.get("amount_usd"):
                existing.estimated_price = b.get("amount_usd")
                existing.updated_at = now
            continue

        amount = b.get("amount_usd")
        platform = b.get("platform", "GitHub Bounty")
        title = b.get("title", "")
        body = b.get("body", "")
        url = b.get("html_url", "")

        opp = models.Opportunity(
            identity_key=identity_key,
            problem=f"[{platform}] {title}",
            target_customer=f"{owner}/{repo}",
            solution=f"Solve GitHub issue #{number} and submit pull request. Claim via {b.get('claim_command', '/attempt')}.",
            business_model="bounty",
            pricing_idea=f"${amount} USD reward on merge" if amount else None,
            estimated_price=amount,
            monetization_model="bounty",
            difficulty=40.0,
            score=75.0 if amount else 40.0,
            status="identified",
            created_at=now,
            updated_at=now,
            economic_consequence=f"Maintainer offered bounty on {url}",
            offer=f"Code fix / PR addressing #{number}",
            acquisition_path=f"GitHub PR to {owner}/{repo}",
            market_confidence=50.0,
            revenue_confidence=70.0 if amount else 20.0,
            uncertainty=30.0 if amount else 70.0,
        )
        db.add(opp)
        created.append(opp)

    if created:
        db.commit()
    return created


def verify_pr_merge_status(
    owner: str,
    repo: str,
    pull_number: int,
    github_token: Optional[str] = None,
) -> dict[str, Any]:
    """Verify whether a pull request has been merged using public GitHub REST API.
    
    Zero-dollar verification: checks public repository pull request metadata.
    Returns cryptographic merge evidence (merge_commit_sha, merged_at, merged_by).
    """
    token = github_token or os.getenv("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="ignore")
        return {
            "verified": False,
            "status": "HTTP_ERROR",
            "error": f"HTTP {exc.code}: {err_msg}",
            "merged": False,
        }
    except Exception as exc:
        return {
            "verified": False,
            "status": "NETWORK_ERROR",
            "error": str(exc),
            "merged": False,
        }

    is_merged = bool(data.get("merged", False))
    merged_at = data.get("merged_at")
    merge_commit_sha = data.get("merge_commit_sha")

    return {
        "verified": is_merged,
        "status": "MERGED" if is_merged else ("CLOSED" if data.get("state") == "closed" else "OPEN"),
        "merged": is_merged,
        "merged_at": merged_at,
        "merge_commit_sha": merge_commit_sha,
        "html_url": data.get("html_url"),
        "title": data.get("title"),
        "state": data.get("state"),
    }


def post_bounty_claim_comment(
    owner: str,
    repo: str,
    issue_number: int,
    claim_command: str = "/attempt",
    github_token: Optional[str] = None,
) -> dict[str, Any]:
    """Post an intent-to-solve comment on a GitHub issue.
    
    Fails closed if GITHUB_TOKEN is not configured.
    Never fabricates success.
    """
    token = github_token or os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GITHUB_TOKEN is not configured. External GitHub mutation requires an authorized token.")

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"body": claim_command}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {
                "status": "POSTED",
                "comment_id": data.get("id"),
                "html_url": data.get("html_url"),
                "created_at": data.get("created_at"),
            }
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub comment failed HTTP {exc.code}: {err_msg}") from exc
    except Exception as exc:
        raise RuntimeError(f"GitHub comment network failure: {exc}") from exc
