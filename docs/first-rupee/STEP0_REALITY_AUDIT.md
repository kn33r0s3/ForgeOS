# STEP 0 — Reality audit (First Rupee mission)

**Date:** 2026-10-23 · **Method:** `git fetch`, repo read at HEAD
`5b5945d7`, live production probe, docs read in full (HANDOFF.md,
UNKNOWN_MAP.md D1–D100, EXPANSION_STRATEGY.md, FIRST_RUPEE_SPRINT.md,
SPRINT_BRIEF.md, REVENUE_LOG.md), workspace/discovery/ read,
`/prototype/inbox` source read. Every claim below is labeled
REAL / TEST / MOCK / HYPOTHESIS with its evidence.

## Verified current state

| Claim | Label | Evidence |
|---|---|---|
| Repo `main` HEAD at audit start | REAL | `git fetch` + `git log`: `5b5945d7`, working tree clean, `main == origin/main` |
| Production is in deliberate maintenance mode | REAL | Live probe 2026-10-23: `GET https://haminp.vercel.app/api/health` → HTTP 503 `{"detail":"Hami is under development."}` (`public_maintenance_gate`). Intentional, not an outage |
| Intake flag | UNKNOWN (last known `intake_enabled: false`) | `/api/forge-bot/config` is behind the maintenance gate; HANDOFF 2026-10-23 snapshot. Not readable while the gate is up — do not claim a current value |
| Unknowns ledger size | REAL | `docs/UNKNOWN_MAP.md` contains D1–D100 (100 rows), matching HANDOFF |
| Real seller conversations held to date | REAL: **zero** | HANDOFF blockers section (unchanged across 2026-10-20 → 2026-10-23 snapshots); REVENUE_LOG.md is empty |
| Verified transactions / revenue to date | REAL: **zero** | `docs/REVENUE_LOG.md`: "No commercial evidence has been recorded in this log yet." |
| `/prototype/inbox` has local logs plus an explicit owner-key substrate sync path | REAL (source); production sync UNVERIFIED | `src/routes/prototype.inbox.tsx`, `src/lib/prototype-inbox.ts`; browser-local storage for timer/log, explicit sync can post only seller-consented pseudonymous commitment metadata to existing owner-key-protected substrate. Runtime is under maintenance/HTTP 503; no production sync was verified. |
| Vercel Hobby plan prohibits commercial use | SUPPORTED (research) | UNKNOWN_MAP C2: Hobby is non-commercial; the first paid pilot creates a ToS risk that must be resolved before revenue, with owner approval for any spend |
| E-Commerce Act 2081 + Directive 2082 listing duties exist | SUPPORTED (primary-source links in D72) | Department pages linked from UNKNOWN_MAP D72; fresh search 2026-10-23 confirms the DoCSCP FMIS listing route and Directive 2082 document requirements (company cert, PAN, domain/hosting proof, privacy policy, cybersecurity test report) |
| Karobar: 500k+ installs, ~Rs 10M/yr revenue, 35 staff | REPORTED (founder claims + press) | UNKNOWN_MAP D25 marks this SUPPORTED (research), but the underlying numbers are founder claims relayed by New Business Age and androidrank estimates — OBSERVED/REPORTED class, not independently verified financials |

## Contradictions between docs and code/reality

1. **HANDOFF takeover checklist is stale vs its own snapshots.** The
   checklist (written for a past takeover) tells the reader to expect
   `{"status":"ok","ready":true}` from both `/api/health` endpoints.
   Reality (verified today): HTTP 503 maintenance detail. HANDOFF's
   dated snapshots at the top of the file record the 503 correctly; the
   checklist text lower in the file was never updated. **Trust the
   snapshots + live probe, not the checklist.**
2. **Offer terms: shipped prototype copy vs sprint governance.**
   `src/routes/prototype.inbox.tsx` tells visitors: "In a real sprint
   week Hami takes a cut of recovered sales only; no recovery, no
   charge." But `docs/FIRST_RUPEE_SPRINT.md` states outcome-based
   pricing is "a hypothesis, not an approved term" and must not be
   proposed until qualified legal/accounting review and an explicit
   owner decision on exact terms. The prototype copy asserts as fact a
   term the sprint doc forbids proposing. **Flagged for the owner
   approval queue — copy not changed by this mission (externally
   consequential change needs owner approval).**
