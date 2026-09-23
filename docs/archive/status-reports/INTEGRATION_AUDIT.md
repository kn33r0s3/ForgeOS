# ForgeOS Next Phase — Frontend/Backend Integration Audit

**Audit scope:** Existing ForgeOS repository in `/home/ubuntu/work`.

**Audit date:** 2026-09-14.

**Change boundary:** No structural application changes were made during this audit. Only audit artifacts and temporary test scripts outside the repository were created. The existing UI redesign remains unchanged.

## Executive finding

ForgeOS is not a collection of fake screens. Most primary pages are connected to the existing FastAPI backend and the bundled SQLite database, and the backend exposes a coherent discovery → evidence → opportunity → decision → execution → outcome → learning architecture. The current primary problem is **integration reconciliation**, not visual polish.

The most important findings are:

1. The core API is live and returns real data from the bundled database: 11,847 signals, 17,815 evidence rows, 7 patterns, 8 opportunity hypotheses, 8 decisions, and 300 cycle records.
2. The database has **zero actions, experiments, outcomes, learning events, products, strategies, goals, customer events, or actual revenue**. The UI must continue to show this honestly.
3. `/earn` is a separate Nepal-first earning-offer workspace. It does have backend persistence through `earning_offers`, but it also uses browser `localStorage` and a local sync queue. It does **not** create a canonical Opportunity, Experiment, Action, Outcome, Product, or Revenue record.
4. `/earn`, `/products`, `/world`, and `/analyze` are not in the primary navigation. `/flow` is linked as “System flow”; `/system-flow` does not exist and returns 404.
5. The local frontend build defaults to `NEXT_PUBLIC_API_URL=http://localhost:8000`. That works only when the browser can reach the backend on the same host. The Docker/Caddy deployment correctly overrides it to `/api`, but the provided ngrok deployment currently rendered a blank page during browser verification.
6. The root loading state is not an infinite backend operation. It is a client-side initial state that resolves after the `Promise.allSettled` batch completes. With an unreachable API it transitions to offline/error after the request timeout. In the local browser test, the browser could not reach the sandbox’s loopback backend, so the page displayed `OFFLINE`; direct backend curl tests returned 200.

## 1. Complete route map

| Route | Page | Purpose | Data source | API / calls | Backend connected? | Navigable? | Status |
|---|---|---|---|---|---|---|---|
| `/` | `frontend/app/page.tsx` | Core overview, current loop, truth audit, money reality, recommendation, activity, autonomy controls | Real aggregate Forge state | `/stats`, `/observer/stats`, `/forge/money/dashboard`, `/forge/execution/recommend`, `/forge/beliefs`, `/observer/signals`, `/forge/execution/actions`, `/forge/goals`, `/forge/autonomy/policy`, `/forge/money/revenue-breakdown`, `/forge/execution/actions/blocked`, `/forge/runtime`, plus strategy lookups | Yes | Yes | Connected; honest zero states depend on API reachability |
| `/analyze` | `frontend/app/analyze/page.tsx` | Submit a free-text idea for structured analysis | Real write path | `POST /analyze` | Yes | No | Connected but hidden from primary nav |
| `/earn` | `frontend/app/earn/page.tsx` | Nepal-first earning-offer hypothesis/workspace | `localStorage` plus `earning_offers` table via sync API | `GET/POST/PATCH /earn/offers` | Partially; separate subsystem | No | Local-first feature; not canonical Forge intelligence pipeline |
| `/execution` | `frontend/app/execution/page.tsx` | View and advance execution-action lifecycle | Real execution records | `GET /forge/execution/actions`, `POST .../approve`, `POST .../start`, `POST .../result` | Yes | Yes | Connected; database currently has zero execution actions |
| `/flow` | `frontend/app/flow/page.tsx` | Canonical human-validation flow and outcome/product gates | Opportunity, experiment, decision, outcome, product, customer data | `/orchestrate/flow`, `advance`, `approve`, `execute`, `reject`, `outcome`, `product`, `next-decision`, plus product/customer endpoints | Yes | Yes, labeled “System flow” | Connected; database currently has no flow experiments/outcomes/products |
| `/knowledge` | `frontend/app/knowledge/page.tsx` | Belief list and belief graph/evidence view | Beliefs, evidence, patterns, related opportunities/goals | `GET /forge/beliefs`, `GET /forge/world/beliefs/{id}` | Yes | Yes | Connected; real beliefs/evidence exist |
| `/opportunities` | `frontend/app/opportunities/page.tsx` | Ranked opportunity hypotheses, discovery, strategies, linked actions | Opportunities, money scores, strategies, execution actions | `GET /forge/money/opportunities`, `POST /forge/economic/discover`, strategy and execution lookups | Yes | Yes | Connected; 8 hypotheses exist, not validated outcomes |
| `/products` | `frontend/app/products/page.tsx` | Product/build/distribution/customer pipeline | Product, channel, customer event, outcome records | `GET /products/pipeline`, `POST /products`, `POST /forge/outcomes` | Yes | No | Connected but hidden from primary nav; currently empty database |
| `/revenue` | `frontend/app/revenue/page.tsx` | Money dashboard and experiment/revenue breakdown | Money engine aggregates and experiments | `GET /forge/money/dashboard` | Yes | Yes | Connected; actual revenue is zero |
| `/world` | `frontend/app/world/page.tsx` | Goals, strategy graph, belief graph | Goals, strategies, beliefs, evidence, causal knowledge | `GET /forge/goals`, `GET /forge/world/goals/{id}`, `GET /forge/world/beliefs/{id}` | Yes | No | Connected but hidden from primary nav; goals/strategies currently empty |
| `/system-flow` | None | Requested/expected alias in the audit brief | None | None | No | No | Broken link/route expectation; canonical implementation is `/flow` |

