# ForgeOS feature and runtime inventory

## Reconstruction — 2026-09-30 (owner Command 1: reconstruct reality before building)

**Evidence cut:** 2026-09-30 21:00 NPT, `origin/main` `7a437bb` → restored in
`f99008d`. Labels: **VERIFIED** = executed/observed by running it in this pass;
**OBSERVED** = read in code, git history, or a live HTTP response; **INFERRED** =
concluded from those, not proven. The older 2026-09-26 inventory below remains
valid for module-level detail of the restored backend.

### What happened to the canonical line (OBSERVED from git/GitHub)

| When (NPT) | Commit | What it did |
|---|---|---|
| 19:16 | `bf8546e` | Last full-source commit; backend CI green. VERIFIED locally: backend `pytest` 554 passed, 2 skipped (Python 3.12). |
| 19:38 | `f240f3e` ("..") | Deleted 2,454 files: all backend Python source and tests, `docs/`, `verification/`, `services/`, `frontend/` source, root TanStack app (`src/lib`, `src/routes`, `scripts/`, `server/`, `public/`), `vercel.json`, `docker-compose.yml`. Added a new root Vite + Express app (`server.ts`, `src/App.tsx`, `metadata.json` with `MAJOR_CAPABILITY_SERVER_SIDE_GEMINI_API`). |
| 19:44–19:55 | `147b821`, `e6a7148`, `6e941b9` | Three further commits on the new app ("Hami schema… six primitives" in TypeScript, `src/serverApp.ts`, `HAMI_SYSTEM_REPORT.md`, Vercel config). **No longer on `main`**: `main` was later moved to `7a437bb`, whose parent is `f240f3e`, so these are unreachable (fetchable by SHA only while GitHub retains them). |
| 19:42 (pushed ~19:59) | `7a437bb` ("..") | Committed ~6,950 generated files (`backend/venv`, `backend/.deps`, `frontend/.next` hot-update chunks, `__pycache__` bytecode) and no source. |
| 21:21 | `f99008d` | This pass: forward restoration of the canonical backend/docs/evidence from `bf8546e`, generated files untracked. |

Bytecode in `7a437bb` shows four source files that were **never committed
anywhere** (local-only work): `backend/app/services/procurement_demand.py`,
`backend/app/services/collectors/ted_procurement.py`,
`backend/tests/test_ted_procurement_collector.py`,
`backend/tests/test_network_connection_relations.py`. Their `.pyc` remain in
history at `7a437bb`; the `.py` must come from the machine that produced them.

### Surfaces now on `main`

| Surface | State | Label |
|---|---|---|
| FastAPI backend `backend/app` (19 routers, 66 ORM tables, `/api` mirror) | Restored, byte-identical to `bf8546e` plus the capability contract below. 558 passed, 4 skipped. | VERIFIED |
| Root Vite/React app + `server.ts` Express API (from `f240f3e`) | `tsc --noEmit` and `vite build` pass. Its API is an **in-memory mock** seeded with hand-written signals, beliefs (with invented support counts, e.g. ">15 hrs/week per counselor"), opportunities with `estimated_revenue`, and decisions. Nothing persists; nothing is sourced. It is a parallel TypeScript model of the domain, not the canonical substrate. Revenue is kept at 0. | VERIFIED (build) / OBSERVED (content) |
| Production `https://forge-os-ebon.vercel.app` | `/` serves the new Vite app; `/api/health`, `/api/stats`, `/api/signals`, `/api/public/feed` all return Vercel `404 NOT_FOUND` because `vercel.json` (web + FastAPI `api` service + daily cron) was deleted. The production API and daily cycle are therefore **down**; the front end's own `/api/*` calls also 404 in production. | VERIFIED (HTTP, 2026-09-30 ~21:10 NPT) |
| Legacy Next.js dashboard `frontend/` + `docker-compose.yml` | Restored source; local Compose only. Not built in this pass. | OBSERVED |
| `services/evidence-triage` (x402 triage), `services/forge-bot` (spec) | Restored; Compose-only / spec-only. | OBSERVED |
| Root TanStack app of `bf8546e` (System home, feed, providers, request intake, auth wiring) | **Not restored** — replaced by the new root app and would collide with its `package.json`/`vite.config.ts`. Recoverable with `git checkout bf8546e -- src/routes src/lib src/components scripts server public`. | OBSERVED |

