# Current focus — Explicit EvidenceRelationship substrate adapter

**Architecture authority:** [`FORGE_SUBSTRATE_BLUEPRINT.md`](../FORGE_SUBSTRATE_BLUEPRINT.md)
**Claim ledger:** [`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md)
**Work order:** serial; claim → build → test → integrate → verify → record.

Wave 1's six logical primitives are present in the ORM with additive migration
support. A read-only inspection of the legacy database found only `evidence`
among those six physical tables; the other five are not yet present. The mature
Signal → Pattern → Belief → Opportunity path remains the first canonical
adapter.

Verified adapters cover the intelligence path; authorized Action attempts,
Outcome and LearningEvent; NetworkConnection relations; Provider and
ServiceListing; runtime ToolRegistry capabilities; Claim, ResearchQuestion,
DomainRecord and Decision; and historical Evidence. The generic
`/forge/substrate` API uses canonical validation and lifecycle services. Feed
and Network remain read projections; existing source tables retain their
documented migration-stage authority.

The historical Evidence adapter maps existing Evidence rows onto canonical
Belief, ScenarioPrediction, Opportunity, or Signal entities, without adding
Evidence rows or changing raw payloads/confidence scales. It advances in
bounded batches and leaves ambiguous or incomplete records unresolved. The
full backend suite passed after that slice (351 tests, 19 existing warnings).

The active claim maps explicit `EvidenceRelationship` links into substrate
relations. A read-only audit found 51 legacy links, all `derived_from` edges to
Claims. The source link and Evidence rows remain authoritative; graph endpoints
and relations are source-linked projections with no guessed edges or target
truth changes.

Earlier S10–S14 and BP work remains recorded in [`SERIAL_PATH.md`](../SERIAL_PATH.md)
as history. Its prior `NetworkConnection`-first substrate direction is
superseded by the Universal Substrate amendment.