## 2. Frontend architecture map

ForgeOS uses **Next.js 15 App Router**, React 18, TypeScript, and Tailwind CSS. `frontend/app/layout.tsx` provides the root shell and imports global styles. `frontend/components/Nav.tsx` provides the only shared navigation. There is no Redux/Zustand-style state manager; state is local React state plus the reusable `useForgeQuery` hook.

The single typed API client is `frontend/lib/api.ts`. It centralizes request timeout handling, API-key headers, error conversion to `ForgeApiError`, and all typed endpoint contracts. `frontend/lib/useForgeQuery.ts` provides `loading`, `ready`, `empty`, `error`, and `offline` states.

Shared presentation components include `GlassPanel`, `QueryStateView`, `StatusPill`, `ConfidenceBar`, `ImportanceBadge`, `OpportunityCard`, and `StatCard`. The route pages use the shared API client rather than duplicating fetch clients.

### Storage and state findings

`/earn` is the only frontend route using browser persistence directly:

- `forgeos-nepal-workspace-key`
- `forgeos-nepal-offers`
- `forgeos-nepal-sync-queue`

The key is a random workspace token stored in the browser and only its hash is stored by the backend. The page merges remote offers into local state and retries queued creates/status updates when connectivity returns. This is durable enough for its own workspace but is not the same state model as Forge’s canonical Opportunity/Action/Outcome pipeline.

No mock-data library or obvious fabricated metric source was found in the application code. The existing comments and API types explicitly distinguish estimated, inferred, actual, and unknown fields. Some generic placeholder wording remains in loading/error UI, but it is not a data fabrication mechanism.

Authentication is optional. The backend uses an optional `FORGE_API_KEY`, and the frontend API client can attach an in-memory session API key. Default local operation has no required auth.

## 3. Backend architecture map

The FastAPI entry point is `backend/app/main.py`. It configures CORS, optional API-key middleware, database initialization/migrations, startup seeding/reconciliation, and registers routers for signals, analysis, opportunities, observation, Forge intelligence, world, workers, intelligence, rare signals, products, lessons, orchestration, earning offers, and payments.

The database layer is SQLAlchemy over SQLite by default at `storage/forge.db`. Startup calls `create_all`, migrations, stale-cycle reconciliation, default source/revenue/policy/scenario seeding, and related initialization.