### Capability map of the canonical backend

| Subsystem | Code | What works | Gaps / honest limits |
|---|---|---|---|
| Six primitives | `models.py`: `entities` (ENTITY), `relations` (RELATION), `events` (EVENT), substrate columns on `evidence` (EVIDENCE), `capabilities` (CAPABILITY); ACTION is the operational `actions` table projected into the substrate by `world_graph.sync_action_outcome_learning_path` | Generic API `/forge/substrate/*` for types, entities, relations, events, evidence, capabilities. A SQLAlchemy `before_flush` write contract enforces lifecycles so ORM assignment cannot bypass services. VERIFIED by `test_world_graph.py`, `test_substrate_api.py`. | ACTION has no generic substrate endpoint and is not a substrate table (projection only). Substrate write endpoints are open when `FORGE_API_KEY` is unset (local default). |
| Type registry | `type_registry` (`schema_json` validated as JSON Schema), `seed_core_types`, `register_type`, `set_type_status` | New types start `proposed`; activation/deprecation needs actor, rationale and an in-repo evidence ref. Attributes/payloads are validated against the registered schema. VERIFIED. | Categories fixed to entity/relation/event/capability types (no action_type category). |
| Truth progression | `_validate_truth_transition` | possible→hypothesized→tested→supported; tested/supported/refuted require stored, non-simulated, provenance-backed evidence; supported requires prior tested evidence. VERIFIED. | Legacy `Belief`/`Opportunity` confidence scores still exist alongside and are not truth states. |
| Identity | `transition_entity_identity`, `find_identity_candidates`, `merge_entities` | candidate→corroborated→canonical only with provenance-backed evidence; candidates are surfaced, never auto-merged; merges keep history. VERIFIED. | — |
| Evidence/provenance | `Evidence` (+ idempotency keys, `legacy_evidence_substrate_adapter`) | Idempotent evidence writes; simulated sources (`simulated*`, `fixture*`, `mock*`, `seed*`, `test-data*`) cannot establish tested/supported. VERIFIED. | Historic rows keep legacy 0–100 confidence; substrate confidence is separate. |
| Capability registry | `capabilities`, `capability_substrate_adapter` (runtime tools), `capability_discovery` (research source candidates: candidate→reviewed→cleared→active) | Lifecycle proposed→building→tested→active. **New in this pass:** enforced by the write contract, and a pass must carry provenance (actor + git revision + a command that invokes the test file). `GET /forge/substrate/capabilities` reports `activation.verified`. VERIFIED by `test_capability_lifecycle_contract.py`. | Test runs are still *attested* by the caller (the server does not re-execute pytest); no deprecation service. Legacy active rows without an attributable pass report `verified: false`. |
| Research / discovery | `research_planner` (2.3k lines), `research_task_engine`, `research_synthesis_engine`, `research_evidence_assessment`, `multi_judge`, `demand_understanding`, `curiosity_engine` | Requirement-grounded research tasks, evidence gates, honest completion state, disagreement preserved. VERIFIED by tests (fixtures/mocked HTTP). | Live behaviour depends on cleared sources; question generation is bounded, not open-world. |
| Collectors / external adapters | `collectors/`: arxiv, crossref, gdelt, github, openalex, reddit, rss, web, world_bank; `source_clearance_registry` + `docs/PUBLIC_SOURCES.md` | Fail-closed source clearance per requirement. Ledger records OpenAlex and World Bank as live-verified, GDELT live but rate-limited. Tests VERIFIED with fixtures only in this pass (no live calls made). | Semantic Scholar, ILOSTAT, Nepal procurement, UK Contracts Finder blocked; TED source never committed (above). |
| Actions & authorization | `action_engine`, `autonomy_engine`/`autonomy_policies`, `execution_engine`, `integration_outbox`/`integration_dispatcher`, `nepal_payments` (eSewa/Khalti) | Policy ALLOW / REQUIRE_APPROVAL / BLOCK; execution ≠ verified outcome; payments fail closed without credentials. VERIFIED by tests. | No standing-authorization record with the full scope/spend/expiry envelope described in `AGENTS.md`; no real outbound channel is authorized. |
| Observers / scheduled work | `observer_engine`, `forge_loop`, `cycle_scheduler`, `scripts/run_daily_cycle.py`, `worker.py`, `/api/scheduled/cycle` | Cycle rollback and stale-cycle recovery tested. VERIFIED (tests). | Production cron is gone with `vercel.json` (VERIFIED 404). |
| Feed / network projections | `public_feed`, `public_network`, `network_substrate_adapter`, `public_epistemics` | Read-only projections over substrate with provenance; GETs do not write. VERIFIED (tests). | Not reachable in production (API down). |
| Economic / commercial | `economic_validation`, `offer_preparation`, `product_engine`, `money_engine`, `revenue_miner`, `repair_shop` | Outcome-gated; willingness to pay stays `unknown` without evidence. VERIFIED (tests). | 0 verified customers, 0 revenue, `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` NOT MEASURABLE (no real transactions). |
| Data | SQLite locally (`storage/`, not in git), PostgreSQL in production per earlier evidence | — | Production DB contents and reachability are UNKNOWN in this pass (no credentials used). |

