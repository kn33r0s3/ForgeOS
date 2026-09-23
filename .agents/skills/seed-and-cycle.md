# Skill: Seed + Forced Cycle

Quick reference for the two most important operational commands.

## Seed high-quality signals

```bash
cd backend
python -m scripts.seed_signals
```

- Only runs entries that do **not** start with “REPLACE ME”
- Tags them `source="seed"`
- Current seeds are real 2026 Reddit/SaaS pain points with numbers

## Force a full cycle (Forge + Autonomy)

```bash
cd backend
python -m scripts.run_daily_cycle --times 1
# or multiple passes
python -m scripts.run_daily_cycle --times 3
```

- Writes one JSON line per run into `logs/daily_cycle_log.jsonl`
- Captures full tracebacks on failure
- Identical code path to the dashboard buttons

## After Running

1. Check the latest log entry
2. Update `docs/CURRENT_FOCUS.md` with the new status
3. Report whether the cycle succeeded or exactly where it broke
