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
- Status: claimed — audit and contract established; implementation not started.