### Duplicated / dead / temporary (OBSERVED)

- **Duplicated domain model:** the root `server.ts`/`src/types.ts` redefine
  Signal/Opportunity/Belief/Decision/Execution in memory — a second
  architecture relative to the substrate. Keep it as a UI surface only; point
  it at the FastAPI API rather than growing its own model.
- **Dead:** `app/cli/{collect,merge_duplicates}.py`,
  `services/{intelligence_pipeline,offer_economics,qwen_worker}.py` (test-only
  references, per the 2026-09-26 inventory).
- **Temporary adapters (canonical until migrated):** the
  `*_substrate_adapter.py` family mirrors vertical tables into the substrate.
- **Generated junk previously tracked:** `backend/.deps` (vendored
  site-packages, tracked since 2026-09-25), `backend/venv`, `frontend/.next`,
  `__pycache__` — now untracked and ignored.

### Highest-leverage missing capabilities (INFERRED, ranked)

1. **A protected canonical line.** `main` accepted a whole-repo deletion and a
   non-fast-forward move of `main` (`6e941b9` → `7a437bb`, OBSERVED from CI run
   SHAs; INFERRED to be a force-push) within one hour, and
   CI was red for both without anyone reacting. Branch protection (no force
   push, required backend CI) is an owner-side GitHub setting.
2. **Production API/cron restored or deliberately retired** (owner decision:
   `vercel.json`).
3. **Open-world discovery engine (Command 2):** research is requirement- and
   clearance-bound; nothing yet generates candidate value hypotheses about
   arbitrary entities from the substrate itself.
4. **Server-verified capability tests (Command 3):** capability passes are
   attributable now, but still attested; a CI-reported result (e.g. GitHub
   check-run for the recorded revision) would make them independently
   verifiable.
5. **ACTION as a first-class substrate primitive** with a standing-authorization
   envelope (scope, spend, rate, counterparty, expiry) — prerequisite for
   discovery-to-real-world experiments (Command 4).
6. **One human surface over the canonical API** (Command 5) instead of the
   in-memory mock.

## Inventory — 2026-09-26 evidence cut

**Evidence cut:** 2026-09-26  
**Repository:** `main` at `ea490c95f1fadd19e4aeef984d1381d301c2e54c`  
**Purpose:** source-grounded map for work on the first Forge Bot pilot. This is a technical inventory, not a claim that every wired feature is commercially useful or currently producing outcomes.

## Product and deployed shape

