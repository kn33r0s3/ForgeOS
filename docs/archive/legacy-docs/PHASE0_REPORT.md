# Hami Operator v0 — Phase 0 Repository Gates

**Inspection date:** 2026-09-29

**Scope:** Report-only repository and recorded-runtime inspection. No files other
than this report were changed for Phase 0. No external production request, test,
build, deployment, deletion, history rewrite, secret rotation, or push was
performed.

## Snapshot and scope

- Snapshot tag: `pre-hami-consolidation-20260929`, annotated, local only, points
  to `ea562b80e75099c3f2eaf04c98b12b82cb09c4ce`.
- The working tree was already dirty before the tag: `FORGE_SUBSTRATE_BLUEPRINT.md`,
  `src/routes/actions.tsx`, and `src/routes/index.tsx` were modified. The tag
  captures `HEAD`, **not** those working-tree edits.
- No `AGENTS.md` change was made. The Phase 0 tag was not pushed.
- Final status must retain those pre-existing edits; this task does not
  authorize stashing, reverting, staging, or committing them.

Evidence: `git status --short --untracked-files=all`,
`git rev-parse HEAD`, `git show-ref --tags pre-hami-consolidation-20260929`,
and `git rev-parse 'pre-hami-consolidation-20260929^{commit}'`.

## G0.1 — Secrets and personal data

**Finding**

- `gitleaks` is not installed. Per the gate instruction, the full-history
  secrets scan was not run; no conclusion that secrets are absent is justified.
- GitHub reports this repository as **PUBLIC**
  (`gh repo view kn33r0s3/ForgeOS --json nameWithOwner,visibility,url`).
- `storage/`, `logs/`, and `attachments/` exist and are not tracked. `storage/`
  contains SQLite databases and backups; `logs/` contains backend, frontend,
  worker, scheduler, public-app, and cycle logs; `attachments/` contains two
  archive files. `screenshots/` contains only tracked `.gitkeep`.
- A limited email/phone-pattern path scan printed no matching paths in those
  current directories. This does not establish that the databases, logs, or
  archives contain no personal data.
- The latest recorded data audit in `STATUS.md:272` says prior reachable Git
  history still contains database/log/archive/context artifacts and reports
  email/address-pattern hits inside archived material. It explicitly says its
  scan was not comprehensive. Because the repository is public, that history
  remains a material exposure concern even though current local copies are
  ignored.

**Evidence:** `command -v gitleaks` -> not installed;
`git ls-files -- storage logs attachments screenshots` -> only
`screenshots/.gitkeep`; `find` of those four paths; `rg -l -a` pattern scan
(no paths); `du -sh` (storage 425M, logs 96K, attachments 17M);
`STATUS.md:272`; `gh repo view ...` -> `visibility: PUBLIC`.

**Owner decision needed:** Whether to authorize a later full-history scan and,
if it finds exposure, a separately planned history remediation. Neither is
authorized by this report-only phase.

**Recommendation:** Keep secrets and personal-data conclusions **UNVERIFIED**.
Install/use an approved scanner in a later authorized task; do not publish raw
scanner output or values. Assess current ignored data and historical objects
before any cleanup or history rewrite.

## G0.2 — Size forensics

**Finding**

- `.git` is 92M.
- Largest tracked files include:
  - 3,848 KiB `backend/.deps/pydantic_core/_pydantic_core.cpython-311-darwin.so`
  - 3,708 KiB `backend/.deps/uvloop/loop.cpython-311-darwin.so`
  - 956 KiB `backend/.deps/watchfiles/_rust_notify.abi3.so`
  - 932 KiB `backend/.deps/rpds/rpds.cpython-39-darwin.so`
  - 568 KiB `backend/.deps/charset_normalizer/md.cpython-311-darwin.so`
  - 260 KiB each for `package-lock.json` and
    `sanipops_clean/river-cinder-bamboo-otter-main/package-lock.json`
  - 184 KiB `docs/archive/status-reports/P0_DATABASE_RAW_DIAGNOSTICS.txt`
- Aggregated tracked directory sizes are led by `backend` (36.48 MiB,
  including tracked `backend/.deps` at 34.22 MiB), then the archived
  `sanipops_clean` tree (1.72 MiB), `.grok` (0.74 MiB), `docs` (0.58 MiB),
  and `frontend` (0.41 MiB).
