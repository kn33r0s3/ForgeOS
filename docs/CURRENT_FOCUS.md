# CURRENT_FOCUS.md — S15: General Entities and Actor Capabilities

**Last updated**: 2026-09-25
**Work order**: [SERIAL_PATH.md](SERIAL_PATH.md) is the only queue.

## Current state

S11's generalized public feed, S12's scoped context, S13's governed source registry, and S14's same-run evidence-to-network cycle are implemented. S15 audits shared actor/resource identity and generalizes typed endpoint resolution only where the canonical records and connections need it. S10 remains evidence-gated; no provider, price, booking, payment, response, or outcome may be invented.

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

- [ ] Feed and context references resolve to existing canonical records with each record's own visibility rules.
- [ ] Typed connections can point to general actors/capabilities/resources without copying provider, signal, opportunity, action, or outcome data.
- [ ] Add a shared identity record only if an evidenced cross-record identity cannot be represented safely by existing records and typed connections.
- [ ] Tests reject dangling or private endpoint exposure and preserve provider contact privacy.

## S10 pilot gate

A real provider still requires evidence and operator review; a booking still requires an operator-submitted request. These are gates on those records, not on generalized feed engineering. Never fabricate a person or contact anyone on their behalf.

## Separate publicity gate

The footer domain and contact mailbox remain pending until the operator supplies a domain they control and a monitored mailbox. See [PUBLICITY_GATE.md](PUBLICITY_GATE.md).

The cycle trigger also needs a production deployment and a configured `CRON_SECRET`; its once-daily schedule invokes the canonical runner only. It does not publish providers, send messages, or invent prices.