README describes ForgeOS as an evidence-to-action intelligence system:
observe, verify, understand, decide, act, measure, learn. Its current real
commercial baseline is **0 customers, $0 revenue, and 0 external validation**.
It is not yet a lead-response product or a commercially validated consultancy
pilot.

The currently deployed application is the root Vite/TanStack web app plus the
FastAPI backend. Vercel routes `/api/*` to that backend. `frontend/` is a
separate Next.js dashboard used by the local Docker Compose stack, not the
deployed Vercel frontend. Docker Compose also defines an optional worker and an
evidence-triage service; those definitions do not prove either process is
running in production.

Production checks at this evidence cut:

- `GET /api/health`: HTTP 200, `status=ok`, readiness true, database available.
- The production database is PostgreSQL (as recorded in `STATUS.md` and the
  production health evidence); local defaults remain SQLite.
- Vercel plan: Hobby. `vercel.json` has one daily cron at `0 0 * * *` for
  `/api/scheduled/cycle`. No deployed sub-daily `WorkerTask` poller was found.
- Production `/openapi.json` (re-checked 2026-09-30) answers the frontend SPA
  HTML rather than the schema, and `/api/openapi.json` answered 404, because
  only `/api/*` reaches the Python service on Vercel. The document itself
  generates correctly, and the `/api` route mirror now covers the schema, so the
  contract is readable at `/openapi.json` locally and at `/api/openapi.json`
  after the next deploy. The route inventory below is cross-checkable against
  that live document.
- The last recorded `/api/public/feed` check was HTTP 200 with 11 items. It
  should be checked again before using the feed as a release gate.
- Local OCI CLI/config/credentials and Oracle-related environment names were
  not found in the previous inventory pass. No Oracle account authorization or
  provisioning is evidenced; no resource was purchased or provisioned.
- Commercial use is not appropriate on the current Hobby plan. The hosting and
  scheduler comparison is in `HOSTING_AND_SCHEDULER.md`.

## Runtime modules

Classification is about current wiring, not whether a feature is useful. All
listed code is preserved; no module has been moved to an archive. The Python
module census found 132 modules under `backend/app`. Package imports and runtime
adapter imports are partly dynamic, so a static-import miss alone is not used
to justify archiving.