- Before this report was created, there were no ordinary untracked files in
  `git status`; the report is now the one new untracked file. There is
  substantial ignored local bulk: `frontend/node_modules` 350M, evidence-triage
  `node_modules` 332M, `frontend/.next` 141M, `storage` 425M,
  `backend/venv` 92M, `.venv` 76M, and `backend/.deps` 65M.

**Evidence:** `git ls-files -z | xargs -0 -r du -k | sort -nr` (tracked files);
tracked-path size aggregation using `git ls-files -z` and Node `fs.statSync`;
`du -sh .git`;
`du -sh` of ignored directories; `git status --untracked-files=all`.

**Owner decision needed:** Whether tracked platform-specific backend dependencies
and large history objects should remain in the public repository. No cleanup
was performed.

**Recommendation:** Decide a dependency/vendor policy before any removal.
Separate tracked source from ignored build/runtime bulk in future reports; do
not mistake ignored local databases or `node_modules` for clean-room evidence.

## G0.3 — `AGENTS.md`

**Finding**

- `AGENTS.md` is 399 lines. Its first substantive rule is owner-dependency
  reduction and it contains Hami commercial, safety, and evidence requirements
  in lines 1-47. Its heading still says `FORGEOS TOP RULE`, a legacy name.
- Lines 49-398 are a separate Grok "App Builder Workspace" contract: it names
  Grok Build, `/workspace`, the preview proxy, scaffold requirements, platform
  branding, and browser/build workflow. This is not a Hami product rule and
  describes a different execution environment from this repository session.
- The two blocks are combined in one file; the Hami rule is first, but the
  Grok contract dominates the remaining body.

**Evidence:** `wc -l AGENTS.md` -> 399; `rg -n '^#{1,6} ' AGENTS.md`; direct
read of `AGENTS.md:1-55` and `AGENTS.md:49-398`.

**Owner decision needed:** Approve a Hami-only replacement, including whether
any Grok preview/template constraints are still intentionally required for
this repository. No edit was made.

**Recommendation — proposed Hami-only draft (36 lines; not applied):**

```markdown
# Hami project rules

## Product and truth
- Hami is the product. ForgeOS, Sanipops, and Pulse are legacy identifiers.
- Preserve the existing repository, routes, and data until a migration is approved.
- The only canonical primitives are ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION.
- Do not create a seventh primitive or duplicate an existing workflow/model.
- Label records REAL, TEST, MOCK, or HYPOTHESIS; tests never prove customers or revenue.
- Unknown facts remain UNVERIFIED. Cite code, tests, or runtime evidence.

## Commercial and safety boundaries
- Optimize for fewer owner actions per verified real transaction.
- Never contact anyone, publish an offer, spend money, or simulate a prospect
  conversation without explicit owner authorization.
- Do not fabricate demand, customers, fulfillment, outcomes, or revenue.
- Keep personal data minimized, consent-scoped, access-controlled, and deletable.
- No new paid software or infrastructure before first real revenue except a
  verified legal, security, payment, or critical-execution requirement.
- Forge Bot runs natively; n8n is not a dependency.

## Engineering
- Inspect existing APIs, models, tests, deployment configuration, and data
  boundaries before changing behavior.
- Reuse existing capabilities and integrations; add no parallel architecture.
- Every meaningful state transition must atomically update state and emit a
  registered canonical EVENT with provenance and an idempotency key.
- External services use adapters with explicit failure behavior; halt unsafe
  outbound work on error.
- Test behavior at the narrowest relevant level, then run required CI gates.
- Never claim a build, deployment, autonomy, or economic outcome without proof.

## Reporting and authority
- STATUS.md is the technical record; docs/REVENUE_LOG.md is commercial evidence only.
- Record owner dependency removed, remaining dependency, and next safe seam in
  the existing capability queue.
- Report OWNER_INTERVENTIONS_PER_REAL_TRANSACTION as NOT MEASURABLE until a
  real transaction is verified.
- Do not rewrite history, change public visibility, or alter external systems
  without explicit owner approval.
```

## G0.4 — Frozen research, capability discovery, and demand understanding

**Finding**

