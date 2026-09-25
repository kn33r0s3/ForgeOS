# Publicity gate

Evidence is recorded below; boxes are not checked unless the external command
output proves the condition.

- [x] Production `/api/health` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-25: `https://forge-os-ebon.vercel.app/api/health` returned HTTP 200 `{"status":"ok","cycle":null}`.
  - A durable `DATABASE_URL` is configured for Production. A domain write survived a second request in the S0 check.
- [x] `GET /public/providers` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-25: `GET /api/public/providers` returned HTTP 200 `[]`. Empty is the true catalog.
- [ ] The footer domain is controlled by the operator.
  - Current value: `Domain pending verification`.
- [ ] The contact mailbox is controlled and monitored by the operator.
  - Current value: `hello@pending-domain.local`.
- [x] At least one verified public provider exists, or the public page honestly says none is public yet.
  - Observed 2026-09-25: `GET /api/public/providers` returned HTTP 200 `[]`. `GET /providers` says a provider appears only when verified and public, and that no verified provider is selected.
- [x] No invented prices or review scores are published.
  - The public provider list is `[]`. `GET /api/public/trust/provider/1` returned HTTP 404 `provider not found or not publicly verified`. No price or review score was added.

## Current gate state

**OPEN.** The public app and the FastAPI service both answer on
`https://forge-os-ebon.vercel.app`. Health and the provider list return JSON.
The provider list is empty. A created domain row survived a second request and
was then withdrawn with its one-time token. The footer domain and contact
mailbox are still pending, and no verified public provider exists. No outreach
or publicity launch is authorized.
