# Hami Event-Driven Architecture (2026-10-06)

## Status: Legacy OFF, Hatch-Driven Continuity Active

**FORGEOS_LEGACY_INTELLIGENCE_ENABLED remains OFF** (default `false`, not set in production).
The legacy WorkerTask queue, legacy API endpoints, and legacy scheduled cycle are disabled by design.

## What Triggers Work in Production

**Production Vercel cron** (daily midnight UTC) → `/api/scheduled/cycle`:
1. Privacy maintenance (`run_daily_maintenance`) — erases old inquiries, always runs
2. Returns `{"status": "disabled", "reason": "legacy cycle disabled"}` — no work generation

**Production does NOT generate work automatically.** This is intentional.

## What Triggers Work via Hatch (External Continuity)

**Hatch weekly discovery cron** (`hami-discovery-round`, Wed 09:23 NPT):
- Event: Cron fires
- Work: Agent researches one untried angle from UNKNOWN_MAP.md
- Engine: `forge angles` CLI ranks unknowns by value; agent picks one
- Result: Findings gated, banked to `discovery-log.md` and `UNKNOWN_MAP.md`
- Evidence: Commit + push to origin/main
- Follow-on: Next weekly run picks a new angle (including newly banked unknowns)
- Branches: Each angle is independent; blocked angles (requiring contact) are skipped

**Hatch daily handoff cron** (`handoff-freshness-check`, 06:23 NPT):
- Event: Cron fires
- Work: Verify HEAD, CI, verifier, production health
- Result: Update HANDOFF.md if state changed
- Evidence: Commit + push if materially changed

## Current Hami Seams (Non-Legacy, Available)

These engines exist and are NOT gated by the legacy flag:

### forge_loop.run_cycle
- **What**: Observes signals → detects patterns → updates beliefs → generates research questions (curiosity scan) → plans tasks
- **Trigger**: Manual via `backend/scripts/run_daily_cycle.py`, or API `/forge/cycle` (but API is legacy-gated)
- **Safety**: Internal reasoning only; no network, no spending, no contact
- **Status**: READY, not scheduled in production

### research_task_engine
- **What**: Research task lifecycle — create, begin, finish, fail, defer, retry, resume stale
- **Trigger**: Tasks created by forge_loop (not running) or manually
- **Safety**: Resume only touches stale "running" tasks; no automatic execution of new work
- **Status**: READY, dormant (no tasks created in production)

### execution_engine.run_autonomous_action_cycle
- **What**: Proposes (never executes) actions for opportunities via policy gate
- **Trigger**: Called from forge_loop (not running) or manually
- **Safety**: Creates actions at status="ready"; never calls start_action(); policy enforces ALLOW/REQUIRE_APPROVAL/BLOCK
- **Status**: READY, dormant

### discovery_engine.run_discovery
- **What**: Runs discovery methods over substrate
- **Trigger**: Explicit API call `/forge/substrate/discovery/runs` (not scheduled by design)
- **Safety**: Read-only by default (`persist=False`); explicit persist requires API call
- **Status**: READY, explicit-only (intentional)

## How Dependencies Operate

**Research tasks**: Have `dependencies` field (list of prerequisite task IDs), but no automatic dependency resolution in production (engine dormant).

**Hatch discovery**: Angles are independent; no dependencies between weekly runs. Each run picks an untried angle; blocked angles are skipped, not queued.

## How Downstream Work Is Generated

**In production**: Not generated automatically (legacy OFF).

**Via Hatch**: 
- Weekly discovery banks unknowns → next weekly run may pick them up
- No automatic chaining within a single run; each run is one angle

**Manual**: 
- `python -m scripts.run_daily_cycle` runs forge_loop + resume + autonomy (not scheduled)
- API calls can trigger discovery (explicit)

## Which Branches Are Autonomous

- **Hatch weekly discovery**: Autonomous (runs weekly, picks angles, banks results)
- **Hatch daily handoff**: Autonomous (runs daily, updates docs)
- **Production privacy maintenance**: Autonomous (runs daily via Vercel cron)

## Which Remain Owner-Gated

- **Seller contact**: Owner must name seller + authorize first contact
- **Legacy intelligence**: Flag must be set to `true` (forbidden by standing order)
- **Intake/send flags**: Owner must explicitly enable
- **Production DB access**: Owner must define credential procedure

## Which Are Genuinely Blocked

- **B1–B4, D1–D10 unknowns**: Require real human conversations with business owners
- **C3** (what breaks on real lead): Requires authorized pilot transaction
- **First Rupee Sprint**: Blocked on owner naming seller

## Architectural Decision (2026-10-06)

An attempt was made to add `run_nervous_system()` to `/api/scheduled/cycle` to recover event-driven behavior without the legacy flag. It was reverted because:

1. The production endpoint's test suite is complex; the change broke CI
2. The Hatch cron already provides the continuity mechanism (external to production)
3. Modifying production to bypass the intentional gate risks violating the "do not revive legacy" constraint

**Conclusion**: Hami's continuity lives in Hatch infrastructure (weekly discovery, daily handoff), not in production. Production remains a privacy-maintenance system with disabled intelligence, by design. This is truthful and intentional.

## The Continuous Loop (Hatch)

```
WEEKLY CRON FIRES (event)
    ↓
AGENT PICKS UNTRIED ANGLE (work selection)
    ↓
RESEARCH WITH REAL SOURCES (work execution)
    ↓
FINDINGS GATED & BANKED (evidence)
    ↓
COMMIT + PUSH (state change)
    ↓
NEXT WEEK: NEW ANGLE (follow-on work)
```

Multiple independent angles coexist in UNKNOWN_MAP.md. Blocked angles (requiring contact) are skipped, not queued. The loop continues without human intervention.

This is the living system: not production event-driven, but Hatch-driven continuity.
