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
from hashlib import sha256
from datetime import datetime, timezone
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from app import models
from app.services.observer_engine import ObserverEngine
from app.services.collectors.reddit import RedditCollector
from app.services.collectors.github import GithubCollector
from app.services.collectors.rss import RSSCollector
from app.services.collectors.arxiv import ArxivCollector
from app.services.collectors.web import WebCollector
from app.services.collectors.crossref import API_URL as CROSSREF_API_URL, CrossrefCollector
from app.services.collectors.world_bank import WorldBankCollector
from app.services.collectors.gdelt import API_URL as GDELT_API_URL, GdeltCollector
from app.services.collectors.openalex import API_URL as OPENALEX_API_URL, OpenAlexCollector
from app.services import research_task_engine
from app.services import evidence_graph
from app.services import tool_usefulness
from app.services import source_clearance_registry
from app.services.research_evidence_assessment import assess_source_record
import json

COLLECTORS = {
    "reddit": RedditCollector,
    "github": GithubCollector,
    "rss": RSSCollector,
    "news": RSSCollector,  # backward-compat alias — see rss.py's docstring
    "arxiv": ArxivCollector,
    "web": WebCollector,
    "crossref": CrossrefCollector,
    "world_bank_indicators": WorldBankCollector,
    "gdelt_doc": GdeltCollector,
    "openalex": OpenAlexCollector,
}

