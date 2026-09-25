yet present. The first canonical path remains Signal → Pattern → Belief →
# Current focus — Vercel API ingress recovery

**Architecture authority:** [`FORGE_SUBSTRATE_BLUEPRINT.md`](../FORGE_SUBSTRATE_BLUEPRINT.md)
**Claim ledger:** [`CAPABILITY_QUEUE.md`](CAPABILITY_QUEUE.md)
**Work order:** serial; claim → build → test → integrate → verify → record.

## Observed failure

As of 2026-09-26, the public Vercel web app responds, but `/api/health`,
`/api/public/feed`, and other API routes return HTTP 500
`FUNCTION_INVOCATION_FAILED`. Vercel function logs require deployment-owner
authentication and are not available in this session. Do not claim the live API
or public record counts are healthy/empty until production responds successfully.

## Code-side work completed

The Vercel API service now explicitly declares `backend/`, the `fastapi`
framework, and `app.main:app`. FastAPI owns both unprefixed and `/api`-prefixed
routes; Vercel only routes the original `/api/*` path to the service. The
duplicate service path transform and unused `app.vercel_asgi` wrapper were
removed. This preserves handlers, response contracts, data sources, and the
substrate's read-projection authority.

Local verification (2026-09-26, macOS/Python 3.13):

- `cd backend && ../.venv/bin/python -m pytest tests/test_public_feed.py -q` → 10 passed.
- `cd backend && ../.venv/bin/python -m pytest -q` → 362 passed, 21 warnings.
- `npm run typecheck && npm run build` → typecheck and Vercel production build passed; migration step skipped because local `DATABASE_URL` is unset.
- Vercel-shaped ASGI startup with `VERCEL=1` and an isolated `/tmp` SQLite URL returned 200 for `/health`, `/api/health`, `/public/feed?limit=1`, and `/api/public/feed?limit=1`.
- `git diff --check` → clean.

These checks do not prove the deployed Python function recovered. Live
`GET /api/health` and `GET /api/public/feed?limit=1` still return HTTP 500.

## Remaining gate

Deploy this Vercel service configuration, then verify production health and
feed endpoints and inspect the function logs if either still fails. Keep the
publicity gate open until those checks pass. The prior substrate claim for
explicit `ResearchQuestion.source_*` relations remains in the ledger and should
resume after this production blocker is resolved.
