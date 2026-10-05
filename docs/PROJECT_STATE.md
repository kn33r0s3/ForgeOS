# PROJECT STATE — Hami (ForgeOS)

> One page, always current. Updated at the end of every task.
> Last updated: 2026-10-05. HEAD: `7dc0e1f` (main).

## What exists

**Public pages (live):** Home `/`, Findings `/discoveries`, Unknowns `/unknowns`,
Experiments `/experiments`, About `/about`, Services `/services`, Group `/group`,
Needs `/needs`, Action state `/actions`, Inbox prototype `/prototype/inbox`,
Terms `/terms`, Privacy `/privacy`, Login `/login`.
**Owner-only:** Owner console `/owner` (behind login).
**Hidden (exist, unlinked):** Opportunities, Contact, What we've learned,
The climb, Feed, Providers, Operations.
**APIs:** `GET /api/health`, `GET /api/public/*`.
Full registry: `features.json`.

**Backend:** ForgeOS engine — six primitives (ENTITY, RELATION, EVENT,
EVIDENCE, CAPABILITY, ACTION), action engine with owner-approval gates,
intervention gate (one active human-involving intervention), evidence
ledger, truth progression. 717 backend tests.

## What is live

- Production: `https://haminp.vercel.app` (alias `forge-os-ebon.vercel.app`).
- `/api/health` returns 200 (`degraded`, not ready — no durable DB in prod).
- Homepage shows the honest pre-revenue state; Experiment 1 proposed, not started.

## In progress

- `doctrine` — Doctrine v1.0 single source of truth (branch, awaiting review).
- `frontend-mission` — five-field experiment cards, about five questions,
  nav home quick action, join-hami wipe animation (branch, awaiting review).
- `owner-gate` — single-active-intervention enforcement (branch, awaiting review).
- `project-memory` — this workstream: PROJECT_STATE.md, features.json,
  DECISIONS.md, `npm run status`, CI guards, dead-work audit.

## Blocked

- **ONE NAMED SELLER.** Experiment 1 (slow-reply recovery) cannot start
  until the owner names one social seller and authorizes first contact.
  Suggested: name by 2026-10-08/09 so a reply week overlaps Dashain shopping.
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

- [ ] Name the first seller + authorize first contact (blocks Experiment 1).
- [ ] Approve/merge: `doctrine`, `frontend-mission`, `owner-gate`, `project-memory` PRs.
- [ ] Company registration: next step when certificate arrives.
- [ ] Payment: personal eSewa/Khalti for the first rupee — approve or decline.
