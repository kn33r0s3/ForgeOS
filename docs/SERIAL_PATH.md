# Serial path

This is ForgeOS's single active work queue. Execute one task at a time:
claim it here, build, test, integrate, verify, then record the evidence and
actual result before claiming the next. Re-scan the full capability loop after
each task. Task numbers are not a product boundary or stopping condition.

## Blueprint authority and amendments

`docs/FUTURE_BLUEPRINT.md` is the architecture authority; this file is the
single sequential implementation queue. The older six-primitives/type-registry
framing is superseded. A future pasted blueprint is an amendment proposal:
diff it against the current architecture, append a dated numbered amendment,
then update this queue. A full incompatible rewrite requires a human checkpoint
before implementation.

## Current status

S11 through S14 are complete. The earlier S15 type-registry/world-graph
framing is superseded by the end-state blueprint and the Build Path dated
2026-09-25. Existing committed code remains in place, but new work follows the
canonical-record/`NetworkConnection` path. Do not add new domains to the
type-registry framing.

**BP-1 — Canonical epistemic-label mapping. DONE (2026-09-25).** Added
`backend/app/services/public_epistemics.py` and routed `/discoveries`, the
public feed/context, and knowledge matching through its label and compliance
gate. Facts and independently corroborated external claims map to
`supported`; observations and single-source claims map to `observed`; direct
conflicts map to `contested`; inferences/unknowns are excluded. Staleness is a
separate flag. Regulated classes require an approved review with reviewer and
reference in claim provenance. Focused BP-1/public tests passed: 34.

**BP-2 — Standing research agenda, bounded per-cycle collection. DONE
(2026-09-25).** Extended the fixed agenda with derivatives and hedge-fund
research and made insurance/reinsurance explicit. Empty or failed collection
reopens the question; a later cycle reuses its task rather than duplicating it.
Daily execution continues to use only `FORGEOS_COLLECT_LIMIT`. Focused BP-2
tests passed: 11.

**BP-3 — Discoveries link the full chain without skipping evidence rules. DONE
(2026-09-25).** `/discoveries` remains claim/evidence/signal-gated and exposes
the separate stale flag; the feed now requires a public research question
between a claim and its opportunity. Focused BP-3/public tests passed: 11.

**[CLAIMED] BP-4 — Public world shows only what passes publication rules.**
Audit every public response schema for internal scoring/confidence fields, then
add one automated contract test.

S10 remains evidence-gated for real provider verification and operator-submitted
bookings. Never seed providers, prices, bookings, payments, or outcomes. Local
tests do not establish a live deployment.

## Build Path (strictly sequential)

### BP-1 — Canonical epistemic-label mapping [DONE]

One `derive_public_label` function maps internal claim state and stored
evidence to `observed`, `supported`, or `contested`, plus a separate `stale`
boolean. Facts map to supported; external claims require at least two
independent sources to map to supported; one-source observations/claims map to
observed; directly conflicting claims map to contested. Inferences and unknowns
are not published. Staleness is freshness metadata and never changes the
epistemic label. Every public claim label uses this function, including
`/discoveries`, feed/context, and matching.

The same publication-compliance module checks whether a claim concerns
equities, fixed income, derivatives, private credit, hedge-fund situations, or
insurance/reinsurance. Publication of those subjects is blocked unless the
existing approval path has an explicit compliance review with a named reviewer
and reference.

Acceptance: one exact-output test for each mapping row; one stale-evidence test;
one test proving a regulated-asset claim cannot publish without explicit
compliance review even when its evidence is otherwise sufficient.

Result: DONE. Four mapping/compliance tests and the public feed/value-flow tests
passed (34 total). The full backend suite separately reported two failures in
the legacy graph tests; see Current status.

### BP-2 — Standing research agenda, bounded per-cycle collection [DONE]

Maintain one fixed, deduplicated agenda of evidence-seeking questions covering
Nepal work/services/trade/housing/money/infrastructure and the wider asset
surface as research-only. Reuse the existing collector batch limit. Repeated
cycles must not duplicate questions; a zero-result question stays open; each
cycle executes no more than the configured batch size.

