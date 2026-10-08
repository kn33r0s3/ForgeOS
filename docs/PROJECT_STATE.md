# PROJECT STATE — Hami (ForgeOS)

> One page, always current. Updated at the end of every task.
> Last updated: 2026-10-08. HEAD: `main` (Batch 14 commits are local and not pushed).

## Current maintenance state (2026-10-08)

- Batch 14 adds autonomy tiers, owner review for Tier 2 paths, CI guards,
  grouped patch/minor Dependabot updates, nightly reports, and read-only
  production smoke checks. Intake and `FORGE_BOT_LIVE` were not changed.
- Main protection is configured for strict CI checks and one code-owner
  approval; admin enforcement is on. Repository auto-merge is enabled for
  check-gated Dependabot PRs. An owner-authored Tier 2 PR needs a different
  eligible reviewer because self-approval and admin bypass are disabled.
- Local verification: backend SQLite suite 916 passed / 2 skipped; frontend
  tests, typecheck, build, route smoke, and guard tests passed. Lint has one
  pre-existing Fast Refresh warning and no errors.
- The commits are not pushed, so Actions and production-only GET checks have
  not run. No production request or write was made during this batch.
- The slow-reply seller probe is paused historical material, not the active
  frontier. No contact or resume action is authorized by this update.

## What exists

**Public pages (live):** Home `/`, Findings `/discoveries`, Unknowns `/unknowns`,
Experiments `/experiments`, About `/about`, Services `/services`, Group `/group`,
Needs `/needs`, Action state `/actions`, Terms `/terms`, Privacy `/privacy`,
Login `/login`.
The experiments record remains reachable but is not linked from the home hero,
top menu, or footer.
**Owner-only:** Owner console `/owner` (behind login).
**Hidden (exist, unlinked):** Inbox prototype `/prototype/inbox`, Opportunities,
Contact, What we've learned, The climb, Feed, Providers, Operations.
**APIs:** `GET /api/health`, `GET /api/public/*`.
Full registry: `features.json`.

**Backend:** ForgeOS engine — six primitives (ENTITY, RELATION, EVENT,
EVIDENCE, CAPABILITY, ACTION), action engine with owner-approval gates,
intervention gate (one active human-involving intervention), evidence
ledger, truth progression. 916 backend tests pass; 2 are skipped.

## What is live

- Production: `https://haminp.vercel.app` (alias `forge-os-ebon.vercel.app`).
- `/api/health` returns 200 (`degraded`, not ready — no durable DB in prod).
- Homepage shows the honest pre-revenue state. The slow-reply probe is paused,
  retained as history, and not an active experiment or priority.

## In progress

- `doctrine` — Doctrine v1.0 single source of truth (branch, awaiting review).
- `frontend-mission` — five-field experiment cards, about five questions,
  nav home quick action, join-hami wipe animation (branch, awaiting review).
- `owner-gate` — single-active-intervention enforcement (branch, awaiting review).
- `project-memory` — this workstream: PROJECT_STATE.md, features.json,
  DECISIONS.md, `npm run status`, CI guards, dead-work audit.

## Blocked

- **PAUSED HISTORICAL PROBE.** The seller slow-reply probe remains paused.
  No contact is authorized, and it is not Hami's active strategic frontier.
- **SECURITY (verified 2026-10-05, needs owner decision):** route audit found
  27 unguarded consequential endpoints on forge.router — including
  POST /forge/actions/{id}/approve and /execute (broken guard call raises
  TypeError instead of enforcing auth) and PATCH /forge/autonomy/policy
  (rewrites spend limits with no key). Middleware 401s writes only when
  FORGE_API_KEY is set. Fix proposed, not applied — awaiting owner.
- Production readiness: no durable database configured; CRON_SECRET absent.
- Company registration (Hami Systems): IN PROGRESS, awaiting approval.
- Payment: no legally verified merchant path until business PAN exists.

## Last 10 decisions

1. 2026-10-05 — Doctrine v1.0 frozen; single file docs/ORIGIN.md (owner).
2. 2026-10-05 — Experiment cards carry five fields; constraint = hypothesis until evidenced (owner).
3. 2026-10-05 — Owner console gate: one active human-involving intervention max (owner).
4. 2026-10-05 — Nav gets quick-action Home; Join Hami gets btn-wipe animation (owner).
5. 2026-10-05 — Branch + PR for doctrine/project-memory work; owner approves merge (owner).
6. 2026-10-05 — User's name is Niroj (owner).
7. 2026-10-04 — Direct-to-main restored after one PR experiment (owner).
8. 2026-10-04 — Intake STAYS CLOSED; readiness checklist has owner-side FAILs (musa, delegated).
9. 2026-10-04 — Whop is not the revenue path; haminp.vercel.app is the live surface (owner).
10. 2026-10-04 — Canonical domain haminp.vercel.app (musa, delegated).

Full log: `DECISIONS.md`.

## Open owner decisions

- [ ] Keep the seller probe paused; any future resume requires explicit owner authorization.
- [ ] Approve/merge: `doctrine`, `frontend-mission`, `owner-gate`, `project-memory` PRs.
- [ ] Company registration: next step when certificate arrives.
- [ ] Payment: personal eSewa/Khalti for the first rupee — approve or decline.
