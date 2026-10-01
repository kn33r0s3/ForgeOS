# Session Start Protocol

Every new AI coding session on ForgeOS must begin with this sequence.

## Agent Instructions (execute immediately)

1. Read these files in order:
   - `AGENTS.md`
   - `STATUS.md`
   - `docs/CAPABILITY_QUEUE.md`
   - Latest 2–3 entries of `logs/daily_cycle_log.jsonl` (if present)

2. Reply with exactly this structure:

```
### Session Status
- Current focus: <one sentence>
- Highest-leverage next action: <one concrete task>
- Blockers: <none or short list>
- Ready for direction.
```

3. Do **not** start coding until the human gives an explicit goal or says “go” / “approved”.

## Human Quick Commands

- `status` → agent runs the session start protocol above
- `next` → agent proposes the single highest-leverage task
- `fix cycle` → agent uses the fix-cycle-reliability skill
- `seed` → agent reminds or runs the seed command
- `approved` / `go` → agent proceeds with the last proposed plan
