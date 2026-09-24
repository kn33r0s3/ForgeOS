"""
DAILY FORCED CYCLE RUNNER — Phase 1
======================================

Runs one Forge Cycle followed by one Autonomy Cycle, end to end, and
appends a structured diagnostic line to logs/daily_cycle_log.jsonl.

This exists so "run it every day and log exactly where it breaks" is a
single command instead of a manual set of clicks through the UI. It
calls the exact same service functions the API endpoints call
(forge_loop.run_cycle / execution_engine.run_autonomous_action_cycle),
so results are identical to clicking "Run Forge Cycle" / "Run Autonomy
Cycle" in the dashboard — this is a scheduling convenience, not a
different code path.

Usage:
    cd backend && python -m scripts.run_daily_cycle
    # or, for multiple forced passes in one day:
    python -m scripts.run_daily_cycle --times 3

Cron example (once daily at 07:00):
    0 7 * * * cd /path/to/ForgeOS/backend && .venv/bin/python -m scripts.run_daily_cycle >> logs/cron.log 2>&1
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database as app_database
from app.services import forge_loop, execution_engine

# Backward-compatible hook for tests and any direct monkeypatches.
_ORIGINAL_SESSION_LOCAL = app_database.SessionLocal
SessionLocal = _ORIGINAL_SESSION_LOCAL

LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "daily_cycle_log.jsonl"

# A SQLite commit can fail transiently (disk I/O on a container overlayfs,
# a momentary lock, WAL checkpoint pressure). We must never let one failed
# commit poison the shared ORM Session for the rest of the run: after any
# stage failure we roll the session back to a clean state before the next
# stage touches it. Rollback drops nothing already committed (SQLAlchemy
# commits are durable the moment they succeed); it only discards the
# un-committed pending state of the failed stage, which is exactly what we
# want — a half-written stage must not leak into the next one.
#
# These error types are the recoverable/"retry-safe" classes: a transient
# squential commit failure in one stage should be recorded as such, and the
# run must continue so later stages can still execute and report.
_RECOVERABLE = (OSError, Exception)  # keep it broad; every rollback path is safe


def _rollback_if_needed(db, label: str) -> None:
    """Roll back any in-flight transaction so the shared session is clean
    before the next stage runs. Record whether we had to, for diagnostics."""
    try:
        db.rollback()
    except Exception:
        # Even the rollback is best-effort; never let recovery itself crash
        # the run loop. The session is closed at the end regardless.
        try:
            db.expunge_all() if hasattr(db, "expunge_all") else None
        except Exception:
            pass


def run_once() -> dict:
    app_database._configure_engine()
    factory = SessionLocal if SessionLocal is not _ORIGINAL_SESSION_LOCAL else app_database.SessionLocal
    db = factory()
    record = {"timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        # --- Stage 1: Forge cycle. A failure here must not poison Stage 2. ---
        try:
            cycle_summary = forge_loop.run_cycle(db)
            record["forge_cycle"] = cycle_summary
            # Bounded collection of tasks the scan just planned. Default is
            # small so one cycle cannot block on the network. Set
            # FORGEOS_COLLECT_LIMIT=0 to plan questions without fetching.
            # Returned items are observations, not public facts.
            collect_limit = int(os.environ.get("FORGEOS_COLLECT_LIMIT", "2"))
            from app.services import research_task_engine
            resume_limit = int(os.environ.get("FORGEOS_RESUME_LIMIT", "10"))
            record["resumed_tasks"] = research_task_engine.resume_running_tasks(db, limit=resume_limit)
            if collect_limit > 0:
                from app.services import collector_runner
                record["collection"] = collector_runner.run_pending_tasks(db, limit=collect_limit)
            from app.services import evidence_graph, network_connections
            claim_limit = int(os.environ.get("FORGEOS_CLAIM_LINK_LIMIT", "20"))
            record["restored_source_addresses"] = evidence_graph.restore_source_addresses(db, limit=claim_limit)
            record["linked_claims"] = evidence_graph.link_unclaimed_observations(db, limit=claim_limit)
            record["connections"] = [
                row.id for row in network_connections.scan_candidates(db, limit=50)
            ]
        except Exception as exc:
            record["forge_cycle_error"] = f"{type(exc).__name__}: {exc}"
            record["forge_cycle_traceback"] = traceback.format_exc()
            # A failed mid-cycle commit (e.g. disk I/O) leaves the session in
            # 'prepared'/'partially-rolledback' state. Discard it cleanly so
            # the autonomy cycle below can still run safely.
            record["forge_cycle_recovered"] = True
            _rollback_if_needed(db, "forge_cycle")
        else:
            # Even on success, be defensive: run_cycle() commits internally in
            # many small steps, and any of those could have left odd state if
            # there was an intervening exception swallowed by a stage guard.
            try:
                db.rollback()
            except Exception:
                pass

        # --- Stage 2: Autonomy cycle, on a clean session. ---
        try:
            autonomy_summary = execution_engine.run_autonomous_action_cycle(db)
            record["autonomy_cycle"] = (
                autonomy_summary.__dict__ if hasattr(autonomy_summary, "__dict__") else autonomy_summary
            )
        except Exception as exc:
            record["autonomy_cycle_error"] = f"{type(exc).__name__}: {exc}"
            record["autonomy_cycle_traceback"] = traceback.format_exc()
            record["autonomy_cycle_recovered"] = True
            _rollback_if_needed(db, "autonomy_cycle")
    finally:
        db.close()
    return record


def _json_default(obj):
    # Best-effort fallback for SQLAlchemy/pydantic objects that aren't
    # plain dicts — never let logging itself crash the cycle run.
    try:
        return obj.__dict__
    except Exception:
        return str(obj)


def main():
    parser = argparse.ArgumentParser(description="Force N Forge+Autonomy cycles and log diagnostics.")
    parser.add_argument("--times", type=int, default=1, help="How many forced passes to run (default 1).")
    args = parser.parse_args()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    for i in range(args.times):
        print(f"--- Forced cycle {i + 1}/{args.times} ---")
        record = run_once()
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(record, default=_json_default) + "\n")

        if "forge_cycle_error" in record:
            print(f"  FORGE CYCLE FAILED: {record['forge_cycle_error']}")
        else:
            print(f"  forge cycle ok: {record.get('forge_cycle')}")

        if "autonomy_cycle_error" in record:
            print(f"  AUTONOMY CYCLE FAILED: {record['autonomy_cycle_error']}")
        else:
            print(f"  autonomy cycle ok: {record.get('autonomy_cycle')}")

    print(f"\nAppended {args.times} record(s) to {LOG_PATH}")


if __name__ == "__main__":
    main()
