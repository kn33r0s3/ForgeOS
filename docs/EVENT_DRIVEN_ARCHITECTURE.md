# Hami Event-Driven Architecture (2026-10-07)

## Status: Legacy OFF, Production Intelligence Seam Active

**The legacy intelligence path remains fail-closed by default** (`FORGEOS_LEGACY_INTELLIGENCE_ENABLED=false` in code defaults). The production environment value is not independently proven by this source document; do not infer activation from code. The midnight `/scheduled/cycle` path is a privacy-maintenance endpoint and must not be expanded to run intelligence.

## What Triggers Work in Production

**Configured Vercel cron** (daily midnight UTC) → `/api/scheduled/cycle`:
1. Privacy maintenance (`run_daily_maintenance`) — erases old inquiries, always runs
2. Returns `{"status": "disabled", "reason": "legacy cycle disabled"}` — no work generation

**Configured Vercel cron** (daily 06:00 UTC) → `/api/scheduled/intelligence` (source path present since 2026-10-07):
1. `forge_loop.run_cycle` — DB reasoning: signals → patterns → beliefs → questions → tasks
2. `collector_runner.run_pending_tasks` — executes planned research tasks via collectors
3. `research_task_engine.resume_running_tasks` — requeues stale running tasks
4. `execution_engine.run_autonomous_action_cycle` — proposes (never executes) actions
5. `discovery_engine.run_discovery` — runs generalized discovery methods over substrate
   (now 15 methods including ignorance_map). Surfaced question findings are
   automatically converted to ResearchQuestion rows, closing the loop so the
   next cycle's planner can investigate them.
6. `forge_bot_owner_notification.retry_queued_owner_notifications` — retries already-queued owner notices only (NEW)
7. `scout.run_scout_cycle` — scores/ranks candidates, generates drafts (never sends) (NEW 2026-10-10)
8. Returns `{"status": "completed", "intelligence": {...}}` with per-engine results

**Source wiring:** the existing intelligence endpoint calls the listed engines without enabling the legacy flag or adding a second scheduler. Discovery runs in Stage 5, persists through the current EVENT/EVIDENCE/RELATION lifecycle, and can promote question findings only under the existing automatic-question-generation setting. The discovery route also remains available for explicit owner-triggered runs.

**Runtime proof boundary:** `vercel.json` declares the daily schedule, and exact-SHA deploy verification confirms which source is deployed. Neither proves that Vercel naturally invoked the intelligence cron, that a scheduled run committed successfully, or that all collection sources were authorized and usable at that time. Those require a persisted `CycleRun` and corroborating runtime evidence. Treat natural scheduled invocation as UNVERIFIED until that evidence is available.

## External continuity paths (runtime verification separate)

**Recorded handoff configuration for a Hatch weekly discovery cron** (`hami-discovery-round`, Wed 09:23 NPT; current live status not verified in this audit):
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

## Current Hami Seams — source-wired versus runtime-proven

The source paths below are present in `backend/app/api/scheduled.py` and are invoked by `GET /scheduled/intelligence`; that endpoint is configured for the daily 06:00 UTC cron. Exact-head CI verifies code and tests. It does **not** prove that the natural cron has executed against the production database.

### `forge_loop.run_cycle`
- **What:** reads recorded signals, detects patterns, updates beliefs, generates questions and plans research tasks.
- **Trigger:** called as part of the scheduled intelligence path; also has a local runner. The legacy `/forge/cycle` endpoint remains separately gated.
- **Safety:** internal reasoning/planning; no customer messaging or autonomous real-world commitment from this call alone.
- **Runtime state:** invocation and persisted side effects from a natural production cron remain UNVERIFIED.

### `collector_runner.run_pending_tasks` and `research_task_engine`
- **What:** executes bounded planned research tasks through exact-source-clearance adapters and repairs stale running tasks; failures are isolated and recorded.
- **Trigger:** collector execution and stale-task recovery are wired into the scheduled intelligence endpoint.
- **Safety:** source clearance, field purpose, rate reservations, task identity and existing retry limits remain required. A collected result is not by itself a semantic evaluation or supported claim.
- **Runtime state:** actual production collection, source authorization freshness and durable task effects require a run record and per-stage evidence; they are not proven by source presence.

