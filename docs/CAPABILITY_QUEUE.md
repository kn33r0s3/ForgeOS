# Hami capability claim ledger (ForgeOS repository)

## Closure map snapshot (2026-10-04)

At the start of this review, `HEAD` and `origin/main` matched
`eb88332138ff3a4343d0744e7caa1b655d1daf7d`. This review's local changes are
recorded below; public health does not establish the deployed source SHA.
Dated entries below are retained as history and may be superseded by this map.

| Area | Current status | Evidence and next dependency |
| --- | --- | --- |
| Customer ledger read authorization (2026-10-10) | **FIXED IN SOURCE — focused and full backend regressions passed; deployment identity NOT VERIFIED** | The existing `GET /products/customers` and `/products/pipeline` handlers returned an inserted `CustomerEvent` with `contact_name`, `contact_identifier`, and free-text `notes` when `FORGE_API_KEY` was unset; `product_engine.pipeline` explicitly serializes those PII fields into `customer_events`. The global middleware intentionally preserves local-first access when disabled, but these owner-written routes had no handler-level gate; their writes already require the owner key. Both handlers now call the shared owner guard, so access fails closed even when the optional middleware is disabled. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_customer_ledger_read_requires_owner_key backend/tests/test_commercial_ops.py::test_optional_middleware_leaves_unmarked_local_first_reads_open_when_key_is_disabled -q` — **2 passed**; `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests -q` — **1009 passed, 2 skipped**. The PII regression directly asserted the unauthenticated 200 and observed the three PII fields before the fix; it now checks 503 without a configured key and successful owner-key access, while the middleware-only regression preserves local-first semantics for routes with no handler-level gate. (1) Owner action still required: authenticate before reviewing customer-contact records; no real person was contacted in this repair. (2) Action removed: anonymous requests cannot enumerate stored names, identifiers, or notes. (3) Remaining: local-first behavior continues for routes without explicit owner gates; this change doesn't create or authorize any contact. (4) Next dependency: continue reviewing product/customer read surfaces and deployed-source identity. |
| Commercial opportunity read authorization (2026-10-10) | **FIXED IN SOURCE — focused route regression passed; full backend validation pending; deployment identity NOT VERIFIED** | The existing `GET /opportunities?limit=1` returned **200** with `FORGE_API_KEY` unset and no owner guard. The route is explicitly the commercial exploitation-lane list; related `/forge/money/opportunities` and `/opportunities/{id}/evidence-graph` reads were already owner-only. The same gap affected candidate-option evaluation and experiment history. These three existing handlers now require the owner key before querying or evaluating internal commercial data. Verification so far: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_commercial_opportunity_reads_require_owner_key -q` — **1 passed**; all three routes fail closed without a configured key. (1) Owner action still required: authenticate to inspect the internal opportunity register, options, and experiment record; no opportunity was published or contacted. (2) Action removed: anonymous callers cannot read those internal commercial plans and experiment details. (3) Remaining: public opportunity publication remains on its separately governed public surface and no demand or revenue claim is implied; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. (4) Next dependency: continue reviewing other routers for private internal reads; full backend validation and deployed-source identity remain pending. |
| Forge memory and operations read authorization (2026-10-10) | **FIXED IN SOURCE — focused route regression passed; full backend validation pending; deployment identity NOT VERIFIED** | A request to the existing `GET /forge/beliefs` returned **200** with `FORGE_API_KEY` unset. The same missing route-level owner check affected reads of belief experiments, source reliability, predictions, belief/goal world graphs, causal knowledge, goals/strategies, pattern corroboration, learning, action/outcome history, cycle errors, and runtime worker/task state. Sixteen internal reads now require the owner key before querying or invoking their service. The explicit `/forge/unknowns` public discovery projection remains ungated and is covered as such by the regression. Verification so far: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_forge_memory_and_operations_reads_require_owner_key backend/tests/test_public_value_flow.py::test_internal_forge_reads_require_owner_key -q` — **2 passed**; all 16 internal reads fail closed with no configured key, while `/forge/unknowns` returns 200. (1) Owner action still required: authenticate to inspect internal beliefs, research results, strategies, outcomes, and runtime state; no external action was performed. (2) Action removed: anonymous callers cannot inspect those owner-only records. (3) Remaining: the public unknowns projection remains intentionally readable; reads being gated do not create transaction evidence or external permission, and `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. (4) Next dependency: continue reviewing remaining API routers for private reads and re-check the public projection boundary; full backend validation and deployed-source identity remain pending. |
| Internal Forge read authorization (2026-10-10) | **FIXED IN SOURCE — focused route regression passed; deployment identity NOT VERIFIED** | The existing `GET /forge/autonomy/policy` returned **200** with `FORGE_API_KEY` unset, exposing the active autonomy limits and allowed action types; the same route-level privacy gap existed for policy evaluation, strategy performance, task history, execution ranking, and execution recommendation. All six existing handlers now require the owner key before database reads or engine calls. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_internal_forge_reads_require_owner_key backend/tests/test_commercial_ops.py -q` — **25 passed**; the focused regression confirms all six fail closed without a configured owner key and that an owner-authorized policy read succeeds. (1) Owner action still required: authenticate to inspect private operating limits, task history, strategy performance, and action recommendations; no action was executed. (2) Action removed: anonymous callers can no longer read those internal operational details. (3) Remaining: this is access control, not an autonomous economic outcome; external permission, customer contact, and action execution remain separately gated, and `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. (4) Next dependency: continue the route-by-route authorization and data-sensitivity review; verify deployed source identity separately. |
| Autonomy-cycle trigger authorization (2026-10-10) | **FIXED IN SOURCE — focused regression passed; deployment identity NOT VERIFIED** | The existing `POST /forge/autonomy/run-cycle` had no route-level owner check and invoked the autonomous proposal/evaluation cycle; a request with `FORGE_API_KEY` unset returned **200**. It never executes actions, but it writes proposal state and consumes execution work. The route now requires the owner key before calling the cycle. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_autonomy_cycle_trigger_requires_owner_key -q` — **1 passed**; the test verifies fail-closed behavior without a configured key and successful owner-triggered invocation of a stubbed cycle. (1) Owner action still required: explicitly request proposal generation and separately authorize any resulting real-world action; no actions were executed here. (2) Action removed: anonymous callers can no longer trigger action-proposal cycles. (3) Remaining: policy ALLOW is not external permission or execution capability. (4) Next dependency: continue auditing the remaining API mutation contracts; owner interventions per real transaction remain **NOT MEASURABLE**. |
| Goal and strategy mutation authorization (2026-10-10) | **FIXED IN SOURCE — focused route regression passed; deployment identity NOT VERIFIED** | The existing goal creation route accepted an anonymous request (`FORGE_API_KEY` unset) and inserted a goal that controls what Forge prioritizes. Goal updates, opportunity links, and strategy generation also lacked route-level owner checks. The four mutation routes now require the owner key before invoking Goal/Strategy engines. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_goal_mutations_require_owner_key -q` — **1 passed**; test verifies 503 and unchanged goal count for no-key calls, and successful owner-authorized goal creation. (1) Owner action still required: define and prioritize goals; no goal or strategy was set based on this test. (2) Action removed: anonymous callers cannot reshape the internal goal/strategy register. (3) Remaining: generated strategies are proposals only and do not authorize execution; owner review and existing action gates remain. (4) Next dependency: continue checking internal mutations against owner-vs-public intake intent; no actual transaction was created. |
| Legacy research mutation authorization (2026-10-10) | **FIXED IN SOURCE — route regression passed; deployment identity NOT VERIFIED** | Eight existing write routes (`/forge/cycle`, task retry/run/run-pending, belief check/experiment, experiment result, and default collection) relied on `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` or no gate, but did not require owner identity. With the legacy feature explicitly enabled and `FORGE_API_KEY` unset, `/forge/cycle` returned **200**. Each route now requires the owner key before legacy gating, record lookup, or service execution. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_legacy_research_mutations_require_owner_key -q` — **1 passed**; it verifies all eight routes return 503 without a configured key and that an authorized owner can invoke a stubbed cycle. (1) Owner action still required: enable the legacy feature deliberately and authorize individual research work; no collection/contact was performed in this test. (2) Action removed: unauthenticated callers cannot trigger a cycle, retry/run tasks, mutate belief/experiment state, or write collection records. (3) Remaining: the legacy feature remains disabled by default; enabling it does not clear external sources or authorize outbound contact. (4) Next dependency: continue auditing the remaining non-public state-changing routes and their source/authorization boundaries; no verified transaction exists. |
| Execution-action creation authorization (2026-10-10) | **FIXED IN SOURCE — focused lifecycle tests passed; deployment identity NOT VERIFIED** | The existing `/forge/execution/actions` handler created a planned Experiment/Action for a customer interview while `FORGE_API_KEY` was unset; its sibling approval, start, result, and read endpoints already require owner authorization. Creation now also requires the owner key before invoking the execution engine. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py backend/tests/test_approval_outcome_bridge.py backend/tests/test_commercial_ops.py -q` — **75 passed**; the regression verifies 503 and no Experiment insertion without a key, then successful owner-authorized planning. (1) Owner action still required: authorize the proposal, separately approve/start if policy demands; this test performed no contact. (2) Action removed: anonymous callers can no longer create internal executable-action records. (3) Remaining: action creation/approval is not external execution permission; a customer interview still requires owner authorization and human performance. (4) Next dependency: continue route-by-route review of remaining Forge write handlers; no buyer contact was made. |
| Opportunity revenue-source link authorization (2026-10-10) | **FIXED IN SOURCE — focused tests passed; deployment identity NOT VERIFIED** | The existing `/forge/money/opportunities/{id}/revenue-source` route accepted an unauthenticated request with `FORGE_API_KEY` unset and linked a stored RevenueSource to an Opportunity. Its paired suggestion route is explicitly owner-only, and the link route’s docstring says this is the sole explicit grounding operation. It now requires the owner key before changing that association. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py backend/tests/test_revenue_source_seed.py -q` — **46 passed**; regression verifies 503 with no key, no association change, and successful authorized linking. (1) Owner action still required: select/confirm a real revenue source and inspect cited terms; no offer or payout terms were published or assumed. (2) Action removed: anonymous callers can no longer ground an opportunity in an owner-selected revenue channel. (3) Remaining: a database RevenueSource is not proof of current external terms or customer demand; the Nepal consultancy segment remains a hypothesis pending owner-run discovery. (4) Next dependency: continue checking generic writers for owner-vs-public-intake intent; genuine terms and transactions remain unverified. |
| Generic action proposal authorization (2026-10-10) | **FIXED IN SOURCE — focused action and Forge Bot tests passed; deployment identity NOT VERIFIED** | With `FORGE_API_KEY` unset, the existing `/forge/actions` route returned **200** for an anonymous `manual_note` proposal and persisted it through `action_engine.propose_action`. The handler now requires the owner key before parsing parameters or creating an Action. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py backend/tests/test_forge_bot_api.py -q` — **106 passed**; the regression asserts 503 and unchanged Action count. (1) Owner action still required: submit intended proposals through the owner-authorized action path; no external activity was requested or triggered by this repair. (2) Action removed: anonymous callers can no longer fill the internal action queue with proposals. (3) Remaining: owner-created proposals still need separate policy evaluation, explicit approval where required, and owner-key authorization for execution. (4) Next dependency: inspect remaining generic Forge writers for anonymous state creation/alteration and distinguish genuine public intake from owner-only records. |
| Outcome writer authorization (2026-10-10) | **FIXED IN SOURCE — focused tests passed; deployment identity NOT VERIFIED** | A focused request to the existing `/forge/outcomes` writer with `FORGE_API_KEY` unset returned **200** and could attach an owner-asserted success to a completed action. `action_engine.record_outcome` appends the outcome and updates that action's lifecycle state. The route now requires the owner key before calling the service. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py backend/tests/test_http_canonical_final.py -q` — **50 passed**; regression verifies 503 with missing key, zero inserted outcomes, and no action-state mutation. (1) Owner action still required: record outcomes through the existing authorized owner path; independent REAL/VERIFIED proof remains required for transaction claims. (2) Action removed: unauthenticated callers can no longer add outcome/learning rows or change linked action state. (3) Remaining: owner-entered results remain MOCK/REPORTED by default and do not establish real-world verification. (4) Next dependency: preserve the distinction between owner-reported action results and independently evidenced outcomes; verified-real transaction metrics remain **NOT MEASURABLE**. |
| Generic action approval/execution authorization (2026-10-10) | **FIXED IN SOURCE — focused API regressions passed; deployment identity NOT VERIFIED** | The existing `/forge/actions/{id}/approve` endpoint returned **200** with `FORGE_API_KEY` unset and transitioned an email action from `APPROVAL_REQUIRED` to approved; `/execute` likewise had no owner-key gate and could execute any policy-permitted action. Both handlers now require owner authorization for generic actions while preserving Forge Bot's existing rate-limited owner guard. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py -q` — **40 passed**; `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_forge_bot_api.py -q` — **64 passed**. New API regression verifies 503 when the owner key is unconfigured, 401 for absent credentials after configuration, and that neither approval nor execution state changes. (1) Owner action still required: explicitly approve and execute any action using the existing owner credential and action/purpose boundary; no email was sent and no external action was executed by this repair. (2) Action removed: anonymous users can no longer approve a consequential email action or invoke generic action execution. (3) Remaining: key-based access is not external permission or standing authorization; adapters still require valid configured capability and eligible policy. (4) Next dependency: continue auditing remaining generic writers, especially outcome creation and action proposals, for integrity/owner-contract violations; no real transaction or customer outcome was created. |
| Outcome evidence-kind rollups (2026-10-09) | **FIXED IN SOURCE — full backend suite passed; deployment identity NOT VERIFIED** | `data_scope` is only the REAL/SANDBOX environment axis; `source_kind` is the separate REAL/TEST/MOCK/HYPOTHESIS evidence label, and only REAL + VERIFIED outcomes count as real financial evidence. An isolated in-memory SQLite reproduction created an outcome with `source_kind=MOCK`, `data_scope=REAL`, `verification_state=REPORTED`; `product_summary` nevertheless reported its $99 as actual revenue. The same trace found internal revenue/customer/truth/observer/public reads filtering only by scope, learning records without provenance, strategy/dashboard calculations trusting bare Experiment revenue/cost fields, and reported revenue updating REAL opportunity confidence. Existing rollups and learning now preserve provenance; financial aggregates require linked REAL + VERIFIED outcomes; reported/mock results cannot update REAL confidence or mark an opportunity measured; legacy learning/lesson rows backfill conservatively as MOCK. Regression coverage includes product/public/internal totals, strategy performance, dashboard status, learning recall, and the REAL product gate. Verification: `cd backend && ../.venv/bin/python -m pytest tests/test_end_to_end_flow.py tests/test_renovation_truth_labels.py tests/test_commercial_ops.py tests/test_public_value_flow.py tests/test_public_feed.py tests/test_approval_outcome_bridge.py tests/test_phase1_provenance_and_identity.py -q` — **119 passed**; `cd backend && ../.venv/bin/python -m pytest -q` — **994 passed, 2 skipped**. (1) Routine owner action still required: submit and verify genuine transaction evidence; no real transaction exists. (2) Action removed by this repair: manually catching mock, test, hypothesis, and unverified rows misrepresented as real revenue/customers or validation, or changing REAL confidence/status. (3) Remaining: the repair cannot verify an arbitrary real-world claim or create payment evidence; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. (4) Next removable dependency: use verified provider/payment evidence through the existing REAL outcome path. |
| Outcome API truth labels (2026-10-10) | **FIXED IN SOURCE — focused tests pass; deployment identity NOT VERIFIED** | The existing `/forge/outcomes` create/list projection previously called every REAL-scope row `REAL ACTUAL`, despite `action_engine.record_outcome` defaulting it to `source_kind=MOCK`, `verification_state=REPORTED`. The existing projection now returns both evidence labels and distinguishes REAL/VERIFIED from non-real evidence without changing the conservative write defaults. Verification: `cd backend && ../.venv/bin/python -m pytest tests/test_http_canonical_final.py -q` — **9 passed**. (1) Owner action still required: record actual outcome evidence with its real source and proof. (2) Action removed: interpreting the scope-only API label as confirmation that a REAL event occurred. (3) Remaining: the response projection cannot verify the underlying claim; transaction evidence remains owner-supplied and externally unverified. (4) Next dependency: use the existing evidence-backed payment path. |
| Network payment confirmation and settlement provenance (2026-10-10) | **FIXED IN SOURCE — full backend suite passed; deployment identity NOT VERIFIED** | `/forge/connections/{id}/advance?next_state=paid` still conservatively writes MOCK/REPORTED. Confirmation requires an existing Evidence row explicitly classified REAL through the owner proof API as `third_party`, L5+, with a verifier and stored external URL or provider reference; evidence links to both the NetworkConnection and payment Outcome before that outcome becomes REAL/VERIFIED. A widened trace found the same owner-attestation flaw in `/forge/connections/{id}/settle-payment`: an owner note and amount promoted a dispute to public SETTLED, and public trust accepted legacy SETTLED rows without settlement-specific proof. Settlement now requires distinct independent evidence linked as an existing evidence-graph `updates` relation; original-payment evidence cannot be reused to substantiate a settlement amount. Public trust downgrades legacy or malformed VERIFIED/SETTLED outcomes lacking their required relation to REPORTED. Proof is immutable through the proof API once it supports a verified or settled network payment. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py backend/tests/test_operating_v4.py -q` — **129 passed**; `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests -q` — **996 passed, 2 skipped**. (1) Owner action still required: obtain and inspect genuine payment and, when disputed, distinct settlement evidence; record its external reference on Evidence rows, mark each via the L5+ proof flow, then confirm/settle with the corresponding IDs. (2) Action removed: owner-entered amounts/notes alone can no longer produce publicly verified or settled payment claims. (3) Remaining: no authenticated provider callback or automatic authenticity check exists; no real payment was observed, and `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. (4) Next dependency: authorized access to provider-generated transaction/settlement verification; do not contact a counterparty or buy infrastructure without explicit authorization. |
| Learning-from-experiment API authorization (2026-10-10) | **FIXED IN SOURCE — focused auth regression passed; deployment identity NOT VERIFIED** | A focused `TestClient` check of the existing `/forge/learning/from-experiment` writer, compared with adjacent owner-only endpoints, returned **422** with `FORGE_API_KEY` unset instead of failing closed with **503**; the handler had no owner-key check before looking up records or creating learning state. The existing canonical route now applies `require_owner_api_key` before data access. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_forge_connections_endpoints_require_owner_key -q` — **1 passed**. (1) Owner action still required: use the already-authorized owner API key to record learning; no key was accessed or changed. (2) Action removed: unauthenticated callers can no longer reach validation or mutate experiment/learning state through this writer. (3) Remaining: owner-supplied learning text remains MOCK by default and cannot establish REAL evidence; the route still depends on a previously recorded canonical outcome. (4) Next removable dependency: bind supplied learning to outcome content rather than accept parallel free-text claims, while preserving the conservative MOCK default. |
| Autonomy policy write authorization (2026-10-10) | **FIXED IN SOURCE — owner-key regression passed; deployment identity NOT VERIFIED** | A focused test seeded the conservative active policy (`max_daily_actions=3`) and sent `PATCH /forge/autonomy/policy` with the key unset. The route returned **200** and changed the policy to 99 actions/day instead of failing closed. The existing route now calls `require_owner_api_key` before reading or mutating the policy. Verification: `/Users/nirojpaudyal/Downloads/ForgeOS/.venv/bin/python -m pytest backend/tests/test_public_value_flow.py::test_autonomy_policy_widening_requires_owner_key backend/tests/test_public_value_flow.py::test_forge_connections_endpoints_require_owner_key -q` — **2 passed**; test covers missing configuration (503), missing presented key (401), no unauthorized policy mutation, and authorized owner update. (1) Owner action still required: explicitly configure standing authorization within the existing bounded policy; no policy was widened by this repair. (2) Action removed: unauthenticated callers can no longer widen the owner-defined autonomy boundary. (3) Remaining: a valid owner may still change the policy, but a policy ALLOW does not itself supply external permission or execution capability. (4) Next dependency: audit and guard the remaining legacy/action/outcome write surfaces according to their intended public or owner-only contracts; no external action is authorized by this repair. |
| Closed `/request` experience | **DONE — locally and live-render verified** | With the demand-understanding flag closed, `/request` renders the not-open message and no form. `/request-a-project` redirects there. A 390×844 browser check on `haminp.vercel.app` observed zero forms, textareas, and submit buttons and no browser errors. |
| Malformed intake validation | **DONE — local only** | TEST-marked malformed email returns 422 with the `email` field and generic message; no lead row is created. Do not test by submitting to production. |
| Public write limits and body caps | **IMPLEMENTED / locally tested; deployment identity UNVERIFIED** | Source enforces keyed durable limits (5/hour for posts/requests, 20/hour for domain close/dispute/response) and 16 KiB caps. Relevant endpoint tests pass on SQLite and throwaway PostgreSQL 18. Production GETs establish current closed flags, not the deployed source SHA; owner-readiness access is required for that SHA comparison. |
| Production flags and basic health | **OBSERVED CLOSED / healthy by GET** | At inspection, both `haminp.vercel.app` and `forge-os-ebon.vercel.app` returned `/api/health` 200 with `status=ok, ready=true` and `/api/forge-bot/config` 200 with `intake_enabled=false`. These responses do not prove authenticated readiness, database state, or which commit is deployed. |
| Operations dashboard owner-key flow | **IMPLEMENTED / production access UNVERIFIED** | `GET /forge/money/dashboard` and `GET /forge/execution/actions` require `FORGE_API_KEY`; backend tests verify 401 without it. The `/operations` UI now asks for the key in a password field, holds it only in component memory, and sends it on protected reads and explicit writes. Owner action still required: enter an already-authorized key. Missing backend configuration fails closed with 503; a wrong key returns 401. Next dependency: authorized confirmation that the production key is configured, then owner verification through the UI. No production key was accessed. |
| Homepage operating map | **IMPLEMENTED / local browser verified** | Home links SYSTEM → WORLD → OPPORTUNITIES → CAPABILITIES → ACTION → OUTCOMES to the existing `/about`, `/discoveries`, `/opportunities`, `/providers`, `/actions`, and `/what-we-learned` views. Production `GET /api/public/discoveries?limit=4` returned 200 with four `observed` records. Owner action still required: name a reachable seller and authorize the exact first contact. Action removed: visitors no longer need footer navigation or a guessed URL to follow these public surfaces. Remaining: each page's actual empty, unavailable, evidence, and authorization states still govern; the map does not imply a stage happened. Next dependency: the named-seller decision remains unchanged. |
| Signup session hydration | **FIXED / local browser verified; production account flow UNVERIFIED** | `ACTIVE_TERMS` is version `1.0`; signup requires an 18+ check and server-issued one-time terms permit. `/login` now keeps the server and first client render aligned while the session resolves. Fresh local reload had no page errors; the create-account form showed DOB and terms acceptance. No account was created. Production configuration and a real signup remain unverified. |
| Owner readiness and maintenance heartbeat | **BLOCKED / unverified** | The readiness endpoint requires the owner key. Do not retry unauthenticated calls or retrieve credentials to bypass this. Owner-authorized access is the next dependency. |
| Independent deploy verification recording | **GREEN — tested and deployed SHA matched 2026-10-09** | Run `37968695498` on main commit `6cdcd52` recorded `deployment_match=true`, test counts of 203 + 206 passing, and a successful verification POST (HTTP 200). Full CI `37968695522` passed every active job; secrets scan `37968695505` passed; repository guards were skipped. Runtime-changing commit `f40eb69` also matched in run `37967353373`. Earlier run `37967203061` recorded a mismatch before a later check matched; do not treat the workflow conclusion alone as proof—inspect the recorded SHA-match result. The original Node 20 test-glob failure and incorrect deployed-SHA source are fixed by using Node 22 and the existing owner-keyed readiness route; production content fetch fails closed. No owner action or external permission was removed; economic owner-intervention metric remains **NOT MEASURABLE**. Next dependency: a verified real transaction is still required to measure the metric. |
| Production database inspection | **BLOCKED** | No authorized credential retrieval procedure is established in the current docs. The owner must define and authorize the credential source and read-only procedure; no production database or credential was accessed. |
| Retention after response `ACTION` | **PLANNED, not implemented** | A linked response `ACTION` is exempt from the existing 30-day unactioned-inquiry purge. The proposed 90-day maximum needs owner approval before implementation. |
| Customer-facing response | **BLOCKED** | No owner-configured response channel/template or Forge Bot sender exists; the send flag defaults false. No outbound messages are authorized or sent. |
| Public stats response contract | **FIXED / production verified 2026-10-09** | The merged `origin/main` commit `a2b88a57` introduced `/public/stats` without a response model; the public-contract test exposed it. Added `PublicStatsOut` at the existing public-route schema seam; `/api/public/stats` has an explicit response contract. Rechecked on the currently matched production deployment: GET on `haminp.vercel.app` returned HTTP 200 with `{"owner_interventions_per_real_transaction":"NOT MEASURABLE"}`. Focused backend tests passed **26/26**; full backend suite passed **982**, **2 skipped**; full CI on `6cdcd52` passed. The task-list test now supplies a test-only owner key; production authorization is unchanged. This work removes no owner action or external permission. A verified real transaction is still absent, so `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. Next dependency: genuine, verified real-transaction evidence. |
| Human-reported bug pass (2026-10-09) | **PARTIAL — route defect production verified; owner-notification retry unverified** | Validation errors are generic and do not echo submitted values; public write rates/body caps are implemented and tested; money dashboard and execution-action reads call `require_owner_api_key`. `/discoveries` and `/feed` had no horizontal overflow at 390px in the local browser, though their API returned 502 because the local backend was unavailable. Unknown paths returned HTTP 200 before the route fix; route-level `notFound()` now returns 404, local smoke asserts it, and the current production deployment returned 404. Transient owner-notification retries previously had no caller; the daily owner digest now retries only due queued notices with an owner-notification idempotency prefix and the exact configured owner recipient. The existing owner readiness view reports pending/failed email; production scheduler execution, SMTP delivery, and permanent-failure repair remain unverified. The restored “Join Hami” CTA follows the later explicit owner-request commit `c9b6bf3c`, so it is preserved. `gh repo view` confirms the repository is public; the private-visibility decision remains with the owner. Database snapshots remain in the repository/history; no history rewrite or privacy change was authorized. Verification: `npm test` 409/409; `npm run check` passed with one pre-existing warning; `env -u DATABASE_URL npm run build` passed and skipped migrations; `npm run smoke` passed all 13 live routes and returned 404 for both unknown-route probes; 56 focused backend tests passed, then the final retry-specific suite passed 29/29. |
| Owner notification retry | **IMPLEMENTED LOCALLY / production unverified** | Routine owner action still required: inspect the owner readiness queue and repair SMTP for permanent failures. Action removed: manually re-enqueue transient owner-notification emails. Retry runs only when the existing scheduled owner digest runs, for due queued SMTP messages with an owner-notification idempotency prefix and exact configured owner recipient; unrelated messages are excluded. The digest is reached only after the scheduled legacy cycle succeeds, so it remains dormant when that cycle is disabled or fails. Production scheduler execution and SMTP configuration remain unverified. Next dependency: owner-authorized production readiness verification. |
| Unknown-route HTTP status | **FIXED / production verified on haminp.vercel.app 2026-10-09** | Previously, an unknown route displayed a 404 page but returned HTTP 200. The existing catch-all route now throws TanStack `notFound()`; local smoke checks pass and a production GET to `/__hami_unknown_route__` returned HTTP 404 on `haminp.vercel.app`. The second configured production domain was not probed. |
| Pilot segment and paid outcome | **HYPOTHESIS / owner action required** | The initial segment remains unverified until the owner reports five real discovery conversations. No real customer/revenue outcome is established; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. |
| ForgeBot v0 — operator's assistant | **IMPLEMENTED / locally tested** | `src/lib/forge/assistant.ts`: `verifyRound()` gates round findings through the evidence gate before banking (rejected findings are never banked); `ripenessQueue()` ranks open unknowns (desk-doable first, oldest first); `isAngleTried()` refuses repeated angles against 14 tried angles parsed from the discovery log. `docs/ROUND_PROTOCOL.md` specifies the loop precisely. 12 assistant tests pass. Per-change analysis: (1) owner action still required: none for the assistant itself — the five real conversations still need a human; (2) action removed: manual angle-picking and manual gate-checking from operator rounds; (3) remains/blocked: ForgeBot running rounds itself (v1) needs the round protocol wired to its tool access — no new permission, just the build; (4) next removable dependency: operator-planned angles → assistant-suggested angles. The operator console lives inside `/owner` behind the owner key only (no public route): gate tester, angle checker, ripeness list — all running the real engine code. |
| Backend PostgreSQL full-suite coverage | **DONE — prior SQLite/PostgreSQL parity verified** | The complete backend suite previously passed 686 tests, 2 skipped on SQLite and throwaway PostgreSQL 18. The focused Forge Bot/owner-notification/privacy/public-write/signal tests passed 112/112 on both dialects. The latest Python 3.11 SQLite run passed 697 tests, 2 skipped after refreshing the D77 parser expectation. PostgreSQL was not rerun for this test-only change; none of this establishes production database behavior or the deployed source SHA. |
| Unknown-map importer test count | **DONE — D1-D77 covered at time of entry; registry now at D1-D83** | `docs/UNKNOWN_MAP.md` contained 9 A, 4 B, 3 C, and 77 D entries (93 total) when this entry was written. `backend/tests/test_import_unknowns.py` asserted the D77 endpoint. Registry has since grown to D1-D83 (verified 2026-10-09); see current UNKNOWN_MAP.md and src/lib/unknowns.ts projection. This corrects test coverage only; owner action still required for the seller pilot. |
| Cleared-source empty retrieval semantics | **FIXED / focused tests pass; live run pending** | A normal empty GDELT response is now recorded as `source_accessed=true`, `valid_empty_retrieval`, zero source records, and no claim effect. The task remains `needs_research` with no Evidence or Opportunity; source usage counts the successful access rather than a provider failure. GDELT remains cleared for media metadata only, not prospect identification. Owner action remains naming/authorizing a seller and a separate exact business-prospect source clearance. |