| Status | Modules / paths | Evidence |
|---|---|---|
| ACTIVE | `backend/app/main.py`, `config.py`, `database.py`, `migrations.py`, `models.py`, `security.py`, `schemas/__init__.py`, `schemas/experiment.py` | ASGI application, startup/migration, API config/security, and shared persistence contracts. `init_db()` imports models, creates all metadata tables, and runs migrations. |
| ACTIVE | `backend/app/api/{analyze,earn,evidence_triage,forge,intelligence,lessons,observer,opportunities,orchestrator,payments,products,public,rare_signals,repair_shop,scheduled,signals,substrate,workers,world}.py` | All 19 routers are included in `main.py` and each is also registered under `/api`. |
| ACTIVE | `backend/app/services/` modules other than the three explicitly listed as ORPHAN below | Runtime service layer imported by routers, the Forge cycle, data initialization, or adapters. Dynamic/package imports make simple textual reachability undercount this layer; check each source before moving it. |
| ACTIVE | `backend/app/services/collectors/{__init__,arxiv,base,crossref,gdelt,github,openalex,reddit,rss,web,world_bank}.py` | Collector package and source adapters used by the collection runner/source registry. |
| ACTIVE | `backend/app/services/{__init__,backup,capability_substrate_adapter,evidence_relationship_substrate_adapter,legacy_evidence_substrate_adapter,legacy_record_substrate_adapter,market_signal_substrate_adapter,network_substrate_adapter,public_services_substrate_adapter,research_question_relation_substrate_adapter}.py` | Package/runtime adapter wiring; several are imported through package or local/dynamic import paths. |
| ACTIVE (optional/local) | `backend/worker.py`, `backend/scripts/scheduler.py`, `backend/scripts/run_daily_cycle.py`, `backend/scripts/backup_retention.py`, `backend/scripts/recovery_verify.py`, `backend/scripts/seed_signals.py`, `backend/scripts/truth_audit_report.py` | Operator/Compose entrypoints. The Compose `worker` profile runs a 30-minute scheduler when deliberately started; this is not evidence of a production process. |
| ACTIVE (Compose only) | `services/evidence-triage/` | Compose defines this separate service and `backend/app/api/evidence_triage.py` is mounted. This is not separately deployed by the current Vercel config. |
| ORPHAN — preserve pending owner decision | `backend/app/cli/collect.py`, `backend/app/cli/merge_duplicates.py` | No current FastAPI, worker, Compose, or README invocation was found. They remain manually runnable candidates, not archive/deletion decisions. |
| ORPHAN — preserve pending owner decision | `backend/app/services/intelligence_pipeline.py`, `backend/app/services/offer_economics.py`, `backend/app/services/qwen_worker.py` | In-repository references found only in their respective tests. No live route, startup, or worker call site was found. |
| ACTIVE | `src/router.tsx`, `src/routeTree.gen.ts`, `src/routes/`, `src/components/layout/`, `src/components/pages/{area-view,demand-intake-form,offer-card,project-inquiry-cta}.tsx`, `src/components/not-found.tsx`, `src/components/preview-host-bridge.tsx`, `src/components/ui/button.tsx`, `src/lib/{content,error-component,preview-embedder-origin,preview-host-bridge,utils}.ts`, `src/lib/auth/` | Current TanStack route tree, deployed pages, existing anonymous demand intake, shell, preview bridge, and platform auth provider/popup integration. |
| ORPHAN — preserve pending owner decision | `src/components/pages/project-form.tsx`, `src/components/ui/{input,label,textarea}.tsx`, `src/lib/app-data/`, `src/lib/db.ts`, `src/lib/multiplayer/` | No current route/runtime import was found for these app-facing modules; the DB bootstrap explicitly skips when there are no migrations. Platform/template relationships should be checked before removal. |
| DUPLICATE — local/legacy surface | `frontend/` (37 TypeScript/JavaScript source modules) | Separate Next.js dashboard wired by Docker Compose. README identifies it as legacy/local; current Vercel frontend is root Vite. No files moved or removed. |

The root Vite app has 22 URL routes (excluding its root-shell route): `/`,
`/$`, `/about`, `/contact`, `/discoveries`, `/domain`, `/feed`, `/group`,
`/group/index`, `/group/businesses`, `/operations`, `/process`, `/providers`,
`/request`, `/request-a-project`, `/requests/$id`, `/services`,
`/services/index`, `/services/$slug`, `/technology`, `/ventures`, and `/work`.
`/request-a-project` redirects to `/request`; `/request` currently accepts
redacted, anonymous demand only and explicitly does not promise contact.

## FastAPI route inventory

There are 214 source-declared method/path operations in the 19 mounted routers.
The same router implementations are available at both the unprefixed path and
the `/api` alias (428 method/path entries before framework-generated docs and
health routes). `{name}` denotes a path parameter; an empty decorator path is
the router root.

