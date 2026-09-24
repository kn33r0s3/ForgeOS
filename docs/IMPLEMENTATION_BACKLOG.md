# ForgeOS implementation backlog

Belief detail for step S5 in `docs/SERIAL_PATH.md`. That file is the only work order. Do not start these tasks while S0 through S4 are open.
Copilot implements. This file is the spec. Do not treat a task as DONE until the code and tests exist.

Rule: one Forge. Extend the named component. Do not add a second database, API, scheduler, research engine, matching engine, outcome system, or frontend.

## Architecture map (current)

```text
storage/forge.db
  → FastAPI app.main
  → public router (/public/*) consumed by root src/
  → forge router (/forge/*) consumed by frontend/ cockpit
  → scripts/scheduler.py → cycle_scheduler → run_daily_cycle
       → forge_loop.run_cycle
            → pattern_engine.detect_patterns
            → belief_engine.form_belief_from_pattern
            → curiosity scan + standing research agenda
            → research planner
       → bounded collectors (FORGEOS_COLLECT_LIMIT)
       → network_connections.scan_candidates
       → execution_engine.run_autonomous_action_cycle (proposes, does not execute external contact)
```

Public surfaces: `/`, `/providers`, `/domain`, `/discoveries`, `/requests/$id`.
Cockpit surfaces: `/knowledge`, `/research`, `/network`, `/actions`, `/outcomes`, `/runtime`.

## Area status

| Area | Status |
| --- | --- |
| Persistence, API, scheduler, forge_loop | EXISTS |
| Signals, evidence, research questions, collectors, curiosity | EXISTS |
| Claims | PARTIAL — states exist; stale is a freshness label, not a claim state |
| Patterns | BROKEN — overlap merge still emits a new title from a different top-4 keyword slice |
| Beliefs | BROKEN — one belief per title string; template asserts a "real, addressable business problem"; confidence is frequency |
| Discoveries, connections, payments, disputes, trust, alerts | PARTIAL — wired, truth-gated, not a settlement rail |
| Opportunities | PARTIAL — connection hypotheses are honest; `opportunity_from_idea` can still invent price and buyer |
| Public frontend, cockpit | PARTIAL — grouped pages exist; knowledge page still renders the bad beliefs |
| Matching | PARTIAL — city/token overlap, no independent-source confidence |
| Transactions | PARTIAL — booking and recorded payment events, not a money rail |
| Integrations, AI providers | EXISTS / PARTIAL — outbox exists; reasoning must degrade if a model is absent |
| Migrations | PARTIAL — additive column sync |
| Resilience, observability | PARTIAL — cycle lock and rollback exist; runtime page is counts only |
| Vercel / production | PARTIAL — deploy docs exist; a deploy is not proof the cycle runs |
| Safety coordination | MISSING — do not build until an evidence threshold exists |
| Identity, geospatial, owned settlement | MISSING — add only when a later task cannot proceed without them |

## Critical path

```text
TASK-001 canonical beliefs (this is the broken knowledge source)
  → TASK-002 knowledge page reads the canonical belief, not keyword prose
  → TASK-003 independent-source confidence
  → TASK-004 opportunity creation refuses a belief that has no corroboration
  → TASK-005 cycle keeps one belief identity across restarts
```

Do not start TASK-002 until TASK-001 is in the repository.

## Blockers

None for TASK-001. It is READY.

Do not block on a new model. `Pattern` and `Belief` already exist.

## Copilot execution rules

- Extend only the files named in the task.
- Do not add a router, a database, a scheduler, or a frontend.
- Do not delete raw signals.
- Do not present test rows as production truth.
- Run the listed tests, then the full backend suite.
- Leave the task status for review. Do not mark DONE in this file yourself unless the tests passed in that same change.

---

## TASK-001

Title: Collapse keyword-permutation patterns into one hypothesis belief.

Goal: Stop the cycle from storing many beliefs that are the same keyword soup with a different token order, and stop calling that soup a real business problem.

Current state: `pattern_engine.detect_patterns` builds a title from the four most frequent keywords in a cluster (`Recurring theme: a, b, c, d`). A later cycle whose top four differ by one token inserts a new `Pattern`. `belief_engine.form_belief_from_pattern` copies that title into `Recurring signals about "..." indicate a real, addressable business problem.` and dedupes only on the exact sentence. `forge_loop.run_cycle` calls this every cycle. The cockpit `/knowledge` page renders those rows.