Major service layers include:

- `observer_engine` / collectors / `signal_processor`: observation and signal quality.
- `pattern_engine`: repeated-signal pattern detection.
- `evidence_graph`, `reality_checker`, `reality_memory`: evidence and epistemic provenance.
- `forge_loop`, `orchestrator`, `cycle_scheduler`, worker services: cycle execution.
- `opportunity_engine`, `economic_intelligence`, `money_engine`: opportunity and economic scoring.
- `decision_engine`, `goal_engine`, `strategy_engine`, `option_space`: decisions and strategies.
- `execution_engine`, `autonomy_engine`, `action_engine`: policy-gated execution lifecycle.
- `outcome_learning`, `learning_engine`, `lessons_engine`: measured outcomes and learning.
- `product_engine`: products, channels, customers, and evidence-gated revenue rollups.
- `ai_engine`, `qwen_worker`, `embedding_engine`, `memory_layer`: provider and knowledge layers.

## 4. Frontend → API → service → database map

| Feature | Frontend | API endpoint(s) | Main service | Primary models/tables |
|---|---|---|---|---|
| Signals / observation | `/`, `/analyze`, observer screens | `/stats`, `/signals`, `/observer/observe`, `/observer/signals`, `/observer/stats`, `/analyze` | `observer_engine`, `opportunity_engine`, `pattern_engine` | `signals`, `patterns`, `opportunities`, `decisions` |
| Full Forge cycle | `/` | `POST /forge/cycle` | `forge_loop` and worker/cycle services | `cycle_runs`, `signals`, `patterns`, `beliefs`, `research_questions`, `research_tasks` |
| Beliefs / evidence | `/knowledge`, `/world` | `/forge/beliefs`, `/forge/world/beliefs/{id}`, `/forge/evidence`, knowledge routes | `reality_checker`, `reality_memory`, `world_model`, `memory_layer` | `beliefs`, `evidence`, `confidence_events`, `knowledge`, related world tables |
| Opportunities | `/opportunities`, `/flow`, `/revenue` | `/opportunities`, `/forge/money/opportunities`, `/forge/economic/discover` | `opportunity_engine`, `economic_intelligence`, `money_engine` | `opportunities`, `opportunity_events`, `evidence`, `revenue_sources` |
| Goals / strategies | `/world`, `/opportunities`, `/` | `/forge/goals`, `/forge/world/goals/{id}`, `/forge/goals/{id}/strategies` | `goal_engine`, `strategy_engine`, `causal_engine` | `goals`, `strategies`, `causal_knowledge` |
| Decisions | `/flow`, `/opportunities`, `/` | `/orchestrate/{id}/next-decision`, decision routes | `decision_engine`, `orchestrator`, `option_space` | `decisions`, `options` |
| Execution actions | `/execution`, `/opportunities`, `/` | `/forge/execution/actions`, approve/start/result/rank/recommend | `execution_engine`, `autonomy_engine` | `experiments` for money-execution actions; `actions` for canonical orchestrated actions |
| Human validation flow | `/flow` | `/orchestrate/flow`, advance/approve/execute/reject/outcome/product | `orchestrator`, `execution_engine`, `decision_engine` | `opportunities`, `experiments`, `outcomes`, `products`, `customer_events` |
| Outcomes / learning | `/flow`, `/products`, `/execution` | `/orchestrate/{id}/outcome`, `/forge/outcomes`, `/forge/learning`, experiment result routes | `outcome_learning`, `learning_engine`, `lessons_engine` | `outcomes`, `learning_events`, `lessons`, `experiments` |
| Money / revenue | `/`, `/revenue`, `/products` | `/forge/money/dashboard`, `/forge/money/revenue-breakdown`, `/forge/outcomes` | `money_engine`, `product_engine` | `revenue_sources`, `outcomes`, `experiments`, `products` |
| Products / distribution | `/products`, `/flow` | `/products/pipeline`, `/products`, channel/customer routes | `product_engine` | `products`, `distribution_channels`, `customer_events`, `outcomes` |
| Nepal earning offers | `/earn` | `/earn/offers`, `/earn/offers/{id}/status` | `earn` router direct DB persistence | `earning_offers` only |