- Research source collectors are under `backend/app/services/collectors/`:
  `arxiv.py`, `crossref.py`, `gdelt.py`, `github.py`, `openalex.py`,
  `reddit.py`, `rss.py`, `web.py`, and `world_bank.py`; the common contract is
  `base.py`. `collector_runner.py` registers these source handlers and checks
  source clearance before collection. Its default sweep explicitly blocks
  uncleared Reddit, GitHub, RSS/news, and arXiv sources.
- Dedicated collector tests exist for Crossref, GDELT, OpenAlex, Web, and
  World Bank. Research-loop tests also cover planning, task execution, evidence
  assessment, and verified/grounded research. No source-named dedicated test
  was found for arXiv, GitHub, Reddit, or RSS.
- `capability_discovery.py` is imported by `demand_understanding.py` and
  `research_planner.py`; its dedicated test is
  `backend/tests/test_capability_discovery.py`.
- `demand_understanding.py` is called by `api/signals.py` and the
  `worker_manager.py` handler; its dedicated test is
  `backend/tests/test_demand_understanding.py`.
- The best-supported seed of a future research engine is the existing
  `SourceCollector` contract + source-clearance registry + collector runner +
  `ResearchTask` engine/planner + evidence assessment/synthesis. These are
  existing code, not a recommendation to add another research architecture.

**Evidence:** `backend/app/services/collectors/base.py`,
`collector_runner.py:35-61,80-90`, `source_clearance_registry.py`,
`research_task_engine.py`, `research_planner.py`,
`research_evidence_assessment.py`, `research_synthesis_engine.py`,
`capability_discovery.py`, `demand_understanding.py`,
`backend/app/api/analyze.py`, `backend/app/api/forge.py`,
`backend/app/api/signals.py`, `backend/app/services/worker_manager.py`;
test paths listed above and `backend/tests/test_*research*.py`.

**Owner decision needed:** Whether to freeze these modules as preservation-only
work pending Phase 0 consolidation, and which cleared source should be the
first research runtime after consolidation.

**Recommendation — proposed STATUS.md wording:**

> **FROZEN FOR CONSOLIDATION:** Preserve the existing source collectors,
> source-clearance registry, research planner/task engine, capability
> discovery, and demand-understanding flow in place. Add no source, channel,
> lead-state architecture, or semantic primitive during consolidation.
> Integrity, privacy, authorization, and reliability fixes remain allowed.
> Reactivation requires an owner-approved scope, current source clearance,
> focused tests, and an explicit REAL/TEST/MOCK/HYPOTHESIS label. Collection
> completion is not validated research, buyer demand, or commercial evidence.

## G0.5 — Documentation and stray files

**Finding**

- There are 44 tracked files below `docs/`:

```text
docs/.DS_Store
docs/AGENT_WORKFLOW.md
docs/BACKUP_RETENTION.md
docs/CAPABILITY_QUEUE.md
docs/CONTAINER_BUILD_PROTOCOL.md
docs/CURRENT_FOCUS.md
docs/FEATURE_INVENTORY.md
docs/FINAL_ARCHITECTURE.md
docs/FORGE_BOT_DISCOVERY.md
docs/FUTURE_BLUEPRINT.md
docs/HOSTING_AND_SCHEDULER.md
docs/IMPLEMENTATION_BACKLOG.md
docs/NEPAL_FIRST_PRODUCT_PLAN.md
docs/NETWORK_FEED_ARCHITECTURE.md
docs/OPERATOR_GUIDE.md
docs/OVERNIGHT_BACKLOG.md
docs/OVERNIGHT_ENGINEERING_REPORT.md
docs/PHASE1_PLAN.md
docs/PUBLICITY_GATE.md
docs/PUBLIC_SOURCES.md
docs/REPAIR_SHOP_FIRST_EXPERIMENT.md
docs/REVENUE_LOG.md
docs/SERIAL_PATH.md
docs/SESSION_START.md
docs/approach/nepal-cultural-property-import-rule.md
docs/archive/.DS_Store
docs/archive/status-reports/INSPECTION_REPORT.md
docs/archive/status-reports/INTEGRATION_AUDIT.md
docs/archive/status-reports/LIVE_REPORT.txt
docs/archive/status-reports/P0_1_SCHEMA_REPAIR_REPORT.md
docs/archive/status-reports/P0_2_RECONCILIATION_REPORT.md
docs/archive/status-reports/P0_2_UNEXPECTED_WRITE_EVIDENCE.txt
docs/archive/status-reports/P0_3_RUNTIME_ATTRIBUTION_REPORT.md
docs/archive/status-reports/P0_4_POST_STARTUP_SNAPSHOT.json
docs/archive/status-reports/P0_4_PRE_CHANGE_SNAPSHOT.json
docs/archive/status-reports/P0_4_RUNTIME_CONTAINMENT_REPORT.md
docs/archive/status-reports/P0_DATABASE_DATA_INTEGRITY.txt
docs/archive/status-reports/P0_DATABASE_INTEGRITY_REPORT.md
docs/archive/status-reports/P0_DATABASE_RAW_DIAGNOSTICS.txt
docs/archive/status-reports/P0_DATABASE_SCHEMA_COMPARE.txt
docs/archive/status-reports/RELEASE_REPORT.md
docs/archive/status-reports/SETUP_COMPLETE.md
docs/superpowers/.DS_Store
docs/superpowers/plans/2026-09-14-repair-shop-vertical-slice.md
```

