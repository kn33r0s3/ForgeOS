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

## D. Discovery-sourced unknowns (2026-10-04 deep listening)

From ~30 substantive public threads (HN, Indie Hackers, Reddit-adjacent,
trade forums, Mumsnet, Quora, Substack/Medium, LinkedIn, one Nepali MBS
thesis n=187, Nepali business press). Evidence class: OBSERVED-at-best
(online discourse). Not Kathmandu ground truth — Nepali voices are
structurally thin in English forums.

| # | Unknown | State | Cheapest legitimate test | What changes if answered |
|---|---------|-------|--------------------------|--------------------------|
| D1 | The "missing middle" gap cost — what does "too busy to answer, not busy enough to hire" cost a shop per month? | UNKNOWN | "How many inquiries did you miss last month because you couldn't respond in time?" | Sizes a pay-per-recovered-job model vs. per-seat |
| D2 | Do owners want to be "found"? — fulfillment/admin may bind harder than demand. **Thesis-threatening:** if presence is the constraint, the "find real opportunities" wedge needs revision | UNKNOWN | "If I brought you 10 new customers tomorrow, what breaks?" — ask first in every discovery conversation | Could revise the wedge thesis before any build |
| D3 | Trust-graph traversal vs. marketing — do first customers come only via pre-existing trust? | UNKNOWN | "How did your first 10 customers find you?" — count trust-traced ones | Hami's RELATION primitive could be the data model |
| D4 | The unguarded surfaces map — where do Nepali kirana owners talk with the camera off? | UNKNOWN — partial map (research, 2026-10-04): broadcast layer visible (TikTok descriptions/bios/stats, public FB page presence); conversational layer walled (comment text never renders, FB/IG hard 403). Actual talk happens on TikTok/FB/WhatsApp | Ask owners directly + one Nepali-language TikTok/FB session by a human | Finds where listening is even possible |
| D5 | The unpredictability tax, quantified — hours/week of presence-demanding chaos | UNKNOWN | "Walk me through last Tuesday." | Turns anecdote into a measurable cost |
| D6 | Accountant-as-translator: human or machine? — does the trust require a human neck to wring? | UNKNOWN | "Would you trust a tool that tells you what the accountant would say?" — listen for the flinch | Decides whether this is automatable at all |
| D7 | Trust-capital stratification — is who gets to start a birth lottery? (family abroad = payments + credit + hiring) | UNKNOWN | ~10 owners with/without abroad connections, compare capital sources | Unmeasured; changes who Hami can serve |
| D8 | Returnee-skill pathway — any working path from foreign-earned skills to businesses, or all dissipation? | UNKNOWN | 3 returnees who started vs. 3 who didn't | May resolve BLOCKED_BY_MISSING_ACCESS |
| D9 | The voiceless-founder population — how many never surface for lack of network? | UNKNOWN (likely BLOCKED_BY_MISSING_ACCESS for direct contact) | "Who do you know who wanted to start but didn't, and why?" | Measures the invisible demand |
| D10 | Reputation vs. paid acquisition by category — which categories run on reputation, and do owners know their game? | UNKNOWN (unmapped in Nepal) | "Where do your customers come from, honestly?" — category by category | Prevents selling funnels to reputation games |
| D11 | Rent-vs-presence split by segment — which merchant classes bind on demand (shutter-density retail) vs. presence (social sellers)? | UNKNOWN (tension observed 2026-10-04: press says density binds; two Nepali case studies say presence binds) | In the five conversations, stratify by channel; ask "which bill scares you most?" + "what breaks with 10 new customers?" | Decides whether Hami's wedge is demand or response-capacity, per segment — the wedge can't be one thing for both |
| D12 | Reply-latency revenue leak on social commerce — how many inquiries die unanswered per week? | UNKNOWN | 5 consenting sellers, 1 week of inquiry-vs-reply timestamp logging (Nepali-speaking human, pure observation); or 1 merchant's 7-day tally of calls/WhatsApps received vs answered vs converted | Decides "find opportunities" vs "catch what you're already dropping" — Kitab Kiro's own "can't keep up" points at the latter |
| D13 | Where does the sale actually close — comment, DM, WhatsApp, or voice call? | UNKNOWN | In the five conversations: "walk me through your last 5 sales, step by step — how did each one actually close?" | If voice is the closer, any text assistant is a bridge not a destination — Hami hands off to calls, not replaces them |
| D14 | What do informal merchants actually use to accept digital money — personal QR (illegal) or formalization just for payments? | UNKNOWN | Sample public Nepali creator walkthroughs ("पसलमा QR कसरी राख्ने") + grievance portals for personal-QR-for-business mentions; observation only | Decides whether the pilot merchant persona is papered or unpapered — which determines whether any QR-based wedge is even legal for them |
| D15 | Sub-merchant/aggregator tier: is a legal informal-merchant tier coming (India's UPI P2PM equivalent), or is the paperwork wall structural? | UNKNOWN | Read NRB Payment System Department unified directives for "sub-merchant"/"agent aggregator" language; track Fonepay/eSewa public roadmap (eSewa hints sub-merchant support coming) | Redraws Hami's entire merchant-addressable map — a legal tier bridges the wall without each kirana getting PAN |
| D16 | Is the E-Commerce Act 2025 pushing micro-sellers off formal surfaces onto informal ones? | UNKNOWN | Quarterly: Daraz's claimed seller count (press/interviews) vs HamroBazaar active listing volume vs TikTok-seller caption density; watch for enforcement-action press | If formalization fragments the seller base toward informal surfaces, the wedge targets the informal surface — where the "one real channel" actually lives |
| D17 | The price-withholding funnel — do Nepali sellers omit prices to force "inbox" comments, and does it convert? | UNKNOWN | Manual audit of 50 posts across 10 seller pages (price present/absent, comment counts) + ask 3 sellers about conversion; no scraping, no accounts | If withholding is deliberate lead-capture, Hami "helping" via price transparency would fight the seller's own strategy — work with the funnel, not against it |
| D18 | Settlement delays: T+1 bank failures or wallet→bank transfer friction — and do they push merchants back to cash? | UNKNOWN (45% of semi-urban merchants report delays — NEPJOL 2026; cause unmapped) | Cross-read NRB monthly payment indicators against delay reports; mine Fonepay Business/eSewa Play Store reviews for "settlement" complaints; one shopkeeper narrates one failure end-to-end | If failures are behavioral, payment confirmation becomes first-class in Hami's evidence layer (receipt-level truth, not policy-level truth); if not, deprioritize entirely |
| D19 | Fake-confirmation scams: how often do Kathmandu merchants get shown fake "Success" screens, and what is the coping check? (round 3: @thepaisamaster warns पसलहरू against the QR scam; cyber-fraud coverage lists fake QR/eSewa/Khalti screens as common cases) | UNKNOWN | In the five conversations: "Has anyone ever shown you a fake payment screen? What do you check before handing over the goods?" | If merchants need adversarial-proof receipt confirmation, Hami's EVIDENCE layer must treat "paid" as receipt-level truth on the merchant's own device — and any verification aid must survive a fake green tick |
| D20 | Multi-person counter: who at the shop checks QR payments, how do they share visibility without sharing credentials? (round 3: FoneBiz 2.73/5 from 1,917 ratings, 610k downloads; two named shop owners say the post-update single-session model broke their staff-checking workflow) | UNKNOWN | Ask: "Who checks the phone when a QR payment comes in — and do they all use the same login?" | The merchant persona isn't the owner alone; staff at the counter are presence-constrained workers too — changes who the verification feature is designed for |
| D21 | Does the dominant merchant QR app's 2.73 rating push merchants toward cash or personal-QR workarounds? | UNKNOWN | Ask: "Which app do you actually use to confirm QR payments, and why?" + track FoneBiz rating over quarters | If the formal rail is unusable at the counter, D14 (informal QR use) gets answered behaviorally — merchants vote with their devices |