Latest local verification after source edits: the full frontend/script suite
passed **364/364** with `FORCE_COLOR=0 NO_COLOR=1`; typecheck, lint, and the
production build passed. The build ran with `DATABASE_URL` unset and skipped
migrations. The full backend suite passed **697**, **2 skipped** on Python
3.11; the focused owner-key guard test also passed. Browser checks at 1280px and 390px found no
horizontal overflow or page/console errors, and no protected operations read
occurred before key submission. Read-only production GETs to `/login` and
`/api/auth/get-session` returned 200 on both domains. No account, production
write, credential access, message, database query, or flag change was made.
GitHub checks for the first pushed commit `6714314` reported frontend success
and backend failure on the stale D70 parser expectation. Both GitHub checks
passed on follow-up commit `8d6d24e`, which updates the test to D77.

## [PARTIAL] Connect owner operations UI to its existing API-key boundary (2026-10-04)

- Owner action still required: provide an authorized `FORGE_API_KEY` in the
  operations page; the production key configuration has not been inspected.
- Action removed: `/operations` previously requested protected money/action
  reads and sent cycle, discovery, and approval writes without the required
  `X-API-Key`, leaving its controls disconnected from the backend boundary.
- Remaining blocker: the backend must have its owner key configured; absent
  configuration returns 503 and a wrong key returns 401. Entering a key does
  not run a cycle, approve an action, authorize contact, or spend money.
- Next removable dependency: owner verifies the configured key in the UI;
  production access remains unverified until then.
- Verification: focused API-header test passed; backend
  `test_money_and_execution_reads_require_owner_key` passed on Python 3.11;
  full frontend/script suite passed 364/364; typecheck, lint, and build passed.
  Browser verification at 1280px and 390px showed the key form,
  no horizontal overflow, no page/console errors, and no protected reads before
  unlock. Backend tests in `backend/tests/test_commercial_ops.py` assert the
  protected GET behavior. No production key or write was used.

## [PARTIAL] Connect existing public system surfaces from the homepage (2026-10-04)

- Owner action still required: name one seller and explicitly authorize the
  exact first contact; homepage navigation does not replace that decision.
- Action removed: a visitor can now move from Hami's identity to its existing
  public observations, opportunity hypotheses, capability graph, action
  aggregate, and recorded learning directly from the homepage.
- Remaining blocker: the map is an index of existing views, not evidence that
  all stages occurred. Local FastAPI was offline and the page displayed its
  explicit unavailable state; production's public discoveries endpoint
  returned HTTP 200 with four `observed` rows.
- Next removable dependency: the seller remains the next real-world blocker;
  no new API, workflow, permission, or data model was added.
- Verification: the focused homepage content test passed 14/14; typecheck
  passed. At 1280px and 390px, all six links rendered in order with no
  horizontal overflow or page errors. No customer, action, outcome, or revenue
  claim was added.

## [DONE WITH LIMITATION] Keep signup's first render hydration-safe (2026-10-04)

- Owner action still required: each registrant must be at least 18 and accept
  current Terms 1.0; no production signup was attempted.
- Action removed: the login page no longer renders different session branches
  during server render and the first client hydration when the session resolves
  quickly.
- Remaining blocker: deployed auth/provider configuration and successful
  production account creation are not established by public GET checks.
- Next removable dependency: verify deployment readiness through an already
  authorized path; do not create a production test account.
- Verification: full frontend/script suite passed 364/364; typecheck, lint,
  and production build passed. A fresh local `/login` reload had no
  hydration/page errors; the signup toggle exposed name, DOB, Terms link, and
  consent checkbox.
  No credentials were entered and no account was created.

## [DONE WITH LIMITATION] Align unknown-map importer test with current inventory (2026-10-04)

- Owner action still required: name one seller and authorize the exact first
  contact; parser coverage does not move that real-world decision.
- Action removed: the backend suite no longer expects the obsolete 86-entry
  map after the repository grew from D70 to D77.
- Remaining blocker: this test-only repair provides no seller, customer, or
  revenue evidence; the owner-named-seller decision remains outstanding.
- Next removable dependency: the owner names one reachable seller and
  authorizes the exact first contact.
- Verification: source inspection confirmed D70 and D77 are present and the
  parser returned 93 entries. The focused parser test passed and the full
  Python 3.11 backend suite passed 697 tests with 2 skipped.

## [PARTIAL] Restore system-first homepage perception (2026-10-04)

- Owner action still required: conduct owner-run discovery and explicitly
  authorize any first contact; any seller must separately authorize the exact
  pilot access and operating scope before messages are handled.
- Action this change removes: a visitor no longer has to distinguish Hami's
  identity from a prominent seller-reply offer or an inbox-tool CTA. The
  homepage describes Hami's open-ended relationship with reality, evidence,
  capabilities, authorization, and actual outcomes before showing one small
  proposed investigation.
- Remaining blocker: Experiment 1 has not started, no seller has agreed, and
  there are no participants or results. The homepage's public record uses
  existing source-observation data only; it does not request restricted
  substrate records or claim that a source observation is verified.
- Verification: the homepage/content contracts passed **38/38**; full
  `npm test` passed **363/363**; `npm run typecheck`, `npm run lint`, and
  `env -u DATABASE_URL npm run build` passed (database migrations skipped
  because `DATABASE_URL` was unset). At desktop width **1280px** and mobile
  width **390px**, the homepage had no horizontal overflow. Visual inspection
  confirmed the Hami identity is the first-glance message, the broader
  reality/evidence section and public record precede the small, explicitly
  not-started Experiment 1 note, and primary navigation no longer names the
  inbox prototype. The mobile menu lists Hami, The system, and Public record.
  `/prototype/inbox` remains directly available (HTTP 200) and labeled TEST.
  The public observations API returned HTTP 502 locally because the backend
  was not running; the homepage displayed an explicit unavailable state
  rather than implying no data or inventing observations. No browser
  JavaScript page errors occurred. PR #5 frontend and Vercel checks passed;
  the backend workflow failed on the unchanged
  `tests/test_import_unknowns.py::test_parses_all_sections` assertion
  (expected 86, parsed 93; 696 passed, 1 failed, 2 skipped). Backend, engine,
  database, API implementation, substrate, research logic, payment, and auth
  architecture remain untouched.
- Next removable dependency: owner-run discovery and an explicitly
  authorized first contact; the page cannot provide seller participation,
  external permission, or pilot access.

## [PARTIAL] Batch 12B: close request-state, copy, and verification gaps (2026-10-04)

- Owner action still required: define an authorized source and retrieval
  procedure for a production database credential, and provide an already
  authorized way to inspect owner readiness if deployed commit evidence is
  required. Neither boundary is bypassed here.
- Action this change removes: stale-copy test patterns are made explicit
  absence checks; malformed intake validation is checked with TEST-marked
  input and must not persist a lead; and the operator documentation now
  states the production database credential-access boundary.
- Current blocker / verification: `/request` returns the closed message with
  no form while the request status is `enabled:false`; `/request-a-project`
  remains a redirect to `/request`. Its route/component changes were already
  present in commit `b774ead746d78f606bf393d305754aa2aefe9dfd`. The current
  content test already asserted the old mailbox copy was absent; this change
  expresses each retired phrase as a separate absence assertion. Local
  content tests passed **10/10**. At 390x844, local browser checks used an
  explicit GET stub of `enabled:false`; both `/request` and
  `/request-a-project` showed the closed message and zero forms, textareas,
  or submit buttons, with no horizontal overflow or browser errors. No
  submission was made. The malformed-intake test runs with
  `FORGE_BOT_INTAKE_ENABLED=false`; Pydantic rejects its TEST-marked malformed
  email before the route can persist a row; the response is 422, contains
  only the `email` field and a generic message, and the lead table remains
  empty. The three affected backend files passed **103 tests on SQLite** and
  **103 tests on throwaway loopback PostgreSQL 18**. The current source has a
  16 KiB public-write cap, 5/hour limits on public posts/requests and
  20/hour on domain control actions. Production deployment of that source is
  not established by a public GET. The owner readiness endpoint is owner-key
  protected; without already authorized access, deployed commit SHAs on both
  production domains are BLOCKED. No production write, credential read, or
  production database query was made.
- Next removable dependency: owner-defined credential retrieval authorization
  and owner-authorized readiness access; then compare the readiness endpoint's
  deployed commit on both domains to `origin/main`. Do not test production
  rate limits by submitting traffic.

## [PARTIAL] Align the closed demand-request UI and owner-shell contract (2026-10-04)

- Owner action still required: keep Forge Bot intake and LIVE closed, review
  any future change that would expose either submission path, and use the
  authorized owner-key path for protected readiness details. No credential
  was requested or read.
- Action this change removes: presenting an apparently usable anonymous
  demand-request form while its existing server gate is disabled; ambiguity
  about whether `/owner` itself is an authentication boundary; and returning
  raw `ValueError` or `HTTPException` text from an app-wide 422 response.
- Current blocker / verification: `/request` now checks the separate
  `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` flag and renders no form when closed
  or when status cannot be confirmed; the POST remains server-gated.
  `/owner` is an intentionally public, unlinked, noindex key-entry shell;
  owner data/actions remain API-key protected. On the local 390px browser,
  `/request` and `/request-a-project` showed the closed message with zero
  forms, textareas, or submit buttons. The local browser used an explicit
  `enabled:false` GET stub because the already-running backend process
  predates the new status route; current-source TestClient coverage verifies
  the config route and closed POST. Local `/owner` showed noindex, one key
  field, and no owner API calls before key entry. Request-validation 422s
  expose safe field paths with generic messages; ValueError and other HTTP
  422s use a generic detail only. Tests cover malformed-email non-echo and
  both ValueError/HTTPException details containing a submitted-value
  sentinel. The
  `/signals/public-request` boundary is tested at five allowed requests and
  a sixth 429 with a keyed visitor hash. Full local verification: backend
  SQLite **685 passed, 2 skipped**;
  frontend/script tests **197 + 107 passed**; typecheck, lint, and build
  passed. The build's database migration step skipped because `DATABASE_URL`
  is not configured locally.
  Read-only production checks on `haminp.vercel.app` and
  `forge-os-ebon.vercel.app` returned health 200/ready, intake disabled, and
  `/api/signals/public-request/config` with `enabled:false`. On the
  `haminp.vercel.app` browser, `/request` and `/request-a-project` both
  displayed the closed message with zero form controls; `/owner` was a
  public noindex shell with no owner data before key entry. The unauthenticated
  owner-readiness GET initially returned 401 on both domains. During a later
  repeated GET-only sweep, owner-data GETs on `haminp.vercel.app` returned
  401; the same routes on `forge-os-ebon.vercel.app` returned 429, so further
  probes there were stopped and no owner details were returned. The failed
  authentication limiter may count such GET attempts; no POST, PUT, PATCH,
  DELETE, authenticated request, or intentional production data write was
  made. The source changes are in commits `b774ead746d78f606bf393d305754aa2aefe9dfd`
  and `84b040315aeaecf22a1d37bbbbf61aa04dae1688`; `origin/main` matches the
  latter. No deployment was explicitly initiated in this task, and the live
  GET evidence does not establish which commit is deployed. Production
  validation/rate-limit enforcement was not tested because proving it would
  require production POSTs. The authenticated maintenance heartbeat and
  production database details remain BLOCKED by the owner-key/credential
  boundary.
- Next removable dependency: review and deploy the source change through the
  normal authorized release path, then verify POST enforcement only against
  local test databases; live owner-only readiness still requires an
  already-authorized owner key.

## [DONE WITH LIMITATION] Add a private owner console and activation procedure (2026-10-04)

- Owner action still required: enter the owner key in a live browser session;
  confirm receipt of the test message; approve the exact privacy text; and
  make the external discovery, channel, booking, and activation decisions.
- Action this change removes: manually inspect the private lead table and
  delivery queue, compute readiness aggregates, and reconstruct owner-marked
  reply/booking/completion from separate notes. Public health now exposes only
  `status` and `ready`; its existing diagnostics are behind
  `/api/health/details` and the required owner key. The console uses the existing
  lead-contact rows, `Action`/`WorldEvent` substrate, and delivery outbox.
- Current blocker / verification: the stored lead stage remains
  `READY_FOR_OWNER_REVIEW`; the console derives `REQUESTED`, `REPLIED`,
  `BOOKED`, and `COMPLETED` from registered non-contact lifecycle events
  instead of adding stored states or a canonical entity. Intake and LIVE stay
  disabled; no key is persisted by the browser; the activation runbook is
  documentation only. Local PostgreSQL and browser verification are complete.
  The full backend suite passed **681 passed, 2 skipped** on SQLite and on
  throwaway PostgreSQL 18; focused Forge Bot owner-notification/API tests
  passed **69/69** on PostgreSQL 18; focused health authorization/ingress
  tests passed **16/16** on both databases. `npm test` passed (197 script and
  106 app tests), and typecheck, lint, and production build passed. The
  pre-deployment public health/config GETs succeeded on both production
  domains and intake remained disabled.
  The attempted production owner-readiness GET returned 401, so authenticated
  production readiness and the live maintenance heartbeat remain unverified.
- Next removable dependency: verify owner-key access and readiness evidence;
  then independently complete every activation-runbook check. Owner-confirmed
  receipt of the one-shot test email and approval of the privacy text remain
  unverified in this workflow. External permission and a real customer
  outcome remain owner/reality dependencies, not capabilities supplied by
  this console.

## [RECORDED] Batch 12 close-out evidence (2026-10-04)

- Owner action still required: approve or reject the unlinked privacy draft and
  the proposed 90-day maximum retention after a response `ACTION`; complete
  owner-run discovery before selecting a segment or pilot terms. No activation
  is authorized by this record.
- Action removed: correct the homepage wayfinding and closed-inquiry copy,
  add “For businesses” once to the primary mobile/desktop navigation without
  removing other entries, set the public share title to Hami, minimize public
  health output, protect health diagnostics with the owner key, and document
  the production database and recovery checks without changing production
  records.
- Current blocker / verification: latest pushed commit
  `80f757f9b0d6b2d2ae4e5e2e4c608e1caa358f5b` passed GitHub Actions frontend
  and backend jobs; Vercel reported a successful deployment. Read-only GETs
  against both `haminp.vercel.app` and `forge-os-ebon.vercel.app` returned
  health 200 with `{"status":"ok","ready":true}` and
  `intake_enabled=false`; unauthenticated health-details and owner-readiness
  returned 401. Both domains return Report-Only CSP, `nosniff`, strict-origin
  referrer policy, `X-Frame-Options: DENY`, and the minimal Permissions-Policy.
  The 390px production browser showed the business link in the mobile menu,
  Hami share/apple titles, and no overflow on `/discoveries` or `/feed`.
  `/privacy` remains `noindex, nofollow` and unlinked from navigation or
  consent. Local backend tests pass on SQLite and PostgreSQL 18, and frontend
  tests/typecheck/lint/build pass. The production database read used
  read-only transactions: all 69 ORM model tables and expected columns were
  present in the 75-table public schema; there were no `REAL` Forge Bot leads.
  One mode-600 backup was restored to a disposable PostgreSQL 18 container and
  all 75 table names and row counts matched. The backup remains outside the
  repository at `~/Downloads/hami-backups/hami-production-2026-10-04.dump`; do
  not commit it. Production owner readiness returned 401; live heartbeat and
  authenticated readiness are not verified. Cal.com was only loaded
  read-only; no slot was selected, so the final booking form fields remain
  unknown.
- Next removable dependency: obtain owner approval and independently verify
  each readiness item in `docs/ACTIVATION.md`. Keep the privacy draft
  unlinked until approval, and keep intake and `FORGE_BOT_LIVE` closed.

## [DONE WITH LIMITATION] Enforce the Forge Bot response ACTION boundary (2026-10-03)

- Owner action still required: conduct owner-run discovery, then choose and
  authorize an exact existing response channel and template reference with
  consent, opt-out, escalation, and send boundaries. Do not infer a channel
  from submitter preference.
- Action removed: prevent generic `smtp/send_email` and `twilio/send_sms`
  paths from serving Forge Bot leads without the canonical decision. An
  owner-only proposal/approval path uses the existing `Action` primitive; the
  same decision is enforced by the ACTION adapter, before outbox creation, and
  immediately before provider dispatch. Proposal, approval, and decision
  transitions emit registered `WorldEvent`s.
- Current blocker / verification: no owner channel/template is configured,
  `FORGE_BOT_RESPONSE_SEND_ENABLED` defaults false, and no Forge Bot sender
  exists. The full ACTION decision is `BLOCKED`; a separate policy subdecision
  may be `ALLOWED` when a TEST inquiry matches policy, but that does not
  authorize execution. Tests cover required blockers, PII-free decision/event
  payloads, generic SMTP/Twilio rejection before queueing, dispatch-time
  checks, audit persistence failure, and zero provider calls/deliveries.
  Local verification on 2026-10-03: focused Forge Bot/API/notification/outbox
  tests **68 passed**; backend suite **640 passed, 2 skipped**; `npm test`
  passed (197 script and 104 app tests), typecheck, lint, build, and
  `git diff --check` passed. Build migration skipped because `DATABASE_URL`
  was unset. No real external message was sent or queued.
- Next removable dependency: the owner must supply one authenticated
  authorization object selecting an existing channel and exact template
  reference. Any later sender implementation must resolve template content
  and sender capability, retain the send flag default false until separately
  authorized, and pass the canonical decision before ACTION and dispatch. Do
  not create a next-day `WorkerTask` until these gates and a production runner
  are verified.

## [DONE WITH LIMITATION] Preserve Forge Bot inquiry lifecycle events (2026-10-03)

- Owner action still required: complete owner-run licensed-agency discovery, identify/confirm the real communication channel, and authorize any reply or follow-up. This change does not reduce those real-world decisions or authorize contact.
- Action removed: reconstruct whether a web inquiry was received, opted out, or erased after its private lead row changes or is deleted. Each transition now leaves a registered event; this does not lower `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION`.
- Current blocker / verification: the actual input is the gated `/forge-bot-intake` web form. A synchronous browser receipt is returned, but no message is sent through the selected email/phone channel. Production intake remains disabled by default; real lead persistence also requires `FORGE_BOT_INTAKE_ENABLED`, the server HMAC key, the API key, and the explicit LIVE setting. Event payloads contain only the opaque reference, `REAL`/`TEST` evidence class, and state transition. Tests verify registration, privacy minimization, erase-history retention, and rollback on event-write failure. On 2026-10-03, backend tests passed (596 passed, 2 skipped), frontend/script tests, typecheck, lint, and build passed; the local browser showed the closed intake state with no console errors.
- Next removable dependency: conduct and record the owner-run discovery, then explicitly identify and authorize one legitimate zero-cost reply channel/template and its consent/opt-out limits. Only afterward evaluate a next-day `WorkerTask` flow and a permitted reliable runner; no sub-daily production worker is established.

## [RECORDED] Archive superseded documents and legacy frontend source

- Owner action still required: resolve the Section 8 wording separately; identify whether the ignored exported context files may be committed; authorize any future live Oracle VM provisioning or real email delivery.
- Action removed: reduce competing current-looking documents and preserve the Next.js dashboard and historical records under `docs/archive/`, while retaining the root `start.sh`/`stop.sh` path and preview-only `startup.sh`.
- Current blocker / verification: `sanipops_clean/river-cinder-bamboo-otter-main/` is only copied preview tooling, not a complete application; no `opencode.jsonc.bad`, `status.sh`, or `start.ps1` exists in the current tree. The requested ignored context files are excluded by `.gitignore` and will not be added to version control without owner clearance.
- Next removable dependency: confirm whether ignored context snapshots are safe and intended for archival in Git, then validate the archived Compose legacy surface without provisioning external infrastructure.

## [DONE WITH LIMITATION] Connect current Hami capabilities to their existing public surfaces

- Owner action still required: complete the five owner-run licensed-agency discovery conversations, choose a retention window, and separately authorize/configure any real intake. Do not infer a customer segment or market decision from navigation.
- Action removed by this change: remove the need to manually share or explain the business and closed Forge Bot inquiry URLs; give the home page a factual route guide; remove the public click-through to detailed approval controls that do not enforce owner identity.
- Current blocker / verification: the business page and closed Forge Bot page are linked from the home path guide and business context; the business path is also in mobile secondary navigation and the persistent footer. Locally, frontend tests pass (103), typecheck and `check:auth` pass, the production build passes with `DATABASE_URL` unset, and backend tests pass (589 passed, 2 skipped). Local browser checks rendered `/`, `/discoveries`, `/feed`, `/opportunities`, `/actions`, `/system`, `/group/businesses`, and `/forge-bot-intake` without console or HTTP errors; the 390px mobile view had no horizontal overflow, and the closed intake page rendered no form. The production deployment for `ff9733afd41a69564c8f5e57a4a23f2156e280a4` is READY (`dpl_DAmKa73xRG9YukfiDpoVFTsLBTVo`); GitHub CI run `37020876876` passed both frontend and backend jobs on that exact SHA, and its Vercel commit status is `success`. Production routes `/`, `/discoveries`, `/opportunities`, `/actions`, `/system`, `/group/businesses`, `/forge-bot-intake`, and `/api/forge-bot/config` returned HTTP 200. Browser verification rendered all checked pages without console errors; `/discoveries` made no `/api/forge/substrate/` request and explained the restricted-state boundary. The intake page rendered the supplied contact and booking links, `noindex,nofollow`, and no form; the production config returned `intake_enabled: false`. `npm run lint` remains unverified because ESLint reports that no `eslint.config.*` exists. Protected substrate reads require the server key when configured. Separate blocker: `/operations` is not owner-authenticated and the current API-key middleware leaves ordinary GETs open, including detailed execution-action reads. Unlinking it from `/actions` is not an access-control fix; do not treat the route or records as private. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains NOT MEASURABLE.
- Blocking capability / authorization: production intake remains disabled; real submissions still require the existing feature flag, stable server HMAC key, API key, distributed ingress controls, retention decision, and explicit bounded owner authorization. SMTP delivery of the internal digest is configuration-dependent. This navigation change does not send email, contact anyone, or expose the owner summary.
- Next removable dependency: establish an owner authorization boundary for detailed operations reads before making that surface discoverable; separately complete owner-run discovery and resolve the existing intake prerequisites. Empty/unavailable states remain distinct from evidence that a capability ran.

## [DONE WITH LIMITATION] Enforce Forge Bot LIVE gate before deployment