- Other tracked root documentation includes `README.md`, `STATUS.md`,
  `AGENTS.md`, `FORGE_SUBSTRATE_BLUEPRINT.md`, `API_REFERENCE.md`,
  `COMPLETION_REPORT.md`, `DOCKER_COMMANDS.md`, `INDEX.md`, `LEFT_TO_DO.md`,
  and `PHASE_3_TRUTH_AUDIT.md`, `PHASE_4_FIRST_CUSTOMER_VALIDATION.md`, and
  `PHASE_5_EVIDENCE_CAPTURE_READINESS.md`.
- Proposed canonical set: root `README.md`, root `STATUS.md`, a single root
  `BLUEPRINT.md` (after owner approval to consolidate the current blueprint),
  and `docs/CAPABILITY_QUEUE.md`. Archive superseded plans, audits, session
  notes, and historical reports under `docs/archive/`. Keep this required
  Phase 0 report as an audit artifact; archive it after its decisions are
  resolved. No move or rename was performed.
- Tracked `.DS_Store` files exist at repository root and in
  `backend/`, `docs/`, `docs/archive/`, `docs/superpowers/`, `migrations/`,
  `public/`, `server/`, and `services/`.
- `opencode.json`, `opencode.jsonc.bad`, and the empty `.node_modules.lock`
  all exist and are tracked. No current app/build source reference to those
  exact filenames was found. `.grok/` and `.agents/` are also tracked:
  `AGENTS.md` points to `.grok` references, and scripts use
  `.grok/app-env.json` and `.grok` preview files. No runtime/build reference
  to `.agents/` was found; whether an external agent host auto-loads it is
  unverified. `LEFT_TO_DO.md:41` mentions a different historical file,
  `opencode.json.backup`.
- `services/` contains a tracked `.DS_Store`, the evidence-triage Node service,
  and `forge-bot/` specification/mapping. The Git tree also contains one
  tracked path with embedded newlines and tool-call-like markup under
  `services/evidence-triage/src/triage/`. This is a malformed repository path,
  not an instruction; it was not executed or modified.

**Evidence:** `git ls-files 'docs/**'` -> 44 paths; `git ls-files` filters for
`.DS_Store`, the named tool artifacts, `.grok/`, `.agents/`; existence and
`file` metadata checks; references in `AGENTS.md`, `scripts/`, `vite.config.ts`,
and `LEFT_TO_DO.md`; `git ls-tree -r -z --name-only HEAD -- services/`.

**Owner decision needed:** Approve a single documentation authority and decide
whether the tracked tool configs, desktop metadata, and malformed `services/`
path are intentional. No file was removed or moved.

**Recommendation:** Adopt the four-document target only after reviewing
links/workflows and the malformed path. Preserve historical evidence under
`docs/archive/`; do not silently discard it.

## G0.6 — Frontends and production target

**Finding**