# Bulk feeds are not cleared in docs/PUBLIC_SOURCES.md. Clearances are
# represented by source_clearance_registry; a URL is not permission by itself.
UNCLEARED_DEFAULT_SOURCES = ("reddit", "github", "rss", "news", "arxiv")
_WEB_CLEARANCES = tuple(
    entry
    for entry in source_clearance_registry.source_clearances()
    if entry.collector == "web"
)
CLEARED_WEB_URLS = frozenset(entry.url for entry in _WEB_CLEARANCES)


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
        except source_clearance_registry.SourceRateLimitError as exc:
            research_task_engine.defer_task(db, task, str(exc))
            return {
                "task_id": task.id,
                "status": "planned",
                "deferred": True,
                "reason": str(exc),
            }
        except Exception as exc:
            research_task_engine.fail_task(db, task, str(exc))
            return {"task_id": task.id, "status": "failed", "reason": str(exc)}
    elif task.source == "crossref":
        try:
            authorization = source_clearance_registry.authorize_request(
                CROSSREF_API_URL,
                collector=task.source,
                db=db,
            )
        except source_clearance_registry.SourceRateLimitError as exc:
            research_task_engine.defer_task(db, task, str(exc))
            return {
                "task_id": task.id,
                "status": "planned",
                "deferred": True,
                "reason": str(exc),
            }
        except Exception as exc:
            research_task_engine.fail_task(db, task, str(exc))
            return {"task_id": task.id, "status": "failed", "reason": str(exc)}
    elif task.source == "gdelt_doc":
        try:
            authorization = source_clearance_registry.authorize_request(
                GDELT_API_URL,
                collector=task.source,
                db=db,
            )
        except source_clearance_registry.SourceRateLimitError as exc:
            research_task_engine.defer_task(db, task, str(exc))
            return {
                "task_id": task.id,
                "status": "planned",
                "deferred": True,
                "reason": str(exc),
            }
        except Exception as exc:
            research_task_engine.fail_task(db, task, str(exc))
            return {"task_id": task.id, "status": "failed", "reason": str(exc)}
    elif task.source == "openalex":
        try:
            authorization = source_clearance_registry.authorize_request(
                OPENALEX_API_URL,
                collector=task.source,
                db=db,
            )
        except source_clearance_registry.SourceRateLimitError as exc:
            research_task_engine.defer_task(db, task, str(exc))
            return {
                "task_id": task.id,
                "status": "planned",
                "deferred": True,
                "reason": str(exc),
            }
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
        if task.source == "web":
            raw_items = collector.collect(task.query, authorization=authorization)
        elif task.source == "crossref":
            raw_items = collector.collect(task.query, authorization=authorization)
        elif task.source == "world_bank_indicators":
            raw_items = collector.collect(task.query, db=db)
        elif task.source == "gdelt_doc":
            raw_items = collector.collect(task.query, authorization=authorization)
        elif task.source == "openalex":
            task_context = task.results if isinstance(task.results, dict) else {}
            search_mode = OpenAlexCollector.validate_search_mode(
                task_context.get("search_mode", "keyword")
            )
            raw_items = collector.collect(
                task.query,
                search_mode=search_mode,
                task_provenance=task_context,
                authorization=authorization,
            )
        else:
            raw_items = collector.collect(task.query)
    except source_clearance_registry.SourceRateLimitError as exc:
        research_task_engine.defer_task(db, task, str(exc))
        return {
            "task_id": task.id,
            "status": "planned",
            "deferred": True,
            "reason": str(exc),
        }
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
    source_results = []
    for raw_item in raw_items:
        normalized = collector.normalize(raw_item)
        task_context = task.results if isinstance(task.results, dict) else {}
        provenance = normalized.get("provenance")
        provenance = dict(provenance) if isinstance(provenance, dict) else {}
        for context_key in (
            "original_research_question",
            "derived_retrieval_query",
            "search_mode",
            "geographic_qualification",
            "population_qualification",
            "unresolved_dimensions",
            "capability_id",
            "discovered_doi",
            "discovery_parent_evidence_id",
            "discovered_source_reference",
        ):
            if task_context.get(context_key) is not None:
                provenance[context_key] = task_context[context_key]
        normalized["provenance"] = provenance
        if authorization:
            authorized_source = authorization.entry
            metadata = dict(normalized.get("metadata") or {})
            metadata.update({
                "source_registry_id": authorized_source.registry_id,
                "source_display_name": authorized_source.display_name,
                "source_geographies": list(authorized_source.geographies),
                "source_categories": list(authorized_source.categories),
                "source_reviewed_on": authorized_source.reviewed_on.isoformat(),
            })
            normalized["metadata"] = metadata
            provenance = normalized.get("provenance")
            provenance = dict(provenance) if isinstance(provenance, dict) else {}
            provenance.update({
                "source_registry_id": authorized_source.registry_id,
                "source_geographies": list(authorized_source.geographies),
                "source_categories": list(authorized_source.categories),
                "source_reviewed_on": authorized_source.reviewed_on.isoformat(),
            })
            normalized["provenance"] = provenance
            if task.source == "web":
                normalized["source"] = authorized_source.registry_id
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
            provenance = normalized.get("provenance")
            provenance = provenance if isinstance(provenance, dict) else {}
            assessment = assess_source_record(
                task.query,
                title=signal.title,
                content=signal.content,
                published_at=signal.published_at,
                retrieved_at=signal.retrieved_at,
                source_identity=signal.external_id or signal.source,
                canonical_url=signal.canonical_url,
                provenance=provenance,
            )
            evidence_provenance = (
                json.loads(evidence.provenance)
                if evidence.provenance
                else {}
            )
            evidence.provenance = json.dumps(
                {**evidence_provenance, "assessment": assessment},
                sort_keys=True,
            )
            source_results.append(
                {
                    "signal_id": signal.id,
                    "evidence_id": evidence.id,
                    "title": signal.title,
                    "url": signal.canonical_url,
                    "external_id": signal.external_id,
                    "published_at": signal.published_at.isoformat() if signal.published_at else None,
                    "retrieved_at": signal.retrieved_at.isoformat() if signal.retrieved_at else None,
                    "source": signal.source,
                    "assessment": assessment,
                }
            )
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

    retrieval_observation = None
    if not raw_items:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        source_registry_id = (
            authorization.entry.registry_id
            if authorization is not None
            else next(
                (
                    entry.registry_id
                    for entry in source_clearance_registry.source_clearances()
                    if entry.collector == task.source
                ),
                None,
            )
        )
        retrieval_observation = {
            "source": task.source,
            "source_registry_id": source_registry_id,
            "source_accessed": True,
            "query": task.query,
            "retrieved_at": retrieved_at,
            "source_records_returned": 0,
            "outcome": "valid_empty_retrieval",
            "claim_effect": "none",
        }

    if task.source == "openalex" and not raw_items:
        task_context = task.results if isinstance(task.results, dict) else {}
        search_mode = OpenAlexCollector.validate_search_mode(
            task_context.get("search_mode", "keyword")
        )
        observation_id = sha256(
            f"openalex:empty:{task.query}:{search_mode}".encode("utf-8")
        ).hexdigest()
        original_question = task_context.get("original_research_question")
        geography = task_context.get("geographic_qualification")
        population = task_context.get("population_qualification")
        unresolved = task_context.get("unresolved_dimensions")
        observation_provenance = {
            "source_type": "openalex",
            "source_registry_id": retrieval_observation["source_registry_id"],
            "metadata_only": True,
            "traceable": True,
            "observation_type": "valid_empty_retrieval",
            "query": task.query,
            "derived_retrieval_query": task.query,
            "search_mode": search_mode,
            "original_research_question": (
                original_question if isinstance(original_question, str) else task.objective
            ),
            "geographic_qualification": geography if isinstance(geography, str) else None,
            "population_qualification": population if isinstance(population, str) else None,
            "unresolved_dimensions": unresolved if isinstance(unresolved, list) else [],
            "discovery_parent_evidence_id": task_context.get(
                "discovery_parent_evidence_id"
            ),
            "discovered_source_reference": task_context.get(
                "discovered_source_reference"
            ),
            "returned_works": 0,
            "claim_effect": "none",
            "external_pdf_fetched": False,
            "publisher_page_fetched": False,
            "source_accessed": True,
        }
        observation_provenance["retrieved_at"] = retrieval_observation["retrieved_at"]
        retrieval_observation.update(
            {
                "search_mode": search_mode,
                "returned_works": 0,
            }
        )
        empty_signal = observer.observe(
            f"0 scholarly works found in OpenAlex for query: {task.query}",
            source="openalex",
            metadata={
                "source_type": "external",
                "title": "OpenAlex empty scholarly retrieval",
                "canonical_url": OPENALEX_API_URL,
                "external_id": observation_id,
                "identity_key": f"openalex:empty:{observation_id}",
                "timestamp": retrieval_observation["retrieved_at"],
                "retrieved_at": retrieval_observation["retrieved_at"],
                "collection_status": "valid_empty_retrieval",
                "provenance": observation_provenance,
            },
            persist_evidence=False,
        )
        created_signal_ids.append(empty_signal.id)
        source_results.append(
            {
                "signal_id": empty_signal.id,
                "evidence_id": None,
                "source": "openalex",
                "observation_type": "valid_empty_retrieval",
                "returned_works": 0,
            }
        )

    final_task = research_task_engine.finish_task(
        db,
        task,
        signal_ids=created_signal_ids,
        evidence_ids=evidence_ids,
        retrieval_observation=retrieval_observation,
    )
    final_task.results = {
        **(final_task.results or {}),
        "source_results": source_results,
        "source_result_count": len(source_results),
    }
    db.commit()
    claim_evidence_ids = evidence_ids
    if task.claim_id:
        claim_evidence_ids = [
            row.evidence_id
            for row in db.query(models.EvidenceRelationship)
            .filter(models.EvidenceRelationship.claim_id == task.claim_id)
            .all()
        ]
    evaluation = (
        research_task_engine.evaluate_claim_after_research(
            db, final_task, claim_evidence_ids
        )
        if evidence_ids
        else None
    )
    question = db.get(models.ResearchQuestion, final_task.question_id)
    if question is not None and isinstance(question.research_plan, dict):
        from app.services import research_planner

        research_planner.plan_tasks_for_question(db, question)
    evidence_rows = db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all() if evidence_ids else []
    evidence_edges = db.query(models.EvidenceRelationship).filter(
        models.EvidenceRelationship.evidence_id.in_(evidence_ids)
    ).all() if evidence_ids else []
    useful_count = sum(1 for edge in evidence_edges if edge.relation_type in {"supports", "contradicts", "updates"})
    novel_count = sum(1 for signal_id in created_signal_ids if db.get(models.Signal, signal_id).is_duplicate_of is None)
    duplicate_count = len(created_signal_ids) - novel_count
    evaluation_judgments = evaluation.get("judgments", []) if evaluation else []
    positive_consensus = bool(evaluation_judgments) and (
        evaluation["comparison"].outcome == "agreement"
        and all(
            judgment.status == "completed"
            and (judgment.conclusion_label or "").lower() == "positive"
            for judgment in evaluation_judgments
        )
    )
    # Agreement alone is not claim support: unanimous negative/uncertain
    # judgments must never inflate verified/corroborated result metrics.
    verified_count = len(evidence_rows) if positive_consensus else 0
    contradicted_count = sum(1 for edge in evidence_edges if edge.relation_type == "contradicts")
    tool_usefulness.record_usage(
        db, tool_name=f"collector:{task.source}", source=task.source, source_type="collector",
        query=task.query, research_task_id=task.id, claim_id=task.claim_id,
        result_count=len(created_signal_ids), useful_result_count=useful_count,
        novel_result_count=novel_count, verified_result_count=verified_count,
        duplicate_result_count=duplicate_count,
        corroborated_evidence_count=verified_count, contradicted_claim_count=contradicted_count,
        freshness=100.0 if created_signal_ids else None,
        latency_ms=(monotonic() - started) * 1000,
        success=True,
        failure_kind=None,
        result_ids=evidence_ids,
    )
    task_results = final_task.results if isinstance(final_task.results, dict) else {}
    evaluation_status = task_results.get("evaluation_status")
    if not isinstance(evaluation_status, str):
        if not evidence_ids:
            evaluation_status = "not_invoked_no_evidence"
        elif task_results.get("comparison_outcome") == "unassessed":
            evaluation_status = "unassessed_metadata_only"
        else:
            evaluation_status = "not_recorded"

    judgment_rows = evaluation.get("judgments", []) if isinstance(evaluation, dict) else []
    judgments_completed = sum(
        1 for judgment in judgment_rows
        if getattr(judgment, "status", None) == "completed"
    )
    judgments_failed = sum(
        1 for judgment in judgment_rows
        if getattr(judgment, "status", None) != "completed"
    )

    return {
        "task_id": task.id,
        "status": final_task.status,
        "signals_created": len(created_signal_ids),
        "evidence_found": len(set(evidence_ids)),
        "evaluation_status": evaluation_status,
        "comparison_outcome": task_results.get("comparison_outcome"),
        "judgments_completed": judgments_completed,
        "judgments_failed": judgments_failed,
    }


