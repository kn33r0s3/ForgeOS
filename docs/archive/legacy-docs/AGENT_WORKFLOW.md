# ForgeOS Local Agentic Coding Workflow

This is the operating manual for every AI coding session on ForgeOS.
It is designed for local-first agentic work (Ollama, Cursor, Claude Code, Continue, Aider, etc.).

## The Only Allowed Loop

```
Intent → Plan (wait for approval) → Implement → Verify → Review & Memory
```

Never skip the approval gate on non-trivial changes.

### Phase 1 — Intent
Human states a goal.
Agent restates it as a precise, testable outcome.

### Phase 2 — Plan
Agent produces:
- Goal restatement
- Exact files that will be touched
- Step-by-step implementation plan
- Acceptance criteria (how we know it worked)
- Risks / things that could break

**Stop and wait for human to say “approved” or “go”.**

### Phase 3 — Implement
- Smallest possible diff
- Follow existing ForgeOS patterns
- No drive-by refactors
- Prefer fixing the cycle / belief commit path over new features

### Phase 4 — Verify
Agent must give the human exact commands:

```bash
# Example
cd backend
python -m scripts.run_daily_cycle --times 1
# then open http://localhost:3000 and check Core page
```

Agent fixes whatever fails.

### Phase 5 — Review & Memory
- Update `docs/CURRENT_FOCUS.md`
- Update `AGENTS.md` if any rule changed
- Summarize what is now true and what the next highest-leverage task is

## Project Memory Files

| File                    | Purpose                                      |
|-------------------------|----------------------------------------------|
| `AGENTS.md`             | Permanent rules for every agent              |
| `docs/CURRENT_FOCUS.md` | What we are working on right now             |
| `docs/PHASE1_PLAN.md`   | Original Phase 1 operating plan              |
| `docs/AGENT_WORKFLOW.md`| This file                                    |
| `logs/daily_cycle_log.jsonl` | Diagnostic history of forced cycles     |

## Session Startup Checklist (Agent must do this first)

1. Read `AGENTS.md`
2. Read `docs/CURRENT_FOCUS.md`
3. Skim latest entries in `logs/daily_cycle_log.jsonl`
4. Report the single highest-leverage next action
5. Wait for direction

## ForgeOS-Specific Guardrails

- Never lower signal quality thresholds
- Never invent revenue or expected value
- Prefer transaction isolation fixes over adding new stages to the loop
- Keep UI changes inside the premium glass system
- Default to `AI_PROVIDER=mock` unless human requests real model calls
- Seed signals must remain concrete, sourced, and numbered

## Recommended Local Tooling

- **Editor / Agent**: Cursor or VS Code + Continue / Claude Code
- **Local model**: Ollama + qwen3-coder (or whatever is already configured)
- **Fallback**: `AI_PROVIDER=mock` for reliable testing without GPU load
- **Terminal layout**: one pane for backend, one for frontend, one for cycle logs

## Definition of Done for Current Phase

Phase 1 is complete only when:

1. Forced daily cycle runs without disk I/O or “session in prepared state” errors
2. At least one opportunity clears the evidence bar
3. That opportunity receives a real money score (or a clear “insufficient evidence” reason)
4. The system can either execute a limited autonomy action or produce a concrete recommendation within 24 hours of a cycle

Until those four items are true, new feature work is secondary.
