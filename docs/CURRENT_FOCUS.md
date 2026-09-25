# CURRENT_FOCUS.md — S13: Governed Source Registry

**Last updated**: 2026-09-25
**Work order**: [SERIAL_PATH.md](SERIAL_PATH.md) is the only queue.

## Current state

S11's generalized public feed and S12's scoped network context are implemented. S13 makes the governed source layer extensible beyond the single currently cleared GovInfo document. S10's pilot remains evidence-gated; that gate does not block engineering. No provider, price, booking, or outcome may be invented.

The feed uses existing source visibility rules and shows chronological activity without popularity or trust scores. Context queries return only already-public feed items. Local tests/build do not prove production deployment. Production was last reported healthy on 2026-09-25 and has not been rechecked in this session.

## S11 completed

- [x] A typed feed projection covers externally evidenced signals, linked research/knowledge/opportunity, public work, verified capabilities/actors, public connections, and real outcomes.
- [x] Feed entries retain canonical IDs, epistemic state, provenance, and typed relations.
- [x] Feed integration tests, UI, build/typecheck, and desktop/mobile browser verification pass.

## S12 completed

- [x] Feed item and relation links open a scoped network context.
- [x] Only public related records appear; hidden endpoints and incomplete filters return no data/validation error.
- [x] Context can be cleared; typecheck/build and browser interaction pass.

## S13 acceptance

- [ ] Source approvals are represented in one validated registry with scope, geography/category, evidence references, and review/expiry dates.
- [ ] Collector dispatch uses the registry; unknown, expired, changed-terms, robots-blocked, or redirect-out-of-scope URLs fail closed.
- [ ] Existing GovInfo clearance still passes; an unapproved source cannot fetch.
- [ ] Feed provenance retains the source identity and canonical reference.

## S10 pilot gate

A real provider still requires evidence and operator review; a booking still requires an operator-submitted request. These are gates on those records, not on generalized feed engineering. Never fabricate a person or contact anyone on their behalf.

## Separate publicity gate

The footer domain and contact mailbox remain pending until the operator supplies a domain they control and a monitored mailbox. See [PUBLICITY_GATE.md](PUBLICITY_GATE.md).

The cycle trigger also needs a production deployment and a configured `CRON_SECRET`; its once-daily schedule invokes the canonical runner only. It does not publish providers, send messages, or invent prices.