## 5. Disconnected or fragmented features

### Confirmed fragmented features

- **Earning workspace:** Backend-connected but separate from canonical Forge intelligence and economic systems. It stores hypotheses/offers in `earning_offers`; it does not create Opportunities, Experiments, Actions, Outcomes, Products, or actual revenue.
- **Products:** Backend-connected but hidden from navigation. It is a separate downstream product/distribution layer that correctly depends on real outcomes for revenue rollups.
- **World:** Backend-connected but hidden from navigation. It exposes goals/strategy/world-model state that is not reachable from the current main navigation.
- **Analyze:** Backend-connected but hidden from navigation. It is a write path that creates a Signal, Opportunity, and Decision.
- **Flow naming:** The implementation is `/flow`, while the audit brief calls the expected route `/system-flow`. There is no `/system-flow` alias.

### No confirmed duplicate canonical engines

The repository contains multiple legitimate layers rather than a second backend: `experiments` represent opportunity/money tests, `actions` represent canonical action records, and `outcomes`/`learning_events` are evidence-gated measurement. This distinction needs clearer UI and documentation, but it is not enough evidence to delete or merge them.

## 6. Broken links and navigation

The current navigation exposes only:

- `/`
- `/opportunities`
- `/execution`
- `/revenue`
- `/knowledge`
- `/flow` labeled “System flow”

Missing from navigation:

- `/earn`
- `/products`
- `/world`
- `/analyze`

Broken/ambiguous route:

- `/system-flow` returns HTTP 404. The working route is `/flow`.

This is a **P1/P2 navigation and route reconciliation problem**, not a purely visual problem.

## 7. Local-storage-only / local-first feature analysis

`/earn` is not purely local-only because it calls the backend. It is **local-first**:

1. It creates a random workspace key in `localStorage`.
2. It loads local offers immediately.
3. It attempts `GET /earn/offers?workspace_key=...`.
4. It merges remote `EarningOffer` rows.
5. It writes offline creates/status changes into `forgeos-nepal-sync-queue`.
6. It retries queue operations on browser `online` events.

The backend stores the SHA-256 workspace-key hash and an `EarningOffer` row. This is a real persistence path, but it is intentionally a separate “earning hypothesis” workflow. It is not currently connected to ForgeOS’s canonical economic-intelligence graph. The UI correctly labels drafts and payments, but the distinction between this workspace and canonical Forge state should be made explicit in a future repair.

## 8. Mock, hardcoded, and fabricated data findings

No mock metric payloads were found in the route pages or `api.ts`. The backend’s default `AI_PROVIDER=mock` is a configured deterministic provider, not a frontend mock-data source; this is an important production disclosure item because it can affect how intelligence is formed.

Hardcoded content exists where expected:

- `/earn` pathway guidance and safety copy.
- Execution lifecycle labels and stage names.
- Truth/audit explanatory copy.
- Navigation labels.

These are product copy, not fake database metrics. No code path was found that converts estimated revenue into actual revenue. The backend and frontend comments explicitly gate actual revenue on actual outcomes.

## 9. API and connection test results

### Backend live test

The existing backend was started against `storage/forge.db`. All tested endpoints returned HTTP 200:

| Endpoint | Result |
|---|---:|
| `/health` | 200 |
| `/stats` | 200 |
| `/forge/runtime` | 200 |
| `/observer/stats` | 200 |
| `/forge/money/dashboard` | 200 |
| `/forge/execution/recommend` | 200 |
| `/forge/beliefs` | 200 |
| `/observer/signals?limit=8` | 200 |
| `/forge/goals` | 200 |
| `/forge/autonomy/policy` | 200 |
| `/forge/money/revenue-breakdown` | 200 |
| `/forge/execution/actions/blocked` | 200 |
| `/earn/offers?workspace_key=...` | 200 |

### Frontend route test

With the built Next server running, all discovered routes returned HTTP 200:

