# ForgeOS / Hami current status

**Updated:** 2026-10-01
**Evidence boundary:** repository and CI observations below are dated; external
state is not assumed current unless explicitly identified as a dated observation.

## Product and commercial state

- Hami evolves this ForgeOS repository in place. The root Vite application is
  the current web surface; FastAPI under `backend/` is the business API.
- The checked-in `docs/REVENUE_LOG.md` contains no commercial evidence entries.
  Real customer, transaction, and revenue counts are therefore not established
  by that ledger; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT
  MEASURABLE**.
- Forge Bot v0 remains unauthorized for real-world contact. A developer-only,
  in-memory TEST qualification demo now exercises the fixed question sequence;
  it is not a real intake or an implemented durable lead workflow. The existing
  demand intake redacts contact details; the mapped system has no general
  private lead-contact/consent record.
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
- Local backend verification recorded in this session: **575 passed, 2
  skipped**; the two corrected Vercel rewrite contract tests also passed.
- Tests and test fixtures are not customer, payment, or revenue evidence.

## Open owner gates

- Provide the accepted wording for Section 8's 30-day rule and reconcile it
  with the 2026-10-29 scoreboard checkpoint before treating that section as
  authority.
- Resolve private contact storage without violating the instruction not to add
  schema; the current mapped records do not provide the required general
  consent-scoped contact record.
- Supply Cal.com account/link details and any email delivery credentials
  before enabling external booking or sending a daily owner summary. No real
  email or booking request has been sent.
- Confirm Oracle Always Free account/terms and cost controls before any live
  instance evaluation.
