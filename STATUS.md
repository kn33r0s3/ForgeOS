# Hami current status (ForgeOS technical lineage)

**Updated:** 2026-10-14 (Nepal time)
**Evidence boundary:** repository and CI observations below are dated; external
state is not assumed current unless explicitly identified as a dated observation.

## Current integration snapshot — 2026-10-14

- **Version 2 charter / latest exact-head observation (2026-10-14):** docs/BRAIN.md was Version 1 and stopped at section 14. This sync restores the owner-supplied Version 2 through section 33, the amendments to sections 4/8/13/16/21/24/28, and a verified Git blob content hash. Base main before the change: 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c. The prior deployment reported READY at a generated hostname, but current deployed SHA, haminp.vercel.app assignment and runtime health are not independently verified. CI on the parent passed frontend, typecheck, evidence triage, route smoke, secret scan, lint, build and repository guards while backend tests were running. Full exact-head CI and customer-facing readiness are not claimed.

- **Owner ForgeBot workspace — source change awaiting exact-head verification:** \`/owner\` now exposes section shortcuts, a read-only snapshot from existing protected APIs, and a query panel calling the existing owner-protected \`/api/forge/ask\` endpoint. The panel shows related knowledge records returned by the API and reads provider configuration from \`/api/ai/status\`. OpenAI calls are disabled in this panel to preserve the zero-spend default. Questions and answers remain in page memory; the panel does not create Evidence, execute Actions or activate customer messaging. Provider configuration status is not proof of a successful query. Exact-head CI and deployed SHA are not yet verified for this change.


- **Production alias:** Vercel reports `haminp.vercel.app` READY for commit `82297e49e1640bd84cedac291bb4eb2fede8eae8` (deployment `dpl_HQLMWrauSmRQfsbwMsHuvVUX6p3H`). This is a deployment/alias observation, not proof that API credentials, durable persistence, scheduled work or economic outcomes are ready.
- **One Hami product surface:** the public NAV/footer/pathway source remains `src/lib/hami-system.ts`; `features.json` remains the route/API lifecycle registry; the reverse-link regression now requires every live page to have a deliberate entry path, with `/requests/$id` documented as a workflow-only route created by an actual provider request.
- **Group and service connections:** the seven group directions share `GroupAreaGrid` across `/group` and `/group/businesses`; all point to existing Hami routes. Each of the six Hami service details links to its five sibling categories and back to `/services`. Shared CTAs distinguish Hami-owned service scope from the independent external-provider directory.
- **Private and closed surfaces:** `/owner` links to `/operations` after the owner unlocks the console, and Operations links back. Both remain hidden/noindex and outside public navigation. The public Businesses page no longer links to `/forge-bot-intake`; it explicitly states intake is closed and routes to existing services/process/work surfaces. The underlying closed route is retained rather than deleted or activated.
- **Brand identity:** the PWA/Grok injection shell is removed; the Hami-owned manifest and browser metadata are guarded by tests. The backend OpenAPI description and API-reference heading now use Hami as product identity while legacy path/env identifiers are documented as implementation compatibility names.
- **Regression coverage added:** route-entry reachability, contextual CTA destination contracts, group-area registry targets, service sibling links, closed-intake exposure, and OpenAPI product metadata. Vercel build/status checks succeeded for the current production alias commit; Vercel status alone does not execute or prove all local backend/frontend test suites.
- **Current limits:** direct rendered-page inspection remains unavailable through the current web/Vercel fetch integration. The code-level link audit found no orphaned live page in the registry, but this is not an end-to-end browser test. Production owner-key presence/access, Better Auth deployed configuration, durable database behavior, scheduled-worker cadence, email delivery, complete provider payment/order/fufilment, real customer activity and revenue remain unverified. See `docs/HAMI_INTEGRATION_AUDIT.md` for prioritized work and evidence boundaries.

**Historical snapshot note:** the sections below preserve dated operational reports and earlier verification results. Treat their explicitly dated observations as historical evidence, not as fresh verification of the current deployment; the system map, capability ledger and integration audit record later changes.

## Product and commercial state

- Hami evolves this ForgeOS repository in place. The root Vite application is
  the current web surface; FastAPI under `backend/` is the business API.
- The checked-in `docs/REVENUE_LOG.md` contains no commercial evidence entries.
  Real customer, transaction, and revenue counts are therefore not established
  by that ledger; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT
  MEASURABLE**.
- Forge Bot intake remains the gated, unlisted form at `/forge-bot-intake`; production
  intake and `FORGE_BOT_LIVE` remain disabled. The current canonical primary
  navigation is defined in `src/lib/hami-system.ts` (Home, Findings, Unknowns,
  Network, Experiments, Services, Group, About). The homepage uses the shared
  `HamiPathways` component to connect findings, unknowns, network, experiments,
  services, and the public work board; it does not render the earlier direct
  “Share a business need” button or the former “For business owners…” copy.
  The public Businesses page explicitly says online inquiries remain closed
  and links to existing Hami service/process/work surfaces, not the closed
  intake route. `/request` is retained but its submission form checks the
  backend `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` gate (default false) and refuses
  submission when closed or unavailable. A retained route is not proof that
  intake is live. If intake is explicitly re-enabled in future, successful
  submission is only synchronous in-page receipt, not a reply through the
  selected email/phone channel. Contact and qualification fields stay outside
  Signals, generic substrate entities, and public projections. Anonymous
  demand-intake redaction remains in place.
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

- At the start of the PostgreSQL parity run, local `HEAD` and `origin/main`
  both matched `f5ca8d82749d82723fa18806fe472bb913a995db`. A test-only parity
  commit was then created locally. `origin/main` subsequently advanced to
  `30e337c2354fb15e397861780b906f2108e40d74`; CI succeeded for both that
  upstream SHA and the original base, but not for the local parity commit.
  The parity change has not been pushed or deployed.
- Current local verification on 2026-10-04: the complete backend suite passed
  **686 tests, 2 skipped** on SQLite and **686 tests, 2 skipped** on throwaway
  PostgreSQL 18. The five formerly failing modules pass **37 tests** on each
  dialect. Failures were test-fixture portability problems: fabricated
  foreign-key references and assertions that assumed the active database was
  SQLite. Test data now uses real TEST-scoped referenced rows; the adapter's
  missing-source branch is covered without inserting an FK-invalid row; and
  health/database-isolation checks follow the selected dialect. No
  production implementation or schema was changed.
- The focused Forge Bot, owner-notification/privacy, public-write-limit, and
  signal-request tests passed **112/112** on both SQLite and throwaway
  PostgreSQL 18. `npm test`, typecheck, lint, and `npm run build` passed. The
  build was run with `DATABASE_URL` explicitly unset, so the deploy-time
  migrator skipped instead of connecting to or writing any database.
- At 390x844 on `haminp.vercel.app`, `/request` displayed the closed message
  with zero forms, textareas, or submit buttons; `/request-a-project`
  redirected to `/request` and showed the same closed state. No browser errors
  were observed. Production GETs to both configured domains returned health
  200/ready, `intake_enabled=false`, `/request` 200 with the not-open message
  and no form, and `/request-a-project` 307 to `/request`. A browser reload of
  the production `/request` page found the closed message, zero forms,
  textareas, or submit buttons, and no console/page errors. These GETs do not
  establish which source commit is deployed. No owner key or production
  database credential was used, and no production database was queried.
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