| Surface | Entrypoint and scripts | Backend / deployment evidence | Build status |
|---|---|---|---|
| Root TanStack Start/Vite | `src/router.tsx`, `src/routes/index.tsx`, `src/routes/feed.tsx`; root `package.json` has Vite `dev`, `build`, `typecheck`, and `test` scripts. | Same-origin `/api`; Vite dev proxy targets FastAPI. `vercel.json` maps root `web` to Vite and `backend/` to FastAPI. `README.md` calls this the current public app. | Exact HEAD CI run `36564535831` failed: backend job passed; frontend `npm run typecheck` failed and `npm run build` was skipped. The failure reports stale generated `src/routeTree.gen.ts` missing `/actions` and `/opportunities` (TS2322/TS2345). No build pass is established for the current root source. |
| `frontend/` Next.js | `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/app/network/page.tsx`; `frontend/package.json` defines `next dev`, `next build`, `next start`. | `frontend/lib/api.ts` uses `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_BASE_URL`; `next.config.js` rewrites `/api` only when configured. `docker-compose.yml` builds this app and Caddy exposes it on 3000. | `STATUS.md:14` records a Next production build pass in the Sep. 14 snapshot; later status says its Earn refactor had not yet been rebuilt. Current build is UNVERIFIED. |
| `sanipops_clean/river-cinder-bamboo-otter-main/` | Separate TanStack/Vite copy with `src/router.tsx` and `src/routes/index.tsx`, using a duplicate `app-builder-workspace` package name and Vite scripts. | No separate deployment target was found. Its root config has the copied Vite app contract; it is a legacy/archived copy, not the configured root Vercel web service. | No current CI/build result found. |
| `services/evidence-triage/` | Framework-neutral request handler at `src/app.ts`, local server at `src/local/server.ts`. | A separate Dockerized Node service used by the backend; `docker-compose.yml` names it `evidence-triage`. It is not a complete end-user frontend. | No production frontend build claim found. |

- **Recommendation, not a selection:** the root Vite app is best evidenced as
  the intended public Hami frontend because `README.md` and `vercel.json`
  identify it as the current web service and it contains the Hami routes.
  The owner still needs to choose whether to retire or preserve the Next and
  `sanipops_clean` copies.
- Home and Network do not redirect to one another in the root app:
  `/` is `createFileRoute("/")` and `/feed` is `createFileRoute("/feed")`.
  The Next app also has separate `/` and `/network` pages; no redirect call
  between them was found. Current root route links are distinct, although the
  generated route tree is stale for two new routes.

**Evidence:** `README.md` production frontend/API section;
`package.json`, `frontend/package.json`,
`sanipops_clean/river-cinder-bamboo-otter-main/package.json`,
`vite.config.ts`, `frontend/next.config.js`, `frontend/lib/api.ts`,
`vercel.json`, `docker-compose.yml`; exact CI run
https://github.com/kn33r0s3/ForgeOS/actions/runs/36564535831 and its job logs;
route definitions in `src/routes/index.tsx`, `src/routes/feed.tsx`,
`frontend/app/page.tsx`, and `frontend/app/network/page.tsx`.

**Owner decision needed:** Choose the authoritative frontend and deployment
surface (G0.6). Also decide whether to repair the generated route-tree/typecheck
gate before treating the root Vite app as buildable.

**Recommendation:** Keep root Vite as the provisional recommendation, but do
not call it build-verified. Reconcile route generation before any next
production-affecting change; this report-only phase did not run a local build.

## G0.7 — Blueprint claims, Forge Bot specification, and revenue log

**Finding**

- Both `services/forge-bot/SPEC.md` and `docs/REVENUE_LOG.md` exist on `HEAD`
  and in the working tree.
- The Forge Bot spec labels itself **HYPOTHESIS / TARGET ONLY**, not
  implemented, not enabled, and not authorized for contact. It calls for
  native reuse of existing records and WorkerTask; it does not add a second
  lead architecture.
- `docs/REVENUE_LOG.md` is an empty commercial evidence template; it says no
  commercial evidence has been recorded.
- The tracked `services/` tree contains:
  - `.DS_Store`
  - `evidence-triage/`: `.dockerignore`, `Dockerfile`, `package.json`,
    `package-lock.json`, `tsconfig.json`, `scripts/inspect-sdk.ts`,
    `src/app.ts`, `src/local/server.ts`, `src/triage.ts`,
    `src/triage/limits.ts`, `src/triage/types.ts`, `src/x402.ts`,
    `test/triage.test.ts`, and the malformed newline-containing path noted
    under G0.5
  - `forge-bot/SPEC.md`
  - `forge-bot/state/MAPPING.md`
