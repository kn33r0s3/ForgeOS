# ForgeOS capability claim ledger

This is the active human/agent claim ledger required by
`FORGE_SUBSTRATE_BLUEPRINT.md`. Search it before work, claim a bounded scope
before implementation, and record verification before marking a claim DONE.
Claims coordinate contributors; database uniqueness and idempotency remain the
enforcement layer when claims overlap.

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
- Verification status before this contract refresh: `tests/test_gdelt_collector.py -v` → **7 passed, 1 skipped, 1 warning**; combined regressions → **72 passed, 1 skipped, 8 warnings**; complete backend → **411 passed, 1 skipped, 22 warnings**. Refreshed contract changes are pending re-verification in the execution report.
- Previous live result: the bounded `"supply chain" OR agriculture` query returned HTTP 429 with “Please limit requests to one every 5 seconds or contact kalev.leetaru5@gmail.com for larger queries.” No metadata, Evidence, or Signal was then persisted. The refreshed one-request/live persistence check will determine whether access is now available.
