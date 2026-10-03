# Hami launch readiness

**Date:** 2026-10-04 (overnight run, Asia/Kathmandu)
**Repo HEAD at check:** `f86d364` (before tonight's copy commits)
**Method:** full backend suite + full frontend suite run locally; read-only
production probes; code inspection. No intake/send flags touched, no outbound,
no spending, no contact with any real person. No synthetic data anywhere in
this document — every READY cites its evidence.

**How to read this:** each line is one of READY (evidence cited),
BLOCKED_ON_OWNER (the exact decision needed, one line), or NEXT (planned,
ordered). A missing, stale, or unverified item is not READY. This document is
a checklist, not authorization — activation still needs the exact phrase in
`docs/ACTIVATION.md`.

## Launchpad: the priority sequence

| # | Requirement | Status | Evidence / decision needed |
|---|-------------|--------|----------------------------|
| 1 | `/request` closed-state | **READY** | `DemandIntakeForm` gates on `getPublicDemandRequestEnabled()`; when the flag is off it renders "Online inquiries are not open yet." with no form (`src/components/pages/demand-intake-form.tsx`). Both production domains report `{"enabled":false}` on `/api/signals/public-request/config` (probed 2026-10-04 ~04:05 NPT). Frontend test "reads the existing public demand gate and fails closed when unavailable" passes. |
| 2 | `/owner` contract | **READY** | Key-entry shell: publicly reachable, unlinked, `noindex,nofollow,noarchive`; loads zero owner data until the key is entered in page memory; key sent only in `X-API-Key` header (`src/routes/owner.tsx`). Readiness signals, lead controls, and the daily routine are all present. The owner key itself is owner-held — nothing to configure here. |
| 3 | Real lead channel selected | **BLOCKED_ON_OWNER** | Decision needed: name exactly one real, authorized, zero-cost lead channel (source/consent/format documented). |
| 4 | Zero-cost response path | **BLOCKED_ON_OWNER** | Decision needed: establish one safe $0 response path on the same channel before any intake opens. |
| 5 | Limit/422 verification | **READY** | Backend suite 2026-10-04: **686 passed, 2 skipped, 0 failed** (local, 4m29s), including `test_public_write_limits.py` (8 tests: 5/hour visitor-HMAC write limits, 16 KiB request caps, 422 paths). Frontend suite: **107/107 pass** (2026-10-04). |
| 6 | Domain/docs reconciliation | **BLOCKED_ON_OWNER** | Decision needed: confirm the canonical domain — `haminp.vercel.app` (recommended) vs `forge-os-ebon.vercel.app` (current sitemap/robots). After the decision: update `public/sitemap.xml`, `public/robots.txt`, `SITE.domain` (currently renders "Domain pending verification" in the footer). |
| 7 | Company registration | **BLOCKED_ON_OWNER** | Hami Systems (हामी सिस्टम्स) registration IN PROGRESS (Private → Sole Ownership; CAMIS name availability subject to review). Owner-side; nothing executable here. |
| 8 | `hamisystems.com.np` | **NEXT** | After registration certificate: register domain, then point/verify. |
| 9 | Payment/merchant onboarding | **BLOCKED_ON_OWNER** | Blocked on business credentials (owner holds personal PAN only). No merchant onboarding attempted or faked. |
| 10 | Pilot readiness review | **NEXT** | After 3, 4, 6, 7 resolve: full ACTIVATION.md checklist pass with the owner. |
| 11 | Opening intake | **BLOCKED_ON_OWNER** | Requires the owner writing exactly `ACTIVATE FORGE BOT LIVE` after every readiness check passes. Not given. Flags verified closed (see below). |

## Activation flags (verified closed, untouched)

| Probe (2026-10-04 ~04:05 NPT) | Observed |
|---|---|
| `haminp.vercel.app/api/health` | `{"status":"ok","ready":true}` |
| `forge-os-ebon.vercel.app/api/health` | `{"status":"ok","ready":true}` |
| `haminp.vercel.app/api/forge-bot/config` | `{"intake_enabled":false, ...}` |
| `forge-os-ebon.vercel.app/api/forge-bot/config` | `{"intake_enabled":false, ...}` |

`FORGE_BOT_LIVE` was not probed directly (no authorized read path without the
owner key); the config endpoint is the public source of truth for intake state
and it is closed on both domains. Nothing was changed.

## What tonight's run changed

Safe, reversible, non-externally-consequential work only:

1. **Full frontend suite: 107/107 pass.** Four files initially failed with
   `ERR_MODULE_NOT_FOUND` (`jose` etc.) — the local `node_modules` was never
   installed. Fixed with `npm ci` (local-only, no code change). No code fix
   was needed or made for any test.
2. **Full backend suite: 686 passed, 2 skipped, 0 failed** (2026-10-04,
   local run, 4m29s). No failures to triage. Includes the public write-limit
   tests (5/hour visitor-HMAC limits, 16 KiB caps, 422 paths).
3. **Nepal-first copy removal from the live site (owner's standing rule).**
   The hero "Hami · Nepal first" was fixed earlier tonight; this run removed
   the remaining instances: `src/lib/og/site.json` description ("starting in
   Nepal" → "built in Kathmandu, serving the world"), `SITE.location`
   ("Starting in Nepal" → "Built in Kathmandu"), `SITE.description` ("Nepal is
   the initial focus" → "Built in Kathmandu, Nepal; serving the world equally,
   with no geographic priority"), and `/about` ("Nepal is the initial focus"
   → same reframe). Verified: zero priority-language strings remain in
   `src/`, `server/`, `public/`; `content.test.ts` (10/10) still passes,
   including its `/Nepal/` assertion. These are copy-only changes; they deploy
   with the next Vercel build of `main`.
4. **Hero copy verified live in production:** the deployed bundle on
   `haminp.vercel.app` contains `` ` Hami · हामी` `` in the hero eyebrow, and
   no deployed chunk contains "Nepal first".

## Backend suite result

**686 passed, 2 skipped, 0 failed** — full run 2026-10-04 ~04:10 NPT, local
SQLite, 4m29s. The 2 skips are pre-existing conditional skips. Warnings are
pre-existing SQLAlchemy table-sort notices, no errors.

## Known limitations of this run (honest)

- **No live-browser render check.** This environment has no interactive
  browser; the homepage was verified by fetching HTML + deployed JS chunks
  (hero copy confirmed in the bundle). A real browser walkthrough (console
  errors, mobile layout) still needs the owner's or an agent's browser.
- **Deployed commit ≠ verified against `origin/main`.** No public commit
  identifier exists; the owner-key readiness endpoint reports the deployed
  SHA, which requires the owner key. Push succeeded; health is green.
- **Production database:** no read-only check performed — no authorized
  credential procedure exists (see `docs/ACTIVATION.md` boundary). Not
  attempted, not worked around.
- **Owner email / SMTP / heartbeat:** unverifiable without the owner key and
  a real mailbox. Marked FAIL-unverified per the runbook, not assumed.
- **Vercel plan / commercial-use status:** unverified. No paid changes made.

## The one-line summary

Hami is **as ready as it can be without the owner**: the site is up, intake is
verifiably closed on both domains, the test suites are green, and the last
Nepal-first copy is out. Everything remaining is a human decision — lead
channel, response path, canonical domain, company registration, payment
credentials, and the activation phrase. None of it can be worked around from
here.
