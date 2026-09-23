# Phase 1 — Force the loop to produce something real

This tracks the operating plan agreed on 2026-09-12. It is a plan for
*days of running the system*, not something a single code change can
finish — the code changes below just remove the friction that was
blocking Phase 1 from being run at all.

## What changed in this pass

1. **`backend/scripts/seed_signals.py`** — injects hand-authored,
   concrete signals through the real `ObserverEngine.observe()` path
   (same quality scoring, same duplicate checks as any collector).
   **Edit the placeholder content in this file with real findings
   before running it** — it does not bypass the quality bar, it just
   gives you full control over what enters instead of waiting on
   collectors. Run: `python -m scripts.seed_signals` from `backend/`.

2. **`backend/scripts/run_daily_cycle.py`** — runs one Forge Cycle +
   one Autonomy Cycle back to back (identical to clicking both buttons
   in the dashboard) and appends a JSON line per run to
   `logs/daily_cycle_log.jsonl`, including full tracebacks on any
   stage failure. This is the "log exactly where the pipeline breaks"
   mechanism. Run multiple forced passes with `--times N`. A cron
   example for a daily 07:00 run is in the script's docstring.

3. **Nav simplified** — `frontend/components/Nav.tsx` now shows only
   Core / Opportunities / Execution / Revenue on the primary bar.
   World, Knowledge, and Analyze moved to a "More" dropdown — nothing
   removed, just de-emphasized per "reduce cognitive load on the core
   path." Move them back once a full cycle is reliably producing
   results.

## What did NOT change (already existed, already fits the plan)

- **Experiment log**: the `Experiment` model + `/forge/experiments`
  endpoints already record hypothesis / method / result / revenue /
  confidence_change per opportunity — this *is* the lightweight
  experiment log Phase 2 asks for. No new table was needed.
- **Money Engine**: `money_engine.score_opportunity()` already
  refuses to compute `expected_value` from a guess — it requires a
  real recorded price/revenue figure AND nonzero `revenue_confidence`.
  The `$0.00` line moving is a data problem (no opportunity has
  cleared evidence + been priced yet), not a scoring-logic problem.
- **Cycle diagnostics**: `forge_loop.run_cycle()` already records a
  `CycleRun` row and per-stage errors independently, so one broken
  stage doesn't mask the rest. `run_daily_cycle.py` just makes running
  it daily/repeatedly a single command instead of manual clicks.

## What's genuinely still open (not a code task)

- Why most signals cap at ~25/100: that ceiling in
  `signal_quality.py` is the *near-duplicate* hard cap, not a tunable
  threshold someone forgot to raise. The fix is upstream — collectors
  (RSS/Reddit/arXiv/GitHub) are likely returning highly similar items
  to each other. Worth checking `logs/daily_cycle_log.jsonl` after a
  few days of forced runs to see which source's signals are getting
  flagged `duplicate_of_signal_*` most often, and either narrowing
  that collector's query or dropping it.
- Definition of done for Phase 1 (one opportunity clears evidence,
  gets a money score, and executes or gets a recommendation within 24
  hours) can only be checked by actually running the seeded + forced
  cycles and watching what happens — that's the next step, not
  something this pass can complete on your behalf.
