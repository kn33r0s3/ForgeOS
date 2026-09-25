# Current focus — Wave 1 Universal Substrate

**Architecture authority:** [`FORGE_SUBSTRATE_BLUEPRINT.md`](../FORGE_SUBSTRATE_BLUEPRINT.md)
**Claim ledger:** [`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md)
**Work order:** serial; claim → build → test → integrate → verify → record.

The repository already contains physical tables for `type_registry`, `entities`,
`relations`, `events`, `evidence`, and `capabilities`. Existing operational and
vertical tables remain functional during additive migration. The mature first
adapter is Signal → Pattern → Belief → Opportunity; its source tables remain
authoritative in Wave 1.

The active claim hardens shared JSON Schema validation and type lifecycle,
evidence-backed truth transitions, canonical identity/deduplication and merge
history, uniqueness/idempotency, provenance, and source/adapter consistency.
Wave 1 must pass those checks, including restart behavior, before any new domain
or alternate Feed/Network storage is started.

Earlier S10–S14 and BP work remains recorded in `SERIAL_PATH.md` as history.
Its prior `NetworkConnection`-first substrate direction is superseded by the
Universal Substrate amendment.
