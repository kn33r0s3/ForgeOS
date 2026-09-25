"""
COLLECTOR RUNNER
=================

Bridges Forge's two collection modes to actual SourceCollector
implementations (in app/services/collectors/) and the Observer Engine:

  - Query-driven: execute_task() / run_pending_tasks() — runs a
    ResearchTask planned by research_planner.py from a Curiosity
    Engine question, passing its query to the matching collector.
  - Standing sweep: run_default_collection() — records a skip for
    Reddit, GitHub, RSS, and arXiv. None of those feeds is cleared in
    docs/PUBLIC_SOURCES.md, so this sweep does not open a request.
    A cleared page is collected only as a web ResearchTask.

Failures (network errors, rate limits, an unimplemented source) mark a
task "failed" or are skipped per-collector rather than raised — a bad
network call should never take down a cycle or the API.
"""

from datetime import date
from time import monotonic
from sqlalchemy.orm import Session

from app import models
from app.services.observer_engine import ObserverEngine
from app.services.collectors.reddit import RedditCollector
from app.services.collectors.github import GithubCollector
from app.services.collectors.rss import RSSCollector
from app.services.collectors.arxiv import ArxivCollector
from app.services.collectors.web import WebCollector
from app.services import research_task_engine
from app.services import evidence_graph
from app.services import tool_usefulness
from app.services import source_clearance_registry

COLLECTORS = {
    "reddit": RedditCollector,
    "github": GithubCollector,
    "rss": RSSCollector,
    "news": RSSCollector,  # backward-compat alias — see rss.py's docstring
    "arxiv": ArxivCollector,
    "web": WebCollector,
}

# Bulk feeds are not cleared in docs/PUBLIC_SOURCES.md. Clearances are
# represented by source_clearance_registry; a URL is not permission by itself.
UNCLEARED_DEFAULT_SOURCES = ("reddit", "github", "rss", "news", "arxiv")
CLEARED_WEB_URLS = frozenset(entry.url for entry in source_clearance_registry.source_clearances())
CLEARED_WEB_REVIEW_DATE = source_clearance_registry.source_clearances()[0].reviewed_on


def _web_clearance_error(value: str, *, today: date | None = None) -> str | None:
    """Validate exact target, canonical URL, approval, and review window."""
    return source_clearance_registry.clearance_error(value, today=today)