Tests: repeated cycles never duplicate a question; a zero-result question
stays open; a cycle with more pending tasks than the existing configured batch
executes no more than that batch.

Result: DONE. Agenda coverage, unresolved-question retry, and a three-task
cycle with `FORGEOS_COLLECT_LIMIT=2` are covered. Focused tests passed: 11.

Depends on BP-1.

### BP-3 — Discoveries link the full chain without skipping evidence rules [DONE]

Preserve the exact chain `signal → claim → question → opportunity`. A signal
without a claim is absent; stale-only evidence stays labeled stale; opportunities
are reachable through the evidence chain and not legacy shortcuts.

Tests: a signal with no claim is absent from `/discoveries`; stale-only evidence
uses BP-1's `stale: true` label; opportunities are reachable only through the
stored evidence chain.

Result: DONE. Regression tests prove the unclaimed-signal exclusion, stale
label, and opportunity suppression until a public question links the evidence
chain. Focused tests passed: 11.

Depends on BP-1 and BP-2.

### BP-4 — Public world shows only what passes publication rules [IN PROGRESS]

No internal score, confidence, or unverified field reaches a public response.
Add one automated schema/snapshot check across public serializers that rejects
internal-only field names.

Tests: one automated public-serializer check fails if a field name matching
`score`, `confidence`, or another internal-only marker appears.

Depends on BP-1 and BP-3.

### BP-5 — Matching as one canonical state machine [HUMAN CHECKPOINT, PENDING]

Use exactly `candidate → evidenced → viable → proposed → authorized →
contacted → accepted → fulfilled → paid → completed`, through one transition
function. Fresh stored evidence is required for `evidenced`; a figure is only
stored in `viable` when it appears in the cited source, otherwise it stays
null. Before starting BP-5, verify that generalized `NetworkConnection`
semantics have been implemented and tested. If they are absent after BP-4,
insert that work as the immediate serial prerequisite; never build it in
parallel. Do not mark BP-5 done without explicit human approval.

Tests: reject every illegal edge, including `candidate → paid` and
`proposed → fulfilled`; prove `viable` cannot store a figure absent from the
cited source.

Depends on BP-1 and BP-4.

### BP-6 — Payment and dispute as recorded events [HUMAN CHECKPOINT, PENDING]

Only fulfilled connections can become paid, and only for a recorded amount that
changed hands. Reported and verified are distinct. Disputes name no winner;
settlement requires a stated new amount and note. Trust reports separate
reported/verified/disputed/settled counts, never a score. Disputes and
settlements write learning events. Do not mark BP-6 done without explicit
human approval.

Tests: separately reject payment without fulfillment/amount, reported treated
as verified, a dispute with a winner, and a settlement without a new
amount/note; verify separate trust counts and a learning event for each
dispute/settlement.

Depends on BP-5.

### BP-7 — Public alerts only from already-recorded outcomes [PENDING]

An alert requires a matching stored `Outcome` for a post, booking, or
connection. A reply can count as an outcome but never as acceptance.

Tests: alert generation without a matching stored Outcome fails; a reply-only
outcome may produce an alert without advancing connection state.

Depends on BP-5 and BP-6.

## After BP-7

Trace `OBSERVE → UNDERSTAND → CONNECT → DISCOVER → CREATE → TEST → ACT →
COORDINATE → CAPTURE VALUE → MEASURE OUTCOMES → LEARN → EXPAND CAPABILITIES`.
Identify the next code-backed gap and add it here before implementation. Keep
work serial and apply the same claim → build → test → integrate → verify →
record discipline. Section 11's safety layer remains out of scope until opened
as its own deliberate task with an explicit evidence threshold.

## Plans that are not queues

`docs/FUTURE_BLUEPRINT.md` is the North Star and architecture.
`docs/IMPLEMENTATION_BACKLOG.md` contains historical belief detail.
`docs/PUBLICITY_GATE.md` is the launch lock.
`docs/NEPAL_FIRST_PRODUCT_PLAN.md` is the first geography.