- Owner action still required: conduct the five licensed-agency discovery conversations before real intake; choose a retention window; configure `FORGE_BOT_INTAKE_ENABLED`, `FORGE_BOT_CONTACT_HMAC_KEY`, and `FORGE_API_KEY` only in a protected server environment; set `FORGE_BOT_LIVE=true` only after explicit bounded authorization; provide protected `SMTP_HOST`, `SMTP_USER`, and `SMTP_PASSWORD` (optionally `SMTP_FROM_EMAIL`) values for daily delivery; separately authorize customer-facing email or follow-up.
- Action removed: enforce `FORGE_BOT_LIVE=false` in the API so TEST validation cannot store REAL leads; implement the approved daily owner status digest through the existing authenticated cron and SMTP outbox without adding schema or contacting customers.
- Current blocker / verification: production `/api/forge-bot/config` reports `intake_enabled: false`; `FORGE_BOT_LIVE` is absent in production and defaults false, so intake remains disabled. A regression test reproduced the former bug (`FORGE_BOT_LIVE=false` returned HTTP 202 for a REAL lead); the route now rejects REAL submissions with HTTP 403 before persistence while still permitting TEST records. The daily digest runs only after a successful authenticated cron, deduplicates per UTC date, labels TEST/REAL evidence, and includes references, stages, and creation times without contact data. Tests use a mocked SMTP dispatcher. Production has no SMTP environment names, so delivery is skipped; no email was sent and no REAL lead was submitted. Full backend tests pass locally and in GitHub Actions (589 passed, 2 skipped); frontend tests (103), typecheck, and production build pass. `npm run lint` remains unavailable because the repository has no `eslint.config.*`. GitHub run `37014849703` passed both jobs on exact commit `effb1e291ec197d9d1880f183a50cf3ac2188b5b`; the backend needed a retry after the pre-existing SQLite concurrency test intermittently failed with `database is locked`. Vercel deployment `forge-n6l6ykex6` (`dpl_8UZ2MubaZZvjbxC9j1YxS3UbVhyz`) is READY, and its successful deployment status is attached to that same commit. The production config endpoint reports intake disabled; the actual `/forge-bot-intake` page rendered the supplied contact email and Cal.com link, stated intake is closed, and had no browser console errors. Unauthenticated `/api/scheduled/cycle` returns HTTP 401. Production-only `npm audit` reports 0 vulnerabilities; the full audit still reports one pre-existing high-severity dev dependency advisory in `brace-expansion`, not changed here. The private storage boundary and public-feed exclusion remain covered. No real transaction is verified; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is NOT MEASURABLE.
- Next removable dependency: owner-run five licensed-agency discovery conversations, a chosen retention window, protected SMTP credentials for internal digest delivery, production distributed ingress abuse controls, and explicit bounded owner authorization/configuration for any real intake. Keep intake disabled and LIVE false until those prerequisites are met; foreign-employment remains out of scope without separate regulatory and reputation review.

## [BLOCKED: NEEDS OWNER] Oracle Always Free live worker and database evaluation

- Owner action still required: provide or authorize an Oracle Cloud account/profile for a local evaluation and confirm the selected tenancy, region, resource quotas, billing safeguards, and acceptable zero-cost boundary before instance creation.
- Action removed: none; a live instance was not created, and no worker/database reliability claim is made.
- Current blocker / verification: repository inspection shows Compose can start the FastAPI backend and optional 30-minute worker with a shared SQLite bind mount, health dependency, and periodic backup settings; `docker compose config --quiet` passed during Step 1. This verifies local configuration syntax only. No Oracle account credentials were provided or used, no VM was provisioned, and no scheduler/database uptime or recovery behavior was measured.
- Next removable dependency: owner-authorized Oracle credentials and an account-specific no-charge guard; then run the worker, scheduler, database, backup, restart, and recovery checks on the actual eligible instance.

## [RECORDED] Operationalize the 30-day Forge Bot v0 decision gate

- Owner action still required: conduct and record real discovery only under the owner's existing authorization; this entry grants no contact or offer permission.
- Action removed: define an observable start event and paid-outcome threshold for the 30-day rule, without treating conversations or stated intent as revenue.
- Current blocker / verification: `docs/ARCHITECTURE.md` Section 8 starts the 30-day clock on the first recorded real owner-run discovery conversation and requires at least one verified real paid consultancy outcome by day 30; otherwise the bet stops without an automatic pivot. This is an operationalized threshold, not verbatim wording found in the prior materials.
- Next removable dependency: owner-run discovery and attributable evidence of any real paid outcome; no customer, revenue, or transaction is asserted here.

## [DONE WITH LIMITATION] Align Vercel rewrite contract tests with Better Auth routing

- Owner action still required: confirm production Google OAuth environment-variable presence in Vercel; the CLI is unavailable in this environment.
- Action removed: resolve the mismatch between the intentional Better Auth web rewrite and two stale backend assertions; no runtime routing behavior changed.
- Current blocker / verification: `/api/auth/$` is implemented by the web app's Better Auth handler, so the `/api/auth/(.*)` web rewrite must precede the general FastAPI `/api/(.*)` rewrite. Focused tests verify the ordered contract. No Vercel configuration or production state was changed.
- Next removable dependency: verify Google variable names in the Vercel dashboard; do not reveal or copy their values.
- Evidence boundary: test assertions are repository-contract checks, not evidence of production OAuth configuration or a completed login.

This is the active human/agent claim ledger required by
`FORGE_SUBSTRATE_BLUEPRINT.md`. Search it before work, claim a bounded scope
before implementation, and record verification before marking a claim DONE.
Claims coordinate contributors; database uniqueness and idempotency remain the
enforcement layer when claims overlap.

## [DONE WITH LIMITATION] Harden local account creation and provider boundary

- Owner action still required: supply direct Google OAuth credentials and an
  approved Hami terms document/version before enabling those signup paths. The
  owner must also arrange rotation of the preview OAuth secret previously
  committed to source history; this work will not rotate it.
- Action removed by this change: the misleading broker-backed Google route,
  user-visible X method, embedded preview OAuth credential, and reliance on a
  frontend-only age check. Server-side account creation now requires a
  single-use age/terms permit; DOB is not retained.
- Current blocker and verification: all frontend tests (197 script + 99 app),
  typecheck, production build, and auth-flag check pass. The local browser
  rendered `/`, `/discoveries`, `/feed`, `/opportunities`, `/system`, and
  `/login` without runtime errors or failed requests. A direct signup API call
  without a permit returned 403. The login page shows Google disabled because
  `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are absent; no Google OAuth
  destination or session flow could be exercised. Signup remains closed
  because no approved Hami terms document/version exists. ESLint cannot run
  because the repository has no ESLint 9 configuration. The former preview
  secret remains in Git history and needs owner-controlled rotation.
- Next removable dependency: owner-provided Google client credentials with an
  exact Hami callback registered at Google, plus the approved legal terms and
  consent version; owner-controlled secret rotation remains outstanding.
- Evidence boundary: implementation and tests use `TEST` state only.
  `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE** because
  there are no verified real transactions.

## [DONE WITH LIMITATION] Keep personal context private to its account

- Owner action still required: a person chooses to create/sign in to an account
  and explicitly reviews and saves any guest context; authentication alone
  never authorizes sharing.
- Action removed: personal context no longer relies on the owner to keep
  persistent browser storage separate from public Hami data. Guest drafts are
  tab-local, and authenticated reads/writes/deletes derive ownership from the
  verified session.
- Current blocker and verification: local account flows, two-account
  isolation, explicit guest save, reload persistence, and public-page
  non-leakage were browser-tested. Local verification uses in-memory PGlite
  with `DATABASE_URL` unset; no durable or production database was touched.
  The clear action was verified to remove stored context and reset the visible
  form. `npm test`, `npm run typecheck`, `npm run check:auth`, and
  `env -u DATABASE_URL npm run build` pass.
- Next removable dependency: verify the existing auth and context migrations
  against an owner-authorized non-production database before relying on
  persistence across server restarts; the local PGlite database is process
  local. Do not provision infrastructure, run migrations against a durable
  database, or deploy without that authorization.
