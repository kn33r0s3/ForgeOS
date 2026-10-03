# ForgeOS / Hami current status

**Updated:** 2026-10-04
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
  `/forge-bot-intake`; production intake and `FORGE_BOT_LIVE` remain disabled.
  The primary navigation now includes “For businesses” without removing its
  other entries. The home page has a direct “Share a business need” button
  and says, “For business owners, Hami helps clarify a need and find a
  practical next step.” The closed route is not an available submission
  channel. When open,
  the successful response is synchronous in-page receipt only, not a reply to
  the selected email/phone channel. Contact and qualification fields stay outside Signals, generic
  substrate entities, and public projections. The existing anonymous
  demand-intake redaction behavior is unchanged.
- Intake, opt-out, and erasure now emit registered, privacy-minimized
  `WorldEvent`s atomically with the private lead-record transition. The event
  payload keeps only an opaque reference, evidence class, and state change;
  it excludes contact, qualification, and consent values. The hard-delete
  path retains that non-contact erasure event while deleting the lead row.
  This behavior is covered by TEST fixtures only; it is not a customer or
  revenue result and does not activate intake or messaging.
- Forge Bot customer-response ACTIONs use the existing `Action` primitive
  through an owner-only creation/approval path. A canonical decision service
  evaluates policy, inquiry, owner confirmation, and safety gates. Its
  decision is rechecked before outbox creation and immediately before generic
  provider dispatch; generic SMTP/Twilio requests matching a lead or retained
  suppression HMAC are blocked. Proposal, approval, and authorization-decision
  transitions emit registered `WorldEvent`s. No channel/template is
  configured; the full response ACTION decision remains `BLOCKED` because the
  send gate is false and no Forge Bot sender exists.
- Unactioned inquiries still in `READY_FOR_OWNER_REVIEW` are erased after 30
  days by the authenticated daily maintenance path; the run also purges
  expired durable rate-limit buckets. A linked response `ACTION` is exempt
  from that purge. The proposed 90-day maximum after an `ACTION` is
  unimplemented and awaits owner approval.
- The owner has identified a `paid pilots >= 1` checkpoint for 2026-10-29,
  anchored to revenue-first mode beginning 2026-09-29. No matching date or
  scoreboard text was found in the local checked-in `docs/REVENUE_LOG.md`;
  do not represent the checkpoint as verified revenue.

## Runtime and hosting

- Root Vite and FastAPI are wired by `vercel.json`; the `/api/auth/*` web
  rewrite precedes the general `/api/*` FastAPI rewrite.
- Public FastAPI health now returns only `status` and `ready`. The diagnostic
  payload is available at `/api/health/details` only with `X-API-Key`.
- `frontend/` is a legacy Next.js dashboard, retained under
  `docs/archive/legacy-frontend/`; Docker Compose continues to build that
  legacy surface from its archived path. The canonical local app scripts are
  `start.sh` and `stop.sh`. Root `startup.sh` is a separate preview-revive
  contract and is retained.
- At the 2026-10-04 inspection, read-only GETs to both `haminp.vercel.app` and
  `forge-os-ebon.vercel.app` returned health 200/ready and
  `intake_enabled=false`. This does not identify the deployed source commit.
  The owner-readiness endpoint requires the owner key, which was not used;
  authenticated readiness and the live maintenance heartbeat remain
  unverified.
- `docs/HOSTING_AND_SCHEDULER.md` records the Vercel Hobby restriction and
  lack of a verified sub-daily production worker. Oracle Always Free has not
  been validated with an instance. The current batch requested an evaluation,
  but no Oracle credentials were supplied or used and no account-specific
  zero-cost guard was established, so no VM was created and no reliability
  claim is made.

## Verification

- At inspection, `HEAD` and `origin/main` were both
  `1459eec34c0105372e2b089a92994528ac393707`. GitHub Actions CI for that SHA
  completed successfully.
- Current local verification on 2026-10-04: backend suite **685 passed, 2
  skipped** on SQLite. The full suite on throwaway PostgreSQL 18 was **676
  passed, 9 failed, 2 skipped**; do not claim full PostgreSQL-suite parity.
  The directly affected Forge Bot, public-write-limit, and signal-request
  tests passed **103/103** on PostgreSQL 18. `npm test` passed **197 script
  tests and 107 app tests**, and typecheck and lint passed. A build passed in
  the preceding verification cycle; it was not rerun for the current
  documentation-only status update.
- At 390x844 on `haminp.vercel.app`, `/request` displayed the closed message
  with zero forms, textareas, or submit buttons; `/request-a-project`
  redirected to `/request` and showed the same closed state. No browser errors
  were observed. Production GETs to both configured domains returned health
  200/ready and `intake_enabled=false`. These GETs do not establish which
  source commit is deployed. No owner key or production database credential
  was used, and no production database was queried.
- `/privacy` remains `noindex, nofollow` and is not linked from navigation or
  consent. No production message, lead submission, or flag change was made.
- Prior focused Forge Bot/API/notification/outbox tests (**68 passed**) and
  backend suite (**640 passed, 2 skipped**) were recorded on 2026-10-03.
  Authorization/ACTION tests verify owner-key access,
  default-closed state, blocked reasons, PII-free decisions/events,
  submitter-preference separation, audit events and rollback, generic
  SMTP/Twilio rejection, dispatch-time checks, and no provider call or delivery
  row for blocked Forge Bot activity.
- Tests and test fixtures are not customer, payment, or revenue evidence.

## Open owner gates

- Approve or reject the proposed 90-day maximum for inquiries with a response
  `ACTION`; it is not implemented. The existing 30-day no-`ACTION` purge is
  implemented and covered by tests.
- Approve or reject the current `/privacy` draft before it can be linked from
  intake consent; it remains unlinked pending owner approval.
- Complete five owner-run discovery conversations before choosing a segment
  or pilot terms. Decide whether and when to enable intake; it currently fails
  closed without the explicit flag,
  stable 32+-character server HMAC key, and server API key.
- No email address is published. The provided Cal.com URL is displayed as a
  link. No inbound email parsing, selected-channel reply,
  automatic booking, customer follow-up, or Forge Bot sender is implemented.
  An owner-only response-authorization object records the selected existing
  `email`/`phone` channel, exact template reference, consent and
  opt-out/escalation boundaries separately from observed submitter preference.
  No channel or template is configured. The canonical ACTION decision remains
  `BLOCKED`: `FORGE_BOT_RESPONSE_SEND_ENABLED` defaults false and no sender is
  wired. To move the policy from CLOSED, the owner must provide one complete
  authenticated configuration object selecting and explicitly authorizing the
  channel and template. A response ACTION still requires owner approval and a
  separately implemented sender path; configuration alone does not enable or
  execute an external send.
  The internal daily owner digest uses the existing authenticated cron/outbox
  path but requires SMTP credentials; production delivery is not established.
- Confirm Oracle Always Free account/terms and cost controls before any live
  instance evaluation.
