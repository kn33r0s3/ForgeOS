# ForgeOS / Hami current status

**Updated:** 2026-10-03
**Evidence boundary:** repository and CI observations below are dated; external
state is not assumed current unless explicitly identified as a dated observation.

## Product and commercial state

- Hami evolves this ForgeOS repository in place. The root Vite application is
  the current web surface; FastAPI under `backend/` is the business API.
- The checked-in `docs/REVENUE_LOG.md` contains no commercial evidence entries.
  Real customer, transaction, and revenue counts are therefore not established
  by that ledger; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT
  MEASURABLE**.
- Forge Bot's lead input is the gated, unlisted web form at
  `/forge-bot-intake`; intake is disabled by default. The successful response
  is synchronous in-page receipt only, not a reply to the selected email/phone
  channel. Contact and qualification fields stay outside Signals, generic
  substrate entities, and public projections. The existing anonymous
  demand-intake redaction behavior is unchanged.
- Intake, opt-out, and erasure now emit registered, privacy-minimized
  `WorldEvent`s atomically with the private lead-record transition. The event
  payload keeps only an opaque reference, evidence class, and state change;
  it excludes contact, qualification, and consent values. The hard-delete
  path retains that non-contact erasure event while deleting the lead row.
  This behavior is covered by TEST fixtures only; it is not a customer or
  revenue result and does not activate intake or messaging.
- The owner has identified a `paid pilots >= 1` checkpoint for 2026-10-29,
  anchored to revenue-first mode beginning 2026-09-29. No matching date or
  scoreboard text was found in the local checked-in `docs/REVENUE_LOG.md` while
  preparing this status. Section 8's separately committed 30-day wording is
  explicitly not accepted as authority and remains blocked pending owner
  wording; do not use it as an operational decision rule.

## Runtime and hosting

- Root Vite and FastAPI are wired by `vercel.json`; the `/api/auth/*` web
  rewrite precedes the general `/api/*` FastAPI rewrite.
- `frontend/` is a legacy Next.js dashboard, retained under
  `docs/archive/legacy-frontend/`; Docker Compose continues to build that
  legacy surface from its archived path. The canonical local app scripts are
  `start.sh` and `stop.sh`. Root `startup.sh` is a separate preview-revive
  contract and is retained.
- The latest recorded production health/API observations are dated
  2026-09-30 in the formerly active focus report; this status does not claim
  they were freshly rechecked on 2026-10-01.
- `docs/HOSTING_AND_SCHEDULER.md` records the Vercel Hobby restriction and
  lack of a verified sub-daily production worker. Oracle Always Free has not
  been validated with an instance. The current batch requested an evaluation,
  but no Oracle credentials were supplied or used and no account-specific
  zero-cost guard was established, so no VM was created and no reliability
  claim is made.

## Verification

- CI for `50f67d873dd0387314d3a8dd8e70516c14694952` completed successfully
  on both backend and frontend jobs.
- Local backend verification recorded on 2026-10-01: **575 passed, 2
  skipped**; the two corrected Vercel rewrite contract tests also passed.
- Local verification on 2026-10-03: backend suite **596 passed, 2 skipped**;
  focused Forge Bot API/notification tests **16 passed**; frontend/script tests,
  TypeScript typecheck, lint, and production build passed. Build migration
  step skipped because `DATABASE_URL` was unset. Browser smoke rendered the
  closed intake page with no console errors; it confirmed the form remained
  closed and did not exercise external messaging.
- Tests and test fixtures are not customer, payment, or revenue evidence.

## Open owner gates

- Provide the accepted wording for Section 8's 30-day rule and reconcile it
  with the 2026-10-29 scoreboard checkpoint before treating that section as
  authority.
- Complete five owner-run licensed-agency discovery conversations and choose
  when to enable intake; decide the retention window and production ingress
  rate-limit. The web route currently fails closed without the explicit flag,
  stable 32+-character server HMAC key, and server API key.
- The provided contact email is a `mailto:` link; the provided Cal.com URL is
  displayed as a link. No inbound email parsing, selected-channel reply,
  automatic booking, or customer follow-up is implemented. The internal daily
  owner digest uses the existing authenticated cron/outbox path but requires
  SMTP credentials; production delivery is not established. Authorize any
  customer-facing activity and supply server credentials separately.
- Confirm Oracle Always Free account/terms and cost controls before any live
  instance evaluation.