def run_pending_tasks(db: Session, limit: int = 5) -> list[dict]:
    """Run a bounded batch: cover open questions before deepening one.

    Existing ResearchQuestion records provide work-track identity. Source
    clearance, idempotency, and per-task authorization checks remain intact.
    The first pass gives one eligible task from each question a turn before
    any question gets a second task. Remaining budget then follows normal
    priority order; this is bounded work scheduling, not an infinite loop.
    """
    if limit <= 0:
        return []

    research_task_engine.resume_running_tasks(db, limit=limit)
    clearances = source_clearance_registry.source_clearances()
    cleared_collectors = {
        entry.collector
        for entry in clearances
        if entry.collector != "web"
        and source_clearance_registry.collector_is_cleared(entry.collector)
    }
    cleared_web_urls = {
        entry.url
        for entry in clearances
        if entry.collector == "web" and _web_clearance_error(entry.url) is None
    }
    currently_clearable = or_(
        models.ResearchTask.source.in_(cleared_collectors),
        and_(
            models.ResearchTask.source == "web",
            models.ResearchTask.query.in_(cleared_web_urls),
        ),
    )

    outcomes: list[dict] = []
    attempted_task_ids: set[int] = set()
    served_question_ids: set[int] = set()
    coverage_pass = True

    def next_task(*, unserved_question_only: bool) -> models.ResearchTask | None:
        query = (
            db.query(models.ResearchTask)
            .join(models.ResearchQuestion)
            .filter(models.ResearchTask.status == "planned")
        )
        if attempted_task_ids:
            query = query.filter(models.ResearchTask.id.notin_(attempted_task_ids))
        if unserved_question_only:
            # A question with only uncleared source work is not eligible to
            # consume a coverage slot. It remains queued for the normal
            # clearance/error handling pass after other eligible tracks turn.
            query = query.filter(currently_clearable)
            if served_question_ids:
                query = query.filter(
                    models.ResearchTask.question_id.notin_(served_question_ids)
                )
        return query.order_by(
            case((currently_clearable, 0), else_=1),
            models.ResearchQuestion.priority_score.desc(),
            case(
                (
                    models.ResearchTask.results["follow_up_reason"].as_string()
                    == "openalex_content_source_reference_follow_up",
                    0,
                ),
                else_=1,
            ),
            models.ResearchTask.id.asc(),
        ).first()

    while len(outcomes) < limit:
        task = next_task(unserved_question_only=coverage_pass)
        if task is None and coverage_pass:
            coverage_pass = False
            task = next_task(unserved_question_only=False)
        if task is None:
            break

        attempted_task_ids.add(task.id)
        question_id = task.question_id
        priority_score = float(task.question.priority_score) if task.question is not None else None
        dispatch_pass = "question_coverage" if coverage_pass else "throughput"
        if coverage_pass:
            served_question_ids.add(question_id)

        outcome = execute_task(db, task)
        # Operational metadata explains scheduling; it is not evidence by itself.
        if isinstance(outcome, dict):
            outcome = dict(outcome)
            outcome["portfolio_dispatch"] = {
                "policy": "one_task_per_question_before_repeat",
                "pass": dispatch_pass,
                "question_id": question_id,
                "priority_score": priority_score,
                "slot": len(outcomes) + 1,
            }
        outcomes.append(outcome)
    return outcomes

