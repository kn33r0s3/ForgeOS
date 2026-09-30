# Publicity gate

Evidence is recorded below; boxes are not checked unless the external command
output proves the condition.

- [x] Production `/api/health` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-30: `GET https://forge-os-ebon.vercel.app/api/health` returned HTTP 200 `{"status":"ok",...,"readiness":{"ready":true,"blockers":[]}}` with `database.driver=postgresql`, `database.url_configured=true`, `database.available=true`, and `scheduler.cron_secret_configured=true`.
  - Observed 2026-09-26: HTTP 500 `FUNCTION_INVOCATION_FAILED` (historical; the ingress fix was deployed and is now confirmed live).
- [x] `GET /api/public/providers` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-30: HTTP 200 `[]`. The provider list is empty because no provider has published a listing, not because the read failed. `GET /api/public/services` returned HTTP 200 and `GET /api/public/discoveries?limit=2` returned Crossref-derived items.
- [ ] The footer domain is controlled by the operator.
  - Current value: `Domain pending verification`.
- [ ] The contact mailbox is controlled and monitored by the operator.
  - Observed 2026-09-30: no mailbox is published. `SITE.email` is empty, so the
    footer and `/contact` render "A monitored contact address has not been
    configured yet." instead of a `mailto:` link. The earlier value
    `hello@pending-domain.local` no longer appears anywhere in the rendered
    production HTML or in `src/lib/content.ts`.
- [x] Public service availability is established from successful live API responses.
  - Rechecked 2026-09-30: `GET /api/public/providers`, `/api/public/services`, and `/api/public/domain` returned HTTP 200 with `[]`; `GET /api/public/discoveries?limit=3` returned HTTP 200 with 3 records. Empty provider/service/work data is known, not inferred from a failed read.
- [x] No invented prices or review scores are published.
  - The public provider list is `[]`. `GET /api/public/trust/provider/1` returned HTTP 404 `provider not found or not publicly verified` on 2026-09-30, unchanged from 2026-09-26. No price or review score was added.

## Local public entry surface — 2026-09-30

- **Files changed:** `src/routes/index.tsx`, `src/routes/domain.tsx`,
  `src/components/layout/site-header.tsx`,
  `src/components/layout/site-footer.tsx`, `src/lib/content.ts`,
  `src/lib/content.test.ts`, `backend/tests/test_public_feed.py`,
  `backend/tests/test_signal_request_demand_api.py`,
  `docs/PUBLICITY_GATE.md`, and `docs/CAPABILITY_QUEUE.md`.
- **Additional local-only Feed preview:** the current change touches
  `src/routes/index.tsx`, `src/lib/content.test.ts`,
  `docs/PUBLICITY_GATE.md`, and `docs/CAPABILITY_QUEUE.md`; it uses the
  existing `GET /api/public/feed` only.
- **Route scope:** the public homepage is `/`; the shared navigation links to
  existing `/domain`, `/feed`, `/providers`, `/discoveries`, and `/request`
  pages. No backend route was added or changed. Existing APIs remain
  `GET /api/public/discoveries`, `GET /api/public/providers`,
  `GET /api/public/services`, `GET /api/public/domain`,
  `GET /api/public/feed`, `POST /api/public/domain`, and
  `POST /api/signals/public-request` (the local Vite dev proxy exposes the
  corresponding paths without `/api`).
- The local homepage and shared navigation now guide visitors to the existing
  public work board, verified-provider list, source-linked observations, and
  anonymous demand-understanding form. The homepage also previews up to three
  records returned by the existing public Feed, retaining each record's
  source, status, and epistemic label and distinguishing an empty response
  from an unavailable API. They no longer present owner-only runtime counts,
  queued tasks, or action-review links as the main public entry points.
- This change adds no provider, service, work post, customer, transaction,
  payment, outcome, testimonial, or engagement record. Production's current
  public reads remain as reported above; the updated frontend has **not** been
  deployed.
- The work-board form now warns that submitted posts are public and must not
  contain contact details or private information. It does not initiate contact
  or promise a match.
- The new Feed preview is client-side read-only; it adds no API route, stored
  record, scanner, or external action. Existing public Feed eligibility and
  privacy gates remain the source of truth.
- In local development, the existing Feed returns three records; one question
  title explicitly says “Browser-only progress fixture” and remains labeled as
  a question, not a customer, outcome, or revenue record. A read-only
  production query for public questions returned HTTP 200 `[]`. This work did
  not mutate either database or promote the local fixture into REAL evidence.
- A separate read-only production request to `GET /api/public/feed?limit=3`
  returned HTTP 200; its first record is explicitly labeled `inference` and
  its text says it is not a verified business problem, demand claim, or price.
- The only existing intake CTA is the anonymous `/signals/public-request`
  path. It redacts email/phone patterns, provides a truthful receipt, and does
  not create a contactable lead or promise a reply. No inbound email/SMS or
  messaging channel is connected. The existing eSewa/Khalti adapters are not
  required for browsing or submitting a request; their credentials and
  provider-side merchant setup remain unverified, and their callback/lookup
  responses are not connected to the canonical payment Outcome → Learning
  writer.
- Commercial hosting remains an external gate. The repository's last Vercel
  account observation is Hobby, dated 2026-09-29; that account plan was not
  rechecked today. Vercel's current [Hobby documentation](https://vercel.com/docs/plans/hobby)
  describes it as free and aimed at personal projects. Do not deploy a
  commercial launch until the operator verifies a commercially permitted
  account/plan. No plan change, purchase, or deployment occurred.
- The footer domain, monitored contact mailbox, and explicit publicity
  authorization remain owner-controlled and unresolved. This local
  implementation does not close or bypass those gates.

## Current gate state

**OPEN.** The FastAPI service is healthy in production: read-only checks on
2026-09-30 returned HTTP 200 for health, feed, providers, services, discoveries,
and work-board projections. Providers, services, and work posts are currently
empty; discoveries are source-linked observations, not buyer demand. The local
homepage is improved, but has not been deployed. The current plan's commercial
eligibility is not confirmed, the footer domain and monitored mailbox remain
unconfigured, and the owner has not authorized publicity or outreach. No real
customer, transaction, or revenue is claimed.