- The working-tree `FORGE_SUBSTRATE_BLUEPRINT.md` is modified and is not the
  blueprint text in the snapshot commit. The committed version starts
  `ForgeOS — Forge Bot v0 Execution Blueprint`; the working copy starts
  `Hami — Universal Economic Intelligence & Action System`. Its contents
  must not be treated as the approved `main` blueprint without review.
- The working-copy blueprint declares exactly six semantic primitives and
  forbids a seventh (`FORGE_SUBSTRATE_BLUEPRINT.md:128-141`). It also calls
  for canonical EVENT records on meaningful semantic transitions
  (`:200-227`, `:355-387`). One concrete code mismatch is
  `backend/app/services/repair_shop.py:47-78`: `_transition` changes work-item
  state and inserts `WorkItemEvent`, but does not call the canonical
  `world_graph.create_event`. This is reported as a contradiction, not resolved
  by choosing the blueprint or code.

**Evidence:** `git cat-file -e HEAD:<path>` and file existence checks for both
requested files; direct read of the spec and revenue log; `git diff` and
`git show HEAD:FORGE_SUBSTRATE_BLUEPRINT.md`; `git ls-tree -r -z HEAD -- services/`;
`backend/app/services/repair_shop.py:47-78`.

**Owner decision needed:** Approve whether the worktree blueprint replaces the
committed blueprint, and decide how the repair-shop transition should satisfy
the canonical EVENT rule without creating another primitive.

**Recommendation:** Keep the spec and empty evidence log. Review the dirty
blueprint separately; do not infer implementation from it or from the spec.
For semantic state changes, update the existing state and emit the canonical
EVENT in the same transaction, preserving the six primitives.

## G0.8 — Database, migrations, WorkerTask, substrate, and table overlap

**Finding**

### Database and scheduler

- Local shell had `DATABASE_URL` and `VERCEL` unset. In that environment the
  app's default is SQLite at `storage/forge.db` (`backend/app/config.py:24-26`,
  `backend/app/database.py:19-27`). `file` identifies that file as SQLite;
  read-only `PRAGMA integrity_check` returned `ok`, and journal mode is `wal`.
  Other ignored local SQLite proof/backup files also exist.
- The database layer accepts an explicit `DATABASE_URL`. If `VERCEL` is set
  and `DATABASE_URL` is absent, it falls back to `sqlite:////tmp/forge.db`,
  which is per-instance ephemeral storage (`backend/app/database.py:19-27`).
- The latest recorded production verification says PostgreSQL was configured
  and available through `DATABASE_URL`; the vendor is unknown
  (`docs/HOSTING_AND_SCHEDULER.md:13-15`, `STATUS.md:271`). This is dated
  evidence, not a new production check in this report. Production's current
  database remains UNVERIFIED.
- `STATUS.md:14-15` describes the Sep. 14 local/container canonical host
  database as SQLite at `storage/forge.db`; `docker-compose.yml:4,42-43`
  explicitly mounts that same local SQLite file. These claims are consistent
  when scoped to the local Compose environment, but not a description of the
  separately recorded PostgreSQL production environment.
- Migrations are SQLAlchemy `Base.metadata.create_all()` followed by
  `app.migrations.run_migrations()` at startup (`backend/app/database.py:101-108`);
  `backend/app/migrations.py:227-313` applies additive DDL and targeted table
  rebuilds. It is not a single numbered migration directory as the only
  authority.
- `vercel.json:16-20` schedules one daily `/api/scheduled/cycle` cron. The
  Compose `worker` service is opt-in under profile `worker` and runs the
  scheduler every 1,800 seconds (`docker-compose.yml:54-62`). That profile is
  not proof that a worker runs in production. The latest recorded deployment
  found no sub-daily production poller and says Hobby is non-commercial
  (`STATUS.md:271`, `docs/HOSTING_AND_SCHEDULER.md:17-26`).

### WorkerTask and event substrate

- `worker_tasks` is an operational table with nullable unique
  `idempotency_key`, due time, attempts, status, inputs/outputs, and error
  (`backend/app/models.py:230-253`). The dispatcher's registered types are
  `discovery`, `research`, `opportunity`, `builder`, `qa`, `evolution`,
  `revenue_miner`, and `demand_understanding`
  (`backend/app/services/worker_manager.py:178-187`). Unsupported types fail
  with “no handler”.