`/`, `/opportunities`, `/execution`, `/revenue`, `/knowledge`, `/flow`, `/earn`, `/products`, `/world`, `/analyze`.

`/system-flow` returned HTTP 404.

### Browser-level result

The local browser rendered the frontend, but its browser context could not reach the backend at sandbox loopback `127.0.0.1:8000`; the root therefore correctly transitioned to `OFFLINE`. This confirms the loading state resolves and is not an infinite promise, but it also exposes the fragility of a browser-visible `localhost` API default outside the Docker/Caddy network.

The provided ngrok URL rendered blank during browser verification, so the current external deployment cannot be considered a valid end-to-end acceptance environment until its process/proxy status is checked.

## 10. Database and schema reality check

The bundled SQLite database contains:

| Entity | Count | Interpretation |
|---|---:|---|
| Signals | 11,847 | Raw/historical observations exist |
| Canonical signals | 171 | Runtime truth audit reports canonical subset |
| Evidence | 17,815 | Evidence rows exist; only 70 have provenance according to runtime audit |
| Patterns | 7 | Inferred patterns exist |
| Beliefs | 7 | Beliefs exist |
| Opportunities | 8 | Opportunity hypotheses exist |
| Decisions | 8 | Decision records exist |
| Research questions | 30 | Research planning exists |
| Research tasks | 75 | Research tasks exist |
| Cycle runs | 300 | 284 completed, 16 failed; no running cycles after reconciliation |
| Worker tasks | 445 | 2 queued at audit time; last task was a queued research task |
| Revenue sources | 4 | Sourced revenue mechanisms exist |
| Actions | 0 | No canonical actions recorded |
| Experiments | 0 | No experiments recorded |
| Outcomes | 0 | No outcomes recorded |
| Learning events | 0 | No measured learning recorded |
| Lessons | 0 | No consolidated lessons recorded |
| Goals | 0 | No goals recorded |
| Strategies | 0 | No strategies recorded |
| Products | 0 | No products recorded |
| Customer events | 0 | No customer ledger records |
| Earning offers | 0 | No persisted earning offers in bundled DB |
| Actual REAL revenue | $0.00 | No actual REAL outcomes |

The live `/forge/runtime` response agrees with these facts: opportunities 8, decisions 8, experiments 0, outcomes 0, learning events 0, actual revenue 0.0, and 16 failed cycles historically. The redesigned UI should not imply execution or revenue success from the opportunity/decision counts.

## 11. `/earn` analysis

1. **Implementation file:** `frontend/app/earn/page.tsx`.
2. **Route registration:** Next App Router filesystem route `/earn`.
3. **Backend API usage:** Yes: `listEarningOffers`, `createEarningOffer`, `updateEarningOfferStatus`.
4. **Local storage:** Yes: workspace key, saved offers, sync queue.
5. **Database record:** Yes, `earning_offers` with hashed workspace ownership.
6. **Creates an Opportunity:** No.
7. **Creates an Experiment:** No.
8. **Creates an Action:** No.
9. **Creates an Outcome:** No.
10. **Connects to Revenue/Money:** No canonical connection; “paid” is an earning-offer status, not a REAL revenue outcome.
11. **Connects to economic intelligence:** No direct connection.
12. **Nature:** A standalone/local-first earning hypothesis wizard with backend sync.
13. **Why absent from primary navigation:** `Nav.tsx` simply does not include `/earn`; this appears to be a navigation omission rather than a route registration failure.

No automatic reconnection was made because the instructions explicitly require analysis before structural changes.

## 12. Root page loading analysis

The root page initializes `connection` to `loading` and calls a `Promise.allSettled` batch in `useEffect`. It does not leave the promise unresolved: after the batch completes it sets one of `offline`, `error`, or `ready`, and records `lastUpdated`.

The initial server-rendered HTML naturally contains the loading copy because the page is a client component. After hydration:

- If the browser can reach the configured API, the page resolves to real dashboard state.
- If all requests fail with network-level errors, it resolves to `OFFLINE`.
- If some requests fail but some data arrives, it resolves to a partial `error` state.
- Individual successful responses populate real values; unavailable values remain `—`.