| Router | Operations (method + router-relative path) |
|---|---|
| `analyze` | `POST /analyze`; `GET /analyze/{question_id}/status`; `POST /patterns/run`; `GET /patterns`; `POST /patterns/{pattern_id}/opportunity`; `GET /stats` |
| `earn` | `GET /offers`; `POST /offers`; `PATCH /offers/{offer_id}/status`; `PUT /offers/{offer_id}/checklist` |
| `evidence_triage` | `POST /triage` |
| `forge` | `POST /cycle`; `GET /questions`; `GET /tasks`; `GET /tasks/{task_id}/history`; `POST /tasks/{task_id}/retry`; `GET /beliefs`; `POST /beliefs/{belief_id}/check`; `POST /beliefs/{belief_id}/experiments`; `POST /experiments/{experiment_id}/result`; `GET /experiments`; `GET /sources`; `GET /predictions`; `GET /evidence`; `POST /knowledge/mine`; `POST /tasks/{task_id}/run`; `POST /tasks/run-pending`; `POST /collect`; `GET /knowledge`; `GET /knowledge/list`; `POST /ask`; `GET /world/beliefs/{belief_id}`; `POST /goals`; `GET /goals`; `PATCH /goals/{goal_id}`; `POST /goals/{goal_id}/opportunities/{opportunity_id}`; `GET /causal-knowledge`; `POST /goals/{goal_id}/strategies`; `GET /goals/{goal_id}/strategies`; `GET /strategies/compare`; `GET /world/goals/{goal_id}`; `GET /money/opportunities`; `GET /money/opportunities/{opportunity_id}`; `GET /money/recommend`; `POST /opportunities/{opportunity_id}/revenue-experiments`; `POST /revenue-experiments/{experiment_id}/result`; `GET /money/opportunities/{opportunity_id}/evidence`; `GET /money/opportunities/owner-ranked`; `GET /money/dashboard`; `GET /revenue-sources`; `GET /money/opportunities/{opportunity_id}/suggested-sources`; `POST /money/opportunities/{opportunity_id}/revenue-source`; `POST /execution/actions`; `GET /execution/actions`; `GET /execution/actions/blocked`; `GET /execution/actions/{action_id}`; `POST /execution/actions/{action_id}/approve`; `POST /execution/actions/{action_id}/start`; `POST /execution/actions/{action_id}/result`; `GET /execution/actions/{action_id}/package`; `POST /execution/actions/{action_id}/human-result`; `POST /execution/actions/{action_id}/verified-revenue`; `GET /execution/rank`; `GET /execution/recommend`; `GET /autonomy/policy`; `PATCH /autonomy/policy`; `GET /autonomy/evaluate`; `GET /money/revenue-breakdown`; `GET /strategies/{strategy_id}/performance`; `POST /autonomy/run-cycle`; `POST /economic/discover`; `GET /economic/patterns/{pattern_id}/corroboration`; `GET /scenarios`; `POST /decisions`; `GET /decisions`; `POST /decisions/{decision_id}/accept`; `POST /learning/from-experiment`; `GET /learning`; `POST /actions`; `POST /actions/{action_id}/approve`; `POST /actions/{action_id}/execute`; `GET /actions`; `POST /outcomes`; `GET /outcomes`; `GET /cycles`; `GET /runtime`; `GET /connections`; `POST /connections/scan`; `POST /connections/{connection_id}/advance`; `POST /connections/{connection_id}/confirm-payment`; `POST /connections/{connection_id}/dispute-payment`; `POST /connections/{connection_id}/settle-payment`; `POST /connections/{connection_id}/response`; `POST /connections/{connection_id}/publish` |
| `intelligence` | `POST /youtube`; `GET /youtube/{analysis_id}`; `GET /performance/tools/{tool_name}`; `GET /performance/sources/{source}` |
| `lessons` | `GET /`; `GET /recall`; `POST /rebuild` |
| `observer` | `POST /observe`; `GET /signals`; `GET /recent`; `GET /stats` |
| `opportunities` | `GET /opportunities`; `POST /needs/{need_id}/economic-validation`; `POST /opportunities/{opportunity_id}/prospect-discovery/readiness`; `POST /opportunities/{opportunity_id}/monitor`; `GET /opportunities/{opportunity_id}/options`; `POST /opportunities/{opportunity_id}/options/decision`; `GET /opportunities/{opportunity_id}/evidence-graph`; `POST /opportunities/{opportunity_id}/claims`; `POST /opportunities/{opportunity_id}/judge`; `POST /experiments/proposed`; `POST /experiments/{experiment_id}/authorize`; `POST /experiments/{experiment_id}/execute`; `POST /experiments/{experiment_id}/outcome`; `POST /experiments/{experiment_id}/action`; `POST /experiments/{experiment_id}/action/approve`; `POST /experiments/{experiment_id}/action/execute`; `POST /experiments/{experiment_id}/action/outcome`; `POST /experiments`; `GET /experiments`; `POST /experiments/{experiment_id}/actual-outcome` |
| `orchestrator` | `GET /flow`; `GET /flow/{opportunity_id}`; `POST /{opportunity_id}/advance`; `POST /{opportunity_id}/approve`; `POST /{opportunity_id}/execute`; `POST /{opportunity_id}/reject`; `POST /{opportunity_id}/outcome`; `POST /{opportunity_id}/product`; `POST /{opportunity_id}/next-decision` |
| `payments` | `POST /esewa/checkout`; `POST /esewa/lookup`; `GET /esewa/callback`; `POST /khalti/initiate`; `POST /khalti/lookup` |
| `products` | `POST /`; `POST /offer-drafts`; `GET /`; `GET /pipeline`; `GET /channels`; `GET /customers`; `POST /customers`; `PATCH /channels/{channel_id}`; `POST /channels/{channel_id}/customers`; `GET /{product_id}`; `POST /{product_id}/offer-approval`; `PATCH /{product_id}`; `POST /{product_id}/channels` |
| `public` | `GET /feed`; `GET /providers`; `GET /providers/{provider_id}`; `GET /services`; `GET /discoveries`; `GET /connections`; `GET /network`; `POST /domain/{record_id}/connections/{connection_id}/response`; `GET /trust/{subject_kind}/{subject_id}`; `GET /revenue-miner`; `GET /alerts`; `GET /matches`; `GET /domain`; `POST /domain`; `POST /domain/{record_id}/close`; `GET /domain/{record_id}/events`; `POST /domain/{record_id}/dispute`; `POST /booking-requests`; `GET /booking-requests/{booking_id}` |
| `rare_signals` | `POST /detect` |
| `repair_shop` | `POST /work-items`; `GET /work-items`; `GET /work-items/{work_item_id}`; `POST /work-items/{work_item_id}/evidence`; `POST /work-items/{work_item_id}/triage`; `POST /work-items/{work_item_id}/communications`; `POST /communications/{communication_id}/approve`; `POST /communications/{communication_id}/response`; `POST /work-items/{work_item_id}/payment`; `POST /work-items/{work_item_id}/outcome` |
| `scheduled` | `GET /cycle` |
| `signals` | `POST /`; `POST /public-request`; `GET /`; `GET /demand-understanding/{task_id}` |
| `substrate` | `GET /types`; `POST /types`; `POST /types/{category}/{type_name}/status`; `GET /entities`; `GET /entities/{entity_id}`; `POST /entities`; `POST /entities/{entity_id}/identity`; `POST /entities/{entity_id}/merge`; `POST /entities/{entity_id}/archive`; `GET /relations`; `POST /relations`; `POST /relations/{relation_id}/truth`; `GET /events`; `POST /events`; `GET /evidence`; `POST /evidence`; `GET /capabilities`; `POST /capabilities`; `POST /capabilities/{capability_id}/build`; `POST /capabilities/{capability_id}/test`; `POST /capabilities/{capability_id}/activate` |
| `workers` | `GET /`; `POST /` |
| `world` | `POST /ingest`; `GET /claims`; `GET /ideas`; `GET /principles` |