### `execution_engine.run_autonomous_action_cycle`
- **What:** proposes actions under the existing decision-rights/autonomy policy; a proposal or policy ALLOW is not proof of execution.
- **Trigger:** wired into the scheduled intelligence endpoint.
- **Safety:** action-time rights and approval gates remain in force; this cycle does not by itself establish a completed real-world action.
- **Runtime state:** proposal effects and any subsequent action execution must be verified from their own EVENT/outcome lineage.

### `discovery_engine.run_discovery`
- **What:** runs the current 15-method registry against Hami's recorded substrate. Findings are proposed hypotheses/questions, not external observations; every persisted finding cites basis rows and creates provenance-bearing EVIDENCE. Candidate relationships remain `possible` until the normal evidence lifecycle justifies more.
- **Trigger:** wired into Stage 5 of scheduled intelligence, as well as the owner-guarded explicit discovery endpoint.
- **Continuation:** per-method cursors are stored as opaque digests in the existing `discovery_run_completed` EVENT, so bounded windows advance rather than repeatedly consuming the same first findings. Preview remains read-only.
- **Runtime state:** the path is implemented and current tests pass; natural scheduler invocation and production persistence remain UNVERIFIED.

## How Dependencies Operate

**Research tasks:** the model includes prerequisite task IDs, and the scheduled path executes planned tasks and resumes stale running tasks. This document does not claim that every dependency is automatically resolved in production; validate the exact task transitions and persisted effects from a real `CycleRun`.

**External/Hatch discovery:** the historic operating notes describe independent angles. Confirm the currently active scheduler and its run log before treating weekly cadence or untried-angle selection as a live guarantee. A blocked real-world angle must not block safe internal research or capability work.

## How Downstream Work Is Intended to Generate

**When `GET /scheduled/intelligence` executes successfully**, the existing path calls:
- the forge reasoning loop for patterns, beliefs, questions and task planning;
- bounded collection through cleared source adapters;
- stale research-task recovery and proposal-only autonomy reasoning;
- the substrate discovery engine, including cross-domain candidate connections and follow-up questions;
- existing owner-notification retry and Scout draft preparation paths.

The design gives the next run recorded state to build on, but only source-level tests and a real persisted `CycleRun` can establish which stages actually executed. Collection is not evaluation, a question is not an answer, a possible relation is not a fact, and a proposed action is not completed work. Failures are meant to be isolated and visible, not converted to green status or fabricated learning.

**Local/manual runners** can exercise selected existing engines, but they do not count as evidence that production cron or a durable production database ran them.

## Automation versus verified operation

- **Configured source automation:** Vercel declares a daily privacy-maintenance route and a daily scheduled-intelligence route.
- **Code-wired execution:** the intelligence route calls the reasoning, collection, recovery, proposal, discovery, owner-notification retry and Scout paths.
- **Natural runtime execution:** UNVERIFIED in this audit. Require a persisted `CycleRun`, per-stage outcomes and deployed-SHA correlation.
- **External action:** remains governed by the existing authorization, consent, decision-rights, source and action-time gates. Internal automation does not authorize customer contact, publishing, spending or payments.

## Evidence-gated commercial questions (not Hami-wide blockers)

Some specific claims cannot be resolved without firsthand human evidence or an authorized real-world transaction. That blocks only the dependent claim/experiment. It does not block broad investigation, source verification, cross-domain connection discovery, model/tool capability work, security, testing, or other independent work. Commercial work may remain a hypothesis; it does not define Hami's identity or the boundary of the system.

## Architectural Decision (2026-10-07)

An attempt was made on 2026-10-06 to add `run_nervous_system()` to `/api/scheduled/cycle`
to recover event-driven behavior without the legacy flag. It was reverted because it
changed the privacy endpoint's contract and broke CI.

On 2026-10-07, the correct seam was implemented: a separate `GET /scheduled/intelligence`
endpoint in the existing scheduled router, triggered by a second Vercel cron entry.
This preserves the privacy endpoint's contract, uses the existing scheduled boundary
(Vercel cron), calls existing non-legacy engines directly (no new abstraction), and
keeps the legacy flag OFF.

**Conclusion:** Hami has a source-wired work-generation seam with daily cron configuration. The current repository and verified tests show the intended path is connected; they do not establish a natural production cron invocation or successful persistent effects. Do not report the cron as operational until a real `CycleRun` and stage outcomes are observed.

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

This diagram describes the intended Hatch continuity protocol, not a verified claim that the external scheduler is currently running. Production scheduled intelligence is a separate, source-wired daily path whose natural invocation must be evidenced independently.