- The worker manager conditionally updates a due `queued` task to `running`,
  commits the claim, then dispatches it (`worker_manager.py:19-50`). Retries
  are bounded by `max_attempts`; demand-understanding tasks use a deterministic
  SHA-256 key and two attempts (`demand_understanding.py:48-90`). However, the
  generic `/workers` create schema does not accept an idempotency key and its
  API handler does not pass one (`backend/app/schemas/__init__.py:1122-1129`,
  `backend/app/api/workers.py:13-23`). The recorded status and Forge Bot spec
  both say stale `running` rows are not recovered (`STATUS.md:271`,
  `services/forge-bot/SPEC.md`).
- The canonical substrate is in `backend/app/models.py`: `TypeRegistry` maps
  typed vocabularies (`type_registry`, lines 712-729), `WorldEvent` persists
  to `events` (lines 803-820), and the other canonical tables are entities,
  relations, evidence, capabilities, and actions. The API is mounted at
  `/forge/substrate` (`backend/app/api/substrate.py:18`); `POST
  /forge/substrate/events` calls `world_graph.create_event` (lines 446-453).
- `world_graph.create_event` requires an active registry event type, validates
  the payload schema, records source/subject/time, and supports idempotency
  (`backend/app/services/world_graph.py:940-990`). For a service transition:
  update the existing row, call `create_event` with the registered type,
  source, subject, previous/next state and evidence in the payload, supply a
  deterministic idempotency key, then commit both in the same transaction.
  Do not add a seventh primitive.

### Overlap with proposed `op_*` tables

- `op_lead`: partial overlap in `CustomerEvent` (lead/customer contact stage,
  contact identifier, action/outcome provenance) and `Customer`; public demand
  `Signal` is not itself a contact record.
- `op_consent`: `Customer.consent_state` exists, but no dedicated consent
  record with channel, timestamp, purpose, opt-out history, and deletion
  evidence was found.
- `op_message`: `CustomerCommunication` is repair-work-item-specific; the
  idempotent `IntegrationDelivery` outbox stores external integration
  delivery. Neither is a general inbound/outbound lead-message history.
- `op_booking_request`: `BookingRequest` already exists as
  `public_booking_requests`, tied to a provider and optional service listing;
  it is not a general appointment scheduler.
- No `op_lead`, `op_consent`, `op_message`, or `op_booking_request` table or
  corresponding Lead/Consent/Message model was found. These are partial
  overlaps, not a reason to create duplicates.

**Evidence:** `backend/app/config.py:24-26`, `backend/app/database.py:19-27,101-108`,
`backend/app/migrations.py:227-313`, `STATUS.md:14-15,271-273`,
`docs/HOSTING_AND_SCHEDULER.md:13-26`, `docker-compose.yml:4,42-43,54-62`,
`vercel.json:16-20`, model/schema/API/worker/event paths cited above,
`file storage/forge.db`, and SQLite integrity/journal pragma output.

**Owner decision needed:** Confirm the production database and commercial
hosting/scheduler authority (G0.8); decide whether the generic worker API
should expose idempotency and what recovery guarantees are required before
outbound work. The report does not authorize either change.

**Recommendation:** Treat local SQLite, recorded production PostgreSQL, daily
Vercel cron, and optional Compose worker as distinct environments. Verify the
current production configuration before relying on it. Reuse `WorkerTask` and
the canonical EVENT API; do not add parallel queue or consent/message/booking
primitives before mapping owner-approved needs to existing models.

## Owner decisions required

- **D2 — UNVERIFIED:** No D2 definition was found in tracked Markdown; only D1
  appears in the current worktree blueprint. Owner must supply or confirm what
  D2 denotes before it can be resolved.
- **D6 — UNVERIFIED:** No D6 definition was found in tracked Markdown. Owner
  must supply or confirm its scope.
- **D7 — UNVERIFIED:** No D7 definition was found in tracked Markdown. Owner
  must supply or confirm its scope.
- **G0.6 — REQUIRED:** Select the authoritative frontend/deployment surface.
  Root Vite is the evidence-backed recommendation, not a selection.
- **G0.8 — REQUIRED:** Confirm the live production database and scheduler
  topology and decide the acceptable WorkerTask idempotency/recovery contract.
