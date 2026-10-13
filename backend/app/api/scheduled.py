"""Daily privacy maintenance with an optional legacy Forge cycle."""

import hmac
import json
import logging
import os
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import database, models
from app.api.forge_bot_owner_notification import send_daily_owner_summary_notification
from app.config import settings
from app.services.forge_bot_privacy import run_daily_maintenance

router = APIRouter(prefix="/scheduled", tags=["scheduled"])
logger = logging.getLogger(__name__)
_local_cycle_lock = Lock()
_intelligence_lock = Lock()
_POSTGRES_LOCK_ID = 4_706_539_182
_POSTGRES_INTELLIGENCE_LOCK_ID = 4_706_539_183


def _acquire_intelligence_lock():
    """Serialize intelligence cycles across PostgreSQL-backed serverless replicas.

    A process-local Lock remains the fallback for SQLite/local development.
    The returned callback releases whichever lock was acquired.
    """
    if database.engine.dialect.name != "postgresql":
        if not _intelligence_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=409,
                detail="An intelligence run is already running",
            )
        return _intelligence_lock.release

    connection = database.engine.connect()
    try:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": _POSTGRES_INTELLIGENCE_LOCK_ID},
            ).scalar_one()
        )
        connection.commit()
    except Exception as exc:
        connection.close()
        raise HTTPException(
            status_code=503,
            detail="Intelligence lock is unavailable",
        ) from exc

    if not acquired:
        connection.close()
        raise HTTPException(
            status_code=409,
            detail="An intelligence run is already running",
        )

    def release() -> None:
        try:
            unlocked = bool(
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": _POSTGRES_INTELLIGENCE_LOCK_ID},
                ).scalar_one()
            )
            connection.commit()
            if not unlocked:
                logger.warning("scheduled intelligence: PostgreSQL lock was not held at release")
        except Exception as exc:
            # Closing the connection also releases a session-scoped lock if the
            # database invalidated it while the run was in progress.
            logger.warning(
                "scheduled intelligence: PostgreSQL lock release failed (%s)",
                type(exc).__name__,
            )
        finally:
            connection.close()

    return release


def _normalize_owner_sms_digest_result(result: dict) -> dict:
    """Make non-delivery outcomes visible to the cycle classifier.

    The raw delivery/provider state is preserved separately. In particular,
    provider acceptance is not evidence of handset delivery.
    """
    if not isinstance(result, dict):
        return {
            "status": "partial",
            "delivery_status": "unknown",
            "reason": "invalid_digest_result",
        }

    raw_status = str(result.get("status") or "").strip().lower()
    reason = str(result.get("reason") or "")
    normalized = dict(result)

    if raw_status == "provider_accepted":
        normalized["status"] = "ok"
        normalized["delivery_status"] = raw_status
        return normalized

    if raw_status == "skipped" and reason == "owner_sms_digest_disabled":
        return normalized

    if raw_status in {"skipped", "failed", "ambiguous_not_retried", "queued", "sending"}:
        normalized["status"] = "partial"
        normalized["delivery_status"] = raw_status or "unknown"
        return normalized

    # Unknown outcomes fail closed so new provider states cannot disappear
    # behind a COMPLETED cycle status.
    normalized["status"] = "partial"
    normalized["delivery_status"] = raw_status or "unknown"
    return normalized