The live backend endpoint works locally. The local browser test failed because `localhost:8000` was not reachable from that browser context, not because the backend operation hung. Docker/Caddy’s `NEXT_PUBLIC_API_URL=/api` override is the correct deployment pattern. The external ngrok URL currently did not return a usable page and must be redeployed or checked separately.

## 13. Duplicated or fragmented systems

- **Execution terminology is split across two legitimate models:** `experiments` power the money-execution lifecycle while `actions` power the canonical orchestrator/action layer. They should not be merged without a domain decision, but UI labels should clearly explain the distinction.
- **Revenue is intentionally split between estimated/potential money-engine fields and actual `Outcome` records.** This is correct architecture; the UI must preserve the distinction.
- **`/earn` is a separate earning-offer subsystem.** It overlaps conceptually with opportunity discovery but is not currently a duplicate implementation of the opportunity engine.
- **Navigation is fragmented:** several real routes are hidden, and `/system-flow` is absent while `/flow` is the working route.
- **No duplicate API client or state-management architecture was found.**

## 14. Prioritized repair plan

### P0 — Prevent misleading system representation

1. Make the production API-base configuration explicit and testable for local, Docker/Caddy, and external deployment modes. Do not rely on a browser reaching `localhost:8000` unless that is intentional.
2. Add a visible connection diagnostic that distinguishes frontend reachability, backend health, and partial endpoint failure without showing raw stack traces.
3. Verify the deployment behind the provided ngrok URL and restore a real end-to-end environment before acceptance.
4. Preserve the current truth rules: opportunities remain hypotheses, estimated values remain estimated, proposed actions remain proposed, and actual revenue remains $0 until a REAL outcome exists.

### P1 — Reconcile disconnected pages/features

1. Decide and document the product boundary for `/earn`: keep it as an explicit local-first earning workspace, or later design a deliberate conversion path into canonical Forge opportunities. Do not silently convert drafts.
2. Expose real but hidden routes in navigation or a clearly labeled secondary menu: `/earn`, `/products`, `/world`, `/analyze`.
3. Add a `/system-flow` compatibility route or change the external expectation to `/flow`; do not leave a known 404 alias.
4. Add route-level integration tests covering every page’s expected API calls.

### P2 — Repair routing/navigation/API contract clarity

1. Build a route manifest from the filesystem and navigation so missing links are detected automatically.
2. Document the distinction between `experiments`, canonical `actions`, `outcomes`, and `learning_events` in the UI and API contract.
3. Validate all production API URLs through the same proxy path used by Caddy.
4. Verify `/earn` workspace-key behavior and server/local merge semantics across refresh, offline queue, and multi-tab use.

### P3 — Improve loading/error handling

1. Keep meaningful stage copy, but show which API group failed when the root is partially degraded.
2. Add retry behavior per failed domain where safe instead of only retrying the entire overview.
3. Ensure empty states are tied to actual zero rows, not unavailable responses.
4. Add an explicit “backend reachable, no records yet” state distinct from “offline.”

### P4 — Reduce fragmentation without deleting capability

1. Provide cross-links between opportunity detail, flow, execution, products, revenue, and knowledge.
2. Reuse canonical read models for shared status labels where possible.
3. Clarify which revenue numbers are money-engine estimates versus outcome-backed actuals.
4. Decide whether the separate earning workspace should remain a separate domain module or become an entry point into opportunity creation; require a product decision first.

### P5 — Visual polish

Defer further visual work until P0–P3 are resolved. The current redesign is adequate for the next phase; the priority is connected, traceable, real, honest, navigable, and testable behavior.

## Audit conclusion

ForgeOS already has a substantial connected backend and real database state. The next phase should not rewrite or replace it. The correct path is to repair deployment/API reachability, reconcile routes and navigation, make the `/earn` boundary explicit, add integration tests, and clarify the two action/experiment layers. No large structural code change should begin until these findings and the repair priority are approved.
