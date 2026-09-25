# Publicity gate

Evidence is recorded below; boxes are not checked unless the external command
output proves the condition.

- [ ] Production `/api/health` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-26: `GET https://forge-os-ebon.vercel.app/api/health` returned HTTP 500 `FUNCTION_INVOCATION_FAILED`.
  - The 2026-09-25 health/write check is historical and does not establish current production health or current durable-database behavior.
- [ ] `GET /api/public/providers` returns JSON from the canonical FastAPI API.
  - Observed 2026-09-26: the API invocation fails with HTTP 500. Current provider count is unknown, not zero.
- [ ] The footer domain is controlled by the operator.
  - Current value: `Domain pending verification`.
- [ ] The contact mailbox is controlled and monitored by the operator.
  - Current value: `hello@pending-domain.local`.
- [ ] Provider availability is established from a successful live API response.
  - The public provider count cannot be checked while the API service returns 500.
- [x] No invented prices or review scores are published.
  - The public provider list is `[]`. `GET /api/public/trust/provider/1` returned HTTP 404 `provider not found or not publicly verified`. No price or review score was added.

## Current gate state

**OPEN.** The public HTML responds, but the FastAPI service currently returns
HTTP 500 for health, feed, provider, service, discovery, and work endpoints.
Local Vercel-shaped startup and route checks pass; production logs are
owner-protected and the current failure is unresolved. Provider/data counts
must not be described as empty until API reads succeed. The footer domain and
contact mailbox remain pending. No outreach or publicity launch is authorized.
