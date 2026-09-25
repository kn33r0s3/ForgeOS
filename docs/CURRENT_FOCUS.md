# CURRENT_FOCUS.md — Continuous Capability Development / S15: World Relations

**Last updated**: 2026-09-25
**Work order**: [SERIAL_PATH.md](SERIAL_PATH.md) is the only queue.

## Current state

`docs/FUTURE_BLUEPRINT.md` defines ForgeOS as an open-ended, autonomous value-creation system. Its numbered tasks are near-term work evidence, never the system boundary or a stopping condition. Keep work serial, and rescan the full observe-to-learning loop after each integrated capability.

S11's generalized public feed, S12's scoped context, S13's governed source registry, and S14's same-run evidence-to-network cycle are implemented. The S15 audit found `NetworkConnection` doubles as a match/action workflow but lacks general relation predicates, explicit epistemic state, temporal/context fields, and reusable typed endpoint adapters. This is the current implementation focus. It must extend existing canonical records, preserve public visibility gates, and avoid a second entity store.

S10 remains evidence-gated; no provider, price, booking, payment, response, or outcome may be invented. Local test results are not evidence of a live deployment.

The only active external clearance is one exact GovInfo document, valid through 2026-09-25 UTC. Every other collector stays disabled until its source is reviewed and entered in the registry. Local tests/build do not prove production deployment. Production was last reported healthy on 2026-09-25 and has not been rechecked in this session.

## S11 completed

- [x] A typed feed projection covers externally evidenced signals, linked research/knowledge/opportunity, public work, verified capabilities/actors, public connections, and real outcomes.
- [x] Feed entries retain canonical IDs, epistemic state, provenance, and typed relations.
- [x] Feed integration tests, UI, build/typecheck, and desktop/mobile browser verification pass.

## S12 completed

- [x] Feed item and relation links open a scoped network context.
- [x] Only public related records appear; hidden endpoints and incomplete filters return no data/validation error.
- [x] Context can be cleared; typecheck/build and browser interaction pass.

## S13 completed

- [x] A typed registry validates exact HTTPS scope, source ID, geography/category, bounded need, review evidence, and review/expiry dates.
- [x] Dispatch, direct web collection, tool adapters, CLI, and research tasks fail closed for unknown/expired URLs; robots, terms, and redirect scope are checked live.
- [x] A database-backed rate gate serializes requests across SQLite/PostgreSQL instances; only the one reviewed GovInfo target is enabled.
- [x] Registry identity and canonical source URL remain in signal provenance; tests cover unauthorized collectors and route bypasses.

## S14 completed

- [x] A bounded second internal pass now structures signals collected during the scheduled run, without starting a second fetch or executing an external commitment.
- [x] Canonical cycles restore source links, connect unclaimed external evidence to observed claims, scan typed network connections, and report these transitions.
- [x] Opportunity hypotheses now reach the public feed through their existing evidence/signal/claim chain; no parallel record is added.
- [x] Policy gates for external actions remain active. Real response/outcome recording and learning continue through the existing actual-outcome path.
- [x] Full backend integration tests pass with network-free fixtures in isolated test storage.

## S15 acceptance

- [x] Feed/context canonical references resolve through endpoint adapters; legacy `post` / `knowledge` labels map to existing canonical records.
- [x] Relations have extensible predicates, direction, epistemic state, optional strength/uncertainty, evidence links, provenance, context, conditions, and validity time.
- [x] Relation workflow state remains independent from epistemic state; supported relations require stored evidence.
- [x] Relation-to-relation endpoints compose without copying endpoint data.
- [x] Public feed resolves both endpoints through original visibility rules, including relation chains; a public edge cannot expose a hidden or dangling record.
- [x] Matching preserves its response vocabulary and persists canonical endpoint types.
- [ ] Run migration and full integration verification; then rescan for the next missing capability.

## Continuous rescan

After S15 passes its migration and integration tests, trace world → observation → representation → relation → understanding → possibility → capability → opportunity → authorized action → outcome → learning → capability expansion. Replace this focus with the next code-backed gap. Do not stop because S16 or another finite list ends.

## S10 pilot gate

A real provider still requires evidence and operator review; a booking still requires an operator-submitted request. These are gates on those records, not on generalized feed engineering. Never fabricate a person or contact anyone on their behalf.

## Separate publicity gate

The footer domain and contact mailbox remain pending until the operator supplies a domain they control and a monitored mailbox. See [PUBLICITY_GATE.md](PUBLICITY_GATE.md).

The cycle trigger also needs a production deployment and a configured `CRON_SECRET`; its once-daily schedule invokes the canonical runner only. It does not publish providers, send messages, or invent prices.
