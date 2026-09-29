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
- [ ] Provider availability is established from a successful live API response.
  - Observed 2026-09-30: the API read now succeeds, so the count is knowable: it is `[]`. Provider availability is therefore empty, not unverified.
- [x] No invented prices or review scores are published.
  - The public provider list is `[]`. `GET /api/public/trust/provider/1` returned HTTP 404 `provider not found or not publicly verified` on 2026-09-30, unchanged from 2026-09-26. No price or review score was added.

## Current gate state

**OPEN, for a different reason than on 2026-09-26.** The FastAPI service is
healthy in production: health, feed, providers, services, and discoveries all
return JSON, so no data count may be called unknown any more. The gate stays
shut because the footer domain and the contact mailbox are still placeholders
and because no publicity or outreach is authorized by the owner. Public reads
still show no verified demand, no customer, and no realized revenue
(`/api/public/providers` = `[]`), so publishing would not misrepresent a
transaction — it would only publish an unready shopfront.
