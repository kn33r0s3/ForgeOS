# Current focus — NetworkConnection → substrate relation adapter

**Architecture authority:** [`FORGE_SUBSTRATE_BLUEPRINT.md`](../FORGE_SUBSTRATE_BLUEPRINT.md)
**Claim ledger:** [`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md)
**Work order:** serial; claim → build → test → integrate → verify → record.

The ORM defines models for `type_registry`, `entities`, `relations`, `events`,
`evidence`, and `capabilities`. A read-only inspection of the existing
`storage/forge.db` found only `evidence` among those six physical tables;
`type_registry`, `entities`, `relations`, `events`, and `capabilities` are not
yet present there. Existing operational and vertical tables, including
signals/patterns/beliefs/opportunities and actions/outcomes, are present and
remain authoritative during additive migration. The mature first adapter is
Signal → Pattern → Belief → Opportunity.

Wave 1 is verified: the full backend suite passed (313 tests), including shared
JSON Schema validation/type lifecycle, evidence-backed truth transitions,
canonical identity/deduplication and merge history, uniqueness/idempotency,
provenance, source/adapter consistency, and SQLite restart behavior. The real
legacy database was inspected read-only and left unchanged.

The Action → Outcome → LearningEvent adapter is verified and runs from the
canonical cycle. The legacy operational tables remain write authority. An
Action is projected only after authorization and execution start are recorded;
an authorized `Experiment` attempt is a fallback only when no corresponding
`Action` row exists. Outcomes and learning remain linked through existing
source identifiers and explicit provenance.

The active claim maps the existing `NetworkConnection` workflow into substrate
relations while preserving the workflow row as the migration-stage write
authority. Feed and Network stay projections; endpoint visibility and source
provenance remain required.

Earlier S10–S14 and BP work remains recorded in `SERIAL_PATH.md` as history.
Its prior `NetworkConnection`-first substrate direction is superseded by the
Universal Substrate amendment.