## Workers, persistence, and Bot-relevant records

| Status | Component | Current behavior / boundary |
|---|---|---|
| ACTIVE (production, daily only) | `/api/scheduled/cycle` | One Vercel Hobby cron per day. It is not a continuous worker and its timing is imprecise. |
| ACTIVE (local/Compose opt-in) | `backend/worker.py`, `backend/scripts/scheduler.py`, Compose `worker` profile | A separate process, configured locally for 30-minute cycles. Not proven running in production. `WorkerTask` has idempotency and conditional claim/retry machinery; stale-running recovery remains a gap recorded in `STATUS.md`. |
| ACTIVE (request-scoped) | FastAPI `BackgroundTasks` used by analyze/demand paths | Executes work after an individual request; it is not a durable recurring scheduler. |
| ACTIVE | `Signal`, `WorldEvent`, `Evidence`, `SubstrateEntity`, `ForgeCapability`, `Action`, `Outcome`, `CustomerEvent`, `Customer`, `CustomerCommunication`, `WorkerTask` | Existing primitives suitable for the Bot mapping; do not create a parallel lead database or state machine. |
| ACTIVE, but not a generic calendar | `BookingRequest` / `public_booking_requests` | Requires a public provider and service listing; it is not a generic appointment calendar. |
| ACTIVE, offer rather than customer evidence | `Product` / `products` and `EarningOffer` / `earning_offers` | Product is an offer hypothesis; actual customer/revenue totals are outcome-gated. The current product/customer flow must not be used to imply a sale. |