def execute_task(db: Session, task: models.ResearchTask) -> dict:
    """Run one ResearchTask through its matching collector, observe
    every result as a Signal, and mark the task completed/failed."""
    if task.status == "completed":
        return {"task_id": task.id, "status": "completed", "reused": True, "signals_created": 0}
    if not research_task_engine.begin_task(db, task):
        return {"task_id": task.id, "status": task.status, "reused": task.status == "completed", "signals_created": 0}

    started = monotonic()
    if task.source in UNCLEARED_DEFAULT_SOURCES:
        reason = f"Source '{task.source}' is not cleared for collection"
        research_task_engine.fail_task(db, task, reason)
        return {"task_id": task.id, "status": "failed", "reason": reason}

    authorization = None
    if task.source == "web":
        try:
            authorization = source_clearance_registry.authorize_request(
                task.query,
                collector=task.source,
                db=db,
            )
        except Exception as exc:
            research_task_engine.fail_task(db, task, str(exc))
            return {"task_id": task.id, "status": "failed", "reason": str(exc)}

    collector_cls = COLLECTORS.get(task.source)
    if not collector_cls:
        research_task_engine.fail_task(db, task, f"No collector registered for source '{task.source}'")
        tool_usefulness.record_usage(
            db, tool_name=f"collector:{task.source}", source=task.source, source_type="unavailable",
            query=task.query, research_task_id=task.id, claim_id=task.claim_id,
            result_count=None, useful_result_count=None, novel_result_count=None,
            verified_result_count=None, duplicate_result_count=None,
            corroborated_evidence_count=None, contradicted_claim_count=None,
            freshness=None, latency_ms=(monotonic() - started) * 1000,
            success=False, failure_kind="unavailable",
        )
        return {
            "task_id": task.id,
            "status": "failed",
            "reason": f"No collector registered for source '{task.source}'",
        }

    collector = collector_cls()
    observer = ObserverEngine(db)

    try:
        if authorization:
            raw_items = collector.collect(task.query, authorization=authorization)
        else:
            raw_items = collector.collect(task.query)
    except Exception as exc:
        research_task_engine.fail_task(db, task, str(exc))
        tool_usefulness.record_usage(
            db, tool_name=f"collector:{task.source}", source=task.source, source_type="collector",
            query=task.query, research_task_id=task.id, claim_id=task.claim_id,
            result_count=None, useful_result_count=None, novel_result_count=None,
            verified_result_count=None, duplicate_result_count=None,
            corroborated_evidence_count=None, contradicted_claim_count=None,
            freshness=None, latency_ms=(monotonic() - started) * 1000,
            success=False, failure_kind="collection_failure",
        )
        return {"task_id": task.id, "status": "failed", "reason": str(exc)}

    created_signal_ids = []
    evidence_ids = []
    for raw_item in raw_items:
        normalized = collector.normalize(raw_item)
        if authorization:
            web_clearance = authorization.entry
            metadata = dict(normalized.get("metadata") or {})
            metadata.update({
                "source_registry_id": web_clearance.registry_id,
                "source_display_name": web_clearance.display_name,
                "source_geographies": list(web_clearance.geographies),
                "source_categories": list(web_clearance.categories),
                "source_reviewed_on": web_clearance.reviewed_on.isoformat(),
            })
            normalized["metadata"] = metadata
            provenance = normalized.get("provenance")
            provenance = dict(provenance) if isinstance(provenance, dict) else {}
            provenance.update({
                "source_registry_id": web_clearance.registry_id,
                "source_geographies": list(web_clearance.geographies),
                "source_categories": list(web_clearance.categories),
                "source_reviewed_on": web_clearance.reviewed_on.isoformat(),
            })
            normalized["provenance"] = provenance
            normalized["source"] = web_clearance.registry_id
        if not normalized["content"]:
            continue
        signal = observer.observe(normalized["content"], source=normalized["source"], metadata=normalized)
        created_signal_ids.append(signal.id)
        evidence = (
            db.query(models.Evidence)
            .filter(models.Evidence.signal_id == signal.id)
            .order_by(models.Evidence.id.desc())
            .first()
        )
        if evidence:
            evidence_ids.append(evidence.id)
            statement = (normalized.get("content") or "").strip()[:400]
            if statement and not task.claim_id:
                claim, _ = evidence_graph.create_or_get_claim(
                    db,
                    statement,
                    epistemic_state="observed",
                    provenance={
                        "signal_id": signal.id,
                        "source": normalized.get("source"),
                        "research_task_id": task.id,
                    },
                )
                evidence_graph.link_evidence(db, evidence, claim=claim, relation_type="derived_from")
            if task.claim_id:
                relation = (normalized.get("metadata") or {}).get("claim_relation", "derived_from")
                if relation not in evidence_graph.RELATION_TYPES:
                    relation = "derived_from"
                claim = db.query(models.Claim).filter_by(id=task.claim_id).first()
                if claim:
                    evidence_graph.link_evidence(db, evidence, claim=claim, relation_type=relation)

    final_task = research_task_engine.finish_task(
        db, task, signal_ids=created_signal_ids, evidence_ids=evidence_ids
    )
    claim_evidence_ids = evidence_ids
    if task.claim_id:
        claim_evidence_ids = [
            row.evidence_id
            for row in db.query(models.EvidenceRelationship)
            .filter(models.EvidenceRelationship.claim_id == task.claim_id)
            .all()
        ]
    evaluation = research_task_engine.evaluate_claim_after_research(db, final_task, claim_evidence_ids)
    evidence_rows = db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all() if evidence_ids else []
    evidence_edges = db.query(models.EvidenceRelationship).filter(
        models.EvidenceRelationship.evidence_id.in_(evidence_ids)
    ).all() if evidence_ids else []
    useful_count = sum(1 for edge in evidence_edges if edge.relation_type in {"supports", "contradicts", "updates"})
    novel_count = sum(1 for signal_id in created_signal_ids if db.get(models.Signal, signal_id).is_duplicate_of is None)
    duplicate_count = len(created_signal_ids) - novel_count
    verified_count = len(evidence_rows) if evaluation and evaluation["comparison"].outcome == "agreement" else 0
    contradicted_count = sum(1 for edge in evidence_edges if edge.relation_type == "contradicts")
    tool_usefulness.record_usage(
        db, tool_name=f"collector:{task.source}", source=task.source, source_type="collector",
        query=task.query, research_task_id=task.id, claim_id=task.claim_id,
        result_count=len(created_signal_ids), useful_result_count=useful_count,
        novel_result_count=novel_count, verified_result_count=verified_count,
        duplicate_result_count=duplicate_count,
        corroborated_evidence_count=verified_count, contradicted_claim_count=contradicted_count,
        freshness=100.0 if created_signal_ids else None,
        latency_ms=(monotonic() - started) * 1000, success=bool(raw_items),
        failure_kind="empty_result" if not raw_items else None, result_ids=evidence_ids,
    )
    return {
        "task_id": task.id,
        "status": final_task.status,
        "signals_created": len(created_signal_ids),
        "evidence_found": len(set(evidence_ids)),
    }


def run_pending_tasks(db: Session, limit: int = 5) -> list[dict]:
    """Execute up to `limit` currently-planned tasks (curiosity-driven
    collection). Used by the Background Forge Worker and available
    on-demand via the API."""
    tasks = (
        db.query(models.ResearchTask)
        .filter(models.ResearchTask.status == "planned")
        .limit(limit)
        .all()
    )
    return [execute_task(db, task) for task in tasks]


def run_default_collection(db: Session) -> list[dict]:
    """Refuse standing feeds that docs/PUBLIC_SOURCES.md has not cleared.

    Reddit, GitHub, RSS, and arXiv each have a collector, but none has a
    robots-and-terms clearance. This returns a skip record and does not
    open a network request. A cleared page is collected through a web
    ResearchTask, not through this default sweep.
    """
    return [
        {
            "source": source_name,
            "status": "skipped",
            "reason": "source is not cleared for collection",
            "signals_created": 0,
        }
        for source_name in ("reddit", "github", "rss", "arxiv")
    ]
