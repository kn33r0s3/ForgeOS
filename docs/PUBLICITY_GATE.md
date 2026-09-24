# Publicity gate

Evidence is recorded below; boxes are not checked unless the external command
output proves the condition.

- [ ] Production `/api/health` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-25: `https://forge-os-ebon.vercel.app/api/health` returned HTTP 404 `DNS_HOSTNAME_RESOLVED_PRIVATE`.
- [ ] `GET /public/providers` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-25: the deployed same-origin path returned HTTP 404; no production FastAPI origin is configured.
- [ ] The footer domain is controlled by the operator.
  - Current value: `Domain pending verification`.
- [ ] The contact mailbox is controlled and monitored by the operator.
  - Current value: `hello@pending-domain.local`.
- [ ] At least one verified public provider exists, or the public page honestly says none is public yet.
  - Canonical local SQL count: `public_providers = 0`.
- [ ] No invented prices or review scores are published.
  - Public content tests pass; no provider rows were created for verification.

## Current gate state

**OPEN.** Production frontend deployment is reachable, but the FastAPI backend
and persisted public API path are not deployed. No outreach or publicity launch
is authorized.
