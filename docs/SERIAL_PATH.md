# Serial path

This is the only work order. One step is open at a time. The next step starts when the current step’s test is true. Nothing else in the repo is a second queue.

Do not run phases side by side. Do not split the public app, the API, the cockpit, and the cycle across workers. One worker, one step.

Production origin: `https://forge-os-ebon.vercel.app`.
Local database: `storage/forge.db`.
Vercel, when `DATABASE_URL` is unset, uses `sqlite:////tmp/forge.db`. That file is not the world of record.

## Now

S0. Durable writes.
`GET /api/health` already returns JSON. `GET /api/public/providers` already returns `[]`.
A `POST /api/public/domain` must still be open on a second request, then close as withdrawn.
That is true only after the operator supplies `DATABASE_URL` and Production redeploys.
Until then, do not seed providers, prices, or bookings, and do not check a publicity box.

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
Then stop. No second app, market, or scraper.

## Plans that are not queues

`docs/FUTURE_BLUEPRINT.md` is the ceiling.
`docs/IMPLEMENTATION_BACKLOG.md` is the belief detail inside S5.
`docs/PUBLICITY_GATE.md` is the launch lock.
`docs/NEPAL_FIRST_PRODUCT_PLAN.md` is the first geography.
`TWO_HUNDRED_DAY_COPILOT.txt` repeats this order for a long session budget. If it disagrees with this file, this file wins.
