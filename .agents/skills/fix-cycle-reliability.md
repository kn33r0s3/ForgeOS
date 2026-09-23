# Skill: Fix Cycle Reliability

Use this skill when the human asks to stabilize the daily Forge + Autonomy cycle.

## Goal
Make `python -m scripts.run_daily_cycle` complete without:
- `sqlite3.OperationalError: disk I/O error`
- `InvalidRequestError: This session is in 'prepared' state`

## Investigation Order

1. Read `logs/daily_cycle_log.jsonl` (latest entries)
2. Read the traceback — it almost always points at `belief_engine.py` → `db.commit()`
3. Inspect `forge_loop.py` around the belief formation loop
4. Inspect `belief_engine.py` (`form_belief_from_pattern`, `_record_confidence_event`)

## Preferred Fix Pattern

- Keep transactions short
- Prefer per-belief or per-stage commit + explicit rollback on failure
- Avoid long-lived sessions that accumulate many objects then commit once
- Consider `session.begin_nested()` (savepoints) if the outer transaction must stay open
- Ensure `run_daily_cycle.py` always closes the session cleanly even on exception

## Acceptance Criteria

```bash
cd backend
python -m scripts.run_daily_cycle --times 1
```

Must produce a log line containing successful `forge_cycle` (not only `forge_cycle_error`).

## Do Not

- Lower signal quality thresholds
- Delete historical signals
- Switch AI_PROVIDER away from mock unless asked
- Refactor the entire loop “while we’re here”
