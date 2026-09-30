"""
LIVE COLLECTION SMOKE CLI COMMAND
===================================

Gated CLI tool for running live research collection against external sources.

Usage:
    python -m app.cli.collect [--sources github,rss] [--query "search term"] [--limit 5] [--dry-run | --apply]

Defaults to --dry-run (no database writes).
--apply must be explicitly passed to insert signals into forge.db.
"""

import sys
import json
import argparse
import hashlib
from typing import List, Dict

from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app import models
from app.services.collector_runner import COLLECTORS
from app.services.observer_engine import ObserverEngine
from app.services import source_clearance_registry


def run_collection_smoke(
    sources: List[str],
    query: str | None = None,
    limit: int = 5,
    apply: bool = False,
    db: Session | None = None,
) -> dict:
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True

    try:
        observer = ObserverEngine(db)
        summary = {
            "mode": "apply" if apply else "dry-run",
            "sources_processed": len(sources),
            "items_fetched": 0,
            "would_insert": 0,
            "would_skip_duplicate": 0,
            "inserted": 0,
            "items": [],
        }

        for source_name in sources:
            collector_cls = COLLECTORS.get(source_name)
            if not collector_cls:
                continue
            
            collector = collector_cls()
            try:
                if source_name != "web":
                    raise PermissionError(f"Source '{source_name}' is not cleared for collection")
                authorization = source_clearance_registry.authorize_request(
                    query or "",
                    collector=source_name,
                    db=db,
                )
                raw_items = collector.collect(query or "", authorization=authorization)
            except Exception as exc:
                summary["items"].append({
                    "source": source_name,
                    "error": str(exc),
                })
                continue

            for raw_item in raw_items[:limit]:
                norm = collector.normalize(raw_item)
                if not norm.get("content"):
                    continue

                summary["items_fetched"] += 1
                canonical_url = norm.get("canonical_url")
                title = norm.get("title") or ""
                content = norm.get("content") or ""
                retrieved_at = norm.get("retrieved_at")
                external_id = norm.get("external_id")

                norm_title = title.strip().lower()
                norm_body = content.strip().lower()
                fingerprint = hashlib.sha256(
                    f"{canonical_url or ''}:{norm_title}:{norm_body}".encode("utf-8")
                ).hexdigest()

                # Duplicate check
                existing = None
                if canonical_url or external_id:
                    q = db.query(models.Signal).filter(models.Signal.source == source_name)
                    if external_id:
                        existing = q.filter(models.Signal.external_id == str(external_id)).first()
                    if not existing and canonical_url:
                        existing = q.filter(models.Signal.canonical_url == canonical_url).first()

                decision = "WOULD_SKIP_DUPLICATE" if existing else "WOULD_INSERT"
                if decision == "WOULD_INSERT":
                    summary["would_insert"] += 1
                else:
                    summary["would_skip_duplicate"] += 1

                item_info = {
                    "source": source_name,
                    "canonical_url": canonical_url,
                    "retrieved_at": retrieved_at,
                    "external_id": external_id,
                    "content_fingerprint": fingerprint,
                    "title": title[:80],
                    "decision": decision,
                }

                if apply and decision == "WOULD_INSERT":
                    sig = observer.observe(content, source=source_name, metadata=norm.get("metadata", {}))
                    item_info["inserted_signal_id"] = sig.id
                    summary["inserted"] += 1

                summary["items"].append(item_info)

        return summary
    finally:
        if close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="ForgeOS Live Collection Smoke Command")
    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="Comma-separated sources to fetch (github, reddit, rss, arxiv, web)",
    )
    parser.add_argument("--query", type=str, default=None, help="Search query parameter")
    parser.add_argument("--limit", type=int, default=5, help="Limit items per source")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute database writes. Defaults to --dry-run (False) if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Perform network fetch but skip database writes (default).",
    )
    args = parser.parse_args()

    sources_list = [s.strip() for s in args.sources.split(",") if s.strip()]
    is_apply = args.apply

    res = run_collection_smoke(sources=sources_list, query=args.query, limit=args.limit, apply=is_apply)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
