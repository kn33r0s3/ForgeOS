# Hami unknowns map

**Date:** 2026-10-04
**Status:** living document — update when an unknown changes state, never to
fill a queue
**States:** UNKNOWN / HYPOTHESIZED / TESTED / SUPPORTED / CONTRADICTED /
BLOCKED_BY_MISSING_ACCESS

An unknown belongs here only if there is a real reason Hami does not know it.
We do not invent questions to populate a list. When reality contradicts an
expectation, that surprise becomes a NEW_UNKNOWN or a HYPOTHESIS_REVISION.

## A. Reality questions (cheap checks nobody has run)

| # | Unknown | State | Cheapest legitimate test | What changes if answered |
|---|---------|-------|--------------------------|--------------------------|
| A1 | Does production owner email actually deliver? (SMTP accept ≠ receipt) | BLOCKED_BY_MISSING_ACCESS | Owner sends test via DAILY CHECK, confirms real mailbox receipt | Establishes whether the owner-notice path is real or theater |
| A2 | What env vars actually exist in production? | BLOCKED_BY_MISSING_ACCESS | Owner defines the credential retrieval procedure first | Unblocks A1, A8, and the DB check |
| A3 | Read-after-write demonstrated on non-prod Postgres? | UNKNOWN | Throwaway local PG: write, read back, compare | Proves the persistence story outside SQLite |
| A4 | What does the daily scheduled cycle actually do? | TESTED (code, 2026-10-04): Vercel cron fires `/api/scheduled/cycle` daily at 00:00 UTC (cron-secret authorized); it runs privacy maintenance, and the legacy intelligence cycle only if `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` is true. Production execution of the cron itself unverified | Check Vercel cron run history / function logs | Ends speculation about what "the daily job" means |
| A5 | Are legacy collectors still active? | SUPPORTED (code, 2026-10-04): collectors exist (reddit, github, rss, arxiv, web, crossref, world_bank) but the legacy cycle is gated by `FORGEOS_LEGACY_INTELLIGENCE_ENABLED`, which defaults to false — inactive unless the owner enables it | Confirm the flag is unset/false in production env | Dead code running in prod is a liability; confirmed it isn't |
| A6 | Secrets/PII in the public repo history? | TESTED (2026-10-04): pattern scan of code/config/scripts found none; docs and full git-history scan not yet done | Finish with a history scan before any sensitive config ever lands | Public repo + leaked secret = compromise |
| A7 | Neon PITR window for the actual project plan? | UNKNOWN | Owner checks Neon dashboard project settings | Turns "we have backups" into a real recovery promise |
| A8 | Current heartbeat/readiness state? | BLOCKED_BY_MISSING_ACCESS | Owner-key DAILY CHECK | The readiness checklist needs this row filled |
| A9 | Does the deployed commit equal origin/main right now? | UNKNOWN (no public commit identifier) | Owner-key readiness endpoint reports the deployed SHA | Connects every code claim to what prod actually runs |

## B. People questions (the discovery core)

These cannot be answered from a screen. Only real conversations answer them.

| # | Unknown | State | Cheapest legitimate test | What changes if answered |
|---|---------|-------|--------------------------|--------------------------|
| B1 | What do five business owners actually struggle with, in their words? | UNKNOWN | Five owner-run conversations, open questions, no pitching | This is the pilot's raw material — everything downstream depends on it |
| B2 | Who do they ask when they're stuck? | UNKNOWN | Ask it directly in the conversations | Reveals the trust channels Hami must eventually live in |
| B3 | What have they already tried, and what happened? | UNKNOWN | Ask it directly | Failed solutions are opportunity gaps with evidence |
| B4 | What would they hand off given a free week of help? | UNKNOWN | Ask it directly | Closest thing to a willingness-to-pay signal before money exists |

## C. System / meta unknowns

| # | Unknown | State | Cheapest legitimate test | What changes if answered |
|---|---------|-------|--------------------------|--------------------------|
| C1 | Which production domain is canonical? | UNKNOWN (old engineering report contradicts current GETs). Recommendation (2026-10-04): `haminp.vercel.app` canonical — the README names it as the deployed frontend; classify `forge-os-ebon.vercel.app` as alias/legacy pending owner call | Owner confirms or overrides | Ends the docs contradiction; one domain to reason about |
| C2 | Is the current Vercel plan permitted for production use? | SUPPORTED (research, 2026-10-04): Hobby explicitly prohibits commercial use (Vercel docs: "intended for personal, non-commercial use"; commercial = revenue, selling, ads, client work). Currently compliant — $0 revenue, intake closed, no ads. The moment the first paid pilot lands, Hobby becomes a ToS violation risk (suspension without warning reported) | Before first revenue: move to Pro ($20/seat/mo) or migrate frontend to Cloudflare Pages/Netlify (both allow commercial on free tiers). No spend without owner approval | Determines whether infra must move before revenue |
| C3 | What breaks first when a real lead arrives? | UNKNOWN — deliberately untested | Only a real authorized pilot transaction answers this | The most valuable unknown on this list; do not fake it with synthetic data |

## Rules

- blocked ≠ completed. A blocked item stays listed as blocked.
- requested ≠ verified, estimated ≠ actual, test ≠ real.
- A surprise (OBSERVED ≠ EXPECTED) is more valuable than another green test:
  record it, preserve the evidence, let it generate the next unknown.