Missing: a stable identity for a keyword cluster, a belief statement that stays a hypothesis, and a regression test that two permutations do not become two beliefs.

Why it matters: the knowledge screen is currently false. Later opportunity and matching code will treat those rows as if they were claims.

Depends on: nothing.

Existing components to reuse: `Pattern`, `Belief`, `pattern_engine.detect_patterns`, `belief_engine.form_or_update_belief`, `forge_loop` step that already calls `form_belief_from_pattern`.

Files likely affected:
- `backend/app/services/pattern_engine.py`
- `backend/app/services/belief_engine.py`
- `backend/tests/` a new or existing pattern/belief test

Implementation requirements:
- Identity of a pattern is the sorted full keyword set of the cluster, not the first four words and not their order.
- Re-running detection on the same signals updates that one pattern.
- The belief statement must not say the pattern is a real, addressable business problem. It must say it is an uncorroborated keyword hypothesis and include the sorted keywords.
- Beliefs merge when that canonical statement matches. Do not create one belief per permutation.
- Do not delete existing signal rows.
- Do not add a new table.

Acceptance criteria:
- Two signals that share the same keyword set produce one pattern and one belief.
- A third pass with the same signals does not insert another belief.
- The belief text does not contain "real, addressable business problem".
- Raw signal content is unchanged.

Tests:
- Add a regression test with three keyword permutations of the same tokens and assert one `Belief` row.
- Run `pytest` for that test and the full backend suite.

Failure/edge cases:
- A cluster below the existing minimum support creates nothing.
- Keywords that do not overlap stay separate beliefs.
- Empty signal text does not create a belief.

Security/truth constraints:
- This record is a hypothesis. It is not a fact, not an opportunity, and not public.
- Do not raise confidence because the same keywords were reordered.

Public/internal consumer: internal `/knowledge` via the existing beliefs API. The public app must not show these rows.

Status: NEEDS_REVIEW

### COPILOT_TASK

Task: Collapse keyword-permutation patterns into one hypothesis belief.
Context: `forge_loop.run_cycle` calls `pattern_engine.detect_patterns` then `belief_engine.form_belief_from_pattern`. Titles use the first four keywords, so permutations become separate beliefs whose text claims a real business problem. Fix that in those two services. Do not add a table, router, or page.
Files: `backend/app/services/pattern_engine.py`, `backend/app/services/belief_engine.py`, backend tests.
Required changes: pattern identity is the sorted keyword set of the cluster. Re-detection updates one row. Belief text is an uncorroborated keyword hypothesis using that sorted set. Exact-statement merge then collapses permutations. Do not delete signals.
Do not change: public routers, scheduler, connection engine, payment states, frontend.
Acceptance tests: three permutations of the same tokens yield one Belief; a second detection does not add another; the statement does not contain "real, addressable business problem". Full backend suite passes.
Definition of done: that regression test and the full suite pass on the current repository.

---

## TASK-002

Title: Knowledge page shows the canonical hypothesis and its evidence count.

Status: BLOCKED on TASK-001.

Depends on: TASK-001.
Existing components to reuse: `frontend/app` knowledge route, existing beliefs API, `Belief.supporting_signal_ids`.
Goal: the cockpit lists one row per canonical belief, with signal count and the hypothesis wording, and does not render the old permutation sentences as separate knowledge.

## TASK-003

Title: Confidence counts independent sources, not repeated copies.

Status: BLOCKED on TASK-001.

Depends on: TASK-001.
Existing components to reuse: `Signal.source`, `Signal.canonical_url`, `Pattern.confidence_score`, existing bulk-source penalty in `pattern_engine`.
Goal: twenty copies of one URL do not raise confidence as twenty confirmations.

## TASK-004

Title: Do not open an economic opportunity from an uncorroborated keyword belief.

Status: BLOCKED on TASK-001.

Depends on: TASK-001.
Existing components to reuse: opportunity creation inside `forge_loop` / `opportunity_engine`.
Goal: a keyword hypothesis does not become an `Opportunity` with a price or a buyer.

## TASK-005

Title: Re-running the cycle keeps the same belief identity.

Status: BLOCKED on TASK-001.

Depends on: TASK-001, TASK-003.
Existing components to reuse: `run_daily_cycle`, existing cycle tests.
Goal: two cycle runs over the same signals leave one belief row and do not double confidence.
