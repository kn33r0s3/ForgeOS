# Serial path

This is the only work order. One step is open at a time. The next step starts when the current step’s test is true. Nothing else in the repo is a second queue.

Do not run phases side by side. Do not split the public app, the API, the cockpit, and the cycle across workers. One worker, one step.

Production origin: `https://forge-os-ebon.vercel.app`.
Local database: `storage/forge.db`.
Vercel, when `DATABASE_URL` is unset, uses `sqlite:////tmp/forge.db`. That file is not the world of record.

## Now

S11 is complete. S12 is open: turn typed feed relations into safe, scoped network-context navigation.
S10 remains evidence-gated for real provider verification and operator-submitted bookings; that does not block network engineering. Never seed providers, prices, bookings, or outcomes. The footer domain and contact mailbox stay pending until the operator supplies real details.
Production was last reported healthy on 2026-09-25; production state has not been rechecked in this turn. Local code and tests are not proof of a live deployment.

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

S10. One pilot, then stop.
A provider exists only if a person supplied evidence. A booking exists only if the operator submitted it.
No fabricated pilot data. This real-world pilot gate does not end Forge engineering.

S11. Generalized public Network Feed. COMPLETE.
Project existing public signals/claims, questions, patterns, beliefs, evidence-linked opportunity hypotheses, verified actors/capabilities, open work records, public connections, and real recorded outcomes into one chronological API. Keep canonical records in their current tables, preserve type/provenance/relations, and enforce each source's existing visibility gate. The root page is the feed. No popularity or trust score.
Acceptance: `/api/public/feed` passes integration tests for heterogeneous records, provenance, relationships, empty state, and private/sandbox exclusion; the browser shows the feed on desktop and mobile; build/typecheck pass.

S12. Feed context navigation.
Feed relations open a scoped feed view around that typed entity reference, composed only from entries that already pass their original public visibility rules. Preserve privacy for provider contact fields, booking requests, internal actions, and unpublished outcomes.
Acceptance: entity context includes its public record and related public items, rejects incomplete filters, cannot use a public edge to reveal a hidden endpoint, and can be cleared back to the whole feed.

S13. Governed discovery expansion.
Move the currently narrow source clearance into a source-registry workflow that can add lawful sources and categories without arbitrary fetching. Keep allowlists, robots/terms checks, rate limits, provenance, deduplication, and expiry per source. A source with uncertain terms stays disabled.

S14. Autonomous structuring and learning.
Connect collected external signals to evidence, research questions, patterns, beliefs, opportunities, public projections, authorized actions, observed responses, outcomes, and learning. Automate internal transitions when existing evidence is sufficient; retain approval for contact, transactions, or other external commitments unless an authorized channel and policy permit the action.

S15. General entities and actor capabilities.
Only introduce durable shared identity or resource records when cross-record identity cannot be represented safely by existing models and typed connections. Migrate by compatibility views/adapters; do not fork provider, signal, opportunity, action, or outcome records.

S16. Geography and category expansion.
Add categories and geographies as data and source-registry configuration, keeping Nepal as the bootstrap geography. Verify each new source and category against the same evidence/privacy/authorization gates.

## Plans that are not queues

`docs/FUTURE_BLUEPRINT.md` is the ceiling.
`docs/IMPLEMENTATION_BACKLOG.md` is the belief detail inside S5.
`docs/PUBLICITY_GATE.md` is the launch lock.
`docs/NEPAL_FIRST_PRODUCT_PLAN.md` is the first geography.
`TWO_HUNDRED_DAY_COPILOT.txt` repeats this order for a long session budget. If it disagrees with this file, this file wins.
