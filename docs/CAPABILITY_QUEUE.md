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