All 66 ORM tables declared in `backend/app/models.py` are registered during
`init_db()` and created/migrated on startup. Application-reference scan found
at least one application reference for each; the tables are therefore ACTIVE
schema, not proof of populated or economically useful data:

`signals`, `patterns`, `rare_signal_assessments`, `rare_signal_events`,
`opportunities`, `opportunity_events`, `worker_tasks`, `experiments`,
`beliefs`, `research_questions`, `research_tasks`, `research_task_steps`,
`research_task_events`, `tool_usage_events`, `source_usage_events`,
`intelligence_cache_entries`, `belief_experiments`, `sources`,
`source_fetch_gates`, `evidence`, `claims`, `evidence_relationships`,
`type_registry`, `entities`, `relations`, `events`, `capabilities`,
`judgments`, `judgment_comparisons`, `predictions`, `knowledge`, `goals`,
`confidence_events`, `causal_knowledge`, `strategies`, `revenue_sources`,
`autonomy_policies`, `forecasters`, `scenarios`, `scenario_predictions`,
`world_source_documents`, `media_analyses`, `world_claims`, `world_ideas`,
`options`, `decisions`, `learning_events`, `lessons`, `actions`, `outcomes`,
`public_providers`, `public_service_listings`,
`public_verification_records`, `public_booking_requests`, `products`,
`distribution_channels`, `customer_events`, `customers`,
`repair_work_items`, `work_item_events`, `customer_communications`,
`integration_deliveries`, `domain_records`, `network_connections`,
`earning_offers`, `cycle_runs`.

`CustomerEvent` is the real prospect/customer contact ledger, but its schema
does not itself provide consent timestamp, purpose, durable opt-out, or a
deletion workflow. `Customer` is described as a repair-shop customer and has a
coarse `consent_state`; `BookingRequest` stores requester contact but is scoped
to a listed service. None is by itself a safe, consent-scoped generic lead
contact store. Preserve those distinctions if adding the separately requested
Bot contact record.

## Archive, duplicate, and owner-review decisions

- **No ARCHIVE modules are moved in this inventory.** The source graph contains
  dynamic imports and optional commands, so absence from the deployed router
  alone is not sufficient evidence that code is obsolete. Do not move/delete
  the ORPHAN candidates without further reference/history and owner review.
- `frontend/` is the one evidenced duplicate UI surface: local Compose uses it,
  production Vercel does not. Keep it until the owner decides whether the
  alternate local dashboard is still needed.
- Three test-only backend service modules and two unreferenced CLI modules are
  explicitly marked ORPHAN above; this is a review label, not permission to
  delete.
- No NEPSE/paper-trading module appeared in the live source inventory; README
  records that path as removed.
- The application contains 19 mounted API routers and 22 web URL routes.
  `main.py` mounts each API router both with and without `/api`; route
  implementations are listed above and are not duplicated by separate
  business logic.

## Immediate Bot implementation boundary

The existing `/request` form records redacted demand without contact details,
idempotently, and promises no follow-up. It must remain unchanged. A Bot intake
must be a separate consent-scoped path and may record inbound data only; it
must not automatically email/text/call, publish an offer, spend money, infer
customer/payment status, or imply client authorization. No owner discovery
conversations or client-approved facts are recorded yet. Accordingly, a form
can be tested as `TEST`, but no lead, customer, booking, or revenue claim can
be made from it.