3. **First-contact script vs mission item 3.** `docs/SPRINT_BRIEF.md`'s
   existing first-contact script is discovery-only: no pitch, no offer,
   no service. The mission asks drafts to include the D2 question and
   the pay-only-on-recovered-sale offer. The drafts in
   `FIRST_CONTACT_DRAFTS.md` follow the mission (they are drafts for the
   owner's approval queue, not sendable text) and carry an explicit
   NOT-SENDABLE banner reconciling the two: the offer clause stays inert
   until the owner approves exact terms and the D72 legal gate is
   recorded.
4. **Sprint length.** `docs/FIRST_RUPEE_SPRINT.md` frames the measure
   as one week; the mission sets a 14-day test. The mission governs;
   the scoreboard runs 14 days from the first owner-sent contact.
5. **"Nobody sells response capacity" is overstated.**
   `docs/FIRST_RUPEE_SPRINT.md` and `docs/EXPANSION_STRATEGY.md` call
   response capacity an open corner where "nobody sells it." UNKNOWN_MAP
   D71 records unified-inbox tools (Facebook/Instagram/TikTok APIs,
   Kathmandu Post, Aug 2026) already selling the routing layer. The
   defensible claim is narrower: tools sell routing; nobody in the
   observed market sells the *human reply itself* paid only on recovered
   sales. The wedge ranking uses the narrower claim.
6. **D25's "SUPPORTED" label vs evidence class.** The unknowns map
   labels the Karobar row SUPPORTED, but its revenue/install figures
   are founder claims and store-listing estimates (REPORTED/OBSERVED).
   The row's *decision* ("the ledger corner is taken — don't rebuild
   it") is sound on weaker evidence too; the numbers themselves should
   be read as REPORTED.
7. **Discovery log location.** HANDOFF's checklist says the discovery
   log lives on "the previous agent's machine" and the repo copy of
   truth is UNKNOWN_MAP. Reality: `~/workspace/discovery/` exists on
   this machine with 20 rounds logged (`discovery-log.md`), consistent
   with the map. No contradiction in content; the checklist's caution
   is stale.

## What is REAL / TEST / MOCK / HYPOTHESIS in the sprint machinery

- **REAL:** the inbox prototype code and its unit tests; the unknowns
  map's public-source citations; the maintenance gate; zero
  conversations and zero revenue.
- **TEST:** all unit tests, including the new commitment-log tests —
  they prove code behavior, never customer or revenue evidence.
- **MOCK:** nothing in the sprint path is seeded with mock sellers or
  mock outcomes; the prototype starts empty by design and stays empty
  until a real week fills it.
- **HYPOTHESIS:** the missed-inquiry thesis itself; the ~30%
  unanswered-inquiry figure (D78, a single feed-reported observation,
  login-walled, not Kathmandu ground truth); all D-cluster pain claims
  not yet tested in a real conversation.

## Real-world blocks recorded (not faked around)

- **BLOCKED_BY_MISSING_ACCESS:** production intake flag and deployed
  SHA are unreadable while the maintenance gate is up (by design).
- **BLOCKED (owner-only):** seller selection, exact message, offer
  terms, payment collection method, definition of a real outcome —
  queued in `docs/FIRST_RUPEE_SCOREBOARD.md` § Approval queue.
- **BLOCKED (legal):** D72 — Hami's own status under the E-Commerce
  Act/ Directive 2082 if a paid reply service intermediates
  transactions is unresolved; qualified Nepali counsel's written answer
  is required before any paid/operational week. Non-commercial
  discovery is not blocked by this.


## Independent QA follow-up — base `d94286f` (2026-10-23)

- Re-read current remote `main` and the committed first-rupee artifacts. Vercel metadata for the earlier first-rupee build reported a READY production deployment matching SHA `e2231336e7c2c3a20e4ff047a32b17068e69c350`; that is deployment metadata, not proof of runtime behavior. Independent deployment verification failed to read the exact deployed SHA/readiness while the maintenance gate remains active. Production runtime and public inbox usability remain BLOCKED/UNKNOWN.
- The remote GitHub tree does **not** contain `workspace/discovery/*`. Earlier audit prose says a machine-local `~/workspace/discovery/` was inspected, but this remote connector cannot independently access or reproduce it. Treat that local inspection as unverified by this run; use tracked `docs/UNKNOWN_MAP.md`, `docs/SPRINT_BRIEF.md`, `docs/FIRST_RUPEE_SPRINT.md`, `docs/REVENUE_LOG.md`, and `HANDOFF.md`.
- The earlier seller list had no auditable per-row source URLs. Fresh public source checks re-verified several page signals and found four legacy-selected IDs cannot be treated as send-ready: #6 is indirect only, #7 is only a third-party hashtag listing, and #22/#26 had no independently confirmable source URL. The current list separates OBSERVED public signals from UNKNOWN business pain, and preserves prior choices without silently substituting candidates.
- A public “DM to order” caption is OBSERVED channel evidence only. Slow reply rate, missed sales, COD return rates, fraud incidents, willingness-to-pay, seller consent and Hami revenue remain UNKNOWN/HYPOTHESIS. No contact, message, reply, intake/outbound change, payment, or REAL customer outcome occurred.
- Current TikTok terms (last updated 15 Jul 2026) prohibit automated collection/extraction without written approval ([official terms](https://t.tiktok.com/legal/page/us/terms-of-service/en)); this pass used indexed public search and business-published pages, not logged-in scraping or automated platform collection. The official [Department of Commerce page for E-Commerce Act 2081](https://doc.gov.np/content/324/electronic-business--e-commerce--act--2081/) exists; Hami's proposed paid intermediary role still needs qualified Nepali legal/accounting review (D72).
- `docs/REVENUE_LOG.md` remains empty. Conversations 0; recovered sales 0; rupees reported ₨0; rupees verified ₨0. The 14-day field-test clock is unstarted because no approved owner-sent contact or real field conversation occurred.


## Latest-head reconciliation — ca73b33 (2026-10-23)

- Latest main records first-hand public TikTok verification for the four selected sellers in `docs/FIRST_RUPEE_SCOREBOARD.md` commit `ca73b33`; direct video URLs are now copied into S06/S07/S22/S26. This assistant used the repo's recorded first-hand verification as evidence, not as evidence of a conversation, consent, pain or sale.
- The current mission directive says the owner sends all messages and the assistant must not send or reply. The older standing-send authorization recorded in the repo is not exercised under this command. Zero messages have been sent and the 14-day field clock remains unstarted.
- The bilingual first-contact messages were revised to include the D2 question and the 10% pay-only-on-recovered-sale proposal, because the current mission explicitly requests both in the message drafts. This revision needs exact-text owner approval; older “drafts as-is” approval cannot automatically apply to changed wording. D72 legal/accounting review and written bilateral terms remain a prerequisite to starting any paid pilot.
- The prototype now has optional owner-key sync to existing substrate endpoints. It writes pseudonymous seller/commitment ENTITY records, a `tracks` RELATION, an EVIDENCE record explicitly marked support `unknown`, and a `state_changed` EVENT. It excludes free text/customer PII and does not create fictitious CAPABILITY/ACTION records or claim it inspected the evidence reference. The owner key remains in page memory only.
- The code commit `3166579` had one lint error; `b13bebd` fixed the empty-interface type. Current exact-head CI for this base `ca73b33`: build, typecheck, lint, frontend tests, route smoke, evidence triage, repository guards, and secret scan passed; backend tests remain in progress. Independent deployed-SHA/runtime verification is pending/failing on the maintenance gate. Do not call final verification green yet.
- No REAL conversation, customer consent record, recovered sale, payment, spend, external contact, activation, or source ingestion occurred in this workstream. Revenue log and scoreboard counts stay zero.