def _count_effect(value) -> int:
    """Normalize a persisted count without accepting bools, strings, or negatives."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _cycle_effect_summary(intelligence: dict) -> dict:
    """Report real stage effects separately from job completion and real-world proof."""
    forge = intelligence.get("forge_cycle", {})
    collection = intelligence.get("collection_cycle", {})
    discovery = intelligence.get("discovery_cycle", {})
    autonomy = intelligence.get("autonomy_cycle", {})
    scout = intelligence.get("scout_cycle", {})
    content = intelligence.get("content_drafts", {})

    outcomes = collection.get("outcomes", []) if isinstance(collection, dict) else []
    source_signals = sum(
        _count_effect(item.get("signals_created"))
        for item in outcomes
        if isinstance(item, dict) and item.get("status") == "completed"
    ) if isinstance(outcomes, list) else 0

    counts = {
        "source_signals_created": source_signals,
        "discovery_proposals_surfaced": _count_effect(discovery.get("surfaced")) if isinstance(discovery, dict) else 0,
        "research_questions_created": (
            _count_effect(forge.get("questions_created")) if isinstance(forge, dict) else 0
        ) + (
            _count_effect(discovery.get("questions_created")) if isinstance(discovery, dict) else 0
        ),
        "research_tasks_created": _count_effect(forge.get("research_tasks_created")) if isinstance(forge, dict) else 0,
        "opportunities_discovered": _count_effect(forge.get("opportunities_discovered")) if isinstance(forge, dict) else 0,
        "autonomy_actions_proposed": _count_effect(autonomy.get("proposed")) if isinstance(autonomy, dict) else 0,
        "decision_actions_proposed": _count_effect(forge.get("actions_from_decisions")) if isinstance(forge, dict) else 0,
        "contact_drafts_prepared": _count_effect(scout.get("drafts_generated")) if isinstance(scout, dict) else 0,
        "unresolved_contact_drafts": _count_effect(scout.get("drafts_already_open")) if isinstance(scout, dict) else 0,
        "pending_contact_replies": _count_effect(scout.get("pending_contact_replies")) if isinstance(scout, dict) else 0,
        "pending_contact_outcomes": _count_effect(scout.get("pending_contact_outcomes")) if isinstance(scout, dict) else 0,
        "dry_wells_recorded": _count_effect(scout.get("dry_wells_recorded")) if isinstance(scout, dict) else 0,
        "content_drafts_prepared": _count_effect(content.get("drafts_generated")) if isinstance(content, dict) else 0,
    }
    # Keep sourced observations separate from Hami-created work. A draft,
    # proposal or prepared Action is not a world-level effect and must not be
    # labeled as one merely because it was persisted successfully.
    source_observations = (
        ["source_signals_created"] if counts["source_signals_created"] else []
    )
    internal_work = [
        key
        for key in (
            "discovery_proposals_surfaced",
            "research_questions_created",
            "research_tasks_created",
            "opportunities_discovered",
            "autonomy_actions_proposed",
            "decision_actions_proposed",
            "contact_drafts_prepared",
            "content_drafts_prepared",
        )
        if counts[key]
    ]
    status = (
        "source_data_collected"
        if source_observations
        else "internal_work_only"
        if internal_work
        else "no_new_effect"
    )
    if counts["pending_contact_outcomes"]:
        next_owner_attention = "review_pending_contact_outcomes"
    elif counts["contact_drafts_prepared"]:
        next_owner_attention = "review_prepared_contact_draft"
    elif counts["unresolved_contact_drafts"]:
        next_owner_attention = "review_existing_contact_draft"
    elif counts["pending_contact_replies"]:
        next_owner_attention = "wait_for_reply_without_repeat_contact"
    elif status in {"internal_work_only", "no_new_effect"}:
        next_owner_attention = (
            "inspect_blockers_and_choose_a_reality-linked_next_action"
        )
    else:
        next_owner_attention = "review_source_observations_and_choose_the_next_action"

    return {
        "status": status,
        "counts": counts,
        "source_observations": source_observations,
        "internal_work": internal_work,
        "next_owner_attention": next_owner_attention,
        "reality_boundary": (
            "Source records and internal proposals are system outputs. They do not establish a real conversation, "
            "acceptance, fulfillment, payment, or revenue."
        ),
    }


def _cycle_stage_summary(intelligence: dict) -> tuple[str, dict[str, str], dict[str, str]]:
    """Use one classification for both persisted CycleRun state and API output."""
    stage_errors = {
        key: (val.get("error") or val.get("status"))
        for key, val in intelligence.items()
        if isinstance(val, dict) and val.get("status") == "error"
    }
    stage_partials = {
        key: val.get("status")
        for key, val in intelligence.items()
        if isinstance(val, dict) and val.get("status") == "partial"
    }
    # A technically successful run with no recorded effect is not presented as
    # fully successful. Preserve real stage failures/partials as the primary reason.
    effect_summary = intelligence.get("cycle_effect", {})
    if (
        not stage_errors
        and not stage_partials
        and isinstance(effect_summary, dict)
        and effect_summary.get("status") in {"internal_work_only", "no_new_effect"}
    ):
        stage_partials["cycle_effect"] = effect_summary["status"]

    cycle_status = (
        "FAILED" if stage_errors
        else "PARTIAL" if stage_partials
        else "COMPLETED"
    )
    return cycle_status, stage_errors, stage_partials
def _promote_discovery_questions(db, report: dict) -> int:
    """Promote discovery proposals only when recurring question generation is enabled.

    Discovery proposals remain available in the substrate for review. Promotion
    into the operational ResearchQuestion queue is paused until the existing
    backlog has been triaged.
    """
    if not settings.FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED:
        return 0

    questions_created = 0
    for surfaced in report.get("surfaced", []):
        if surfaced.get("kind") != "question":
            continue
        statement = (surfaced.get("statement") or "").strip()
        if not statement or len(statement) > 2000:
            continue
        # Deduplicate across every lifecycle status, including planned.
        existing_q = (
            db.query(models.ResearchQuestion)
            .filter(models.ResearchQuestion.question == statement)
            .first()
        )
        if existing_q:
            continue
        db.add(
            models.ResearchQuestion(
                question=statement,
                status="open",
                priority_score=50.0,  # Discovery-sourced; planner will reprioritize
            )
        )
        questions_created += 1
    if questions_created:
        db.commit()
    return questions_created


_cycle_scheduler = None
if settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
    from app.services.cycle_scheduler import CycleScheduler

    _cycle_scheduler = CycleScheduler(
        backup_interval_seconds=None,
        max_run_seconds=240,
    )


@router.get("/cycle")
def run_scheduled_cycle(authorization: str | None = Header(default=None)):
    """Run daily privacy maintenance and the legacy cycle only when enabled."""
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Scheduled cycle is not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with database.SessionLocal() as db:
            maintenance = run_daily_maintenance(db)
    except SQLAlchemyError as exc:
        logger.error("Forge Bot daily privacy maintenance failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Daily privacy maintenance failed.",
        ) from exc

    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        logger.info("legacy cycle disabled")
        return {
            "status": "disabled",
            "reason": "legacy cycle disabled",
            "maintenance": maintenance,
        }
    if _cycle_scheduler is None:
        raise HTTPException(status_code=503, detail="Legacy cycle is not configured.")

    connection = None
    acquired_postgres_lock = False
    lock_release_deferred = False
    if database.engine.dialect.name == "postgresql":
        connection = database.engine.connect()
        try:
            acquired_postgres_lock = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": _POSTGRES_LOCK_ID},
                ).scalar_one()
            )
            connection.commit()
        except Exception as exc:
            connection.close()
            raise HTTPException(status_code=503, detail="Cycle lock is unavailable") from exc
        if not acquired_postgres_lock:
            connection.close()
            raise HTTPException(status_code=409, detail="A cycle is already running")
    elif not _local_cycle_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A cycle is already running")

    def release_cycle_lock() -> None:
        if connection is not None:
            try:
                if acquired_postgres_lock:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": _POSTGRES_LOCK_ID},
                    )
                    connection.commit()
            finally:
                connection.close()
        elif database.engine.dialect.name != "postgresql":
            _local_cycle_lock.release()

    try:
        record = _cycle_scheduler.run_single_cycle(on_timeout=release_cycle_lock)
        lock_release_deferred = record.get("lock_release_deferred") is True
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cycle failed: {type(exc).__name__}") from exc
    finally:
        if not lock_release_deferred:
            release_cycle_lock()

    if record.get("status") == "timeout":
        raise HTTPException(status_code=504, detail="The canonical cycle timed out")

    forge_error = record.get("forge_cycle_error")
    autonomy_error = record.get("autonomy_cycle_error")
    if forge_error or autonomy_error:
        raise HTTPException(status_code=500, detail="The canonical cycle reported a failure")
    cycle = record.get("forge_cycle") or {}
    try:
        with database.SessionLocal() as db:
            owner_summary = send_daily_owner_summary_notification(db)
    except SQLAlchemyError as exc:
        logger.error(
            "Forge Bot daily owner summary failed with a database error (%s).",
            type(exc).__name__,
        )
        owner_summary_status = "FAILED"
    else:
        owner_summary_status = (
            owner_summary.get("status")
            if owner_summary is not None
            else "SKIPPED_SMTP_NOT_CONFIGURED"
        )
        if owner_summary_status == "FAILED":
            logger.error(
                "Forge Bot daily owner summary failed (delivery=%s).",
                owner_summary.get("delivery_id") if owner_summary else None,
            )
        elif owner_summary_status == "QUEUED":
            logger.warning(
                "Forge Bot daily owner summary remains queued (delivery=%s).",
                owner_summary.get("delivery_id") if owner_summary else None,
            )
    return {
        "status": "completed",
        "maintenance": maintenance,
        "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
        "forge_cycle_failed": bool(forge_error),
        "autonomy_cycle_failed": bool(autonomy_error),
        "owner_summary_status": owner_summary_status,
    }


@router.get("/intelligence")
def run_scheduled_intelligence(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Run Hami's non-legacy intelligence cycle (current lineage, no legacy flag).

    Uses only existing non-legacy engines, called directly (no wrapper):
    - forge_loop.run_cycle: state → patterns → beliefs → questions → tasks.
      Pure DB reasoning; creates plans/proposals, executes nothing.
    - collector_runner.run_pending_tasks: execute planned ResearchTasks via
      collectors. Idempotent per (question_id, source, query); enforces
      source clearance before network access; per-task failure isolation.
    - research_task_engine.resume_running_tasks: requeue stale running tasks.
    - execution_engine.run_autonomous_action_cycle: propose (never execute)
      actions via the owner's AutonomyPolicy gate.

    Safety: bounded network calls via cleared sources only, no spending, no human contact, no external
    commitments. Network access occurs only through collector_runner.run_pending_tasks,
    which enforces source clearance (source_clearance_registry.py) before any fetch.
    Only the five governed sources (OpenAlex, Crossref, World Bank, GDELT, GovInfo)
    are permitted, each with its authorized purpose and rate limits. Idempotent:
    re-running with unchanged state creates minimal new work (engines skip
    already-tasked questions, duplicate actions, etc.).
    Each engine runs in its own DB session with per-engine failure isolation:
    one engine failing is recorded and the others still run.

    This endpoint is separate from /scheduled/cycle (privacy-only contract)
    and is not gated by the legacy intelligence flag.

    Auth: the cron Bearer secret OR the owner X-API-Key. The owner key path
    lets the owner console trigger the supported intelligence path on demand;
    the legacy-gated POST /forge/cycle remains disabled by standing order.
    A run is recorded as a CycleRun row (existing observability model) so the
    owner console can show last execution, per-stage results, and errors.
    """
    secret = os.getenv("CRON_SECRET", "")
    cron_ok = bool(
        secret
        and authorization
        and hmac.compare_digest(authorization, f"Bearer {secret}")
    )
    owner_ok = False
    if not cron_ok:
        # Owner-key alternative: reuse the existing owner gate without raising.
        try:
            from app.security import require_owner_api_key

            require_owner_api_key(request)
            owner_ok = True
        except HTTPException:
            owner_ok = False
    if not cron_ok and not owner_ok:
        if not secret:
            raise HTTPException(
                status_code=503, detail="Scheduled intelligence is not configured"
            )
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Vercel's default SQLite database is stored under /tmp and can disappear
    # with the function instance. Never report an intelligence cycle as
    # completed against storage that cannot durably retain its evidence/state.
    if os.getenv("VERCEL") and database.engine.dialect.name == "sqlite":
        raise HTTPException(
            status_code=503,
            detail="Durable database is required for scheduled intelligence",
        )

    # Cross-instance PostgreSQL advisory lock in production; process-local
    # lock only for SQLite/local development. Never rely on one serverless
    # instance's memory to serialize work across replicas.
    release_intelligence_lock = _acquire_intelligence_lock()

    # Observability: record this run in the existing CycleRun table.
    # A durable RUNNING record is required before work can begin, and failure
    # to finalize it is surfaced rather than disguised as a successful run.
    cycle_run_id: int | None = None
    cycle_started_at = datetime.now(timezone.utc)
    try:
        with database.SessionLocal() as odb:
            # Operating Model v4: dormancy freezes scheduled agent runs too.
            # Check in the same durable session before creating a CycleRun or
            # allowing any reasoning, collection, discovery, or draft work.
            try:
                from app.services import operating_v4

                operating_v4.check_agent_run_allowed(odb)
            except ValueError as exc:
                raise HTTPException(status_code=423, detail=str(exc)) from exc

            # Recover abandoned history before recording a fresh run. Keep the
            # new run usable even if reconciliation itself is unavailable.
            try:
                from app.services import truth_audit

                reconciled = truth_audit.reconcile_stale_cycles(odb)
                if reconciled:
                    logger.warning(
                        "scheduled intelligence: reconciled %s stale CycleRun record(s)",
                        reconciled,
                    )
            except Exception as exc:
                odb.rollback()
                logger.warning(
                    "scheduled intelligence: stale CycleRun reconciliation failed (%s)",
                    type(exc).__name__,
                )
            row = models.CycleRun(started_at=cycle_started_at, status="RUNNING")
            odb.add(row)
            odb.commit()
            odb.refresh(row)
            cycle_run_id = row.id
    except HTTPException:
        release_intelligence_lock()
        raise
    except Exception as exc:
        logger.warning("scheduled intelligence: CycleRun record failed (%s)", type(exc).__name__)
        # Evidence and state work must never run without a durable run record.
        # Release here because the main execution/finalization finally block
        # has not been entered yet.
        release_intelligence_lock()
        raise HTTPException(
            status_code=503,
            detail="Scheduled intelligence run could not be recorded",
        ) from exc

    intelligence: dict = {}

    # Orient from the existing Operating Model contact clock. This is a soft
    # two-day priority signal; the existing 14-day STARVED threshold remains
    # the hard freeze for non-obligatory building.
    contact_state: dict = {
        "days_since_last_contact": None,
        "contact_priority_due": True,
        "starved": True,
        "pending_contact_replies": 0,
        "pending_contact_outcomes": 0,
        "dry_wells_recorded": 0,
        "next_priority": "contact_preparation",
    }
    try:
        with database.SessionLocal() as db:
            from app.services import operating_v4

            contact_state = operating_v4.contact_state(db)
            next_priority = contact_state.get("next_priority")
            if not isinstance(next_priority, str):
                next_priority = (
                    "review_pending_contact_outcomes"
                    if contact_state.get("pending_contact_outcomes", 0)
                    else "contact_preparation"
                    if contact_state.get("contact_priority_due", True)
                    else "evidence_and_value"
                )
                contact_state["next_priority"] = next_priority
            intelligence["operating_priority"] = {
                "status": "ok",
                **contact_state,
            }
    except Exception as exc:
        # Unknown contact state fails toward contact preparation, never toward
        # more building. The stage error remains visible in cycle status.
        logger.warning("scheduled intelligence: contact orientation failed (%s)", type(exc).__name__)
        intelligence["operating_priority"] = {
            "status": "error",
            "error": type(exc).__name__,
            **contact_state,
            "next_priority": "contact_preparation",
        }

    # When contact is overdue, reuse the existing Scout queue before research
    # collection. Scout only drafts; sending still requires the owner's action.
    scout_ran_early = False
    if (
        contact_state.get("contact_priority_due", True)
        or contact_state.get("pending_contact_outcomes", 0) > 0
    ):
        scout_ran_early = True
        try:
            with database.SessionLocal() as db:
                from app.services import scout

                scout_result = scout.run_scout_cycle(db)
                db.commit()
                err_count = len(scout_result.get("errors", []))
                intelligence["scout_cycle"] = {
                    "status": "partial" if err_count else "ok",
                    "priority": contact_state.get("next_priority", "contact_preparation"),
                    "candidates_ranked": scout_result.get("candidates_ranked", 0),
                    "candidates_scored": scout_result.get("candidates_scored", 0),
                    "drafts_generated": scout_result.get("drafts_generated", 0),
                    "drafts_already_open": scout_result.get("drafts_already_open", 0),
                    "pending_contact_replies": scout_result.get("pending_contact_replies", 0),
                    "dry_wells_recorded": scout_result.get("dry_wells_recorded", 0),
                    "blocked": scout_result.get("blocked", 0),
                    "errors": err_count,
                }
        except Exception as exc:
            logger.warning("scheduled intelligence: priority scout failed (%s)", type(exc).__name__)
            intelligence["scout_cycle"] = {
                "status": "error",
                "priority": "contact_preparation",
                "error": type(exc).__name__,
            }

    # Stage 1: reasoning cycle — plans questions/tasks/opportunities/proposals.
    try:
        with database.SessionLocal() as db:
            from app.services import forge_loop

            summary = forge_loop.run_cycle(db)
            stage_errors = summary.get("stage_errors", {})
            # Truthful status: ok only when no internal errors; partial when
            # the cycle completed but one or more sub-operations failed.
            stage1_status = "partial" if stage_errors else "ok"
            intelligence["forge_cycle"] = {
                "status": stage1_status,
                "cycle_id": summary.get("cycle_id"),
                "signals_processed": summary.get("signals_processed", 0),
                "questions_created": summary.get("questions_created", 0),
                "research_tasks_created": summary.get("research_tasks_created", 0),
                "opportunities_discovered": summary.get("opportunities_discovered", 0),
                "actions_from_decisions": summary.get("actions_from_decisions", 0),
                "stage_errors": stage_errors,
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: forge_cycle failed (%s)", type(exc).__name__)
        intelligence["forge_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 2: collection cycle — execute planned ResearchTasks via collectors.
    # Uses the existing collector_runner.run_pending_tasks() which:
    # - processes tasks planned by research_planner (explicit, not indiscriminate)
    # - enforces source clearance via require_cleared_source() before network access
    # - is idempotent per (question_id, source, query) via uq_research_tasks_idempotency_key
    # - handles failures per-task (max_attempts=3) without killing the cycle
    # Does NOT call run_default_collection() — that deliberately skips uncleared feeds.
    try:
        with database.SessionLocal() as db:
            from app.services import collector_runner

            collection_outcomes = collector_runner.run_pending_tasks(db, limit=5)
            outcomes_list = [
                {
                    "task_id": o.get("task_id"),
                    "source": o.get("source"),
                    "status": o.get("status"),
                    "signals_created": o.get("signals_created", 0),
                }
                for o in collection_outcomes
            ]
            # Truthful status: ok only when all outcomes completed; partial
            # when any failed or were deferred. A returned list is not proof
            # of success — check each outcome's status.
            failed_or_deferred = [
                o for o in outcomes_list
                if o.get("status") in ("failed", "deferred")
            ]
            stage2_status = "partial" if failed_or_deferred else "ok"
            intelligence["collection_cycle"] = {
                "status": stage2_status,
                "tasks_executed": len(outcomes_list),
                "tasks_failed": len([o for o in outcomes_list if o.get("status") == "failed"]),
                "tasks_deferred": len([o for o in outcomes_list if o.get("status") == "deferred"]),
                "outcomes": outcomes_list,
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: collection_cycle failed (%s)", type(exc).__name__)
        intelligence["collection_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 3: requeue stale research tasks so eligible work is not stuck.
    try:
        with database.SessionLocal() as db:
            from app.services import research_task_engine

            resumed = research_task_engine.resume_running_tasks(db, limit=10)
            intelligence["resumed_tasks"] = {"status": "ok", "count": len(resumed)}
    except Exception as exc:
        logger.warning("scheduled intelligence: resume_tasks failed (%s)", type(exc).__name__)
        intelligence["resumed_tasks"] = {"status": "error", "error": type(exc).__name__}

    # Stage 4: propose (never execute) actions for opportunities via policy.
    try:
        with database.SessionLocal() as db:
            from app.services import execution_engine

            autonomy = execution_engine.run_autonomous_action_cycle(db)
            counts = autonomy.__dict__ if hasattr(autonomy, "__dict__") else autonomy
            intelligence["autonomy_cycle"] = {
                "status": "ok",
                "proposed": counts.get("proposed", 0),
                "allowed": counts.get("allowed", 0),
                "blocked": counts.get("blocked", 0),
                "require_approval": counts.get("require_approval", 0),
            }
    except Exception as exc:
        logger.warning("scheduled intelligence: autonomy_cycle failed (%s)", type(exc).__name__)
        intelligence["autonomy_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 5: discovery — run the generalized discovery engine over the substrate.
    # Uses app.services.discovery_engine.run_discovery with the DEFAULT_REGISTRY
    # (14 methods including curiosity_questions). Each method runs with per-method
    # failure isolation; findings are validated and persisted via the existing
    # discovery lifecycle (idempotent by fingerprint). Findings are emitted with
    # honest epistemic states (hypothesized/possible) — never as validated.
    # Bounded: max_findings_per_method=10 uses itertools.islice for genuine
    # early-stop (does not materialize the full iterable first). This bounds
    # findings consumed, not DB rows scanned or time spent — see method
    # docstrings for per-method work characteristics.
    # Separate DB session; commit only on success, rollback on failure.
    # Returns only an operational summary (counts), never raw internal details
    # or private records.
    try:
        with database.SessionLocal() as db:
            from app.services import discovery_engine

            try:
                discovery_methods = None
                if not settings.FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED:
                    discovery_methods = [
                        method.name
                        for method in discovery_engine.DEFAULT_REGISTRY.methods()
                        if method.name != "curiosity_questions"
                    ]
                report = discovery_engine.run_discovery(
                    db, methods=discovery_methods, max_findings_per_method=10
                )
                db.commit()
                # Count actually executed methods (status=="ran"), not blocked/errored
                methods_executed = sum(
                    1 for m in report.get("methods", []) if m.get("status") == "ran"
                )
                errors_count = len(report.get("errors", []))
                deferred_count = len(report.get("deferred", []))
                # Truthful status: ok only with no errors and no deferred work;
                # partial when the discovery ran but some methods errored or
                # were deferred. Preserve the distinction among errors,
                # deferred, rejected, and normal no-result findings.
                stage5_status = "partial" if (errors_count or deferred_count) else "ok"
                intelligence["discovery_cycle"] = {
                    "status": stage5_status,
                    "methods_run": methods_executed,
                    "methods_total": len(report.get("methods", [])),
                    "surfaced": len(report.get("surfaced", [])),
                    "existing": len(report.get("existing", [])),
                    "rejected": len(report.get("rejected", [])),
                    "deferred": deferred_count,
                    "errors": errors_count,
                    "capability_gaps": len(report.get("capability_gaps", [])),
                }
                # Keep discovery proposals in existing evidence/substrate records.
                # Promote them into ResearchQuestion only when recurring
                # question generation is explicitly enabled.
                questions_created = _promote_discovery_questions(db, report)
                intelligence["discovery_cycle"]["questions_created"] = questions_created
                intelligence["discovery_cycle"]["question_generation"] = (
                    "enabled"
                    if settings.FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED
                    else "paused_backlog_review"
                )
            except Exception:
                db.rollback()
                raise
    except Exception as exc:
        logger.warning("scheduled intelligence: discovery_cycle failed (%s)", type(exc).__name__)
        intelligence["discovery_cycle"] = {"status": "error", "error": type(exc).__name__}

    # Stage 6: retry previously queued owner emails only.
    # This legacy email retry path does not enqueue new mail or send customer messages.
    try:
        with database.SessionLocal() as db:
            from app.api import forge_bot_owner_notification

            retry_result = forge_bot_owner_notification.retry_queued_owner_notifications(db)
            db.commit()
            if retry_result["status"] == "skipped":
                intelligence["owner_notification_retry"] = {
                    "status": "skipped",
                    "reason": retry_result["reason"],
                    "retried": 0,
                }
            else:
                intelligence["owner_notification_retry"] = {
                    "status": "ok",
                    "retried": retry_result["retried"],
                }
    except Exception as exc:
        logger.warning("scheduled intelligence: owner_notification_retry failed (%s)", type(exc).__name__)
        intelligence["owner_notification_retry"] = {"status": "error", "error": type(exc).__name__}

    # Stage 6b: separate owner-only daily SMS digest. The Vercel schedule for
    # this authenticated intelligence cycle is 06:00 UTC; the feature flag defaults OFF.
    try:
        with database.SessionLocal() as db:
            from app.api import forge_bot_owner_notification

            sms_result = forge_bot_owner_notification.send_daily_owner_status_sms(db)
            intelligence["owner_sms_digest"] = _normalize_owner_sms_digest_result(sms_result)
            db.commit()
    except Exception as exc:
        logger.warning("scheduled intelligence: owner_sms_digest failed (%s)", type(exc).__name__)
        intelligence["owner_sms_digest"] = {"status": "error", "error": type(exc).__name__}

    # Owner inactivity is evaluated daily even when the Telegram digest flag is closed.
    try:
        with database.SessionLocal() as db:
            from app.services import owner_control
            intelligence["owner_control_safety"] = owner_control.evaluate_owner_inactivity(db)
            intelligence["owner_telegram_digest"] = owner_control.send_daily_owner_digest(db)
            db.commit()
    except Exception as exc:
        logger.warning("scheduled intelligence: owner Telegram control failed (%s)", type(exc).__name__)
        intelligence["owner_control_safety"] = {"status": "error", "error": type(exc).__name__}
        intelligence["owner_telegram_digest"] = {"status": "error", "error": type(exc).__name__}

    if not scout_ran_early:
        # Stage 7: scout cycle — autonomous candidate processing.
        # Scores and ranks registered candidates, generates drafts for top
        # eligible ones (draft only, never sends). Uses existing scout.py seams.
        # Isolated: separate DB session, isolated exception handling.
        # A scout failure does not fail or conceal the other stages.
        try:
            with database.SessionLocal() as db:
                from app.services import scout
    
                scout_result = scout.run_scout_cycle(db)
                db.commit()
                err_count = len(scout_result.get("errors", []))
                stage7_status = "partial" if err_count else "ok"
                intelligence["scout_cycle"] = {
                    "status": stage7_status,
                    "candidates_ranked": scout_result.get("candidates_ranked", 0),
                    "candidates_scored": scout_result.get("candidates_scored", 0),
                    "drafts_generated": scout_result.get("drafts_generated", 0),
                    "drafts_already_open": scout_result.get("drafts_already_open", 0),
                    "pending_contact_replies": scout_result.get("pending_contact_replies", 0),
                    "dry_wells_recorded": scout_result.get("dry_wells_recorded", 0),
                    "blocked": scout_result.get("blocked", 0),
                    "errors": err_count,
                }
        except Exception as exc:
            logger.warning("scheduled intelligence: scout_cycle failed (%s)", type(exc).__name__)
            intelligence["scout_cycle"] = {"status": "error", "error": type(exc).__name__}

    # At the hard starvation threshold, non-obligatory building freezes.
    # Public-content drafting is build work, so preserve the gap and report it
    # as intentionally skipped while contact preparation and sensing continue.
    if contact_state["starved"]:
        intelligence["content_drafts"] = {
            "status": "skipped",
            "reason": "STARVED freeze: contact preparation, sensing, verification, and System Obligations only",
            "source_questions_scanned": 0,
            "drafts_generated": 0,
            "existing_drafts": 0,
            "skipped_private_or_sensitive": 0,
            "published": 0,
            "publish_status": "blocked",
            "publish_blockers": ["STARVED operating-model freeze"],
            "errors": 0,
        }
    else:
        # DRAFT content assets into the six-primitive substrate; it never publishes
        # or sends. Publishing remains blocked until an official destination and
        # the corresponding authorization are verified.
        try:
            with database.SessionLocal() as db:
                from app.services import content_loop
    
                content_result = content_loop.run_content_draft_cycle(db)
                db.commit()
                content_status = "partial" if content_result.get("errors") else "ok"
                intelligence["content_drafts"] = {
                    "status": content_status,
                    "source_questions_scanned": content_result.get("source_questions_scanned", 0),
                    "drafts_generated": content_result.get("drafts_generated", 0),
                    "existing_drafts": content_result.get("existing_drafts", 0),
                    "skipped_private_or_sensitive": content_result.get("skipped_private_or_sensitive", 0),
                    "published": 0,
                    "publish_status": content_result.get("publish_status", "blocked"),
                    "publish_blockers": content_result.get("publish_blockers", []),
                    "errors": len(content_result.get("errors", [])),
                }
        except Exception as exc:
            logger.warning("scheduled intelligence: content_drafts failed (%s)", type(exc).__name__)
            intelligence["content_drafts"] = {"status": "error", "error": type(exc).__name__}

    # Record the cycle's actual outputs before finalizing status. A job run is not
    # proof of demand, contact, fulfillment, or revenue.
    intelligence["cycle_effect"] = _cycle_effect_summary(intelligence)

    # Finalize the CycleRun observability record with per-stage outcomes.
    # A response is successful only when its run record is finalized durably.
    try:
        if cycle_run_id is None:
            raise RuntimeError("scheduled_cycle_run_not_started")
        with database.SessionLocal() as odb:
            row = odb.get(models.CycleRun, cycle_run_id)
            if row is None:
                raise RuntimeError("scheduled_cycle_run_missing")
            ended_at = datetime.now(timezone.utc)
            row.ended_at = ended_at
            start = row.started_at
            if start is not None:
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                row.duration_ms = int((ended_at - start).total_seconds() * 1000)
            # One classifier drives persisted state and API response.
            row.status, stage_errors, stage_partials = _cycle_stage_summary(intelligence)
            row.summary_json = json.dumps(
                {
                    "stages": intelligence,
                    "stage_errors": stage_errors,
                    "stage_partials": stage_partials,
                },
                default=str,
            )
            run_notes = [
                *(f"{key}: {value}" for key, value in stage_errors.items()),
                *(f"{key}: partial" for key in stage_partials),
            ]
            if run_notes:
                row.error = "; ".join(run_notes)
            odb.commit()
    except Exception as exc:
        logger.warning(
            "scheduled intelligence: CycleRun finalize failed (%s)", type(exc).__name__
        )
        raise HTTPException(
            status_code=503,
            detail="Scheduled intelligence results could not be persisted",
        ) from exc
    finally:
        release_intelligence_lock()

    # "status" describes this HTTP request; cycle_status describes the work.
    # A successful response must not disguise partial or failed cycle stages.
    cycle_status, stage_errors, stage_partials = _cycle_stage_summary(intelligence)
    return {
        "status": "completed",
        "cycle_run_id": cycle_run_id,
        "cycle_status": cycle_status,
        "stage_errors": stage_errors,
        "stage_partials": stage_partials,
        "intelligence": intelligence,
    }
