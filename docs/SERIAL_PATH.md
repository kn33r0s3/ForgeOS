# Serial path

This file tracks the next near-term engineering task. Work stays sequential:
one capability is changed, tested, integrated, and verified before the next
begins. The numbered items are not ForgeOS's product boundary or a terminal
roadmap. After each item, rescan the end-to-end capability loop in
`docs/FUTURE_BLUEPRINT.md` and replace this focus with the next demonstrated
gap. Do not develop surfaces in parallel.

Production origin: `https://forge-os-ebon.vercel.app`.
Local database: `storage/forge.db`.
Vercel, when `DATABASE_URL` is unset, uses `sqlite:////tmp/forge.db`. That file is not the world of record.

## Now

S11 through S14 are complete. S15 is open: generalize the shared typed-relation
substrate and endpoint adapters while preserving canonical records. The audit
found that `NetworkConnection` is currently a narrow matching workflow: it
does not represent general relation types, temporal/context conditions, typed
evidence sets, or epistemic status independently from workflow state.

S10 remains evidence-gated for real provider verification and operator-submitted
bookings; this does not block network engineering. Never seed providers,
prices, bookings, or outcomes. The footer domain and contact mailbox stay
pending until the operator supplies real details. Local tests do not establish
a live deployment.

## Then, in this order

S1. Public read contract.
`/api/health`, `/api/public/providers`, `/api/public/services`, `/api/public/discoveries`, `/api/public/domain`, `/api/public/alerts` return JSON. HTML is a failure. Empty arrays are a pass.

S2. Verified service path.
`Provider`, `ServiceListing`, and `BookingRequest` stay the only tables for that path.
Publish only after `provider_verify` with evidence_type, evidence_reference, and reviewed_by.
A missing price stays null. `opportunity_from_idea` and `opportunity_from_pattern` store no invented model, price, or customer.
Booking status for an unknown provider is 404. A public booking read has no name, phone, email, or notes.

S3. Needs and gaps.
A domain post can exist with an incomplete contract. Acceptance stays blocked until `terms_complete`.
A question whose text starts with `Gap:` creates no collector task.
Matches expose unknowns and no score. `forge_role` stays introducer.

S4. One lawful source.
Add a row to `docs/PUBLIC_SOURCES.md` only after robots.txt and the terms allow it.
One `ResearchTask`, one collector run, `FORGEOS_COLLECT_LIMIT`. A failure stays failed.
A discovery stays observed. An approach file is a draft, or it says no lawful contact. Nothing is sent.

S5. Canonical beliefs.
`docs/IMPLEMENTATION_BACKLOG.md` TASK-001, then 002, then 003, then 004, then 005.
The knowledge page reads that belief. No new belief UI.

S6. Cockpit reads the same API.
`frontend/` stays `/forge`. It is not the public site. Network fields that are not stored stay unknown. Runtime is counts. Actions propose and do not send.

S7. One cycle.
`python -m scripts.scheduler` is the only runner. It does not publish providers, send messages, or invent prices. Dry cycle uses the pytest database.

S8. Trust and money as records.
`/public/trust` is not a score. Alerts exist only after an outcome. Close needs the token. Paid needs an amount that was stated. No payment credentials.

S9. Public copy and build.
Forge stays the name. Nepal stays the first geography. Pending domain and pending mailbox stay until the operator supplies real ones.
`src/lib/content.test.ts` and `npm run build` pass before a push.

S10. One verified provider pilot.
A provider exists only if a person supplied evidence. A booking exists only if the operator submitted it.
No fabricated pilot data. This real-world pilot gate does not end Forge engineering.

S11. Generalized public Network Feed. COMPLETE.
Project existing public signals/claims, questions, patterns, beliefs, evidence-linked opportunity hypotheses, verified actors/capabilities, open work records, public connections, and real recorded outcomes into one chronological API. Keep canonical records in their current tables, preserve type/provenance/relations, and enforce each source's existing visibility gate. The root page is the feed. No popularity or trust score.
Acceptance: `/api/public/feed` passes integration tests for heterogeneous records, provenance, relationships, empty state, and private/sandbox exclusion; the browser shows the feed on desktop and mobile; build/typecheck pass.

S12. Feed context navigation. COMPLETE.
Feed relations open a scoped feed view around that typed entity reference, composed only from entries that already pass their original public visibility rules. Preserve privacy for provider contact fields, booking requests, internal actions, and unpublished outcomes.
Acceptance: entity context includes its public record and related public items, rejects incomplete filters, cannot use a public edge to reveal a hidden endpoint, and can be cleared back to the whole feed.

S13. Governed discovery expansion. COMPLETE.
Move the currently narrow source clearance into a validated source-registry workflow that can add lawful sources and categories without arbitrary fetching. Keep exact-target allowlists, live robots/terms checks, cross-instance rate limits, provenance, deduplication, and expiry per source. Collector, tool-adapter, CLI, task, and feed paths share the gate. A source with uncertain terms stays disabled.

S14. Autonomous structuring and learning. COMPLETE.
Connect collected external signals to evidence, research questions, patterns, beliefs, opportunities, public projections, authorized actions, observed responses, outcomes, and learning. Automate internal transitions when existing evidence is sufficient; retain approval for contact, transactions, or other external commitments unless an authorized channel and policy permit the action.

S15. General world relations and endpoint adapters. IN PROGRESS.
Use existing canonical records as graph endpoints. Support open relation predicates, direction, epistemic state, optional strength/uncertainty, evidence IDs, provenance, context, conditions, and validity time. Keep the existing matching/action lifecycle separate. Reject dangling endpoints and invalid evidence. Public projections must resolve every endpoint using that record's existing visibility rules. Do not add duplicate identity or resource records without a demonstrated cross-record identity need.
Acceptance: service and migration tests cover legacy compatibility, idempotency, relation-to-relation composition, provenance/time bounds, dangling endpoints, and public/private endpoint exclusion; matching persists canonical endpoint types while preserving its public vocabulary.

S16. Geography and category expansion.
Add categories and geographies as data and source-registry configuration, keeping Nepal as the bootstrap geography. Verify each new source and category against the same evidence/privacy/authorization gates.

S17 and later are discovered by the continuous rescan; they are not a closed task list. Likely next gaps include open-world observations beyond source headlines, reusable capability creation, action-channel qualification, and outcome-to-capability reuse. The rescan must confirm the actual code gap before implementation.

## Plans that are not queues

`docs/FUTURE_BLUEPRINT.md` is the North Star and architecture.
`docs/IMPLEMENTATION_BACKLOG.md` contains historical belief detail and must stay aligned with that architecture.
`docs/PUBLICITY_GATE.md` is the launch lock.
`docs/NEPAL_FIRST_PRODUCT_PLAN.md` is the first geography.
`TWO_HUNDRED_DAY_COPILOT.txt` is historical session guidance, not a stop condition or a second queue.
