# Publicity gate

Evidence is recorded below; boxes are not checked unless the external command
output proves the condition.

- [ ] Production `/api/health` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-25 later: `https://forge-os-ebon.vercel.app/api/health` returned HTTP 200 `{"status":"ok","cycle":null}`.
  - Left open because no durable `DATABASE_URL` is configured. The function database is `/tmp/forge.db`, not a durable world-of-record database.
- [ ] `GET /public/providers` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-25 later: `GET /api/public/providers` returned HTTP 200 `[]`. Empty is the true catalog. The box stays open until that JSON comes from the durable database.
- [ ] The footer domain is controlled by the operator.
  - Current value: `Domain pending verification`.
- [ ] The contact mailbox is controlled and monitored by the operator.
  - Current value: `hello@pending-domain.local`.
- [ ] At least one verified public provider exists, or the public page honestly says none is public yet.
  - Canonical local SQL count: `public_providers = 0`.
- [ ] No invented prices or review scores are published.
  - Public content tests pass; no provider rows were created for verification.

## Current gate state

**OPEN.** The public app and the FastAPI service both answer on
`https://forge-os-ebon.vercel.app`. Lists are JSON and empty. A created domain
row survived a second request and was then withdrawn with its one-time token.
No outreach or publicity launch is authorized.