- Evidence boundary: all local accounts/context used for tests are `TEST`, not
  human/customer or revenue evidence. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION`
  remains **NOT MEASURABLE** because there are no verified real transactions.

## [DONE WITH LIMITATION] Surface persisted open-world discoveries in Hami

- Evidence: the restored home centers on a browser-local personal System and a
  public Feed; `/discoveries` currently shows only public sourced observations.
  The canonical backend already exposes persisted discovery entities through
  `GET /forge/substrate/discovery/findings`, using the existing substrate and
  discovery engine.
- Owner action still required: decide whether to explicitly run a local
  discovery pass after reviewing its methods and boundaries. This interface
  does not run it, and no production run was made.
- Action removed by this change: navigate to the backend endpoint manually to
  review already-persisted findings; the Hami discoveries surface will project
  those records alongside clearly separated public observations.
- Blocker and boundary: this is a read-only projection. It does not run
  discovery, create findings, authorize actions, or claim real-world outcomes.
  The findings endpoint remains subject to the backend's `FORGE_API_KEY` gate;
  no key is sent to the browser. The local endpoint currently reports no stored
  discovery findings. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT
  MEASURABLE** because this work has no verified real transaction evidence.
- Verification (local): `backend` pytest 575 passed, 2 skipped; `npm test`
  passed 196 script tests and 81 app tests; `npm run typecheck`, `npm run
  build`, and `git diff --check` passed. Build skipped database migration
  because `DATABASE_URL` was unset. The local findings GET returned 200 with
  an empty array; the public observations projection returned 34 records.
  Browser checks rendered `/`, `/discoveries`, `/feed`, `/opportunities`,
  `/actions`, `/operations`, and `/system`; no failed requests or console
  errors were observed, and the 390px mobile viewport had no horizontal
  overflow. No discovery run or production endpoint was called.
- Tooling limitation: the targeted ESLint command could not run because the
  repository has no `eslint.config.js`, `.mjs`, or `.cjs` configuration for its
  installed ESLint 9. No lint configuration was added as part of this work.
- Next removable dependency: a trusted, authenticated owner-context read path
  for private substrate records, so protected findings can be viewed without
  manually inspecting an API or exposing the backend key to the browser.

## [DONE WITH LIMITATION] Command 2: open-world discovery engine

- Agent: Grok (executor), owner-authorized direct commits to `origin/main`, 2026-09-30 NPT.
- Scope: build a replaceable discovery capability inside the substrate so Hami can surface things it did not know to look for, without a fixed research workflow or a domain taxonomy. No new table, primitive, service or ledger. See `docs/archive/legacy-docs/FEATURE_INVENTORY.md` § Open-world discovery engine.
- Implementation:
  - `backend/app/services/discovery_engine.py` adds a `DiscoveryMethodRegistry` of versioned plugins and eight built-in methods: `evidence_contradiction`, `question_reframe`, `numeric_divergence`, `disconnection`, `isolation`, `recurrence`, `capability_integrity` and `refuted_basis_stop`.
  - Findings persist only as ENTITY + EVIDENCE + RELATION + EVENT. Entities are validated by `type_registry.schema_json`. Evidence stays `possible`/`hypothesized` with basis provenance. Relations are `derived_from` (hypothesized), or `may_relate`/`reframes`/`stops` (possible). Events are `discovery_run_completed` and `discovery_deferred`.
  - An unknown finding kind is registered as a proposed `entity_type` and deferred until activated through `set_type_status`.
  - Unmet method inputs become a proposed `discovery_input` CAPABILITY plus a `capability_gap` finding. Only a capability that `provides` the input and has a verified activation record satisfies it.
  - The discovery vocabulary is registered through `register_type` → `set_type_status` on the first persisted run, not in `seed_core_types`, so a deploy writes nothing.
  - Endpoints: `GET /forge/substrate/discovery/{methods,preview,findings}` and `POST /forge/substrate/discovery/runs`, private under `FORGE_API_KEY`. The engine is not wired into the scheduled cycle and makes no network calls.
- Proof (`backend/tests/test_discovery_engine.py`, 11 tests):
  - In a world recorded through the canonical services, one run surfaces three things. First, a contradiction on a need that has supported and refuted evidence, citing both evidence ids. Second, a reframed question whose premise that need is. Third, a capability gap for a pre-contract `active` capability with no attributable pass.
  - Every engine output is `possible`/`hypothesized` and cites resolvable rows. The inspected relation's truth is unchanged.
  - An empty substrate yields nothing. Reruns add only the run event.
  - A missing input creates a proposed gap row. An unverified "active" provider does not close it. Building, testing and activating the gap row does close it.
  - A new kind is proposed and deferred, and materializes after activation, with no new table.
  - Fabricated, basis-less and overclaiming findings are rejected, and a crashing plugin is isolated.
  - A measured 2.8x price difference yields an observation and a research question. A shared address across an organization and a need yields a `possible` `may_relate` hypothesis. That relation cannot reach `tested` without evidence. After it is refuted by recorded evidence, the next run emits `reason_to_stop`.
  - An unanswered question with two empty research tasks is reframed. Isolation and recurrence are detected.
  - Methods are replaceable. Preview writes nothing, and the endpoints return 401 without the key when one is set.
  - Mutation checks: disabling finding validation, or counting the engine's own relations as connections, makes the corresponding tests fail.
- Verification (local): backend `pytest` 575 passed, 2 skipped (only the opt-in live GDELT/OpenAlex checks). `git diff --check` is clean. The root app was not touched.
- GitHub Actions (OBSERVED): run `36743983066` on `1b1b63a`. The `backend` job (the required check) succeeded. The `frontend` job failed only at `npm test`, as on every commit since `2b11fb5`, because the root app has no tests. The workflow change needs the `workflow` token scope. The push was accepted with the remote notice `Required status check "backend" is expected.` (admin enforcement is off).
- Current limitation: the engine only proposes. No discovery has been run against production data (by instruction), so nothing about the real production substrate has been discovered yet. The built-in methods cover the recorded substrate only. External comparisons (prices, time series, other markets) need cleared sources declared as input tags and are surfaced as capability gaps until then. Discovery questions are not yet handed to `ResearchQuestion` or the planner automatically.
- Owner action still required: decide whether and when to run `POST /forge/substrate/discovery/runs` against production. This writes discovery rows and registers the discovery vocabulary. Production answered `401` to an unauthenticated `GET /api/forge/substrate/types` on 2026-09-30 (OBSERVED), so `FORGE_API_KEY` is set there and these endpoints are key-gated.
- Next removable dependency: an explicit, reviewed hand-off from discovery `question` entities to `ResearchQuestion` rows, so cleared collectors can gather evidence that advances or refutes them.

## [DONE WITH LIMITATION] Restore the Vercel API/web/cron topology (`vercel.json`)

- Agent: Grok (executor), owner-authorized 2026-09-30 NPT after the Command 1 reconstruction.
- Scope: restore `vercel.json` byte-identical from `bf8546e` (blob `617edb3`); no routing, service, or cron change. Re-enable the two tests that were skipped while it was absent and add `backend/tests/test_vercel_config_contract.py` (file exists; exact services; API rewrite ordered before the web catch-all; cron `/api/scheduled/cycle` at `0 0 * * *` equals `app.main.CRON_SCHEDULE`; `app.main:app` imports and its route table serves the cron path, `/api/health` and representative `/api/public/*` GETs, with negative controls; `/api/health` and `/api/public/feed` answer 200 under `/api` in-process). No cycle is run by these tests.
- Compatibility: no correction needed. The `web` service builds the current root Vite app with `npm run build` (`vite build`, verified); the root `server.ts` Express mock is not part of the Vercel deployment.
- Verification (local): backend `pytest` 564 passed, 2 skipped (only the opt-in live GDELT/OpenAlex checks); config tests fail (6) when `vercel.json` is removed; root `npm ci`, `npm run typecheck`, `npm run build` exit 0.
- Current blocker: production restoration is **not** claimed by this entry; it depends on the Vercel project deploying this commit with its existing environment (database URL, `CRON_SECRET`) and plan. The root app's own `/api/stats`-style calls target a mock contract that the FastAPI API only partly serves.
- Owner action still required: confirm the Vercel deployment and production environment; enable branch protection on `main`.

## [DONE WITH LIMITATION] Command 1 reconstruction: restore the canonical line and enforce the CAPABILITY lifecycle

- Agent: Grok (executor), owner-authorized direct commits to `origin/main`, 2026-09-30 NPT.
- Scope: reconstruct the real state of `main` (see `docs/FEATURE_INVENTORY.md` § Reconstruction — 2026-09-30); restore the canonical backend substrate that `f240f3e` deleted; implement the single highest-value substrate fix found. No new ledger, primitive, table, repo or branch.
- Repository evidence: `f240f3e` deleted all backend Python source/tests, `docs/` (this ledger included), `verification/`, `services/`, `frontend/` source and `vercel.json`; `7a437bb` then committed ~6,950 generated files. Three later commits (`147b821`, `e6a7148`, `6e941b9`) that built a TypeScript in-memory "Hami schema" were pushed and then dropped from `main` by a non-fast-forward move to `7a437bb`. `7a437bb` bytecode reveals four never-committed sources (`procurement_demand.py`, `collectors/ted_procurement.py` and two tests). Production `https://forge-os-ebon.vercel.app/api/*` returns 404 (VERIFIED) because `vercel.json` is gone.
- Gap found and fixed: the CAPABILITY primitive was the only lifecycle not guarded by the `before_flush` write contract. VERIFIED on `bf8546e` code: an ORM insert with `status="active"` and a non-existent `test_ref` committed; assigning `status="active"` to a proposed row committed with zero passing test events; `command="echo ok", exit_code=0` activated a capability. `economic_validation` trusts `status == "active"` as its capability gate, so this allowed an unproven capability to pass that gate.
- Implementation: `f99008d` restores `backend/`, `docs/`, `verification/`, `services/`, `frontend/` source and `docker-compose.yml` byte-identical from `bf8546e` and untracks generated files. The follow-up commit adds `world_graph._set_capability_lifecycle` (proposed→building→tested→active only), write-contract enforcement (new rows start `proposed` without `test_ref`; status/test_ref changes only through lifecycle services; `active` re-checked at flush), required pass provenance (`actor`, git `revision`, command must invoke the test file), `world_graph.capability_activation_record`, API fields `actor`/`revision` on `POST /forge/substrate/capabilities/{id}/test`, and `activation.verified` on capability responses. Failing runs are still recorded without provenance.
- Owner action still required (routine action identified): (1) decide whether to restore `vercel.json` (production API + daily cron) — exact change `git checkout bf8546e -- vercel.json`; (2) enable branch protection on `main` (block force-push, require backend CI); (3) commit the four never-committed source files from the machine that has them; (4) decide whether the root in-memory mock app should call the canonical API.
- Action removed by this change: nobody has to manually audit whether an `active` capability was really tested — non-lifecycle writes fail and each active row reports whether an attributable pass exists.
- Verification: backend `python -m pytest tests -q` (Python 3.12, `DATABASE_URL=sqlite:///:memory:`, `AI_PROVIDER=mock`) → 558 passed, 4 skipped (baseline `bf8546e`: 554 passed, 2 skipped; +6 new contract tests; +2 skips are the `vercel.json` checks, which skip with an explicit reason while the file is absent). The 6 new tests fail against `bf8546e` code. Root app `npx tsc --noEmit` exit 0; `npx vite build` exit 0.
- GitHub Actions (OBSERVED): backend job `success` on `f99008d`, `59face7` and `2b11fb5` (first green backend run since `bf8546e`). Frontend job still fails: before `2b11fb5` in `actions/setup-node` (the root app had no lockfile); from `2b11fb5` only at `npm test`, because the root app from `f240f3e` has no tests. Adjusting `.github/workflows/forgeos-ci.yml` (e.g. `npm test --if-present`) needs a token with the `workflow` scope, which this session did not have.
- Current blocker / limitation: capability test passes are attributable but still caller-attested (the server does not re-run pytest). Existing production rows cannot be inspected (API down, no DB credentials used). `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION`: NOT MEASURABLE (no verified real transactions).
- Next removable dependency: bind capability passes to an independently observable CI result for the recorded revision (GitHub check-run), so attestation is no longer required.

## [PARKED / OUT OF CURRENT PHASE] Hami System-home redesign audit

- Agent: Copilot, read-only audit at the owner's revenue-first scope gate.
- Scope: preserve the System-home redesign for later review; do not continue UI/product-model redesign during the current revenue-first pilot phase.
- Repository evidence: `origin/main` contains `61c4b20` (System home replaces the post/request-board home), `1b537aa` (navigation, route tree, tests, browser QA), `b47d463` (System navigation and regenerated route tree), and `7637cae` (primary navigation aligned to the System model). The aggregate change from local `main` `e37c063` to `origin/main` `7637cae` touched exactly: `docs/CAPABILITY_QUEUE.md`, `docs/amendments/BAC-001-system-as-primary-view.md`, `package.json`, `scripts/qa-system.mjs`, `src/components/layout/site-footer.tsx`, `src/components/layout/site-header.tsx`, `src/components/system/system-editor.tsx`, `src/components/system/system-panels.tsx`, `src/lib/content.test.ts`, `src/lib/content.ts`, `src/lib/system/paths.ts`, `src/lib/system/state.ts`, `src/lib/system/system.test.ts`, `src/lib/system/use-system.ts`, `src/routeTree.gen.ts`, `src/routes/index.tsx`, and `src/routes/system.tsx`.
- Routes/surfaces changed: `/` became the local-first “My System” home; `/system` was added for profile editing; shared header/footer and `NAV` were changed to expose the System/world/providers/research navigation. The visible System state is stored in this browser's `localStorage`, not the backend.
- Reusable code and ideas to preserve: versioned, client-local stated profile parsing in `src/lib/system/state.ts` (client-stored `verified` claims are downgraded to `stated`); explainable possibility-path and evidence-gated progression logic in `src/lib/system/paths.ts`; the editor, panels, route tests, and QA script. The useful future idea is to show a person's stated capabilities/resources alongside clearly-labeled possibilities, unknowns, and next steps. These heuristics do not establish local demand, a match, a customer, income, or a verified capability.
- What remains untouched by these commits: backend routes/services, canonical database models and migrations, public request handling, WorkerTask execution, communications/payment adapters, and the Outcome/Learning writers. No real lead channel, contact workflow, transaction, customer, or revenue evidence was added.
- Owner action still required: conduct and report the owner-led discovery required by the current pilot scope, then choose and authorize a specific pilot path and set N/M. No price, target segment, offer, or external action is chosen by this audit.
- Change boundary: documentation/status only; this entry removes ambiguity about which work is active, not any owner approval, contact, payment, or execution dependency. No System code is reverted, deleted, or extended.
- Current blocker: there is no documented real customer or revenue evidence; the Bot/channel and pilot authorization gates remain open. The Vercel account plan is not currently verified. Local `main` (`e37c063`) is one commit ahead and four behind `origin/main`. The checkout was observed mid-rebase with three UI conflicts at the start of this audit; the reflog later recorded `rebase (abort)` at 2026-09-30 18:33 +0545, without any rebase command from this audit. The conflicts are no longer present. Branch synchronization remains an owner decision.
- Verification: isolated `origin/main` (`7637cae`) passed backend `pytest` (553 passed, 2 skipped), both `npm test` suites (196 script tests + 81 app tests; 277 passed total), `npm run typecheck`, and `npm run build` with `DATABASE_URL` unset so migrations could not touch a database. Isolated local `main` (`e37c063`) passed typecheck and build; its script tests passed (196), but the app tests had one failure (69 passed, 1 failed): `src/lib/content.test.ts` expects `/domain` and `/providers` in primary navigation while `NAV` contains `/discoveries` and `/opportunities`. Production probes used GET requests only; no mutating request, deployment, or infrastructure action occurred.
- Next removable dependency: first complete the owner-controlled discovery/authorization decision; then pick only the smallest technical prerequisite for that authorized pilot. Do not resume the System redesign as part of the current phase.

## [PARKED / OUT OF CURRENT PHASE] Unify UI interactions, titles, and route discovery

- Agent: Copilot, paused user-directed UI task
- Scope: define distinct, accessible interaction patterns for existing semantic button variants and align remaining native action buttons; preserve the diagonal wipe as Hami's primary signature. Use the home hero's sans-serif display face for every page-level heading. Make existing public routes discoverable through grouped navigation and a full public footer sitemap without exposing owner/operator controls in public navigation.
- Repository evidence: `src/components/ui/button.tsx` centralizes primary, secondary, ghost, and warning variants; direct controls also use one-off Tailwind hover styles. `PageHeader` explicitly applied `font-gothic` while Home uses `font-display`. The root header exposed five public routes, while public pages including opportunities, services, about, process, technology, ventures, group, businesses, and contact had no primary navigation path; `/operations` is an owner/operator surface, and `/requests/$id` and `/services/$slug` are contextual detail routes.
- Owner action still required: none for this presentation-only change. Any real-world action behind a button remains subject to its existing authorization and approval flow.
- Change boundary: presentation/navigation only; no route behavior, backend, data, evidence, external communication, spending, or automation changes. This removes manual route hunting; it does not remove any owner approval or action.
- Current blocker: this presentation work is parked by the owner at the revenue-first scope gate. `/operations` and `/actions` remain unlinked from public navigation because no route-level owner identity gate is established; do not expose those controls as public destinations.
- Verification required: typecheck/lint, live-browser checks of semantic button patterns, route-link coverage, page-title consistency, keyboard focus, reduced motion, mobile overflow, and console errors.
- Next removable dependency: establish an existing owner-authenticated route boundary before adding operator destinations to any owner-only navigation.

## [DONE WITH LIMITATION] Make the current Hami app the documented local UI

- Agent: Copilot, current user-directed task
- Scope: align the root local-run documentation with the same root Vite app used by the Hami deployment; preserve the backend and optional legacy Compose dashboard.
- Repository evidence: the root Vite app is the current public app and is configured for port 8080; the Next.js UI under `frontend/` is labeled legacy in README/inventory and is still wired into optional Docker Compose. A root Vite instance was already serving Hami on port 8083 while the legacy Next.js app occupied 8080.
- Owner action still required: start the backend separately when using only `npm run dev`; no separate UI selection is needed after stopping the legacy server and using the root app's standard port.
- Implementation: updated Quick Start to identify `npm run dev` / port 8080 as the current Hami UI, and clearly labeled the port-3000 Compose UI as legacy. Stopped the identified `frontend/` Next.js process and the duplicate root Vite process, then started the root app with `npm run dev` on its configured port 8080. No uncertain source modules or compatibility code were deleted.
- Verification: `http://127.0.0.1:8080/` rendered the Hami home and live local API data; same-origin `/api/health` returned HTTP 200/readiness true; `npm run check:auth` passed. The browser returned HTTP 200 for `/`, `/feed`, `/discoveries`, `/opportunities`, `/operations`, `/domain`, and `/work`, with no console errors or failed requests. A 390px viewport had no horizontal overflow. Local state is separate from production: its counts and recorded cycle differ from haminp.vercel.app.
- Current blocker: the local API reports readiness true, but its most recent recorded cycle is FAILED (id 335, started 2026-09-24 and ended 2026-09-26). No cycle was launched during this UI switch; investigation/recovery must preserve existing evidence and avoid an unapproved external action.
- Next removable dependency: decide whether the legacy Compose dashboard is still needed; do not delete it while Compose still references it.

## [DONE WITH LIMITATION] Run the frontend test suite in CI

- Agent: Copilot, current user-directed audit
- Scope: connect the existing root frontend `npm test` suite to the existing GitHub Actions workflow; do not add test infrastructure or dependencies.
- Repository evidence: `.github/workflows/forgeos-ci.yml` installed Node 22 dependencies, then ran typecheck and build, but omitted the existing `npm test` script.
- Owner action still required: review CI results and authorize any merge or deployment; this change only removes reliance on a separate manual test invocation for PR/push CI.
- Acceptance: the frontend workflow runs `npm test` after `npm ci` and before typecheck/build; the existing suite passes locally; backend authorization and deployment behavior are unchanged.
- Implementation: added `npm test` to the `frontend` CI job.
- Verification: `npm test` → 70 passed, 0 failed; `git diff --check` passes. Backend full suite → 549 passed, 2 skipped; root typecheck and production build pass.
- Current blocker: CI will validate the test suite only after the change is pushed; production remains on the previous deployment until an explicitly authorized release.
- Next removable dependency: after authorized publication, verify the deployed `/api/openapi.json` mirror, which currently still returns 404.

## [DONE WITH LIMITATION] Persist blocked external capability-discovery requirements

- Agent: Copilot, current user-directed task
- Scope: trace existing internal capabilities and exact source clearances; when a research requirement has no eligible route, persist the external capability-discovery requirement and authorization blocker through its existing capability-gap record, Evidence, and idempotent canonical EVENTs; expose the route state on the existing research plan. Do not add a crawler, provider, source, task executor, table, primitive, candidate, or external request.
- Repository evidence: `source_clearance_registry.capabilities_for_requirement` returns only exact, time-current purpose-scoped entries; its existing entries do not include a capability-catalog discovery purpose. `ToolRegistry` and `capability_substrate_adapter` describe locally registered providers/collectors but do not search external catalogs; `CollectorToolAdapter` still requires source clearance and request-time authorization. Existing `ensure_capability_gap` records a gap and possible Evidence but reports only an internal registry lookup, while `build_research_plan` labels an empty route unresolved without naming an external-discovery authorization blocker.
- Owner action still required: review and authorize a specific external catalog/source for the capability-discovery purpose, including its target, permitted operation/fields, and applicable terms. This change removes silent ambiguity about why no candidate is found; it does not remove the source-clearance approval or enable external discovery.
- Acceptance: no-route plans explicitly distinguish external discovery required from authorization-blocked; request/block events and requirement evidence are idempotent and reference the existing ResearchQuestion and capability gap; repeated planning creates no fabricated candidate/provider/source, collection, action, customer, or revenue.
- Implementation: `ensure_capability_gap` now persists `external_discovery` with purpose, blocker, required clearance scope, eligible source IDs, queried catalogs, request count, candidate count, and stable request time on the existing CAPABILITY gap. It records idempotent `state_changed` lifecycle events for `capability_discovery_requested` and `capability_discovery_blocked`, and the existing possible-level gap EVIDENCE explicitly says no external catalog was queried. `research_planner` exposes `capability_route` (`existing_tested_capability`, `existing_untested_capability`, `external_discovery_required`, or `owner_evidence_required`) plus discovery status/blocker. No ResearchTask is scheduled for an unknown/unapproved source, and no candidate is fabricated.
- Verification: focused `cd backend && ../.venv/bin/python -m pytest tests/test_research_capability_routing.py tests/test_capability_discovery.py tests/test_multi_source_orchestration.py -q` → **25 passed**; full `cd backend && ../.venv/bin/python -m pytest tests -q` → **540 passed, 2 skipped**; Problems reports no diagnostics for changed Python files; `git diff --check` passes.
- Isolated in-memory demonstration: an objective about software-problem incidence produced route `external_discovery_required`, status `blocked_by_authorization`, zero eligible candidate sources, zero external requests, zero candidates, and possible-level Evidence referring to the internal clearance check. The canonical event trail contains both requested and blocked lifecycle events. It created **0 Actions, 0 Customers, and 0 Outcomes**. No external catalog was actually discoverable under current permissions; no external candidate or external-source provenance exists to report.
- Current blocker: no repository source clearance or executable catalog adapter is authorized for capability-catalog discovery. No external catalog was queried and no candidate can truthfully be reported.
- Next removable dependency: obtain owner review of a real, documented capability-catalog source and its exact access terms; then add only a source-specific clearance and adapter if authorized.

## [DONE WITH LIMITATION] Rank and persist evidence-backed research capability routes

- Agent: Copilot, current user-directed task
- Scope: extend the existing `capability_discovery` and `research_planner` seams to rank only exact, currently cleared sources that map to an existing `collector_runner` implementation, using observed `SourceUsageEvent`/`ToolUsageEvent` history when present. Persist the selected route and its authorization, evidence, and cost boundaries on the existing ResearchTask and canonical EVENT records; use existing task/usage events to preserve execution results. No source crawling/discovery requests, new models/tables/types, invented providers, truth promotion, or external-action execution.
- Repository evidence: `capability_discovery.active_cleared_sources` already resolves source-registry entries and gates managed candidates; `research_planner.build_research_plan` queries it, but it selects the first route and its task carries only an optional manually-managed candidate id. `collector_runner.COLLECTORS` is the executable route map and `tool_usefulness.source_summary` persists measured usage outcomes, yet planning does not consult that history. Runtime source metadata is declared in the exact clearance registry; costs for those collectors are not recorded.
- Owner action still required: none for local planning/collection within already cleared exact sources beyond the existing request-time source authorization/rate reservation; owner approval remains mandatory for consequential external actions and real-world pilot decisions. This change removes repeated manual route selection/reconstruction where outcome history exists. Remaining: source-specific clearance for any source/purpose not already cleared, and owner-run discovery before a commercial pilot.
- Acceptance: only registered collector implementations with current exact clearance can route; no-history candidates report untested, prior recorded results affect deterministic route ranking, selection records preserve authorization/cost/evidence boundaries, execution outcomes remain in existing usage/task events, repeated planning is idempotent, and metadata cannot become commercial demand.
- Implementation: discovers/ranks the existing, currently cleared source+collector routes using at most 250 recent source-use events; persists them as CAPABILITY records without activating them; records selection rationale and boundaries on ResearchTask and a deterministic canonical EVENT; and enriches existing task lifecycle EVENT projections with the measured usage outcome. Candidate hypotheses remain fallback-only when no eligible route exists. No new model, table, registry type, collector, or external-action path was added.
- Verification: focused capability-routing/discovery/planner suites → **61 passed** before the final candidate-limit and identity-collision guards; complete `cd backend && ../.venv/bin/python -m pytest tests -q` after those changes → **539 passed, 2 skipped**; unapproved-execution checks → **2 passed**; Problems reports no diagnostics for changed Python files; `git diff --check` passes.
- Actual isolated research execution: the cleared Crossref collector completed; **5 Signals** and **5 provenance-bearing Evidence rows** were persisted with registry id `crossref-public-works-metadata` and `metadata_only=true`; evidence support remained `unknown`; **8/8** task lifecycle events were projected, including measured collector usage; no Opportunity, Action, Outcome, or Customer was created. This reached research execution/evidence persistence and canonical lifecycle projection, not supported economic demand or an external action.
- Metric: `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**; there is no verified real transaction.
- Remaining blockers: a commercial demand question needs a source with current permission for that purpose; owner-led customer discovery and validation are still required; any consequential external step remains behind the existing authorization system. External execution capability, customer response, payment, and revenue were not established here.
- Next removable dependency: obtain and record the owner's real discovery findings, then verify whether a specifically cleared source can answer the resulting factual questions. Do not contact prospects or execute external actions without explicit authorization.

## [DONE WITH LIMITATION] Project research-task lifecycle into canonical events

- Agent: Copilot, current user-directed task
- Scope: project existing `ResearchTaskEvent` lifecycle rows as bounded, idempotent `state_changed` WorldEvents attached to their source ResearchQuestion entity. Use the existing `event_type` registry and canonical entity adapter; retain only source IDs, lifecycle labels, timestamps, and a digest of event details. No new table/type/worker/provider, no raw detail copying, no truth transition, action proposal, or execution.
- Repository evidence: `backend/scripts/run_daily_cycle.py::run_once` already runs `forge_loop.run_cycle`, resumes stale tasks, collects up to `FORGEOS_COLLECT_LIMIT` cleared tasks, and runs a conditional post-collection cycle when signals are observed. Existing research planning, provenance-bearing collectors, task events, evidence assessment, and authorization gates are present. `forge_loop.run_cycle` projects ResearchQuestion entities and explicit source relations, but no `ResearchTaskEvent` rows into the canonical EVENT primitive.
- Owner dependency still required: owner review/authorization for any consequential external action and for any real commercial pilot; no real transaction is present. This change removes manual reconstruction of the research-task lifecycle from legacy task-event rows when reading canonical events. Source access remains limited to current exact clearances; external access/terms, owner validation, and authorization still block other activity.
- Verification: `cd backend && ../.venv/bin/python -m pytest tests/test_research_task_event_substrate_adapter.py tests/test_research_question_relation_substrate_adapter.py tests/test_operational_substrate_adapter.py tests/test_grounded_research_loop.py tests/test_research_task_engine.py tests/test_world_graph.py -q` → **50 passed**; complete backend `pytest tests -q` → **534 passed, 2 skipped**; unapproved-execution checks → **2 passed**; Problems reports no diagnostics for changed Python files; `git diff --check` passes.
- Actual isolated research execution: planner routed “What evidence describes repair demand?” to Crossref. The live, currently cleared public metadata collector completed with **5 Signals and 5 persisted Evidence rows**, all carrying registry id `crossref-public-works-metadata` and `metadata_only=true`. The canonical cycle mapped the evidence with `support_level=unknown` and projected **8/8** task lifecycle events for the executed task; no cycle stage errors. This is bibliographic discovery only; it does not establish demand, a customer, a transaction, or a supported commercial claim.
- Implementation: `backend/app/services/research_task_event_substrate_adapter.py` projects at most 250 unprojected task-event rows per cycle into existing `state_changed` WorldEvents, attached to the canonical ResearchQuestion entity. Deterministic event keys make retry/restart idempotent; details are SHA-256 summarized, not copied. The canonical Forge cycle reports projected/unresolved counts. No new table, type-registry entry, ontology, source request path, evidence, truth transition, or action behavior was introduced.
- Status: DONE WITH LIMITATION — a real public-source research task reached persisted, provenance-bearing metadata evidence and canonical event projection; it did not reach supported economic demand or any external action/outcome. Approval-gate regression tests passed, and live execution added **0 Actions** and **0 Outcomes**.
- Metric: `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**; no verified real transaction is recorded.
- Remaining blockers: commercial buyer/demand research needs a current source-specific authorization/clearance that permits that purpose; owner validation and required authorization still block external action. No customer, payment, or revenue evidence exists.
- Next removable dependency: owner-run discovery and explicit reporting of the five real conversations before selecting a pilot; then any additional data collection still requires source-specific permission. Verified real-transaction intervention metrics remain NOT MEASURABLE.

## [DONE WITH LIMITATION] Bounded Hami Cognitive Worker

- Agent: Copilot, current user-directed task
- Claimed at: 2026-09-29T20:40:00+05:45
- Scope: add a replaceable proposal-only cognitive provider seam with a deterministic mock; dispatch bounded tasks through existing `WorkerTask` and `ResearchTask` records; validate proposal shape and evidence references; record provider provenance in the existing research and substrate event primitives. Do not create evidence, actions, new primitives/tables, execute collectors, invoke a paid provider, or change authorization boundaries.
- Verification: focused cognitive/worker/research/substrate suite → **35 passed**; Python `compileall` passed; workspace Problems reports no diagnostics for changed Python files; `git diff --check` passed. The test run made no external provider calls.
- Implementation: `COGNITIVE_PROVIDER=mock` is the default. A replaceable `CognitiveProvider` protocol and deterministic mock are wired through `WorkerTask`; `create_cognitive_task` reuses tasks by idempotency key and references an existing `ResearchTask`. Context is bounded to a 2,000-character objective and at most 10 persisted evidence IDs; outputs are limited to 3 validated `research_follow_up` proposals with `execution_authorized=false`. Successful proposals record hashes and provider mode in an idempotent `WorldEvent` and the existing `ResearchTaskEvent`; they do not mutate research evidence/status or create an `Action`.
- Owner dependency: no real-transaction owner action is removed and no customer/revenue evidence is created. The code only replaces manual drafting of an internal follow-up proposal when explicitly queued. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.
- Remaining blocker: no Gemini adapter, `GEMINI_API_KEY` setting, or Gemini client dependency exists in this repository; the Gemini provider selector therefore fails closed. Attachment archive path inspection found no Cognitive Worker specification file; implementation follows the explicit request scope and repository contracts. No provider call was authorized or attempted.
- Next removable dependency: only after explicit owner authorization for provider/data handling and a credential/config decision, implement and verify an external provider adapter. No authorization, credential, or paid inference was assumed.

## [CLAIMED] Forge Bot bootstrap reconciliation and repository data hygiene

- Agent: Copilot, current user-directed task
- Claimed at: 2026-09-29T08:35:00Z
- Scope: keep DRIVE OWNER DEPENDENCY TO ZERO first; encode the bootstrap constraints; replace the n8n/second-database Bot proposal with a native ForgeOS mapping; keep commercial records evidence-only; prepare the owner-run discovery/baseline and hosting decision memo; remove tracked runtime data, archives, and exported agent context from the current index without rewriting history or deleting local copies. Do not contact prospects, publish an offer, spend money, fabricate evidence, or create a Bot contact architecture before discovery and authorization.
- Acceptance: cite actual ForgeOS worker, event/entity/evidence, booking, and offer behavior; classify infrastructure from production/config evidence; verify production health/feed; ensure artifact paths are ignored and absent from the new index; report unparseable database files and any unresolved historical exposure; run repository verification and record the next real-world dependency.
- Verification: native mapping and scope documents added; 47 tracked runtime/archive/context artifacts removed from the index (working copies retained); ignored paths verified; the runtime autonomy policy already states that an ALLOW verdict alone does not remove an owner action or prove execution. `WorkerTask` has due-time eligibility, conditional claim, and retry, but inspection found no stale-running-task recovery. The current `ea490c9` production deployment is READY. One health request briefly reported `OperationalError`; six later checks through the stable alias all returned HTTP 200, ready, PostgreSQL available, and the public feed returned 200 with 11 items. The last-hour production error-log query returned no matching request logs. The exact pushed-session SHA, CI, and deployment remain to be verified after this commit.
- Status: DONE WITH LIMITATION — this work removes no owner action from a real economic transaction and builds no Bot runtime. There is still no measured lead or transaction. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**.
- Remaining dependency: the owner must conduct and report the five real licensed-agency discovery conversations before selecting fields, channel, cadence, or pilot terms. No software can truthfully substitute for those external conversations or their authorization. After discovery, the next technical prerequisites include consent-scoped contact storage, explicit authorization, and safe stale-task recovery for idempotent handlers.

## [SUPERSEDED] Pulse identity migration and bounded research continuation

- Agent: Copilot, current user-directed task
- Claimed at: 2026-09-29T11:00:19Z
- Scope: the interim Pulse identity pass was superseded by the Hami commercial direction. The bounded research continuation remains implemented; no separate Pulse architecture or product is intended.
- Acceptance: retain the bounded follow-up regression coverage and replace interim Pulse product labels with Hami without changing ForgeOS route, schema, table, primitive, or source-authorization contracts.
- Owner dependency: no routine economic transaction owner action is removed because no real transaction is available to measure. A research follow-up no longer waits for another scheduled batch when capacity remains; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.
- Remaining dependency: relevant evidence and source access are still bounded by existing clearances; no currently available collector establishes buyer willingness to pay. No Pulse domain or deployment is asserted.
- Status: SUPERSEDED BY HAMI.

## [CLAIMED] Hami identity, commercial guardrails, and blocker snapshot

- Agent: Copilot, current user-directed task
- Claimed at: 2026-09-29T11:30:08Z
- Scope: make Hami the active product-facing identity while preserving ForgeOS API paths, persisted data, environment keys, imports, migrations, and the six canonical primitives; put the outcome-first pilot and bootstrap restrictions in the existing project instructions; record the evidenced Nepal demand-to-outcome blocker here. Do not create or publish an offer, contact a person, spend money, simulate a prospect, create customer evidence, or add a parallel architecture.
- Acceptance: active product surfaces identify Hami; domain/DNS/deployment claims remain unverified unless independently checked; no API shape, schema, table, primitive, authorization, or source-clearance behavior changes; focused tests and build/typecheck pass; the ledger records the next external dependency without treating tests as evidence.
- Owner dependency: no routine owner action per real transaction is removed by a brand/instruction migration. There is no verified real transaction from which to calculate `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION`; it remains **NOT MEASURABLE**.
- Remaining dependency: the owner-run five licensed-agency discovery conversations remain necessary before selecting the pilot’s segment, qualification fields, channel, follow-up cadence, or outcome metric. Current public-source clearances do not establish Nepal commercial demand or authorize prospect contact; a public request is only possible demand, not a qualified opportunity or customer. Foreign-employment cases require additional legal/reputation review.
- Reality matrix: **PASS** — one in-place ForgeOS/Hami identity and compatibility boundaries; **PARTIAL** — evidence-grounded research and bounded planning exist, but source coverage does not verify Nepal buyer demand; **BLOCKED** — owner discovery, authorized prospect acquisition/contact, a capable provider and evidence-backed pilot terms, fulfillment, payment verification, and repeatable revenue. No response, outcome, revenue, or $0 commercial result is created by this code change.
- Status: IN PROGRESS.

## [CLAIMED] Owner-dependency invariant and production blocker snapshot

- Agent: Copilot, user-directed current task
- Claimed at: 2026-09-29T07:51:00Z
- Scope: make “DRIVE OWNER DEPENDENCY TO ZERO” the first ForgeOS project rule, reference it in the existing agent instructions, README, and runtime autonomy policy, and refresh the existing prospect-discovery dependency record with current production evidence. Do not add a new domain primitive, authorize an uncleared source, or claim economic autonomy.
- Acceptance: rank the current bottleneck from code and live production evidence; record why no safe in-repository automation removes it yet; document `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` as unmeasurable when there are no verified real transactions; run repository verification, push, verify CI, and confirm the production deployment.
- Verification: `cd backend && ../.venv/bin/python -m pytest tests -q` → **509 passed, 2 skipped**; `npm run typecheck` passed; `npm run build` passed; `git diff --check` clean. Production snapshot and source-authorization blocker are recorded below.
- Status: DONE WITH LIMITATION — the project rule is in place, but no economic owner dependency was removed because the first blocker requires external source authorization and no real opportunity is available to advance. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

## [CLAIMED] Wave 1 — universal substrate hardening and intelligence-path adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T14:17:00Z
- Scope: inspect existing primitives and legacy authority; make type schema validation and activation
  testable through one service; enforce evidence-backed truth transitions; add idempotent canonical
  source identity, explicit uncertainty, merge history support, and database uniqueness; harden the
  existing Signal → Pattern → Belief → Opportunity adapter while preserving source authority and
  provenance. Additive changes only; no new domain or feed/network storage.
- Acceptance: valid/invalid/unknown/proposed/deprecated/malformed type tests; direct truth-state bypass,
  evidence requirement, refuted-state, and provenance tests; duplicate/candidate identity and explicit
  merge-history tests; registry activation/deprecation evidence tests; adapter/source consistency and
  idempotency tests; migration/restart behavior verified without deleting source rows.
- Status: DONE — `backend/tests/test_world_graph.py` and full `backend/tests` suite passed (313 passed, 17 existing deprecation/cycle warnings); additive migrations, source consistency, idempotency, and SQLite reopen/restart checks are covered. Existing `storage/forge.db` was inspected read-only and not altered.

## [CLAIMED] Action → Outcome → LearningEvent operational adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T14:53:56Z
- Scope: expose already-authoritative Action attempts, Outcomes, and LearningEvents as substrate references; treat an Action as an attempt only after authorization and `started_at` are recorded; preserve links through existing `action_id` and `experiment_id` provenance; adapt an authorized `Experiment` attempt only when it has no corresponding `Action` row; avoid duplicate wrappers across those linked source tables; make synchronization idempotent and refresh wrappers from source rows; add auditable event and relation references; invoke both the Signal→Pattern→Belief→Opportunity and Action→Outcome→LearningEvent adapters from the canonical cycle. Keep proposal/approval/denial records in their operational tables without misrepresenting them as attempts. No new domain, table, execution behavior, or independent truth store.
- Authority during this slice: legacy `actions`, `experiments`, `outcomes`, and `learning_events` remain write authority; substrate entities/events/relations are read/query projections. Corrections remain in their source record path and projection updates retain source references.
- Acceptance: pre-start or unauthorized actions are not projected as attempts; approved and started attempts preserve source identity/provenance; Experiment fallback does not duplicate an Action row; explicit and experiment-linked outcome/action relations are reproducible; learning/outcome links require a shared experiment reference and matching data scope; conflicting/ambiguous joins are not guessed; repeated sync creates no duplicates; source edits refresh projection with recorded provenance; restart/repeated-migration tests preserve parity; the canonical cycle runs both adapters and reports their additive changes.
- Status: DONE — `backend/tests/test_operational_substrate_adapter.py` and full `backend/tests` passed (319 passed, 18 existing framework/migration warnings). Verified pre-start and unapproved rows stay out, Experiment fallback is deduplicated against linked Action rows, provenance and unambiguous links persist, repeat sync/restart are idempotent, source refresh emits history, and the canonical Forge cycle runs both registered adapters.

## [CLAIMED] NetworkConnection → substrate relation adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T15:13:58Z
- Scope: inspect the endpoint registry and current public/operator projections; map existing `NetworkConnection` workflow rows to typed substrate entities and `WorldRelation` references where endpoint and relation types are active; preserve source IDs, epistemic state, evidence/provenance links, validity window, direction, and workflow record history; make the refresh idempotent through database keys; keep the operational workflow row as the migration-stage write authority and use `relation_id` only as its link to the substrate relation. Keep public visibility gates. Do not create a Network entity store or Feed storage.
- Acceptance: repeated sync creates no duplicate wrappers/relations; unknown endpoints or unactivated relation types remain explicit and are not guessed/activated; source provenance and evidence references survive; source-to-substrate consistency and restart/repeated-migration tests pass; canonical cycles run the adapter; Feed/Network continue to resolve public context through existing visibility rules and typed substrate relations.
- Status: DONE — `backend/tests/test_network_substrate_adapter.py`, `backend/tests/test_public_feed.py`, and full `backend/tests` passed (325 passed, 18 existing warnings). Verified active-type gating, explicit endpoint resolution, nested connection traversal, evidence/provenance snapshots, source state retained pending substrate evidence, Feed relation pointers under public visibility gates, canonical cycle integration, and SQLite reopen/repeat idempotency.

## [CLAIMED] Public Feed provenance closure over substrate projections

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T15:32:43Z
- Scope: audit every public Feed item builder for explicit identity and provenance paths; attach typed references to substrate entity/relation/event records and evidence where those projections exist, using registered legacy adapters during migration. Keep Feed read-only, preserve public visibility rules, and never expose private evidence content or add feed storage.
- Authority during this slice: source rows and registered adapters remain migration-stage authority; Feed is a deterministic read projection with references back to each source row plus available substrate and evidence records.
- Acceptance: table-driven coverage for Feed item types and trace references; evidence references retain their `EvidenceRelationship` provenance; items without eligible evidence still identify their source record and registered source; hidden/private nodes/evidence do not leak through traversal; repeated reads write nothing; full backend test suite passes.
- Status: DONE — `backend/tests/test_public_feed.py` and full `backend/tests` passed (325 passed, 18 existing warnings). Every item retains its source identity; existing substrate entity/event and evidence references are attached where available. Reads do not create substrate/feed rows, evidence content stays private, and hidden-connection evidence is excluded.

## [CLAIMED] Substrate-first Network traversal with legacy workflow adapters

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T15:38:57Z
- Scope: make public and operator Network read paths resolve graph topology, relation type, direction, and epistemic state from the linked substrate `WorldRelation` when projected. Keep the existing `NetworkConnection` row authoritative for workflow status, response, payment, and visibility; use its explicit endpoint adapter as migration fallback when no substrate relation exists. Expose both source endpoint refs and substrate entity refs; never write a second Network store.
- Authority during this slice: the substrate relation is graph/read authority after successful projection; the legacy connection remains workflow authority and provides a registered endpoint/source adapter during migration.
- Acceptance: API tests cover substrate-first graph fields, deferred truth state, unprojected legacy fallback, endpoint/provenance references, and visibility; existing mutations continue to update only the operational row; full backend suite passes.
- Status: DONE — focused Network/Feed/operator API tests and full `backend/tests` passed (327 passed, 18 existing warnings). Public/operator graph reads now use substrate relation type, direction, endpoints, and truth when present; operational workflow fields remain on `NetworkConnection`; legacy fallback is explicit; public connection traversal reuses Feed endpoint visibility.

## [CLAIMED] General substrate Network traversal projection

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T15:47:06Z
- Scope: audit the existing Network read surface for non-`NetworkConnection` substrate relations. Add a read-only traversal projection over public substrate entities, relations, events, and evidence, while including only explicitly registered legacy adapters during migration. Reuse Feed visibility references; do not add storage, copy entity payloads, or introduce a new business domain/frontend.
- Authority during this slice: `entities`, `relations`, `events`, and existing `evidence` are graph/read authority; the Feed remains the public visibility projection; legacy endpoint records remain their registered migration adapters.
- Acceptance: public traversal includes eligible Signal→Pattern→Belief→Opportunity substrate edges and projected NetworkConnection edges; excludes private/dangling nodes and edges; exposes typed source/evidence/event refs without duplicating source payload; unprojected visible connections remain explicit adapter edges; reads write no rows; full backend suite passes.
- Status: DONE — `backend/tests/test_public_network.py` and full `backend/tests` passed (329 passed, 18 existing warnings). `/public/network` traverses visible substrate relations and explicitly registered unprojected NetworkConnection adapters, returns evidence/event references, excludes private mapped edges even when both endpoints are public, and writes no graph/feed rows.

## [CLAIMED] Additive Evidence idempotency for new writes

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T15:55:14Z
- Scope: add nullable database idempotency keys to existing Evidence and EvidenceRelationship records, enforce uniqueness only for new keyed writes, and route the provenance-based evidence/relationship services through those keys. Keep all historical rows intact; do not make legacy `provenance_hash` unique or deduplicate existing evidence.
- Authority during this slice: existing `evidence` and `evidence_relationships` remain the evidence/provenance source of truth; the new key columns only protect retries for writes that opt into idempotency.
- Acceptance: repeated keyed evidence and link writes return the original rows; conflicting key reuse fails explicitly; DB uniqueness prevents duplicates; migration preserves rows including duplicate historical provenance hashes; restart/migration and full backend suite pass.
- Status: DONE — focused Evidence/service/migration tests and full `backend/tests` passed (331 passed, 18 existing warnings). New Evidence and EvidenceRelationship keys are nullable and unique; same-key retries return the original record, mismatched Evidence payloads fail, and migration tests preserve duplicate legacy provenance hashes and relation keys unchanged.

## [CLAIMED] Deterministic legacy Evidence writer coverage

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:03:05Z
- Scope: audit the remaining deterministic Evidence producers (`observer_engine`, `reality_memory`, `scenario_engine`, and `opportunity_engine`) and assign stable idempotency keys that match their existing source/pair identity. Preserve distinct raw observations and source rows; do not force uniqueness on legacy provenance hashes or content.
- Authority during this slice: existing Evidence rows remain authoritative. Each producer's current domain/source keys define retry identity; idempotency keys only prevent duplicate writes for the same intent.
- Acceptance: repeated producer runs retain one row per intent; distinct source/subject pairs remain separate; overlapping Opportunity evidence paths do not collide; existing provenance values/history remain; full backend suite passes.
- Status: DONE — focused producer tests and full `backend/tests` passed (333 passed, 18 existing framework/migration warnings). Observer, Reality Memory, Scenario Engine, and all four Opportunity evidence paths now assign stable keys based on existing provenance/source/subject identity. Tests verify repeat behavior and distinct observations/subjects remain separate; legacy provenance hashes and historical Evidence rows stay unchanged.

## [CLAIMED] Public Provider and ServiceListing substrate adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:08:05Z
- Scope: adapt the existing `Provider` and `ServiceListing` rows into canonical substrate entity wrappers, and represent the existing listing-to-provider ownership as an idempotent typed relation. Preserve source IDs, current verification/visibility/workflow authority, data provenance, and source-to-substrate parity. Keep adapters additive and read-only with respect to existing rows; do not add marketplace behavior, UI, or tables.
- Authority during this slice: `public_providers` and `public_service_listings` remain authoritative for provider identity claims, listing content, verification, visibility, bookings, and pricing. `entities` and `relations` are substrate projections that reference those rows without copying their payloads; the Feed remains a read projection.
- Acceptance: inactive/private rows are projected without becoming public; repeated sync and reopen are idempotent; each substrate entity retains an explicit source reference; `offered_by` relations are supported only when the registered type is active and endpoints exist; source edits refresh wrappers with audit events; tests compare source and substrate identities while preserving every source row; full backend test suite passes.
- Status: DONE — focused Provider/ServiceListing, Feed, Network, and canonical-cycle tests plus full `backend/tests` passed (337 passed, 18 existing framework/migration warnings). Source-linked Provider and ServiceListing entities, hypothesized `offered_by` relations, provenance evidence, and digest-only refresh events are idempotent across restart. Existing rows and visibility/verification fields remain authoritative; private listings remain absent from public projections.

## [CLAIMED] Runtime ToolRegistry → substrate Capability adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:17:19Z
- Scope: adapt the existing runtime `ToolRegistry` definitions into the existing substrate `capabilities` primitive. Preserve stable source identity and a digest-only change history, keep registry definitions as runtime authority, and keep substrate capability lifecycle at `proposed` until the canonical build/test/activation process is satisfied. Do not execute tools, invoke external providers, add a table, or create a business-domain feature.
- Authority during this slice: `ToolRegistry` owns which implementations can be selected and their declared runtime metadata. The substrate `ForgeCapability` rows are auditable, idempotent projections and lifecycle records; runtime availability does not automatically activate a substrate capability.
- Acceptance: repeat sync/restart creates no duplicate capability or history; changed definitions refresh source metadata without skipping lifecycle state; all mirrored capabilities start proposed; no adapter code calls `execute`; canonical Forge cycle runs the adapter; full backend suite passes.
- Status: DONE — adapter, lifecycle-preservation, restart, and canonical-cycle tests plus full `backend/tests` passed (340 passed, 18 existing framework/migration warnings). Default runtime tool metadata mirrors to the existing Capability primitive, changes produce digest-only history, existing capability states survive refresh, new rows remain proposed, and no tool availability check or execution is triggered.

## [CLAIMED] Generic Universal Substrate API surface

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:22:47Z
- Scope: expose the existing canonical substrate services through a focused `/forge/substrate` API for registry types, entities, relations, evidence, and capabilities. Route all writes through the existing validated/authorized services; expose explicit status transition paths; keep reads as projections and preserve the current optional API-key middleware. No domain-specific endpoints, new storage, feed/network persistence, or parallel validation/state-transition logic.
- Authority during this slice: the type registry and substrate services remain the only generic mutation authority. Legacy adapters continue to own their source rows. This API is a transport boundary only.
- Acceptance: API tests cover type proposal/activation/deprecation, entity insertion and source identity, relation truth transition/evidence gates, evidence insertion, capability lifecycle, idempotency/error responses, and read behavior; writes reach the canonical services; full backend test suite passes.
- Status: DONE — focused API and authorization tests plus full `backend/tests` passed (345 passed, 18 existing framework/migration warnings). `/forge/substrate` now exposes types, entities, relations, events, evidence, and capabilities through the canonical services; type/truth/identity/capability lifecycles remain enforced. Optional `FORGE_API_KEY` gates both substrate reads and writes. Repeated source identities and same-intent writes are idempotent; mismatched relation/evidence keys return conflicts.

## [CLAIMED] Remaining canonical legacy record adapters

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:33:10Z
- Scope: add non-destructive, source-identity projections for existing `Claim`, `ResearchQuestion`, `DomainRecord`, and `Decision` rows that are not yet registered in the canonical Forge cycle. Use only existing canonical adapters, preserve source IDs, and add digest-only refresh events for safe source lifecycle fields. Do not infer relationships from similar text or claim a Decision is an executed Action; add typed relations only when an existing foreign key and active relation type make the semantics explicit.
- Authority during this slice: the existing four legacy tables retain all write authority and source payloads. Substrate entities are reference wrappers; source status and data stay authoritative until a named future cutover. Feed visibility remains the public gate.
- Repository evidence: read-only inspection of `storage/forge.db` found 33 Claims, 89 ResearchQuestions, 1 DomainRecord, and 10 Decisions; the existing canonical adapter registry recognizes these types, but the cycle currently syncs only the intelligence path, action/outcome/learning path, NetworkConnection, Provider/ServiceListing, and runtime ToolRegistry.
- Acceptance: every adapted source row has one stable substrate identity; no source payload or decision claim is rewritten; repeat sync/restart is idempotent; source changes leave digest-only audit events; public Feed references remain subject to existing gates; full backend suite passes.

- Status: DONE — `backend/tests/test_legacy_record_substrate_adapter.py`, canonical-cycle coverage, and full `backend/tests` passed (347 passed, 18 existing warnings). Claim, ResearchQuestion, DomainRecord, and Decision now have stable source-linked entity wrappers with digest-only refresh events; retries/restart are idempotent, no relations are guessed, Decision is not recast as an Action, and source payloads remain authoritative.

## [CLAIMED] Historical Evidence substrate adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:43:10Z
- Scope: expose existing Evidence rows through the canonical Evidence primitive without deleting, deduplicating, rewriting, or rescaling legacy fields. Resolve each legacy row's explicit Belief, ScenarioPrediction, Opportunity, or Signal target to an existing canonical entity; preserve its source/provenance and raw observation; record substrate mapping in additive nullable fields and through the canonical evidence service. Use bounded, idempotent batches in the Forge cycle, report unresolved rows, and keep target truth states unchanged. Preserve existing EvidenceRelationship claim links and Feed visibility.
- Authority during this slice: legacy Evidence and its explicit foreign keys/content/direction/confidence/provenance remain the raw-evidence authority. The substrate Evidence view is an additive mapping on the same row; no duplicate evidence store or independent truth is introduced. Legacy 0–100 confidence remains untouched and is not treated as substrate 0–1 confidence.
- Repository evidence: read-only inspection of `storage/forge.db` found 39,290 Evidence rows; all have a Signal, with mutually exclusive Belief (37,239), ScenarioPrediction (1,975), Opportunity (3), or Signal-only targets. 73 have no higher target than Signal, and 3 raw `source` values are null although their linked Signal has a source. Existing `EvidenceRelationship` claim links and raw evidence/provenance fields must remain intact.
- Acceptance: bounded repeat/restart sync is idempotent and creates no Evidence duplicates; every mapped subject resolves through canonical identity; direction, raw content, source, provenance, and historic confidence remain unchanged; source-null rows retain an explicit source reference when available; unsupported/missing targets are reported unresolved without guessed joins or target-state mutation; Feed/API projections retain evidence provenance and access gates; additive migration and full backend suite pass.

- Status: DONE — `backend/tests/test_legacy_evidence_substrate_adapter.py`, substrate API/world graph coverage, restart and additive migration checks, and full `backend/tests` passed (351 passed, 19 existing warnings). Historical rows map incrementally (500 per cycle by default, maximum 2,000) onto canonical Belief, ScenarioPrediction, Opportunity, or Signal entities in the same Evidence rows. Legacy content/source/direction/provenance/0–100 confidence and explicit FKs remain unchanged; substrate truth stays `unknown`; ambiguous/incomplete rows remain unresolved; restart creates no duplicate Evidence rows.

## [CLAIMED] Explicit EvidenceRelationship → substrate relation adapter

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T16:55:12Z
- Scope: project only explicit `EvidenceRelationship` foreign-key links into canonical WorldRelations, beginning with the repository's current legacy population of Evidence → Claim `derived_from` links. Use a minimal source-linked `evidence_record` Entity wrapper as the graph vertex, the existing Claim adapter as the other endpoint, and the same Evidence row as the provenance source. Keep source relation type and direction, require an active registered type, add a nullable back-reference to the existing relationship row, and make synchronization bounded/idempotent. Never infer links from `relation_key`, never create a duplicate Evidence row, and never advance target truth based on this adapter.
- Authority during this slice: `evidence_relationships` remains authoritative for its explicit endpoints and source relation type; Evidence remains raw evidence authority; the WorldRelation and evidence-record Entity are graph projections carrying source IDs/digests. Existing Feed and public visibility rules remain authoritative.
- Repository evidence: read-only inspection of `storage/forge.db` found 51 `EvidenceRelationship` rows, all with an explicit `claim_id` and `relation_type='derived_from'`; the physical legacy table has no substrate relation back-reference yet. The row's `evidence_id` is an explicit path to preserved raw evidence.
- Acceptance: explicit Claim links produce one substrate relation with source-linked endpoints and evidence provenance; unsupported/missing/ambiguous targets remain unresolved; no source payload or Claim state is rewritten; repeated sync/restart does not duplicate entities/relations or Evidence; source row points to the projected relation; visibility remains unchanged; migration and full backend suite pass.

- Status: DONE — `backend/tests/test_evidence_relationship_substrate_adapter.py`, canonical-cycle integration, legacy Evidence migration tests, and full `backend/tests` passed (355 passed, 21 existing warnings). Explicit `EvidenceRelationship` rows now project to idempotent, directed, hypothesized WorldRelations between source-linked `evidence_record` and Claim entities. A unique nullable `substrate_relation_id` preserves the back-reference; unsupported types and ambiguous endpoints stay unresolved; Claims and Evidence remain unchanged.

## [CLAIMED] Explicit ResearchQuestion source relations

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T17:00:16Z
- Scope: project only the existing `ResearchQuestion.source_pattern_id`, `.source_belief_id`, and `.source_claim_id` foreign keys as directed `derived_from` WorldRelations from the canonical ResearchQuestion entity to the referenced canonical source entity. Record the source field/table/id in relation attributes and use deterministic idempotency keys. Never infer links from question text, change source rows, or advance target truth. Leave unsupported/unregistered source kinds unresolved.
- Authority during this slice: `research_questions` owns question content/status and explicit source fields; registered WorldRelations are graph projections only. Feed visibility remains its existing gate.
- Repository evidence: read-only inspection of `storage/forge.db` found 89 ResearchQuestions: 23 with `source_pattern_id`, 52 with `source_belief_id`, and none with `source_claim_id` or `source_rare_signal_id`. These explicit relationships are not currently projected by the legacy record adapter.
- Acceptance: supported explicit FKs map to one directed typed relation with full provenance; missing/ambiguous/inactive sources remain unresolved; repeat sync/restart creates no duplicates; no question/Claim/Belief state or source payload changes; Feed/Network visibility stays intact; full backend suite passes.
- Status: DONE — `cd backend && ../.venv/bin/python -m pytest tests/test_research_question_relation_substrate_adapter.py -q` → 4 passed. `cd backend && ../.venv/bin/python -m pytest tests -q` → 364 passed, 21 warnings. The explicit-FK adapter creates directed, hypothesized `derived_from` relations only for registered source fields; missing sources and a deprecated relation type remain unresolved, text similarity creates no relation, and restart retries create no duplicates. The adapter is called from the canonical Forge cycle; no source rows or target truth were changed.

## [CLAIMED] Preserve failures in market-signal substrate projection

- Agent: Copilot, user-directed current task
- Claimed at: 2026-09-27T07:00:00Z
- Scope: narrow the market-signal adapter's broad exception handler to expected substrate conflicts so programming, database, and infrastructure failures are not silently reclassified as unresolved data. Keep expected `SubstrateError` handling nonfatal and preserve subsequent cycle behavior for known source conflicts. No schema changes.
- Acceptance: expected substrate conflicts increment `unresolved_signals`; unexpected exceptions propagate; normal projection/idempotency tests and the full backend suite pass.
- Status: DONE — `cd backend && ../.venv/bin/python -m pytest tests/test_wave2_market_signal_domain.py -q` → 3 passed. `cd backend && ../.venv/bin/python -m pytest tests -q` → 366 passed, 21 warnings. Known `SubstrateError` identity conflicts remain counted as unresolved; unexpected runtime errors propagate. No schema change. Live checks during this slice: frontend `/` → HTTP 200; backend `/health` → HTTP 200. `git diff --check` → clean.

## [CLAIMED] Wave 2 — generic market signal substrate projection

- Agent: Codex, current task (serial implementation)
- Claimed at: 2026-09-25T17:08:00Z
- Scope: add market-signal vocabulary to the existing universal type registry, map raw `signals` rows into a typed `market_signal` substrate entity, attach the source `signals` relation and market-signal observation event, and write a single supporting evidence row without creating a new domain table or independent storage. Use the existing `signals` table as the authority while the substrate layer remains a read/projection boundary, preserving `Signal` payloads and provenance.
- Authority during this slice: `signals` remains the write authority and every market-signal wrapper keeps an explicit `source_system`/`source_id` reference to the original row. The substrate entity, relation, event, and evidence are additive graph projections only, and all ids are deterministic for retry-safe sync.
- Acceptance: `world_graph.seed_core_types()` includes `market_signal`, `market_segment`, `signals`, `tracks`, `responds_to`, and the `market_signal_observed` event type; raw signals create one wrapper entity per source row, one `signals` relation, one typed observation event, and one `hypothesized` evidence item; repeated sync is idempotent; the canonical Forge cycle includes the adapter in the substrate summary; the backend suite passes under the repo virtual environment with no destructive schema changes.
- Status: DONE — the new adapter is implemented in `backend/app/services/market_signal_substrate_adapter.py`, registered in the Forge cycle, and verified by the focused regression tests plus the backend suite.

## [CLAIMED] Advance bounded market-signal projection batches

- Agent: Copilot, user-directed current task
- Claimed at: 2026-09-27T07:05:00Z
- Scope: prevent the registered market-signal adapter from retrying only the lowest-ID batch forever. Select the next unprojected source rows in bounded batches using the existing source-linked market-signal entity identity; preserve exact retry behavior and source table authority. No cursor table or schema changes.
- Acceptance: repeated calls with a fixed limit project every source Signal exactly once across batches; subsequent calls do not duplicate entities, relations, events, or evidence; existing adapter and full backend tests pass.
- Status: DONE — `cd backend && ../.venv/bin/python -m pytest tests/test_wave2_market_signal_domain.py -q` → 4 passed. `cd backend && ../.venv/bin/python -m pytest tests -q` → 367 passed, 21 warnings. Repeated limit-2 sync calls projected three Signals in batches of 2, 1, then 0 without duplicates. Frontend `/` and backend `/health` both returned HTTP 200; `git diff --check` was clean. No schema change.

## [CLAIMED] Enable source-grounded general research with honest completion state

- Agent: Copilot, user-directed current task
- Claimed at: 2026-09-27T13:03:00Z
- Scope: trace and correct `/analyze` task/result status; replace planner defaults that point only to uncleared feeds with general-purpose, permissioned source strategies; persist subquestions, prior public observations, unknowns, assumptions, source status, and restart-safe follow-up tasks in the existing ResearchQuestion/ResearchTask/Evidence/Signal path. Add a no-key Crossref public metadata API adapter using only fields safe for reuse (never abstracts), current policy validation, persistent rate limiting, source timestamps/provenance, and recoverable deferrals. Preserve the expired GovInfo clearance and do not create unsupported claims/opportunities.
- Source review evidence: Crossref REST API docs state public access requires no signup and metadata may be reused while some abstracts may be copyrighted; access docs state the public pool is rate limited. Its `/robots.txt` returned 404; the integration uses only the documented `/works` API, not site crawling. Initial live requests exposed an unsupported `updated` select field (HTTP 400); removing it fixed the request.
- Acceptance: unfamiliar, unrelated questions produce reusable source plans/subquestions; actual API records persist with DOI/URL, retrieval/publication timestamps and source provenance; no abstract is stored; no result is called complete when incomplete/empty; rate-limit deferrals do not consume retry attempts; retry/restart is idempotent; exact-token overlap and publication age are explicit; focused + full backend tests and local HTTP/runtime checks pass.
- Verified on 2026-09-27: live `/works` retrieval returned five records for each of two unrelated questions (Nepal postharvest loss; bicycle-repair appointment reminders). The five records per query were written through `collector_runner` into separate temporary SQLite databases, then remained queryable after closing and reopening each database. DOI URLs, publication/retrieval times, and metadata-only provenance were present; abstracts were not requested or persisted. These records were discovery leads only; the appointment query returned mostly hospital reminder studies and unrelated matches, so relevance remains explicitly unassessed.
- Verification: final `cd backend && ../.venv/bin/python -m pytest tests -q` → 383 passed, 22 warnings; `cd frontend && npx tsc --noEmit` → passed; `cd frontend && npm run build` → passed; `git diff --check` → clean. Local `/health` and `/analyze` returned HTTP 200; browser confirmed the styled page and all checked CSS/JS assets return HTTP 200 at 390px with no horizontal overflow.
- Status: BUILDING — exact-token overlap and publication age are reported transparently, but source reliability, semantic relevance, contradiction assessment, broad public web search, economic validation, and a real-world response are not. Crossref metadata alone does not validate a market opportunity. The only other runtime web clearance is expired GovInfo; Reddit, GitHub, RSS, arXiv, and general direct web search remain blocked.
- Next capability: inspect actual source content using a fresh, bounded permission review, then assess reliability, contradictions, and relevance from the retrieved material. No opportunity, customer, experiment execution, or revenue is claimed from this milestone.

## [CLAIMED] Vercel FastAPI ingress ownership and verification

- Agent: GitHub Copilot, user-directed current task
- Claimed at: 2026-09-25T18:21:46Z
- Scope: make the existing FastAPI app the single owner of `/api` aliasing; remove the duplicate Vercel service-level path-strip rule and the unreferenced `vercel_asgi` wrapper after proving its only use is obsolete. Preserve all API handlers, response contracts, service routing, and source/data authority. Pin the API service to the documented FastAPI framework and entrypoint.
- Authority: `backend/app/main.py` owns direct and `/api`-prefixed HTTP aliases; the Vercel top-level rewrite selects the API service and passes the original path. Existing FastAPI routers/services remain the sole implementation.
- Acceptance: the Vercel configuration parses with the API rooted at `backend/`, framework `fastapi`, and entrypoint `app.main:app`; local cold-start checks return 200 for `/health`, `/api/health`, `/public/feed`, and `/api/public/feed`; public-feed tests/build pass; deployment health and feed smoke return JSON/200 before status is DONE.
- Status: CODE COMPLETE, PRODUCTION BLOCKED — verification evidence (2026-09-26, macOS/Python 3.13): `cd backend && ../.venv/bin/python -m pytest tests/test_public_feed.py -q` → 10 passed; `cd backend && ../.venv/bin/python -m pytest -q` → 362 passed, 21 warnings; `npm run typecheck && npm run build` → passed; `git diff --check` → clean. A `VERCEL=1` cold-start `TestClient` check with an isolated `/tmp` SQLite URL returned 200 for `/health`, `/api/health`, `/public/feed?limit=1`, and `/api/public/feed?limit=1`. Live production probes on 2026-09-26 still return HTTP 500. Deployment and owner-only function logs are unavailable in this session. Do not mark DONE until production `/api/health` and `/api/public/feed` return JSON successfully.

## [CLAIMED] Reject conflicting substrate source-identity retries

- Agent: Copilot, user-directed current task
- Claimed at: 2026-09-27T06:43:00Z
- Scope: make `world_graph.create_entity` reject reuse of an existing stable source identity when the identity-bound entity payload or provenance differs. Preserve exact retries as idempotent and leave source refreshes to registered canonical adapters. No schema/table changes and no fuzzy matching.
- Acceptance: exact repeat returns the original entity; conflicting payload/provenance raises `SubstrateError` without mutating the original; canonical adapters can still refresh their source-linked projections; focused and full backend tests pass.
- Status: DONE — reproduced three silently accepted source-identity conflicts before the fix. `world_graph.create_entity` now returns the original only for identical payload/provenance and raises an explicit conflict for changed name, attributes, canonical identifier, normalized identity, uncertainty, or provenance. Registered adapter refreshes remain separate. `pytest backend/tests/test_world_graph.py backend/tests/test_substrate_api.py backend/tests/test_public_services_substrate_adapter.py backend/tests/test_wave2_market_signal_domain.py -q` → 23 passed; the HTTP identity/lifecycle test → 1 passed; full `pytest backend/tests -q` → 363 passed, 21 warnings. No migration required.

## [CLAIMED] Reject conflicting substrate event retries

- Agent: Copilot, user-directed current task
- Claimed at: 2026-09-27T06:46:00Z
- Scope: make keyed `world_graph.create_event` retries reject changes to source/provenance and to an explicitly supplied occurrence timestamp while retaining idempotency for exact retries and retries that omit the generated timestamp. No schema/table changes.
- Acceptance: same key + same intent returns original; changed source, payload, target, or explicit timestamp conflicts; existing adapters remain idempotent; focused and full backend tests pass.
- Status: DONE — `cd backend && ../.venv/bin/python -m pytest tests/test_world_graph.py::test_event_idempotency_rejects_provenance_and_timestamp_conflicts tests/test_substrate_api.py::test_event_and_capability_api_enforce_lifecycle_and_idempotency -q` → 2 passed. `cd backend && ../.venv/bin/python -m pytest tests -q` → 364 passed, 21 warnings. Exact retries return the stored event; changed source or explicitly supplied occurrence time conflict; retries omitting generated time remain idempotent. `git diff --check` → clean; no migration required.

## [CLAIMED] Requirement-grounded research tasks and evidence gate

- Agent: Copilot, current task (serial implementation)
- Scope: persist per-question evidence requirements and scoped source capabilities on existing research records; distinguish bibliographic discovery from claim support; generate bounded/idempotent follow-ups; preserve contradiction/provenance state; prevent concurrent task claims; block metadata-only or unattributed evidence from creating an opportunity or experiment proposal. Do not introduce a new research table, source permission, or seventh substrate primitive.
- Status: IMPLEMENTED AND VERIFIED TO THE CURRENT AUTHORIZATION BOUNDARY — requirement plans cover publication leads, incidence, alternatives/costs, disconfirmation, and willingness to pay. Crossref is usable only for metadata discovery; expired GovInfo and other uncleared sources remain inactive. Opportunity-from-pattern requires attributable persisted evidence and rejects metadata-only inputs; experiment proposals require every requirement explicitly evidence-grounded.
- Evidence: focused research/evidence/opportunity suite → 107 passed, 10 warnings; full backend suite → 396 passed, 22 warnings; root typecheck and frontend `npx tsc --noEmit` passed; production build passed in the isolated output directory; `git diff --check` clean. Fresh isolated live `/analyze` and `/health` returned HTTP 200. The unfamiliar produce-transport question persisted five Crossref Evidence records and five external Signals; only bibliographic discovery became satisfied, and the other four requirements stayed terminal-unresolved. SQLite/API restart preserved the question plan, two tasks, five evidence rows, and six signals. Browser Analyze UI rendered; mobile width 390px had no overflow or page errors.
- Remaining blocker: World Bank structured statistics now cover bounded macro baselines only. There is still no authorized source that establishes customer pain, local incidence/demand, alternatives/prices, disconfirmation, or buyer response. The loop does not treat macro data as a commercial opportunity. Next: obtain a reviewed source capability for the specific unresolved micro-level evidence requirements.

## [BLOCKED] Semantic Scholar substantive abstract source

- Requested capability: add a bounded Semantic Scholar paper-search collector using explicitly selected API fields, persistent one-request-per-second pacing, 429 backoff, attributable evidence, and requirement-scoped evidence assessment.
- Inspection: official API license (`https://www.semanticscholar.org/product/api/license`) says S2 Data is subject to accompanying data licenses and underlying third-party content licenses, and requires Semantic Scholar attribution. The requested API response fields do not expose a per-item abstract license. The public API page recommends API-key use; the runtime environment has no `SEMANTIC_SCHOLAR_API_KEY`.
- Live check: one request to `https://api.semanticscholar.org/graph/v1/paper/search` for “appointment scheduling algorithm” → HTTP 429. No retry was made; no abstract was retained.
- Status: BLOCKED before collector implementation or source registration. Treating this as cleared would overstate content rights and ignore a live provider throttle. Semantic Scholar remains a documented candidate in `docs/PUBLIC_SOURCES.md`, not an active source capability.
- Required unblock: provide/obtain permitted authenticated access or provider-approved retry conditions, and establish the applicable per-record abstract license plus compatibility with storage/use in ForgeOS. Then record attribution and policy evidence, add a dated exact-endpoint clearance, and test the collector and evidence gates. Do not mark `problem_incidence` or `alternatives_and_costs` answerable until this passes.

## [DONE] World Bank Indicators API v2 macro evidence

- Scope: add the World Bank Indicators API v2 as a bounded, read-only structured source through the existing clearance registry, collector runner, Signal, and Evidence path. No new table or substrate primitive.
- Clearance: exact HTTPS API root, metadata/observation path constraints, explicit allowed response fields, policy recheck, 21-year maximum span, exact country/indicator validation, provenance/attribution requirements, dated clearance, and database-backed minimum one-second pacing per API request. World Bank Data Catalog licensing states CC BY 4.0 is the default for World Bank-produced open datasets while also documenting other/external licenses; the indicator API does not return an item-specific license. Provenance preserves that limitation and flags listed third-party source organizations.
- Epistemic boundary: only matched `macro_demographics`, `population_baseline`, and `economic_indicator` requirements may be satisfied, and any listed third-party source must have explicitly verified compatible license terms. Macro observations cannot support micro demand, customer pain/incidence, alternatives/prices, or buyer willingness to pay. Planner terminal reasons explicitly preserve those unresolved needs.
- Live evidence: isolated HTTPS query `NPL / SP.POP.TOTL / 2022` stored one Evidence and one Signal, with value `29,715,436`, canonical API URL, WDI/World Bank attribution, third-party organizations listed (UN, NSOs, Eurostat), and `third_party_sources_indicated: true`. Restart/reopen retained both records.
- Verification: focused collector **7 passed**; research/provenance regressions **34 passed**; complete backend **403 passed, 22 warnings**; local `/health` and frontend `/` HTTP 200; `git diff --check` clean.
- Limit: the observation is a national macro demographic statistic, not evidence of customer demand, local pain, or commercial viability. Per-indicator license is not supplied by the API and is not claimed.

## [DONE WITH LIMITATION] World Bank third-party reuse gate

- Scope: prevent World Bank observations that name external/source organizations from clearing commercial research requirements without verified compatible reuse terms.
- Implementation: collector provenance now records `license_status: "unconfirmed_third_party"` and `license_compatibility_verified: false` for such records. The planner requires explicit verified CC BY 4.0 compatibility before accepting a third-party observation; blocked evidence remains traceable but is not attached as requirement-supporting evidence.
- Verification: `tests/test_world_bank_collector.py -v` → **8 passed, 1 warning**; planner integration asserts the population requirement remains terminal-unresolved with the specific license reason.

## [BLOCKED] ILOSTAT SDMX labor statistics

- Requested capability: bounded, HTTPS-only aggregate country labor-statistics collection via the ILO SDMX REST API, using only public non-microdata and satisfying labor-baseline requirements only.
- Inspected endpoint: `https://sdmx.ilo.org/rest/v1/dataflow/ILO/DF_EMP_TEMP_SEX_AGE_NB/latest?references=children` returned HTTP 200 for the dataflow “Employment by sex and age”. Its structure response also returned HTTP 200 and included a `LAST_UPDATE` annotation (`27/09/2026 07:13:04`), but neither response exposed the dataset's publication date or an explicit CC BY 4.0 tag.
- Official policy: `https://www.ilo.org/rights-and-permissions` says datasets and referential metadata published/made available on or after 2023-05-03 are CC BY 4.0; restricted microdata provided by constituents/partners are excluded, and older datasets do not automatically receive the license. A last-updated date is not a substitute for the required publication date or license evidence. SDMX robots and API-specific terms were not established.
- Status: no ILOSTAT registry entry, collector, observation persistence, or requirement satisfaction was added. One malformed candidate data key returned HTTP 500 and wildcard candidates returned 404; no observation was obtained. No live observation/persistence or full ILOSTAT test suite is claimed.
- Exact unblock: establish dataset-specific qualifying publication/license metadata and review the official SDMX robots/terms and permitted operations. Then add a dated exact clearance, implement the bounded parser through the existing collector/Evidence pipeline, and test that only labor-baseline requirements can be satisfied.

## [IMPLEMENTED — LIVE RATE-LIMITED] GDELT DOC API metadata discovery

- Scope: register and implement bounded GDELT DOC API v2 article metadata through the existing clearance registry, task runner, Observer, Signal, and Evidence pipeline; no new domain table or parallel adapter system.
- Clearance and limits: exact HTTPS `/api/v2/doc/doc` endpoint, fixed `artlist` + JSON parameters, only `url`, `title`, `seendate`, `domain`, `language`, and `sourcecountry` retained, max 25 records, bounded timespan/query length, and deterministic SHA-256 source identity. No article URL is requested; bodies/images are not collected. Provenance includes GDELT attribution URL, country, bounded result count/cap, and metadata-only status.
- Rate control: persistent clearance gate enforces a five-second interval. HTTP 429 triggers at most two exponential retries (5 and 10 seconds, honoring a longer bounded `Retry-After`); continued rate limiting defers the ResearchTask without consuming attempts.
- Epistemic boundary: metadata can ground `media_coverage_observation` and `recent_event_signal`, but cannot prove article claims, customer pain, willingness to pay, product demand, market size, or financial viability. `public_reporting_velocity` means only an uncapped count of GDELT-indexed articles in the declared query/time window; capped results remain unresolved. These counts cannot create or advance Opportunities; existing opportunity creation ignores `metadata_only` signals. Separate article URLs and their provenance remain separate observations.
- Verification: `tests/test_gdelt_collector.py -v` → **9 passed, 1 skipped, 1 warning**; combined GDELT + registry + research/opportunity/Crossref/public-value regressions → **74 passed, 1 skipped, 8 warnings**; full backend → **413 passed, 1 skipped, 22 warnings**; `git diff --check` passed.
- Refreshed live result: `("supply chain" OR "logistics")`, `artlist`, JSON, `1w`, max 5 remained rate-limited after bounded exponential backoff. An earlier invalid query returned GDELT's instruction to parenthesize OR terms. No article metadata, Evidence, or Signal was obtained or persisted, so SQLite reopen persistence remains unverified for live records. No publisher page/body was fetched.

## [IMPLEMENTED — LIVE VERIFIED] OpenAlex scholarly evidence

- Scope: registered `openalex-public-works-cc0` and integrated the Works endpoint into the existing collector runner and Observer/Evidence/Signal persistence path. The project keeps its `services/collectors/` architecture; no external-PDF adapter or separate evidence store was added.
- Policy: official API docs describe keyless GET access, `search` and `search.semantic` + `per_page`, and state all OpenAlex data is CC0. Robots allowed `/`. Runtime rechecks robots and the current CC0 statement. Clearance is exact HTTPS `/works`, allowlists the requested scholarly fields, caps keyword results at 100 and semantic results at 50 (with semantic query text truncated to 2,000 characters), and uses persistent one-second pacing across both modes.
- Content/provenance: reconstructs `abstract_inverted_index` in token-position order and stores OpenAlex ID, optional DOI, title, publication year (not a fabricated exact date), citation count, bounded authorship/concept summaries, safe primary-location/open-access summaries, abstract, query, license and retrieval provenance. PDF/landing URLs are discarded, no external links are opened, and OpenAlex retrieval relevance is not stored as evidence strength.
- Epistemic boundary: OpenAlex can satisfy only scholarly-evidence/prior-research/documented-intervention/literature-existence observations. Affiliation country is not study geography and publication year is not study period; explicit local applicability and study-context requirements remain unresolved. OpenAlex cannot satisfy customer pain, WTP, local market size, demand or revenue, and its signals are excluded from opportunity creation/advancement.
- Live result: `postharvest loss smallholder farmers Nepal`, `search.semantic`, `per_page=5` returned 5 works; 5 Evidence and 5 Signal records persisted to isolated SQLite and remained 5/5 after close/reopen. Tracked outbound requests were limited to `api.openalex.org` and the already-authorized OpenAlex policy host `help.openalex.org`; no publisher or PDF request occurred. Live persistence checked OpenAlex ID, title, CC0 license, provenance, and abstract reconstruction status; mocked parser tests additionally check DOI, year, citation count, concepts, and authorship.
- Identity/empty-result hardening: canonical Work ID SHA-256 identity is enforced by a unique Signal identity key and SQLite/PostgreSQL-compatible unique index; Evidence uses its existing unique idempotency key with atomic conflict recovery. Repeated or concurrent ingestion returns one Signal and one Evidence per Work. Empty semantic/keyword results are recorded on the task as `valid_empty_retrieval` with `claim_effect: none`; they do not support or disprove a claim or complete scholarly requirements.
- Planner audit: explicit exact phrases/DOIs/author or paper lookups select keyword mode; broad conceptual and intervention questions select semantic mode. Task and Evidence provenance retain the unreduced research question, derived query, selected mode, any detected geography/population, and unresolved dimensions. Invalid caller-supplied modes fail before outbound Works requests.
- Verification: focused OpenAlex tests → **15 passed, 1 skipped, 1 warning**; available research/provenance/opportunity regressions → **26 passed, 4 warnings**; full backend → **428 passed, 2 skipped, 22 warnings**; live isolated semantic SQLite persistence/reopen test → **1 passed, 1 warning**; `git diff --check` passed. The requested `test_evidence_provenance.py` path is absent; see the exact regression selection and live row counts in the latest RESULT card in `verification/CONTINUOUS_EXECUTION_REPORT.md`.
- Latest planner/concurrency audit counts: focused OpenAlex suite **20 passed, 1 skipped, 4 warnings**; research/provenance/opportunity regressions **54 passed, 12 warnings**; full backend **433 passed, 2 skipped, 24 warnings**; one bounded live semantic query returned/persisted/reopened **5/5/5/5/5** works/Evidence/Signals/reopen Evidence/reopen Signals. Latest RESULT card supersedes earlier totals.

## [IMPLEMENTED — TEST VERIFIED] Multi-source research orchestration and synthesis

- Scope: decompose broad research objectives into phenomenon, population, geography, reporting, intervention, and commercial-validation nodes; route collection only through currently cleared capability-registry entries and the existing ResearchTask/collector runner.
- Routing: Crossref remains bibliographic discovery only; OpenAlex handles literature and intervention abstracts; World Bank handles bounded country-level population/macro observations; GDELT handles bounded article metadata/reporting observations. A five-task per-question ceiling is retained. Qualifiers and unresolved dimensions are persisted on tasks and copied into Evidence provenance.
- Synthesis: the read-only plan synthesis cites persisted Evidence IDs and canonical provenance URLs, records explicit contradiction edges without replacing source observations, and marks unsupported dimensions unresolved. Completed collection tasks do not become completed research. Customer pain, buyer willingness to pay, commercial demand, opportunity, and experiment gates remain locked without direct customer/transaction evidence.
- Verification: focused orchestration + planner tests **9 passed, 1 warning**; research/OpenAlex/provenance/opportunity regression selection **79 passed, 1 skipped, 14 warnings**; full backend **438 passed, 2 skipped, 24 warnings**; `git diff --check` passed.
- Bounded persistence test: five mocked tasks across Crossref, OpenAlex, World Bank, and GDELT executed sequentially; five Evidence records with IDs 1–5 were present before and after SQLite close/reopen. No provider network request was made and no new schema/table or source clearance was added. This is test-mode verification, not a live source-data result.

## [DONE — LIVE VERIFIED] Adaptive closed-loop research cycle

- Objective-adaptive requirement profiles now cover agricultural/commodity, software/service, and logistics/corridor questions. Requirement qualifiers and unresolved dimensions remain explicit; source collection still runs only through the existing capability clearances and collector runner.
- Unresolved requirements can receive a deterministic follow-up task only from an active, unused cleared capability. SHA-256 task identity plus the migrated unique `ResearchTask.idempotency_key` index prevents concurrent duplicate tasks. Three concurrent orchestration workers each synthesized the question and attempted the same task; one task persisted. The existing five-task ceiling remains in force.
- Synthesis persists standard requirement states and provenance-cited Evidence IDs in the `ResearchQuestion.research_plan` JSON. Failed source attempts remain visible beside any usable observations. There is no dedicated synthesis-result table to duplicate or upsert.
- Live bounded cycle: specified Nepal postharvest objective; two OpenAlex semantic tasks and two World Bank tasks completed. OpenAlex-supported requirement citations: phenomenon **Evidence IDs 1, 2, 3, 5, 6, 7, 9, 10**; interventions **2, 3, 5, 7, 10, 11, 14**. Affected population and geographic baseline remained unresolved; commercial validation was blocked. Persisted Evidence/Signal counts were **24/24**, and reopened counts were **24/24**. No next task was generated; final state `research_terminal_unresolved`.
- Observed hosts: `api.openalex.org`, `help.openalex.org`, `api.worldbank.org`, and `datacatalog.worldbank.org`. No publisher/PDF endpoint was requested; the bounded live cycle cost **$0**. Public-source evidence did not satisfy customer pain, willingness-to-pay, or commercial-demand gates.
- Tests: focused orchestration **9 passed, 3 warnings**; research/provenance/opportunity regressions **74 passed, 1 skipped, 14 warnings**; full backend **442 passed, 2 skipped, 25 warnings**; `git diff --check` passed. The specifically requested `test_evidence_provenance.py` is absent; the existing provenance-focused suites listed in the latest execution report were run.

## [NEXT — NOT CLEARED] Nepal-specific postharvest primary evidence

- **Capability needed:** a reviewed, cleared primary Nepal agriculture source or study-data capability that can return local crop/postharvest-loss observations with geography, season, and smallholder/population scope. Current OpenAlex retrieval and country-level World Bank indicators do not provide this coverage; they must not be substituted for it.
- **Verification status:** not implemented or cleared. The isolated follow-up regression proves only that an empty OpenAlex semantic retrieval can generate a bounded, clearance-preserving keyword task. Its deterministic test-double Evidence remained `claim_support: not_inferred`; affected-population and local-applicability claims stayed unresolved.
- **Terminal boundary:** customer pain, buyer willingness-to-pay, and commercial demand still require genuine direct customer or transaction evidence. Neither the follow-up nor any public-source capability may unlock an Opportunity or commercial validation.
- **Latest verification:** focused research selection **56 passed, 1 skipped, 7 warnings**; full backend **447 passed, 2 skipped, 27 warnings**; isolated SQLite follow-up persistence/reopen **1 passed, 3 warnings**. See the latest RESULT in `verification/CONTINUOUS_EXECUTION_REPORT.md`.

## [IMPLEMENTED — TEST VERIFIED] General research capability discovery

- Unanswered requirements now create a durable CAPABILITY-primitive gap record rather than Evidence. The record includes requirement/question IDs, evidence and geographic/temporal/population scope, insufficiency reason, candidate-discovery state, clearance state, provenance, and a bounded next action.
- Discovery is deliberately conservative: it creates at most **3** generic source-adapter hypotheses at depth **1**, performs **0** external requests in the current implementation, and enforces a **2-second** cycle budget. It does not invent providers, query uncleared hosts, activate candidates, or treat search metadata as evidence.
- Lifecycle is explicit: `candidate` → `reviewed` (must bind an existing registry entry) → `cleared` (must match a current exact clearance) → substrate-tested `active`. The planner refuses inactive/uncleared discovered candidates; only an active candidate plus the authoritative registry clearance can create a ResearchTask.
- Verified isolated SQLite reopen retained the gap, candidate, active lifecycle, ResearchTask, and Evidence. The task and Evidence both retained the activated capability ID and source registry ID. Discovery itself created no Evidence, Signal, Opportunity, or Decision.
- The Nepal-specific agriculture capability remains **NOT CLEARED**. The next missing capability is still a reviewed primary Nepal agriculture/postharvest source with crop/loss, geography, season, and smallholder scope.

## [IMPLEMENTED — TEST VERIFIED] Demand-first understanding

- Raw observations now enter through the existing `Signal` observer and are projected into substrate `WorldEvent` + `Evidence` records before any category or need type is required. The new `need` entity type is an open-vocabulary substrate type; no vertical table was added.
- The deterministic seam records `possible_demand`, `hypothesized`, or `sufficiently_understood_need`, keeps unresolved outcome questions explicit, and uses only `possible`/`hypothesized` evidence. It does not infer customers, market size, willingness-to-pay, fulfillment, or Opportunity state.
- A sufficiently understood need calls the existing `active_cleared_sources()` path. Existing cleared capability is reused without research; an empty authorized match calls the existing `ensure_capability_gap()` path. Inactive/uncleared capability candidates remain non-executable under the prior lifecycle.
- Isolated SQLite proof (synthetic mechanics fixture): after close/reopen, Signal **1**, Need **2**, and capability gap **1** remained durable; one downstream ResearchQuestion was created only for the explicit no-capability gap; Opportunity and Decision counts were **0**.
- Remaining capability: consent-preserving real-world demand observation plus an authorized response/fulfillment channel. This increment does not claim real demand validation or economic action.

## [IMPLEMENTED — TEST VERIFIED] Authorized observation handoff

- Added a guarded handoff from an already-authorized adapter result into the existing Signal/EVENT/EVIDENCE substrate. It requires the exact current registry entry, matching persistent rate reservation, and a specifically cleared `allowed_fields` entry. It performs no fetch itself; public visibility or HTTP success alone does not authorize use.
- Normalization records source/registry identity, source type and reference, source and ingestion timestamps, authorization reservation, and deterministic hashed source identity. Email and phone-like strings are redacted from observation text/title/provenance. Identity-bearing observations are deduplicated deterministically while independent source IDs/times remain separate records.
- The demand worker uses existing `WorkerTask`; task creation is SHA-256 idempotent and does not contact people or trigger actions. Need and capability results remain hypothesis/process records, never customer, buyer, WTP, Opportunity, order, or revenue evidence.
- Capability gaps are represented by existing CAPABILITY records plus `capability_gap_recorded` EVENT and possible-level EVIDENCE with exact registry-search provenance, timestamp, considered sources, candidates, and an explicit limitation on the inference.
- Verification: broad focused observation/demand/worker/capability/research/clearance/collector/substrate suites **73 passed, 9 warnings**; complete backend **466 passed, 2 skipped, 30 warnings**; TypeScript typecheck passed. Synthetic isolated SQLite proof retained both adequate-match and gap paths after reopen. **No live source request or real-world demand was exercised.**
- Next missing capability: a genuine non-test user submission through an appropriately configured public/authenticated client, followed by direct human response and separate economic validation. The local developer-test request path is not market evidence.

## [DONE — TEST VERIFIED] Need-linked economic assessment

- **CURRENTLY IMPLEMENTED:** reused the existing `Opportunity` and append-only `OpportunityEvent` projection, plus substrate `economic_validation_assessed` EVENT and hypothesized Need relation. No new table, CRM, lifecycle primitive, or alternate opportunity store was introduced.
- The assessment requires a sufficiently specified hypothesis-grade Need and a recorded existing capability search. It distinguishes `insufficient_evidence`, `economically_uncertain`, and `testable`; keeps unknown cost, price, and WTP explicit; rejects Evidence references without a source, claim/content, provenance, and explicit non-refuted support state; and states that cited Evidence has not received semantic support adjudication.
- **ACTION BOUNDARY:** a `testable` state stores only a concrete proposed WTP experiment. The assessment records `authorization_required_before_external_action: true` and `external_action_authorized: false`; it creates no Experiment or Action and invokes no external side effect. Existing Experiment/Action approval/execution paths remain separate.
- Tightened existing CustomerEvent stage writes: `contacted` requires a properly authorized started Experiment-linked Action of matching data scope or a recorded response; `interested` requires non-disputed linked `ACTUAL_RESPONSE`; `paid_customer` requires linked verified positive `ACTUAL_REVENUE`. Missing evidence and reported-only payment are rejected.
- Verification: focused economic/public API/customer-stage regressions **34 passed, 11 warnings**; full backend, including demand/capability/research/action regressions, **479 passed, 2 skipped, 32 warnings**; frontend TypeScript check passed; isolated SQLite close/reopen passed with search provenance, assessment history, relation, and authorization state preserved. No live-world request or external action occurred.

## [FUTURE CAPABILITY — NOT IMPLEMENTED] Authorized prospect discovery and response path

### Owner-dependency ranking — production snapshot 2026-09-29

**Rank 1: acquiring a legitimate real need/opportunity without the owner
supplying it.** This is the first blocked seam on the production path to money:
production currently exposes 0 opportunities, 0 products, and a revenue
breakdown of 0 potential, 0 expected, and 0 realized revenue. `/api/health`
reports PostgreSQL available and ready, and `/api/forge/runtime` reports a
completed cycle, 10 signals, and 4 outcome rows; cycle execution and row
counts are not commercial validation. The public Feed contains 11 items; its
inspected belief is explicitly uncorroborated, and the inspected pattern is
derived from Crossref scholarly metadata. Neither is buyer demand.

The code confirms why this dependency remains:

- `source_clearance_registry` contains five exact-purpose entries, none
  supporting `authorized_prospect_discovery`; the readiness test asserts that
  this yields no eligible source, no external request, and no candidate.
- `collector_runner` explicitly excludes GitHub, Reddit, RSS, news, and arXiv
  from standing collection until cleared. The separate GitHub bounty module
  has a public-search helper, but no runtime caller for its fetch/ingest
  functions; its claim mutation requires `GITHUB_TOKEN`. Existing bounty tests
  also accept a public issue with no amount as an Opportunity with unknown
  price and low confidence, so that adapter cannot by itself establish a
  funded offer or verified revenue.
- `/api/signals/public-request` can receive a request from an external person,
  and the demand worker can classify it as `possible_demand`; neither discovers
  or attracts that person. Research collection and the public Feed do not
  establish customer pain, buyer interest, or willingness to pay.

**Exact owner dependency:** provide a genuine inbound need through the existing
intake, or obtain/review source-specific authority for a bounded source that
can reveal real commercial demand. Forge cannot remove this dependency merely
by querying a publicly reachable endpoint. Existing automated work includes
the intelligence cycle, bounded demand understanding after submission, source
clearance checks, capability search, and evidence-gated economic assessment.

**Why no economic implementation is made in this task:** the source registry
has no applicable authorization, and no genuine opportunity exists to advance.
Adding a collector or enabling the uncleared GitHub helper would bypass the
existing source-authorization boundary; fabricating a demand record would not
reduce owner actions on a real transaction. The external unblock is a current,
documented source authorization and bounded permitted operation/fields. Once
that exists, a source-specific adapter can be assessed against existing
Signal/Evidence/Opportunity machinery.

**Other observed downstream dependencies (not rankable before a real
opportunity/transaction exists):**

| Stage | Existing path and verified boundary | Remaining routine interaction or prerequisite |
|---|---|---|
| Understand / capability reuse | The demand worker and existing capability search run after intake; the economics service records unresolved evidence rather than inferring it. | A real requester must provide missing facts; a consented, configured clarification channel is not evidenced. |
| Economic test / prospect qualification | Need economics can identify a `testable` hypothesis; prospect readiness is a read-only source audit and fails closed with no eligible prospect source. | Real cost/price/WTP evidence and source authorization are required before an external test or buyer discovery. |
| Offer | `POST /products/offer-drafts` creates an existing Product with `PENDING_REVIEW`; the brief leaves delivery, cost, price, and value unresolved. | Owner review/approval and actual capability/customer-specific scope remain required; draft creation does not send an offer. |
| Authorized action / communication | `AutonomyPolicy` evaluates boundaries; `execution_engine` maps external work to integrations or owner action. Existing SMTP and GitHub adapters report provider execution, not a buyer response. | A bounded standing policy plus an authorized, configured adapter and permitted recipient/channel are prerequisites. GitHub mutation fails closed without its token. |
| Fulfillment / response | The offer brief explicitly reserves customer-facing delivery for manual review; actual responses enter through the existing outcome-recording path, whose default source is `manual`. | A real fulfillment capability and external response evidence are not demonstrated in production. |
| Payment / outcome / learning | eSewa and Khalti routes support provider checkout/lookup and verification; outcome learning runs from recorded outcomes. | Production variable-name inspection found no eSewa/Khalti credential names; no payment-provider call was made, and the public revenue projection reports zero realized revenue. Recording a response/outcome still requires an external event or owner-entered evidence. |

Production API reads on 2026-09-29 returned `/api/opportunities` = `[]`,
`/api/products` = `[]`, and revenue breakdown
`{potential_30d: 0, potential_90d: 0, expected: 0, realized: 0}`. Therefore
`OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE** (there are
no verified real transactions established by the inspected production
responses); it is not zero. The runtime endpoint's count of four Outcome rows
does not classify their evidence, so those rows are not counted as buyer
responses or transactions. The public revenue projection reports zero
realized revenue.

- **CURRENTLY IMPLEMENTED:** the Opportunity-scoped readiness endpoint requires the latest economic assessment to be `testable`, records a bounded criteria/source-registry audit as existing Opportunity ENTITY/EVENT/EVIDENCE, and retains the existing Opportunity→Need RELATION. It is idempotent, creates no candidate or prospect, and records unresolved qualification evidence while withholding outreach eligibility.
- **Repository evidence for the source block:** the runtime registry has five entries (GovInfo, Crossref, World Bank, GDELT, OpenAlex); GovInfo's review expired 2026-09-25 and none includes the exact `authorized_prospect_discovery` requirement. Their authorized operations/fields are exact public-rule retrieval, scholarly metadata, country indicators, media article metadata, and scholarly metadata/abstracts—not business/client identification or sales prospecting. GDELT specifically bars commercial-demand inference. Additional public pages listed in `docs/PUBLIC_SOURCES.md` lack applicable terms/clearance (Bolpatra terms were not established); they are not source adapters. Provider/ServiceListing public visibility is directory publication, not prospecting/contact consent. No provider contacts were read.
- **REAL DISCOVERY:** none. The bounded registry check made no external request and found zero eligible entries; no real candidate or potential prospect was created. The result does not assert no prospects exist outside this bounded review.
- **OUTREACH / COMMERCIAL STATE:** outreach **NONE**; this milestone created no ACTION, response, interested party, buyer/customer, WTP evidence, order, payment, or revenue. Production counts are recorded above; all verification intake remains internal/test data, not market evidence.
- **TARGET ARCHITECTURE:** `testable Opportunity → explicit source authorization → bounded read-only query → candidate ENTITY + discovery EVENT/EVIDENCE + relevance RELATION → potential only with relevance evidence → later qualification evidence → separately authorized outreach/response`. Do not add a CRM, infer stage promotions, or execute an ACTION because an Opportunity exists.

## [DONE WITH LIMITATION] Keep Forge Bot contact private and clarify booking state

- Owner action still required: choose and configure an email provider for internal owner summaries; decide the retention period and complete owner-run market discovery before any real intake; separately authorize bounded live operation.
- Action removed: the public Forge Bot config and inquiry page no longer publish the owner's mailbox address; the page distinguishes an available booking link from a submitted request or confirmed appointment, and owner summaries carry the booking link without marking a lead booked.
- Current blocker / verification: local and production browser checks rendered the closed intake state and supplied booking URL with no console errors; the 390px production viewport had no horizontal overflow. Production `/api/forge-bot/config` returned HTTP 200 with intake disabled, no public contact-email field, and a configured booking URL; the owner summary and protected substrate/customer reads returned HTTP 401 without credentials. `backend/tests/test_forge_bot_api.py` exercises a consented TEST lead through storage, summary, and a mocked email sender while outbound sockets are blocked; the full backend suite passes (594 passed, 2 skipped), and `npm test` passes (197 script tests and 103 app tests). GitHub CI run `37025946665` passed on exact SHA `cf338648fcb51eaa96d695daa9f9100ced6f3efd`; Vercel deployment `dpl_3yS2AxanVCYrXnCkoHn6uB8fnYC8` is READY for that SHA. Filtered production environment-name inspection found only `FORGE_API_KEY` among the relevant live/intake/legacy/SMTP names; no production lead or email was created or sent. `FORGE_BOT_LIVE` remains false and intake remains closed.
- Next removable dependency: configure a protected server-side provider only after owner selection, set the existing HMAC/API/abuse-control requirements, choose retention, and grant explicit bounded authorization before enabling real intake. A booking URL is not an appointment and TEST evidence is not customer or revenue evidence.

## [DONE WITH LIMITATION] Gate legacy intelligence behind explicit configuration

- Owner action still required: keep `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` unset or false unless the owner explicitly authorizes re-enabling the legacy intelligence routines and their separately scoped data-source/integration permissions.
- Action removed: default startup no longer seeds or imports the legacy intelligence stack; legacy research and demand endpoints reject work, the scheduled cycle returns a disabled no-op, and the worker exits before starting when the flag is false.
- Current blocker / verification: the flag defaults false in `backend/app/config.py`, and no matching legacy-flag variable name is configured in production. A subprocess with the flag false ran the startup hook, created the expected application tables, and reported no legacy target modules loaded. Focused gate/scheduler/public-flow tests passed (48); full backend suite passed (594 passed, 2 skipped). Root typecheck, production build, frontend TypeScript check, auth invariant, and `npm test` passed (197 script tests and 103 app tests). GitHub CI run `37025946665` passed on exact SHA `cf338648fcb51eaa96d695daa9f9100ced6f3efd`; Vercel deployment `dpl_3yS2AxanVCYrXnCkoHn6uB8fnYC8` is READY for that SHA. Production `/api/health` returned HTTP 200, `status=ok`, PostgreSQL/configured/available, readiness true with no blockers; unauthenticated `/api/scheduled/cycle` returned HTTP 200 with `status=disabled`.
- Next removable dependency: if legacy intelligence is ever needed, obtain a separate explicit owner decision and the exact source/integration authorization before re-enabling it. The flag alone grants no external permission.

- **FUTURE CAPABILITY — precise blocker:** a source-specific, current terms/privacy/authorization review that explicitly permits bounded business/client discovery for an economic hypothesis, plus an adapter constrained to authorized fields and query/rate boundaries. Current research/macro/news sources and provider directories do not meet that requirement. Safest next step: select one source and verify its applicable written authorization before implementing an adapter; do not query a merely accessible source or contact anyone.

### OCR source decision — 2026-09-28

- **OCR / CAMIS Public Data Portal: NOT CLEARED.** Official OCR pages expose an unauthenticated company-search interface and a company table with legal name, registration number, masked PAN, company type/status, address, and registration/expiry dates. Search is described as using name, registration number, or PAN and the interface adds a math challenge. That establishes human-facing access, not automated access or permission to reuse company rows for prospecting.
- No written terms/privacy/reuse permission or documented API contract was found. The company subdomain's `/robots.txt` and apparent `/terms`/`/privacy` routes returned the single-page-app shell, not policy content. OCR parent-domain crawl delay cannot be transferred to `company.ocr.gov.np`. Sensitive detail fields were not inspected and are not approved for collection.
- **Live request:** visiting the search route automatically loaded the UI's default page via the undocumented `/api/public/v1/company-register`: ten table rows rendered, with a displayed result total of 181,992; OCR's home page separately advertised 111,290. No search was submitted and no row was retained or classified. This incident is disclosed in the OCR result card; it is not real discovery and is not permission for repeat requests.
- **Decision:** do not register OCR or build an adapter until OCR provides written permission specifically covering automated access and business/prospect-discovery reuse, a documented interface/request scope, allowed field list, rate and retention/privacy rules, and a valid review date.
- **Next candidate:** Nepal PPMO/Bolpatra procurement notices and awards/vendors, because a bounded tender/award query could reveal a real buying requirement and the responsible public entity or vendor. Current repo evidence says its robots endpoint served a maintenance page and no reuse terms were established. Before use, obtain PPMO's written automated-access and Opportunity-scoped commercial-discovery permission, documented machine endpoint/export and fields, privacy/retention limits, rate constraints, and dated clearance evidence. It is **NOT CLEARED** meanwhile.

## [BLOCKED — SOURCE NOT CLEARED] Nepal procurement-demand discovery

- **SOURCE REVIEW:** the official PPMO site is `https://www.ppmo.gov.np/`; its e-GP reference points to the official system at `https://bolpatra.gov.np/egp/`. Bolpatra root, e-GP, and both robots URLs currently serve a maintenance page, not a searchable or machine-readable interface. The separate PPMO host's robots file specifies a 10-second crawl delay only for that host; it does not grant access to Bolpatra.
- **AUTHORIZATION:** no applicable API/export specification, terms/license, automated-access permission, rate/fair-use limit, privacy/retention policy, or reuse authorization for procurement-demand analysis was established. Historical notice reuse and commercial prospect identification remain unknown. The source is **NOT CLEARED**; no registry entry or adapter was added. Procurement-demand observation must not be conflated with consent to contact a public purchasing organization.
- **FAIL-CLOSED PROOF:** `backend/tests/test_source_clearance_registry.py::test_public_bolpatra_url_is_not_cleared_for_procurement_discovery` verifies the official target is absent from the exact-URL registry, no `procurement_demand_discovery` capability is currently cleared, `authorize_request` rejects the URL, and no persistent fetch-rate reservation is created.
- **CURRENT INTERNAL HANDOFF:** reuse the already-tested six-primitive substrate path when an authorized source observation exists: exact source authorization → existing Signal observation plus `demand_observed` EVENT/EVIDENCE and provenance → `demand_understanding` (possible demand stays without a Need; only a sufficiently described Need proceeds) → existing capability search/gap record → evidence-bounded economic assessment and Opportunity. This generic path is not a procurement adapter and no procurement evidence has entered it.
- **TARGET ARCHITECTURE:** an explicitly permitted bounded notice query → procurement observation EVENT/EVIDENCE with official notice ID/URL, publication/deadline, requirement and permitted purchasing-organization fields → demand understanding → Need only when warranted → existing capability search → economic assessment → organization identity/RELATION only when directly evidenced → qualification handoff. A tender alone cannot establish ForgeOS-specific interest, WTP, customer status, or permission for outreach.
- **REAL PROCUREMENT / BUYER / COMMERCIAL STATE:** no procurement search or notice retrieval was performed; procurement records **0**; identified procuring organizations **0**; potential buyers **0**; outreach **NONE**; this work created no WTP, customer, order, payment, or revenue evidence.
- **PRECISE NEXT DEPENDENCY:** obtain current PPMO authorization or applicable published terms explicitly permitting automated read-only access and Opportunity-scoped procurement-demand analysis; a documented operational API/export and bounded query shape; permitted notice/organization fields and historical scope; privacy/retention, rate, and attribution rules; plus a dated review/expiry. Recheck the live interface only after that permission is established.

## [NEXT — TED SEARCH FIELD CONTRACT REQUIRED] Global procurement-demand source

- **Strongest candidate:** European Union Publications Office TED Search API, `POST https://api.ted.europa.eu/v3/notices/search`. Its official [Search API docs](https://docs.ted.europa.eu/api/latest/search.html) explicitly allow anonymous access to published procurement notices for analysis/reuse and identify commercial added-value services to buyers/vendors.
- **Why not yet executable:** one tightly bounded publication-date query requesting notice number/title, buyer name, publication/deadline, country and CPV returned HTTP 400 because requested `fields` values were unsupported. No record was returned or persisted. The Search API docs do not expose the accepted field schema; the Swagger spec does not expose the Search operation. No numeric API quota or selected-field privacy/retention/license basis was established. TED is a source candidate with explicit purpose-level reuse language, but ForgeOS did not register a clearance or adapter because permitted field-level request cannot yet be represented safely.
- **Fail-closed verification:** `backend/tests/test_source_clearance_registry.py::test_public_bolpatra_url_is_not_cleared_for_procurement_discovery` now proves neither Bolpatra nor the unverified TED request target has runtime clearance, no `procurement_demand_discovery` capability is currently active, and authorization fails before a fetch slot is reserved.
- **Other sources checked:** Contracts Finder's official API intro describes an inbound interface for approved notice publishers; the reviewed docs did not establish a read/reuse permission and schema for this use. USAspending's inspected official overview concerns awarded/federal spend data rather than currently open procurement demand, and its exact reuse/license basis was not verified. Neither was selected or queried.
- **REAL OBSERVATION / SUBSTRATE:** **0** procurement records and **0** buyer entities. No procurement EVENT/EVIDENCE, Need, Opportunity, potential buyer, qualification, or external Action was created. Existing generic source-authorized observation → demand understanding → capability search → economic assessment remains unchanged; it has no procurement evidence to process yet.
- **Precise unblock:** obtain current machine-readable Search API field schema or written TED confirmation for ID/title/authority/publication/deadline/CPV/country request fields; confirmation those selected fields are covered by reuse and privacy/retention conditions; and source rate policy (or written acceptance of a local one-request/hour cap). The just-attempted API call reserved the local one-hour cooldown; no retry before it expires.

## [BLOCKED — CONTRACTS FINDER ACCESS CONTRACT UNRESOLVED] UK procurement-demand source

- **OFFICIAL INTERFACE:** the current [Contracts Finder V2 API docs](https://www.contractsfinder.service.gov.uk/apidocumentation/V2) recommend `POST /api/rest/2/search_notices/{MimeType}` over deprecated V1 and document search criteria, result `Size`, and a notice-summary response. Summary fields include notice ID/title/description, publication/deadline, type/status, buyer organization name, CPV, region and source-reported value. Full-notice retrieval includes contact details and is expressly outside the proposed field scope.
- **REUSE BASIS:** [Contracts Finder service terms](https://www.contractsfinder.service.gov.uk/Home/TermsAndConditions) say most content is Crown copyright and published under OGL v3 and that most content is available through feeds for other websites and applications. [OGL v3](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) permits commercial reuse with attribution, but excludes personal data and third-party rights not licensed by the provider. Terms prohibit disruptive crawling/avoiding restrictions, require lawful purpose, and state service access is subject to business need. No numerical request quota or field-specific notice license was established.
- **WHY NOT CLEARED:** the API-wide documentation says authentication is required for certain methods but does not identify whether the V2 read/search operation is public. The official Authentication documentation request returned HTTP 403 with a message that the request rate limit may have been exceeded; no retry was made. The site's `/robots.txt` returned 404. Therefore the endpoint auth/public-access rule, numeric/fair-use rate bound, and exact OGL coverage for the retained summary/free-text fields are not sufficiently explicit for ForgeOS runtime clearance. No collector or source registry entry was added.
- **FAIL-CLOSED PROOF:** `backend/tests/test_source_clearance_registry.py::test_public_bolpatra_url_is_not_cleared_for_procurement_discovery` now checks that the Contracts Finder search endpoint is absent from the exact-URL registry, the collector is not active, authorization fails, and no fetch-rate reservation is written.
- **REAL SOURCE RESULT:** no Contracts Finder search/data request was made; notices **0**, buyer organizations **0**, potential buyers **0**. No source record, demand EVENT/EVIDENCE, Need, Opportunity, prospect, outreach ACTION, or commercial evidence was created.
- **NEXT CANDIDATE:** Find a Tender's official service terms independently state OGL reuse for most content and feeds for other websites/apps, and its public service page states current UK notice coverage. Its exact read API/OCDS endpoint, authentication, rate policy, and field-level rights still need official confirmation; it remains a source candidate, not an executable clearance.
- **PRECISE UNBLOCK:** obtain authoritative operation-level confirmation that V2 search is permitted for unauthenticated read-only commercial demand analysis (or obtain the required credentials/approval), establish the applicable source rate/fair-use bound, and confirm chosen NoticeIndex summary fields are reusable under OGL while excluding personal/third-party content. Then register only those fields and perform one `Size=1`, bounded-date/status/type query after ordinary source eligibility; do not retry a rate-limit response.

## [IMPLEMENTED — OWNER REVIEW REQUIRED] Offer preparation bridge

- **CURRENT CAPABILITY:** the owner-operated path uses Forge's existing built-in `offline-mock` reasoning capability, which is locally available without network credentials. Optional providers remain unresolved until separately configured and checked.
- **OFFER PATH:** `POST /products/offer-drafts` converts a real business-problem description into the existing `Product` substrate with a structured offer brief: workflow, scope, exclusions, assumptions, unresolved questions, authorization requirements, and explicit unresolved delivery/cost/price/value hypotheses.
- **APPROVAL BOUNDARY:** the draft persists as `PENDING_REVIEW`; `POST /products/{id}/offer-approval` records `APPROVED`, `NEEDS_EDIT`, or `REJECTED` with a note and timestamp. Approval does not send outreach or create a customer, Action, Outcome, payment, or revenue record.
- **NEXT LEGITIMATE CLIENT PATH:** owner-led inbound, owner-supplied contacts, or owner-authorized relationships may be presented manually after review. No restricted public source is repurposed and no automatic contact is implemented.
- **REMAINING DEPENDENCY:** a real customer channel and owner/customer authorization for any external contact or system access. The repository contains no verified prospect, response, fulfillment, payment, or revenue from this bridge.

## [DONE — BROWSER VERIFIED] Public site delivery: cached reads, intent preload, working quality gate

- Agent: Cline, owner-directed performance/UX/defect pass on the public Hami site (Vite + TanStack Start root app).
- Scope: make the public pages load and navigate faster and fix the defects found while doing it. No authorization, evidence, source-clearance, commercial, or outreach surface was touched, and no new ledger, dependency, table, or primitive was introduced.
- Repository evidence: every public route fetched its data inside a `useEffect` with no cache, so each visit re-issued 2–4 `/api` reads and `/api/forge/runtime` was read independently by four routes; `src/router.tsx` configured no `defaultPreload` even though route components are already split into their own chunks (`.vercel/output/static/assets/discoveries-*.js`); `src/lib/app-data/client.server.ts` held the repository's only ESLint error; and `npm run check` could never pass because `eslint .` linted generated `frontend/.next/**` output plus two embedded projects.
- Owner action still required: **none** for this change, and **no owner-dependency metric changed**. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE** (no verified real transactions exist in this repository). This work removes repeat-waiting and re-fetching on page visits; it does not remove an approval, permission, or execution step, because none of them are on the path it touches.
- Acceptance: each route renders the same content as before with no console, hydration, or request failures; a "Retry"/"Refresh" press always reaches the network; reads after a write reflect that write; build and typecheck pass.
- Implementation: new `src/lib/api-cache.ts` — 20s reuse for a settled read, 5s for a `null` "could not be checked" result, in-flight de-duplication for concurrent callers, explicit `{ fresh: true }` bypass, and browser-only state so SSR never shares one visitor's response with another request. Wired into the single public-GET choke point in `src/lib/content.ts` and the engine reads in `src/lib/operations-data.ts`; `fresh: true` threaded through every Retry button and every post-write read (`/domain`); intent preload in `src/router.tsx`; `loading`/`decoding`/intrinsic-size on images; Roboto 600 added so `font-semibold` is no longer silently rendered as 700; generated and embedded-project ignores in `eslint.config.js`.
- Verification: `npm run check` → 0 errors (one pre-existing `react-refresh` warning); `npm run typecheck` clean; `npm test` → 70 passed (8 new cache tests, including TTL, de-duplication, `fresh` bypass, uncached exceptions, scoped invalidation, and the disabled/SSR path); `npm run build` clean. Browser evidence collected on the dev server and on the built output (served behind a local front proxy so `/api` reaches the engine): 18 public routes including the 404 route all returned 200 with real content, **0 console/page errors**, mobile 390×844 with no horizontal overflow, API reads **4 → 1 → 0** across home → navigate → back, and the route chunk fetched on nav hover. Screenshots: `screenshots/forge-{dev,prod}-*.png`.
- Current blocker: none on this seam. Two local-environment findings that do not affect deploys: port 8080 is held by the legacy Next.js `frontend/` app, so the contracted dev-server port is currently unavailable; and `vite preview` cannot reach the API locally because the built app's Start/Nitro handler owns `/api` (Vercel's `vercel.json` rewrite supplies it in production), so the local built-output preview shows live panels as "unavailable".
- Next removable dependency: free port 8080 (or relocate the legacy app) so `npm run dev` / `startup.sh` and the live preview serve ForgeOS; then, only if local built-output data verification is needed, give the preview an explicit API path.


## [DONE — VERIFIED] Full reinspection pass: broken recovery drill repaired, production recovery confirmed, substrate idempotency proven

- Agent: Cline, owner-directed full-system reinspection/repair/verification pass. Scope was to connect and repair existing capabilities, not to add features; no authorization, source-clearance, outreach, payment, or commercial surface was touched.
- Baseline checkpoint: branch + tag `recovery/audit-checkpoint-20260930` at `bdc7c33f1e296dc6b9ebfa969eddbeeefa3712db`. Working tree was clean and in sync with `origin/main`; `git fsck --full` reported only dangling blobs/commits (normal garbage), no corruption.

### Verified by running it (not by reading)

| Check | Command | Observed 2026-09-30 |
| --- | --- | --- |
| Backend suite | `cd backend && ../.venv/bin/python -m pytest tests -q` | 540 passed, 2 skipped |
| Frontend contract | `npm run typecheck`, `npm test`, `npm run build` | typecheck clean; 70 passed; `.vercel/output` produced |
| DB integrity + anomalies | `../.venv/bin/python -m scripts.truth_audit_report` | `integrity=ok`; anomalies `[]` — no FK violations, no duplicate keys, no stale `RUNNING` cycle |
| Recovery drill | `../.venv/bin/python -m scripts.recovery_verify` | repaired (below); snapshot restores to 66 tables / 54,625 rows with per-table counts equal to live, 0 FK violations, 0 stale rebuild tables, canonical DB unmodified, operator backups 10 before / 10 after |
| Substrate adapters on real data | `forge_loop.run_cycle` twice on a copy of `storage/forge.db` | 0 stage errors both runs; 949 canonical entities and 3,314 relations, **all distinct — zero duplicates**; the second cycle re-created 0 already-projected capabilities/relations/records and advanced 500 more legacy evidence rows plus 250 more market signals |
| Inbound demand path, end-to-end | `POST /signals/public-request` against a local uvicorn on an isolated copy | HTTP 202; stored `source=user_request`, `collection_status=user_submitted`; demand task completed `interpretation_state=possible_demand` with its 7 unresolved questions preserved; replaying the same `Idempotency-Key` returned the same signal id with exactly 1 row; the request never appeared in `/public/feed` |
| Production reads | `GET https://forge-os-ebon.vercel.app/api/health`, `/api/public/{feed,providers,services,discoveries,trust/provider/1}` | health 200 (`status=ok`, `driver=postgresql`, `available=true`, `ready=true`); feed/providers/services/discoveries 200; trust 404 as designed |
| Deployed API contract | `GET https://forge-os-ebon.vercel.app/{openapi.json,api/openapi.json}` vs local `:8000` | production `/openapi.json` answers the frontend SPA HTML and `/api/openapi.json` 404s (only `/api/*` reaches the service); the root schema generates fine (282,611 bytes of valid OpenAPI JSON). Repaired so the mirror covers the schema (below); verified on the reloaded local service as 200 `application/json`, identical to `/openapi.json` |
| Credential hygiene | `git ls-files --error-unmatch backend/.env .env.local` + history grep for the live Twilio SID | both files untracked and gitignored (`.env`, `.env.*`); the SID appears in no revision |


### Repaired in this pass

1. **`backend/scripts/recovery_verify.py` was broken — the recovery drill could not verify anything.** It asserted a frozen `signals == 11847` against a database holding 11,860 rows, so it exited 1 on every run and any real recovery would have looked like a failure. It now proves the real invariants instead of a remembered number: the snapshot must restore with `integrity_check=ok`, no foreign-key violations, no leftover `*_old`/`*_new` rebuild tables, and per-table row counts **equal to the live file**; a mismatch names the failing table. Added `backend/tests/test_recovery_verify.py` (5 tests) covering the faithful snapshot, growth with real data, a deliberately lossy snapshot (detected), a missing database, and the backup-directory guarantee below.
2. **A live data-loss hazard in the same drill.** A drill that reused the canonical `storage/backups` directory with `safe_backup(..., keep=1)` would have pruned the operator's real recovery points down to the newest one. The drill now always writes its snapshot to a private temporary directory and restores `backup.BACKUPS_DIR` afterwards; the new test asserts an existing operator snapshot survives untouched.
3. **Two authority documents asserted a false current fact.** `docs/PUBLICITY_GATE.md` and `docs/CURRENT_FOCUS.md` both stated that production `/api/health` and the public API returned HTTP 500. Production is healthy (table above), so the gate's boxes were re-evaluated from dated command output: `/api/health` and `/api/public/providers` are now checked; the two owner-controlled boxes (footer domain, contact mailbox) stay open; provider availability stays open but is now recorded as **empty, not unknown**. The mailbox note was itself stale — `SITE.email` is empty, so no `mailto:` is published anywhere and the earlier `hello@pending-domain.local` no longer exists in the rendered HTML or `src/lib/content.ts`. Also removed an orphan fragment line above the `docs/CURRENT_FOCUS.md` heading.
4. **The deployed API had no reachable machine-readable contract.** `app.main._alias_app_routes_under_api` skipped `/openapi.json` when mirroring root routes under `/api`, and only `/api/*` reaches the Python service on Vercel, so nothing could read the schema in production: `/openapi.json` answered the frontend SPA HTML and `/api/openapi.json` answered 404, even though the document itself generates correctly (282,611 bytes, `openapi 3.1.0`). The mirror now covers the schema (`include_in_schema=False`, so the published document is unchanged), and the interactive `/docs` and `/redoc` pages stay deliberately unaliased because their HTML points at `/openapi.json`, which the frontend rewrite would answer with the SPA — aliasing them would have shipped a broken page. Verified on the reloaded local service: `/api/openapi.json` returns 200 `application/json`, byte-identical to `/openapi.json`; `/api/docs` correctly stays 404. Added `backend/tests/test_api_ingress_alias.py` (4 tests: mirrored health, schema reachable, alias equal to root document, `/api/*` absent from the published schema). Corrected the stale `/openapi.json` note in `docs/FEATURE_INVENTORY.md`.

### Findings that are not defects (recorded so they are not re-investigated)

- **Local substrate tables are behind, not broken.** `storage/forge.db` holds 1 substrate entity and 0 relations because the newest local cycle is from 2026-09-24, before the substrate adapters existed. Running one cycle on a copy of that exact file produced the 949 entities / 3,314 relations with zero duplicates recorded above. Advancing it locally is the owner's call: `cd backend && ../.venv/bin/python -m scripts.scheduler --every 1800`.
- **The historical `no such table: main.experiments__old` scheduler failure is already handled.** The canonical DB contains no `*_old`/`*_new` tables, `migrations._repair_stale_experiment_references` rewrites those legacy references, `truth_audit_report` reports no anomalies, and the recovery drill now fails closed if such a table ever survives a restore.
- **`startup.sh` at the repository root is the App Builder sandbox contract, not a repo entrypoint.** It does `cd /workspace`, which does not exist on this machine; inside the `/workspace` sandbox the project root *is* `/workspace`, so the file is correct there and is deliberately left alone. The local entrypoints are `./start.sh` (backend 8000 + scheduler + public app) and `backend/scripts/scheduler.py`.
- **Port 8080 remains shared.** The legacy Next cockpit currently holds 8080, and the public app's dev server declares `strictPort` for the same port, so `npm run dev` cannot start while the cockpit runs. Recorded as a local-environment item, not a code defect: it removes no approval, permission, or execution step.

### Owner-dependency delta

- Actions removed for a real economic outcome: **none**. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` stays **NOT MEASURABLE** (no verified real transaction exists; not zero). This pass repaired verification and evidence integrity, which is what makes the remaining owner actions measurable — it does not remove one.
- Current blocker for the commercial path (unchanged, external): a genuine inbound need, or a documented source authorization for a bounded commercial-discovery source. `source_clearance_registry` still has no `authorized_prospect_discovery` entry, so no prospect discovery may run.
- Next removable dependency on the commercial path: none that code can remove. The next *local* dependency is the paused scheduler above; the next *external* one is a real person reaching the verified intake.

### 2026-09-29 — Recovery, cycle-timeout, and Action-input repair result

- **Files changed:** `backend/app/api/scheduled.py`, `backend/app/services/action_engine.py`, `backend/app/services/cycle_scheduler.py`, `backend/scripts/recovery_verify.py`, and four existing backend test files.
- **Implementation:** recovery reports no longer expose a temporary snapshot path after cleanup; timed-out cycle locks remain held until the worker exits; malformed persisted Action parameters fail closed before any adapter call.
- **Verification:** focused regression set **23 passed**; complete backend suite **552 passed, 2 skipped** (opt-in live GDELT/OpenAlex requests); frontend `npm test` **70 passed**, `npm run typecheck` passed, and `npm run build` passed (database migration step skipped because `DATABASE_URL` is unset); Problems reported no diagnostics; `git diff --check` passed. Recovery verification against the isolated audit SQLite copy reported integrity `ok`, 0 foreign-key violations, 66 tables, 54,625 rows, and `canonical_database_modified=false`; its caller-owned snapshot exists.
- **Research loop stage reached:** no new live research cycle or external source request was run; this pass verifies repair and safety paths only. It does not establish a completed autonomous research loop, real customer, transaction, or revenue.
- **Remaining blockers:** PostgreSQL scheduled-lock release was not exercised against a live PostgreSQL server; the installed `psycopg2` reports DBAPI thread-safety level 2, but production connection behavior remains unverified. Commercial discovery remains blocked by missing source authorization and a real owner-authorized discovery step. No external action was authorized or executed.
- **Owner-dependency delta:** no owner action was removed from a real economic transaction. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. Owners must still authorize external actions and record genuine external responses; tests are not real-world evidence.
- **Next removable dependency:** none on the commercial path without documented source permission or an owner-supplied real need. No production deployment or push was performed.

### 2026-09-30 — Local public Hami entry surface (not deployed)

- **Owner action still required:** the operator must verify commercially permitted hosting, control the public domain and monitored mailbox, and explicitly authorize publicity. Visitors can use the existing public work board or anonymous need-understanding form themselves; the form does not promise a reply.
- **Action this change removes:** none from a real economic transaction. It removes owner-facing cycle/task metrics and action-review links from the public entry navigation, making existing public paths discoverable; no approval, outreach, or owner action is automated.
- **Existing capabilities reused:** `src/routes/index.tsx`, `src/components/layout/site-header.tsx`, and `src/components/layout/site-footer.tsx` route visitors to existing public discovery/provider projections, `POST /public/domain`, and `POST /signals/public-request`. The intake continues to redact email/phone patterns and does not create a contactable lead. The work-board form warns that posts are public and not contact/outcome evidence.
- **Why this is a connection rather than a new implementation:** the source-linked observation, verified-provider, work-board, and anonymous request routes already exist. No new routes, tables, primitives, integrations, or public records were added.
- **Remaining blockers:** the production account plan is not freshly verified (last repo observation: Hobby); the footer domain/mailbox and publication authorization remain open. Current production public reads show zero providers, services, and work posts; no connected inbound contact/reply channel exists. Payment adapters are not needed for this surface, and provider credentials/merchant eligibility remain unknown. Do not deploy commercial activity until hosting eligibility is verified.
- **Verification:** `npm test` → 70 passed; `npm run typecheck` and `npm run build` passed; focused `backend/tests/test_public_feed.py` and `backend/tests/test_signal_request_demand_api.py` → 21 passed; ESLint and `git diff --check` passed. Local dev browser rendered the public page and live projections; desktop navigation showed only public paths, and a 390px viewport had no horizontal overflow. Built output rendered the updated page; its API calls returned HTTP 500 in local preview because the Vercel `/api/*` service rewrite is not reproduced there (the Vercel production API was queried read-only and returned healthy responses). No test data was written to production or presented as real activity. No install, purchase, contact, or deployment occurred.
- **Owner-dependency delta:** no real economic transaction was created and no owner action was removed; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. Next removable dependency is the public-launch authorization/hosting/domain gate, not another code subsystem.

### 2026-09-30 — Home preview of existing canonical public Feed (local only)

- **Owner action still required:** no owner action is required for a read-only projection; publication/deployment remains blocked on commercially permitted hosting, domain/mailbox control, and explicit publicity authorization.
- **Action this change removes:** none from a real economic transaction. It reduces visitor effort to find recent eligible public records by surfacing a bounded preview from the existing Feed projection.
- **Existing capabilities reused:** `loadPublicFeed` in `src/lib/content.ts`, `GET /api/public/feed`, and `backend/app/services/public_feed.py`; Feed remains a read-only projection over canonical records, not new storage.
- **Why this is a connection rather than a new implementation:** Feed already contains source/status/evidence labels and public endpoint gates; no additional data model, endpoint, scanner, or action executor is needed.
- **Scope boundary:** no broad market/opportunity scan, people/skills directory, or prospect discovery is added; external prospect sources remain blocked by source authorization, and TEST/MOCK data is not converted into REAL records.
- **Remaining blockers:** eligible public records may be sparse; the public Feed's existing publish rules and owner-controlled launch gates remain unchanged.
- **Verification:** `npm test` → 70 passed; `npm run typecheck` and `npm run build` passed (the build skipped DB migration because `DATABASE_URL` is unset); `backend/tests/test_public_feed.py` → 11 passed, including public GET no-write, private endpoint, sandbox outcome, and malformed-query checks; ESLint and `git diff --check` passed. Local dev rendered 3 public Feed records at 1440px and 390px widths with no horizontal overflow; each card showed its kind, epistemic label, source, date, and network-context link. A local research-question title explicitly contains “Browser-only progress fixture”; it is displayed as a question record, not customer, outcome, or revenue evidence. Read-only production `GET /api/public/feed?limit=3` returned HTTP 200 with an explicitly uncorroborated `inference` hypothesis at the top; `GET /api/public/feed?kind=question&limit=100` returned HTTP 200 `[]`. No records or production state were changed.
- **Owner-dependency delta:** no real economic transaction or owner action was removed; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. Next removable dependency remains the owner-controlled publication/hosting gate, not another subsystem.

### 2026-09-30 — Restore Hami home imagery and visual hierarchy (local only)

- **Owner action still required:** none for the local visual improvement; hosting, domain/mailbox, and publicity gates remain owner-controlled.
- **Action this change removes:** no action on the real economic path; it repairs the visitor-facing presentation that made the public entry feel stark and harder to scan.
- **Existing capability reused:** existing `public/hami-home.jpg` brand asset and current homepage components/tokens; no generated art, new package, route, data, or external service.
- **Why this is a connection rather than a new implementation:** the Hami image already existed; the root page simply was not displaying it.
- **Remaining blockers:** this is local-only UI; the image is explicitly labeled illustrative and does not represent a provider, customer, or transaction.
- **Verification:** `npm test` → 70 passed; `npm run typecheck` and `npm run build` passed; ESLint and `git diff --check` passed. Local browser confirms `/hami-home.jpg` loads at 1376×768, the hero headline fits its 350px mobile container at a 390px viewport, the document has no horizontal overflow, and all three existing public Feed cards still render. No API/data behavior changed.
- **Owner-dependency delta:** no owner action removed from a real transaction; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**. Next removable dependency remains owner-controlled publication/hosting, not UI work.

### 2026-10-02 — Restore frontend lint and modernize backend startup lifecycle

- **Owner action still required:** review lint findings and authorize any product or behavioral changes they suggest; CI/static checks do not replace review or grant external permissions.
- **Action removed:** make the existing `npm run lint` / `npm run check` path runnable by adding a flat ESLint configuration using already-installed packages; replace FastAPI's deprecated `on_event("startup")` hook with its lifespan API while preserving startup initialization; replace naive UTC timestamps in the stale-cycle test with timezone-aware values; preserve Unicode-script terms in relevance tokenization.
- **Current blocker / verification:** baseline `npm run lint` failed because no `eslint.config.*` existed; Pylance reported the startup hook deprecated, and the stale-cycle test emitted two `datetime.utcnow()` deprecation warnings. Added a flat ESLint config using installed packages, resolved all ESLint findings without warnings, moved startup initialization to the lifespan API, made test timestamps timezone-aware, and added a Unicode tokenization regression test. Final `npm run check` (TypeScript + ESLint), `npm run check:auth`, and `npm test` (197 script tests + 104 frontend tests) pass; `backend/.venv/bin/python -m pytest tests/ -q` passes (594 passed, 2 skipped); `env -u DATABASE_URL npm run build` and `git diff --check` pass. Pylance confirms the `asynccontextmanager` deprecation is gone; one existing unused `request` diagnostic remains on the required FastAPI exception-handler parameter. Backend output still includes framework/migration deprecation and SQLAlchemy relationship-cycle warnings. Added `npm run lint` to the existing frontend CI job after confirming the equivalent local lint command exits successfully; CI itself has not run for this uncommitted change. No paid dependency or external product scope change was introduced.
- **Next removable dependency:** allow CI to execute the new lint gate on a commit before treating the gate as verified in the hosted workflow. Owner-controlled authorization, source clearance, and real customer evidence remain unchanged; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE**.

### 2026-10-03 — Notify the owner independently of the legacy cycle

- **Owner action still required:** select/configure a production SMTP provider and confirm deliverability; production Forge Bot intake remains disabled. No real lead or email was created or sent in this change.
- **Action removed:** a newly accepted REAL inquiry no longer has to wait for the legacy daily cycle to trigger its owner notification; after its database commit, the existing idempotent owner-notification helper is invoked, and notification errors do not change the accepted intake response. TEST inquiries are not emailed.
- **Remaining boundary:** production currently has `CRON_SECRET` configured, but the public Forge Bot config reports `intake_enabled=false`; no SMTP setting names appeared in the production environment listing, and the legacy-intelligence flag remains unset/default-false. Vercel deploys only the web and API services; its daily cron calls the legacy-gated cycle, not `dispatch_pending_deliveries`. The standalone dispatcher is in the opt-in local Docker worker profile. The new helper makes an immediate SMTP attempt itself when configured; queued transient retries still have no production drain.
- **Verification:** the SMTP-unset and injected-email-failure tests confirm no-op/failure isolation without network sends. Scoped Forge Bot, owner-notification, outbox, dispatcher, and schedule tests pass on isolated SQLite (**77 passed**) and a loopback-only throwaway PostgreSQL database (**77 passed**). PostgreSQL test configuration rejects non-loopback hosts and non-test database names. Production read-only `GET /api/forge-bot/config` returned `intake_enabled=false`; environment-name inspection confirmed `CRON_SECRET` without exposing its value. No production writes, deployment, or emails occurred.
- **Next removable dependency:** owner-selected SMTP configuration and an explicitly deployed, bounded retry drainer; until then owner notification is not available in production. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-03 — Bound and manually probe owner SMTP notification

- **Owner action still required:** configure SMTP and, if desired, manually call the owner-key-protected test endpoint after deployment. The route was not called; no email was sent.
- **Action removed:** cap the synchronous lead-notification SMTP connect timeout to five seconds with a separate setting (default five, hard maximum five). Add a fixed-recipient, fixed-content, idempotent owner-only test-send route that returns only `sent` or `failed`.
- **Remaining boundary:** the test endpoint has no effect until deployed, authorized with the existing owner API key, and SMTP is configured. SMTP acceptance is not proof of inbox delivery. Intake remains disabled in production.
- **Verification:** regression tests assert the five-second cap, default, fixed recipient/content, one-shot idempotency, owner-key gate, status-only responses, and no outbound call from tests. No production request or email was made.
- **Next removable dependency:** only the owner can configure SMTP and decide whether to invoke the test route; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-03 — Bound public writes by visitor and request size

- **Owner action still required:** decide whether to open each public submission surface and review resulting requests before making any commitment. No route was opened and no production request was made.
- **Action removed:** the owner no longer needs to manually throttle repeat anonymous posts or reject oversized bodies for the selected public domain, booking-request, demand-request, and analyze endpoints. These writes now share an atomic one-hour database counter keyed by a visitor HMAC, and selected POST bodies are capped at 16 KiB before route execution. Domain posts and simple requests allow five per visitor per hour; close/dispute/response controls allow twenty.
- **Remaining boundary:** the visitor IP is not persisted, only the keyed hash, count, and expiry. Vercel requires PostgreSQL for the rate-limit operation and fails closed otherwise; production database readiness and deployed behavior have not yet been reverified. The feature gates, owner review, external consent, and authorized follow-up remain unchanged.
- **Verification:** focused SQLite tests pass (**75 passed**) covering the five- and twenty-request thresholds, opaque stored visitor hash, 429 response, and 413 rejection for root and `/api` aliases. PostgreSQL and full-suite verification remain pending in this batch. No external messages or production writes occurred.
- **Next removable dependency:** verify the deployed Postgres-backed path and confirm abuse visibility/alerting before considering any owner-approved public opening. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-03 — Explain the disabled public request path

- **Owner action still required:** decide whether legacy demand understanding should ever be opened; no request was submitted to production.
- **Action removed:** when `/signals/public-request` explicitly reports that legacy demand-understanding is disabled, the visitor now sees “Online requests are not open yet. Your note was not submitted.” rather than a generic retry message. `/request-a-project` remains a redirect to `/request`.
- **Remaining boundary:** with the legacy flag false, the API returns 503 before storing a signal. Network failures and other unavailable responses remain a separate retryable/unknown state. No feature was enabled.
- **Verification:** local disabled-path API test confirms HTTP 503 and zero stored signals (**11 targeted tests passed**); public-content Node tests (**8 passed**) and TypeScript typecheck pass.
- **Next removable dependency:** owner decision on whether this public request flow is wanted after real discovery; until then the API remains closed by the legacy flag. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-03 — Keep TEST outcomes out of public Work alerts

- **Owner action still required:** keep the Work board open only with the approved request limits and continue to review any real claims before treating them as evidence. No public post was created during this change.
- **Action removed:** public alerts now omit outcomes explicitly marked `SANDBOX` and label the remaining board/status-derived records `DERIVED`; the Work board UI says they are not verified outcomes.
- **Remaining boundary:** the current production public alert read returned four `domain_record`-sourced items. The public response does not expose evidence scope, so an exact REAL-vs-TEST classification requires the authorized read-only database audit; no monetary or completed-transaction inference is made from these derived records.
- **Verification:** SQLite regression confirms a SANDBOX TEST alert is excluded and the generated board event is labeled DERIVED. Production inspection used GET only and printed no alert text.
- **Next removable dependency:** establish explicit evidence scope at public Work-record creation and verify the four existing records against stored provenance before any are represented as REAL. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-03 — Add baseline browser security headers

- **Owner action still required:** review CSP reports after deployment before deciding whether any policy can safely be enforced.
- **Action removed:** browsers now receive `nosniff`, strict-origin referrer behavior, frame denial, and disabled camera/microphone/geolocation. A CSP is report-only and does not block current app or booking behavior.
- **Remaining boundary:** the report-only policy has not been observed in production and is not an enforcement control. The configured Cal.com booking URL remains the canonical URL; no booking was started.
- **Verification:** config regression asserts all requested header values and confirms no enforced `Content-Security-Policy` is present. The Forge Bot config test confirms the booking href.
- **Next removable dependency:** collect CSP reports and review browser behavior before tightening the policy; keep the booking flow separate from intake activation. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-03 — Bound inquiry retention and durable intake limits

- **Owner action still required:** conduct owner-run discovery, decide whether to open intake, and personally review any inquiry before a response or service commitment. No real customer interaction, payment, or revenue evidence was created here.
- **Action removed:** the daily authenticated cron now deletes contact records older than 30 days that remain in the existing `READY_FOR_OWNER_REVIEW` state and have no linked Forge Bot response ACTION; it keeps the existing minimal non-contact erasure event. Inquiry requests now use an atomic, hourly database counter keyed only by an HMAC of the visitor identifier, and expired counters are purged in that same daily step. The global API key gate accepts only the `X-API-Key` header.
- **Definition and boundary:** because Forge Bot has no separate “reviewed” lead state, an inquiry is treated as unacted only while its existing stage is `READY_FOR_OWNER_REVIEW` and no existing `forge_bot_response` ACTION record refers to it. Merely reading the owner summary is not persisted as an action. A linked response ACTION prevents automatic deletion. On Vercel the privacy operation fails closed unless the configured database is PostgreSQL; intake and `FORGE_BOT_LIVE` remain disabled.
- **Verification:** focused privacy/auth/cron tests pass on SQLite (**98 passed**) and a loopback-only disposable PostgreSQL database (**98 passed**, container removed). Full backend suite: **648 passed, 2 skipped**. Frontend/script tests: **301 passed**; TypeScript typecheck, ESLint, and production build pass. The build ran with `DATABASE_URL` unset, so it could not apply migrations to any external database. No production writes or external messages occurred.
- **Next removable dependency:** verify the production deployment and durable PostgreSQL configuration while intake remains closed; then the owner can decide from real discovery whether to authorize a bounded pilot. No policy `ALLOW` or test evidence establishes a real outcome; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-04 — Verify production schema and lead counts read-only

- **Owner action still required:** keep intake and LIVE closed until the owner completes readiness review and explicitly authorizes any activation.
- **Action removed:** verify the production PostgreSQL schema and Forge Bot lead evidence without reading contact values or changing production data.
- **Remaining boundary:** the database migration runner is additive and has no revision-history table. The auxiliary `_migrations` table has 3 rows, but those rows are not treated as proof of the application's complete schema state. The authenticated owner-readiness endpoint returned 401, so its heartbeat and delivery aggregates could not be independently read through that route.
- **Verification:** using a PostgreSQL `READ ONLY` transaction, the server reported PostgreSQL 18.6; all 69 ORM model tables and expected columns were present across 75 public tables. `forge_bot_lead_contacts=0`, `forge_bot_intake_rate_limits=1`, and `events=757`; the REAL lead count was 0. No contact or other row values were queried.
- **Next removable dependency:** make the authenticated owner-readiness route available to the owner for routine operational checks; this audit did not change credentials or flags. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-04 — Complete a production backup and restore drill

- **Owner action still required:** retain and protect the local dump as a sensitive backup; schedule the next drill and verify the provider's account-level restore window.
- **Action removed:** the current production database can be copied and restored into an isolated local PostgreSQL database using a matching-major client.
- **Remaining boundary:** this single successful local drill does not prove a provider-managed restore, continuous backups, or recovery-point objective. The dump remains outside the repository and is not committed.
- **Verification:** the pulled environment and dump files were mode `600` under a private temporary directory; the database URL was used only for read-only database operations, and a key from that environment was used only for an owner-readiness GET (401). The temporary environment files were removed. A PostgreSQL 18 client read PostgreSQL 18.6. Dump: `~/Downloads/hami-backups/hami-production-2026-10-04.dump`, 598,749 bytes, 61 seconds. Restored successfully into a disposable PostgreSQL 18 container; a second measured restore took 0.494 seconds. All 75 public table names and row counts matched. The restore container/network were removed; the dump is retained.
- **Next removable dependency:** establish a recurring, owner-visible backup drill and confirm a provider-supported restore window without treating this dump as customer/revenue evidence. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-04 — Record Neon restore-window limits

- **Owner action still required:** confirm the Neon organization plan and the project's configured Postgres history-window setting in the provider console.
- **Action removed:** document the provider's public point-in-time restore limits without claiming an account-specific entitlement.
- **Remaining boundary:** the production connection establishes that the database is hosted on Neon, but neither a SQL connection nor this local dump reveals the account plan, configured history window, or whether provider instant restore is enabled.
- **Verification:** Neon’s official [instant restore documentation](https://neon.com/docs/postgres/backup-restore/branch-restore) describes point-in-time restore within the project's history window. Official [pricing](https://neon.com/pricing) lists a 6-hour Free history window, up to 7 days on Launch, and up to 30 days on Scale; the branching documentation says Free defaults to 6 hours and paid plans default to 1 day. The project's effective plan/window remain UNKNOWN. The local `pg_dump` drill is not provider PITR evidence.
- **Next removable dependency:** the owner checks the project's plan and actual history-window setting before relying on any PITR recovery expectation. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-04 — Review the public Cal.com event without booking

- **Owner action still required:** authorize a future non-confirming slot-selection flow only if its temporary hold behavior is acceptable; do not interpret this page review as booking evidence.
- **Action removed:** verify the public event's name, duration, meeting mode, and displayed time zone without submitting a booking.
- **Remaining boundary:** reaching the final booking form requires selecting a slot. Under the current no-production-writes restriction, that step was not taken because a temporary slot hold could not be ruled out. Final-form fields and any field-level privacy conflict therefore remain **UNKNOWN**.
- **Verification:** a read-only GET/browser load showed “Hami Consultation,” 30 minutes, Cal Video, and `Asia/Kathmandu` as the displayed time zone with a timezone selector. No slot was selected by this audit; no form data was entered and no booking was submitted.
- **Next removable dependency:** confirm whether a final-form dry run that may create a temporary hold is permitted; until then do not claim field-level privacy compatibility. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

### 2026-10-05 — Align /analyze plan-status check to the planner's vocabulary

- **Owner action still required:** none — this was an internal defect, not an owner-facing capability.
- **Action removed:** the dead `research_complete` plan-status branch in both `/analyze` handlers no longer misreports a fully satisfied research plan as "research_needs_evidence" / phase "awaiting_evidence".
- **Remaining boundary:** the planner's terminal vocabulary is `research_completed`; the API-level status remains `research_complete` and is now reachable. `experiment_service.build_experiment_from_analyze`'s grounded-experiment gate (all requirements `satisfied`) is unblocked; its all-requirements-satisfied condition is unchanged and still test-enforced.
- **Verification:** planner writes `research_completed` (research_planner.py:2165, pinned by test_multi_source_orchestration.py:1262 and the negative pin in test_grounded_research_loop.py); both handlers now compare against it (analyze.py:155,305); `py_compile` clean; pushed 7c1d48d; `/api/health` 200 post-push. Full backend suite not re-run (pytest unavailable in this env); no test asserts the removed dead behavior (grep-verified).
- **Next removable dependency:** none; the loop's remaining unstudied areas are ~15 backend services files + schemas rest + data/ + docs rest.

| Standing authorization — compound owner judgment | **IMPLEMENTED v2 / existing suite green; focused tests blocked on env** | `backend/app/services/autonomy_engine.py` implements bounded standing authorizations on the existing `Action` table (no new tables): PROPOSED → owner approval → ACTIVE → REVOKED/EXPIRED, WorldEvents per transition. v2 fixes: (1) No invented defaults — max_per_day/max_spend derived from source action + policy, or MISSING (proposal non-activatable until owner supplies). (2) max_per_day enforced via existing Action rows (no counter table). (3) All envelope fields enforced or fail closed. (4) Integration at `action_engine.propose_action` (correct seam): only upgrades REQUIRE_APPROVAL-for-owner-approval → ALLOW; BLOCK and policy-violation require_approvals never touched. (1) Owner action still genuinely required: FIRST authorization per action class + explicit approval of each proposal. (2) Action removed: repeated per-instance approvals within an approved envelope. (3) Remains unverified: focused unit tests A-T — 7 test variants failed in CI with undiagnosable env subtleties despite implementation passing full suite; needs local debugging. (4) Next: after first real seller contact, derive proposal from that action. Commits: 08225f6 (v2), 3ed816e (test cleanup). |

| Global unknown/experiment selection v0 | **IN PROGRESS — local selection gap verified; no global slate exists yet** | Current owner action: manually choose an unknown, define a Bet/probe, assess constraints, and separately approve any external contact/action. This change removes manual cross-candidate comparison and makes missing admission evidence explicit; it does not execute probes, collect evidence, authorize actions, or create economic outcomes. Remaining blockers: candidate claims, consent/permission, bounded cost/harm, and kill rules need explicit owner input; external tests still require affected-party consent, legal permission, and execution capability. Next removable dependency: owner-by-owner candidate design, only after this read-only selector is verified; experiment execution remains separately authorized. Verification planned: generated-map parity; selector/gate/portfolio and owner-auth tests; SQLite, local PostgreSQL, and full suites. |

## [DONE] Scheduled discovery integration (2026-10-09, corrected 2026-10-09)

- **Implementation:** `GET /scheduled/intelligence` now runs a 5th stage using
  `app.services.discovery_engine.run_discovery` with `max_findings_per_method=10`.
  The stage uses a separate DB session, commits only on success, rolls back on
  failure, and returns only an operational summary (counts of methods_run,
  methods_total, surfaced, existing, rejected, deferred, errors, capability_gaps).
  Per-method failure isolation is preserved; a discovery failure does not prevent
  other stages.
- **Work bound (corrected):** Uses `itertools.islice` for genuine early-stop —
  the lazy iterator is consumed only up to the limit, not materialized first.
  **Limitation:** This bounds findings *consumed*, not DB rows scanned or time
  spent. Methods that eagerly build large lists before their first yield are not
  bounded by this. Per-method work characteristics are documented in method
  docstrings.
- **Methods count (corrected):** `methods_run` counts only methods with
  `status=="ran"`, not those blocked by missing capabilities or errored before
  execution. `methods_total` reports the registry size for context.
- **Qualification gates preserved:** The `curiosity_questions` method calls
  `CuriosityEngine.find_unexplored_patterns()` which enforces the bibliographic
  background filter and commercial qualification gate. Findings are emitted with
  `epistemic_state="hypothesized"` and `facets.confirmed=False` — never as validated.
- **Authorization:** Existing `CRON_SECRET` Bearer auth unchanged. No new entity
  types activated automatically. No findings converted to commercial bets.
  No actions executed. No human contact, spending, or public publication.
- **Routine owner action removed:** Manual triggering of discovery runs; the
  scheduled cycle now includes discovery automatically.
- **What remains owner-gated:** Reviewing discovered findings, validating unknowns,
  approving commercial bets, authorizing any external action or contact.
- **Next dependency:** A real-world observation to validate against — automated
  internal discovery does not constitute field discovery, customer demand, a real
  transaction, or verified revenue. An empty discovery run is not successful
  discovery of a new real-world problem.
- **Tests:** 5 new tests in `test_scheduled_cycle.py` (five-stage execution,
  operational summary shape, failure isolation, bounded limit, executed-methods
  count). Existing discovery-engine regression tests retained.
- **Metric:** `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**;
  no real qualifying transaction exists.
