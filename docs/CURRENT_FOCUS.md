# Current focus — Explicit ResearchQuestion source relations

**Architecture authority:** [`FORGE_SUBSTRATE_BLUEPRINT.md`](../FORGE_SUBSTRATE_BLUEPRINT.md)
**Claim ledger:** [`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md)
**Work order:** serial; claim → build → test → integrate → verify → record.

Wave 1's six logical primitives are in the ORM with additive migration
support. The read-only legacy database inspection found `evidence` as the only
one of those six already present as a physical table; the other five are not
yet present. The first canonical path remains Signal → Pattern → Belief →
Opportunity.

Verified adapters now cover the intelligence path; authorized Action, Outcome
and LearningEvent; NetworkConnection relations; Provider and ServiceListing;
runtime ToolRegistry capabilities; Claim, ResearchQuestion, DomainRecord and
Decision; historical Evidence; and explicit EvidenceRelationship → Claim links.
The `/forge/substrate` API routes writes through the canonical services. Feed
and Network remain read projections and existing tables retain their
migration-stage authority.

Historical Evidence now maps incrementally to its explicit Belief,
ScenarioPrediction, Opportunity, or Signal subject in the same row, preserving
all legacy raw fields and confidence scales. The verified
EvidenceRelationship adapter maps explicit Evidence → Claim links to source-
linked WorldRelations, without adding Evidence rows or changing Claim state.
The complete backend suite passed after these slices (355 tests, 21 existing
warnings).

The active claim covers explicit `ResearchQuestion.source_pattern_id`,
`source_belief_id`, and `source_claim_id` links. A read-only audit found 89
ResearchQuestions, including 23 Pattern links and 52 Belief links; these
foreign keys are not yet projected as substrate relations. The adapter will
preserve those source links without interpreting question text.

Earlier S10–S14 and BP work remains recorded in [`SERIAL_PATH.md`](../SERIAL_PATH.md)
as history. Its prior `NetworkConnection`-first substrate direction is
superseded by the Universal Substrate amendment.
