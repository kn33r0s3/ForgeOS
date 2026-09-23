"""
FORGE BACKGROUND WORKER
=========================

Runs Forge's intelligence cycle automatically on an interval, in its
OWN process — separate from `uvicorn app.main:app`, so it can never
block an incoming API request. Both processes read/write the same
SQLite file at ../storage/forge.db.

Each iteration ("Forge wakes up"):
  1. Autonomous collection — every network collector (Reddit, GitHub,
     RSS, arXiv) is called with NO query, so each falls back to its own
     default feed/topic. This is what lets Forge observe reality with
     zero human input and zero prior Curiosity-Engine questions — the
     actual mechanism behind "Forge wakes up without you manually
     feeding it," not just a description of intent.
  2. Curiosity-driven collection — up to a handful of currently-planned
     ResearchTasks (generated from questions Forge has already asked
     itself) are executed.
  3. One full forge_loop.run_cycle(): patterns -> beliefs -> reality
     check -> prediction resolution -> new questions -> new tasks.

All three steps are best-effort: a dead feed, a rate-limited API, or a
transient DB issue is logged and skipped rather than killing the
worker — it just tries again next interval.

Run it (from the backend/ directory, same place you'd run uvicorn):

    python worker.py                  # default 30-minute interval
    python worker.py 60               # custom interval in seconds

Stop with Ctrl+C. Safe to run with or without the API server running
at the same time.
"""

import sys
import time
from datetime import datetime, timezone

from app.database import SessionLocal, init_db
from app.services import forge_loop, source_manager, collector_runner, money_engine, autonomy_engine, scenario_engine

DEFAULT_INTERVAL_SECONDS = 1800  # 30 minutes — real network sources have rate limits; adjust to taste
TASKS_PER_CYCLE = 5


def run_forever(interval: int = DEFAULT_INTERVAL_SECONDS) -> None:
    init_db()

    # Seed an initial discovery task if the queue is empty
    db = SessionLocal()
    try:
        from app.models import WorkerTask
        if db.query(WorkerTask).filter(WorkerTask.status == "queued").count() == 0:
            initial = WorkerTask(
                worker_type="discovery",
                task_name="initial_discovery",
                priority=1,
                inputs={},
            )
            db.add(initial)
            db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        source_manager.seed_default_sources(db)
        money_engine.seed_default_revenue_sources(db)
        autonomy_engine.seed_default_policy(db)
        scenario_engine.seed_default_scenarios(db)
        scenario_engine.seed_musk_forecaster_and_predictions(db)
        scenario_engine.seed_phase1_indicators(db)
    finally:
        db.close()

    print(f"[forge-worker] starting — one cycle every {interval}s. Ctrl+C to stop.")

    while True:
        started = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            # Process persistent worker tasks
            from app.services.worker_manager import process_worker_tasks
            process_worker_tasks(db)
            print(
                f"[forge-worker] {started.isoformat()} processed worker tasks"
            )

            # Process outbound integration queue (e.g. SMS delivery)
            from app.services.integration_dispatcher import dispatch_pending_deliveries
            deliveries_attempted = dispatch_pending_deliveries(db)
            if deliveries_attempted > 0:
                print(
                    f"[forge-worker] {started.isoformat()} processed {deliveries_attempted} outbound deliveries"
                )
        except Exception as exc:
            # A single bad cycle (e.g. a transient DB or network issue)
            # should never kill the worker — log it and try again next
            # interval.
            print(f"[forge-worker] cycle failed: {exc}", file=sys.stderr)
        finally:
            db.close()

        time.sleep(interval)


if __name__ == "__main__":
    requested_interval = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INTERVAL_SECONDS
    run_forever(requested_interval)
