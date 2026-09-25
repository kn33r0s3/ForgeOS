# CURRENT_FOCUS.md — BP-4: Public Serializer Audit

**Last updated**: 2026-09-25
**Work order**: [SERIAL_PATH.md](SERIAL_PATH.md) is the only queue.

## Current state

`docs/FUTURE_BLUEPRINT.md` defines ForgeOS as an open-ended, autonomous value-creation system. The 2026-09-25 Build Path is the current sequential implementation order. Keep work serial, and rescan the full observe-to-learning loop after each integrated capability.

S11's generalized public feed, S12's scoped context, S13's governed source registry, and S14's same-run evidence-to-network cycle are implemented. The previous S15 type-registry/world-graph framing has been superseded. BP-1's shared evidence-aware labels/compliance gate, BP-2's bounded agenda, and BP-3's signal → claim → question → opportunity publication chain are implemented. BP-4 is active: audit every public serializer for internal scoring or confidence fields.

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

## BP-1 complete

- [x] Facts and independently corroborated external claims map to `supported`.
- [x] Single-source observations and claims map to `observed`.
- [x] Direct conflicts map to `contested`; inferences and unknowns are excluded.
- [x] Stale evidence adds a separate `stale: true` flag without changing the label.
- [x] Discoveries, feed/context, and matching share the same label function.
- [x] Regulated-asset claims require an explicit compliance review before publication.
- [x] BP-1 mapping, stale-evidence, and compliance tests pass.

## BP-2 complete

- [x] One fixed, deduplicated agenda covers Nepal work/services/trade/housing/money/infrastructure and the wider asset surface for research only.
- [x] Repeated cycle runs do not duplicate a question; no-result questions remain open and can reuse the existing task.
- [x] Per-cycle collection reuses the current configured batch limit and never exceeds it.

## BP-3 verification target

- [x] A signal with no linked claim is absent from `/discoveries`.
- [x] A claim whose only evidence is stale retains its BP-1 label and exposes `stale: true`.
- [x] An opportunity is publicly reachable only through its stored signal/claim/question path.

## BP-4 verification target

- [ ] One automated audit covers every public response schema.
- [ ] Internal field names matching score/confidence and known private ranking markers fail the audit.

## Continuous rescan

After BP-4 is integrated and verified, proceed to BP-5 in `SERIAL_PATH.md`, then trace the full capability loop again after every completed task. Finite task numbers are never a stopping condition.

## S10 pilot gate

A real provider still requires evidence and operator review; a booking still requires an operator-submitted request. These are gates on those records, not on generalized feed engineering. Never fabricate a person or contact anyone on their behalf.

## Separate publicity gate

The footer domain and contact mailbox remain pending until the operator supplies a domain they control and a monitored mailbox. See [PUBLICITY_GATE.md](PUBLICITY_GATE.md).

The cycle trigger also needs a production deployment and a configured `CRON_SECRET`; its once-daily schedule invokes the canonical runner only. It does not publish providers, send messages, or invent prices.