def run_pending_evaluations(
    db: Session,
    limit: int = 2,
    *,
    max_retries_per_task: int = 3,
) -> list[dict]:
    """Retry incomplete substantive evaluation for already-collected evidence.

    Collection tasks are intentionally separate from judge/model execution.
    This bounded recovery pass resumes only existing completed tasks whose
    evaluate step was never run or failed because evaluation was unavailable.
    It never recollects sources, creates synthetic evidence, or performs
    customer-facing actions. Retry counters live in the existing step JSON.
    """
    if limit <= 0 or max_retries_per_task <= 0:
        return []

    candidate_limit = min(max(limit * 20, 20), 200)
    candidates = (
        db.query(models.ResearchTask)
        .filter(
            models.ResearchTask.status == "completed",
            models.ResearchTask.evidence_ids.isnot(None),
            models.ResearchTask.evidence_ids != "",
        )
        .order_by(models.ResearchTask.updated_at.asc(), models.ResearchTask.id.asc())
        .limit(candidate_limit)
        .all()
    )
    retryable_statuses = {
        "not_evaluated",
        "no_judges_available",
        "judge_execution_failed",
        "judge_execution_incomplete",
    }
    outcomes: list[dict] = []

    for task in candidates:
        if len(outcomes) >= limit:
            break
        evaluate_step = next((step for step in task.steps if step.name == "evaluate"), None)
        if evaluate_step is None or evaluate_step.status not in {"pending", "failed", "skipped"}:
            continue
        output = evaluate_step.output_data if isinstance(evaluate_step.output_data, dict) else {}
        previous_status = output.get("status")
        if previous_status not in retryable_statuses:
            # In particular, metadata-only/unassessed evidence is not retried
            # as though a judge could turn bibliographic metadata into proof.
            continue
        try:
            retry_count = int(output.get("automatic_retry_count") or 0)
        except (TypeError, ValueError):
            retry_count = 0
        if retry_count >= max_retries_per_task:
            continue

        evidence_ids = []
        for item in (task.evidence_ids or "").split(","):
            try:
                evidence_id = int(item.strip())
            except (TypeError, ValueError):
                continue
            if evidence_id > 0 and evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
        if not evidence_ids:
            continue

        # Match first-pass semantics for claim-scoped work, but never fetch or
        # collect new sources on this recovery path.
        evaluation_ids = evidence_ids
        if task.claim_id:
            linked_ids = [
                row.evidence_id
                for row in db.query(models.EvidenceRelationship)
                .filter(models.EvidenceRelationship.claim_id == task.claim_id)
                .order_by(models.EvidenceRelationship.id.asc())
                .all()
            ]
            evaluation_ids = list(dict.fromkeys(evidence_ids + linked_ids))
        if not evaluation_ids:
            continue

        prior_status = previous_status
        prior_error = evaluate_step.error
        try:
            from app.services import research_task_engine

            research_task_engine.evaluate_claim_after_research(db, task, evaluation_ids)
            db.refresh(task)
            refreshed_step = next((step for step in task.steps if step.name == "evaluate"), None)
            if refreshed_step is None:
                continue
            updated_output = (
                dict(refreshed_step.output_data)
                if isinstance(refreshed_step.output_data, dict)
                else {}
            )
            next_retry_count = retry_count + 1
            updated_output["automatic_retry_count"] = next_retry_count
            updated_output["automatic_retry_reason"] = prior_status
            refreshed_step.output_data = updated_output
            if refreshed_step.status in {"completed", "skipped"}:
                refreshed_step.error = None
            elif not refreshed_step.error:
                refreshed_step.error = prior_error
            task.updated_at = models.utcnow()
            db.commit()
            db.refresh(task)
            db.refresh(refreshed_step)
            outcomes.append({
                "task_id": task.id,
                "status": refreshed_step.status,
                "evaluation_status": updated_output.get("status", "not_recorded"),
                "retry_count": next_retry_count,
                "max_retries": max_retries_per_task,
                "evidence_count": len(evidence_ids),
            })
        except Exception as exc:
            db.rollback()
            latest = db.get(models.ResearchTask, task.id)
            if latest is not None:
                latest_step = next((step for step in latest.steps if step.name == "evaluate"), None)
                if latest_step is not None:
                    failed_output = (
                        dict(latest_step.output_data)
                        if isinstance(latest_step.output_data, dict)
                        else {}
                    )
                    failed_output["automatic_retry_count"] = retry_count + 1
                    failed_output["automatic_retry_reason"] = prior_status
                    failed_output["recovery_error_type"] = type(exc).__name__
                    latest_step.output_data = failed_output
                    latest_step.error = f"Evaluation recovery failed: {type(exc).__name__}"
                    latest.updated_at = models.utcnow()
                    db.commit()
            outcomes.append({
                "task_id": task.id,
                "status": "failed",
                "evaluation_status": "evaluation_recovery_failed",
                "retry_count": retry_count + 1,
                "error_type": type(exc).__name__,
            })
    return outcomes


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
