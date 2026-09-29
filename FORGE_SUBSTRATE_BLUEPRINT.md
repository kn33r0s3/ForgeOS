# ForgeOS — Forge Bot v0 Execution Blueprint

## 0. Rules for every agent

1. Only Copilot commits. Every other agent drafts in chat.
2. One slice per PR. Write acceptance tests first. Full backend suite green, `git diff --check` clean.
3. Do not edit AGENTS.md unless the owner has approved that specific change (see G0.3).
4. No new paid service, no new top-level framework, no new ledger or status file. Record progress in STATUS.md only.
5. Test data is TEST evidence. It never counts as customer, demand or revenue evidence.
6. Real lead data, credentials and client configuration never enter the repo, logs or test fixtures.
7. If this document contradicts the code, stop and report the contradiction. Do not silently pick one.
8. Unknown facts stay UNVERIFIED. Do not fill gaps with plausible guesses.

## 1. Objective

One real paying consultancy using Forge Bot v0 by **2026-11-28**. Kill rule (from REVENUE_LOG): no paid pilot
by day 30 (**2026-10-28**) means change the customer or the offer, not the technology.

Forge Bot v0 = inbound lead → instant honest reply → qualify → follow-up → booking request → owner confirms
→ daily owner summary.

**Non-goals (frozen, not deleted):** research collectors, capability discovery, global demand engine,
WhatsApp/Viber/Messenger, paid LLM, multi-tenant SaaS, payments, mass outbound.

**Measure only these** (from real pilot data, never tests):
median time-to-first-response, % leads qualified, % booking requests, % bookings confirmed,
owner minutes per day (self-reported). If there is no real data, report NOT MEASURABLE, never zero.

---

## 2. Phase 0 — Repo gates (run in parallel with Phase 1; owner is not blocked)

| Gate | Action | Owner approval? |
|---|---|---|
| G0.1 | Set the repo private, or at minimum run a secret scan (e.g. gitleaks, free) over the FULL history. Rotate anything found. Review `storage/`, `logs/`, `attachments/`, `screenshots/` for personal data or DB files. | Yes (visibility) |
| G0.2 | Run the local-size forensics already written. Report only; no cleanup or history rewrite before the report. | No |
| G0.3 | AGENTS.md currently pairs ForgeOS rules with a long Grok "App Builder" sandbox contract (different framework, port, branding injector, no-.env rule). Replace with a ForgeOS-only file (target under 80 lines): top rule, bootstrap rule, agent roles, truth labels, test/verify commands. Move the Grok contract out of the default agent path. | **Yes — explicit** |
| G0.4 | Mark research collectors, capability discovery and demand-understanding modules FROZEN in STATUS.md. No new collectors. Keep code and tests. | No |
| G0.5 | Consolidate docs to one README (what/run/test), one STATUS (current only), one BLUEPRINT (this), one backlog (CAPABILITY_QUEUE). Move the rest to `docs/archive/`. Untrack `.DS_Store`, `opencode.jsonc.bad`, `.node_modules.lock`, other agents' folders (`.grok`, `.agents`, `opencode.json`) unless a current tool needs them. | Yes (file removal) |
| G0.6 | Choose ONE frontend (README says root Vite is current; STATUS references `frontend/` Next.js) and ONE production target. Record the decision in STATUS.md. | Yes |
| G0.7 | Verify the briefing's claim that `services/forge-bot/SPEC.md` and `docs/REVENUE_LOG.md` are on main. On 2026-09-29 the root listing showed `services/` containing only `evidence-triage`. If missing, report it. | No |
| G0.8 | Decide the database for v0 and record it. STATUS.md documents SQLite (WAL) as canonical; the build instruction says PostgreSQL. *(Claude proposal)* SQLite on the VM's local disk, nightly encrypted off-box backup; move to Postgres when concurrency or a second client requires it. | Yes |

---

## 3. Phase 1 — Concierge pilot (no new code)

Purpose: learn the real workflow before automating it. This is the owner's work; agents only draft materials.

1. Run the five consultancy-owner conversations. Ask in this order:
   - Where does a new lead first contact you? (Facebook, WhatsApp, Viber, phone, walk-in, web form.) **HYPOTHESIS to test: most arrive outside a web form.**
   - How long until you reply? Who replies? What do you ask first?
   - How many leads per week? How many book a consultation? How many enrol?
   - What do you lose when replies are slow? What would you pay to fix it?
2. Offer one consultancy a two-week concierge pilot: a form link on their existing channel; the owner (or the
   consultancy's staff) sends templated replies; every lead and timing goes in a spreadsheet.
3. Output: real question list, real objections, baseline response times, real volume, and a price signal.
   These become the configuration for Phase 2. Label as REAL only if it came from actual leads.

**Exit gate:** at least one consultancy agrees to a pilot, or Day 21 (**2026-10-19**), whichever first.
Slices S4 onward wait for this gate. S1–S3 may start earlier because any demo needs them.

---

## 4. Phase 2 — Architecture

### 4.1 Approach *(Claude proposal — REQUIRES OWNER, decision D1)*

Forge Bot owns a small set of narrow tables in the existing database and **emits a substrate Event per
transition** (audit trail and learning input). The substrate is the record of what happened; Forge Bot tables
are the working state. This avoids forcing consent, booking and messaging records into Signal/Evidence shapes.
If the owner rejects D1, Copilot must map every field below onto existing records and show the mapping before coding.

Adapt paths to the real layout. Suggested module: `backend/app/forgebot/`

```
models.py     schemas.py     service.py      guard.py        templates.py
followup.py   booking.py     summary.py      email_smtp.py   api.py
```

### 4.2 Tables (all carry `client_id`; v0 has one client)

- `fb_lead`: id, client_id, created_at, name, email, phone, destination, course, timeline, budget_range,
  source, state, outcome, outcome_note, last_inbound_at, last_outbound_at, idempotency_key (unique),
  is_test (bool), purged_at. Require email OR phone.
- `fb_consent` (append-only): id, lead_id, channel, purpose, action (`granted`/`opted_out`/`re_granted`),
  consent_text_version, at, request_fingerprint_hash. No raw IP.
- `fb_message`: id, lead_id, direction, channel, template_id, status (`queued`/`sent`/`failed`/`blocked`),
  block_reason, idempotency_key (unique), created_at.
- `fb_booking_request`: id, lead_id, requested_slot, status (`requested`/`confirmed`/`declined`/`expired`),
  confirmed_by, confirmed_at.
- Follow-ups use the existing `WorkerTask` machinery: type `forgebot.followup`, idempotency key `lead_id:step`.
- Client configuration (approved FAQ answers, slots, criteria, templates text) lives in the database or a
  secret store, never in the public repo.

### 4.3 State model — three independent axes

**Conversation state** (bot- or owner-driven):
`NEW → CONTACTED → QUALIFYING → QUALIFIED → BOOKING_REQUESTED → BOOKED`,
plus `DISQUALIFIED`, `NO_RESPONSE`, `ESCALATED`, `CLOSED`.

| From | To | Required evidence |
|---|---|---|
| NEW | CONTACTED | sent `fb_message` (or owner marks manually sent) |
| CONTACTED | QUALIFYING | first questionnaire answer stored |
| QUALIFYING | QUALIFIED / DISQUALIFIED | all required answers present; client criteria applied |
| QUALIFIED | BOOKING_REQUESTED | lead selected a slot |
| BOOKING_REQUESTED | BOOKED | owner confirmation action (never automatic) |
| BOOKING_REQUESTED | QUALIFIED | owner declined slot |
| active states | NO_RESPONSE | final follow-up sent + configured wait passed |
| any | ESCALATED | out-of-policy question, complaint, or human requested |
| any | CLOSED | owner action |

**Consent state** (orthogonal, from `fb_consent`): `granted` or `opted_out`. Opt-out can happen in ANY state and
permanently blocks outbound until a fresh explicit `re_granted` record exists.

**Commercial outcome** (owner-entered only, never inferred by the bot):
`NONE / MEETING_HELD / PROPOSAL / ENROLLED / LOST`, with a note.
"Enrolled" means the consultancy's client enrolled. It is not ForgeOS revenue. ForgeOS revenue lives only in
`docs/REVENUE_LOG.md` as REAL evidence (invoice, bank record).

### 4.4 Outbound guard (single choke point)

All sends go through `send(lead, template_id)`, which calls `guard.can_send()`:

- consent is `granted` and not opted out
- channel enabled for this client
- `template_id` exists, is client-approved, and has no forbidden claim words (lint at load time)
- state permits the send; rate and quiet-hours limits (Asia/Kathmandu) respected
- idempotency key not already used

Blocked attempts are logged as `fb_message.status = blocked` with a reason. v0 sends **templates only**: no
generated free text. An architecture test must fail if any code imports the SMTP adapter except through `send()`.

Every template must state that it is automated, give the next step, and include an opt-out link. Nepali text is
reviewed by a native speaker (REQUIRES OWNER). Forbidden-claim lint covers guarantees of visas, admission,
employment, or unsupported fees.

---

## 5. Build slices

Each slice: tests first, one PR, STATUS.md updated with real command output.

**S1 — Intake.** `POST /forgebot/leads` plus a simple form. Validation, honeypot, per-IP and per-email rate limit,
payload size cap, idempotency key, consent checkbox with versioned text stored. No document uploads.
Done when: valid submit creates lead + consent + Event; duplicate submit is a no-op; invalid input is rejected;
the submission creates no customer, opportunity, payment or revenue record.

**S2 — Consent registry and guard.** Implement `fb_consent`, opt-out endpoint (signed link), and `guard.can_send()`.
Done when: opted-out leads cannot be sent anything through any path; re-consent requires an explicit new record;
the architecture test for the single choke point passes.

**S3 — Auto-reply.** `T_ACK` with disclosure, opt-out link and questionnaire link. Behind a feature flag.
If email is not configured, create an owner-send draft instead of sending.
Done when: reply is queued exactly once per lead; contains disclosure and opt-out; no unsupported claims.

**S4 — Qualification** (after Phase 1 gate). Config-driven questions on a signed, expiring, single-lead page
`/q/{token}`. Each question allows "not sure". Unknown stays unknown.
Done when: answers persist across restart; QUALIFIED/DISQUALIFIED follows client criteria; tokens cannot be reused
for another lead.

**S5 — Follow-up.** Max two follow-ups (about +24h and +72h, configurable) via `WorkerTask`.
Cancel on: opt-out, booking requested or later, owner marks "replied", ESCALATED, CLOSED.
Done when: retry, stale-lease recovery, idempotency and cancellation are each tested; restart does not duplicate sends.

**S6 — Booking request.** Owner-configured slots; lead picks on `/b/{token}`; state becomes BOOKING_REQUESTED;
owner is notified; owner confirms in the dashboard; confirmation message sent. All wording says "requested"
until the owner confirms.
Done when: no code path can set BOOKED without the owner action; a test asserts the "requested" wording.

**S7 — Owner summary.** Daily generated report and a `/owner/summary` page from persisted state: counts by
state, lead table, stuck more than 48h, escalations, opt-outs, median response time. No free-text personal data
beyond what the owner already sees in the lead table.
Done when: numbers match a hand count on seeded TEST data.

**S8 — Ops.** Docker Compose on the chosen host, HTTPS, health endpoint, nightly backup encrypted then copied
off the machine, and one **restore drill** before go-live.
Done when: a clean machine can be rebuilt from the repo plus the backup within a documented time.

**Email (part of S3/S6).** SMTP send only. Credentials from environment or a secret store, never the repo.
Use the consultancy's own authorized mailbox, or keep email disabled. Owner checks the mailbox provider's
sending limits and terms (REQUIRES OWNER). Set up SPF, DKIM, DMARC for the sending domain and test deliverability.
**Inbound email parsing is out of scope for v0**: replies go to the owner's normal inbox and the owner clicks
"mark replied." Add IMAP only after real pilot friction proves it is needed.

---

## 6. Privacy and data

Collect only: name, email or phone, destination, course, timeline, budget range. Never passports, IDs,
financial or academic documents. No personal data in application logs. Retention: purge or anonymise closed and
no-response leads after a period chosen with a lawyer (placeholder 90 days; REQUIRES OWNER/LAWYER). Provide an
owner action to export or delete a lead. Nepal's Individual Privacy Act, 2075 implications for the pilot terms
need a real lawyer (REQUIRES EXTERNAL CONFIRMATION).

## 7. Hosting

- Oracle Always Free Arm: Oracle's "Always Free Resources" docs page lists **2 OCPU / 12 GB** (REAL, read 2026-09-29).
  Oracle's docs are inconsistent: another Oracle page still shows 4 / 24. Plan for 2 / 12 and confirm the real limits
  in the account's own console. The 2026-08-18 enforcement date comes from community/blog reports, not from Oracle
  (REPORTED). Idle Always Free instances may be reclaimed: idle means, over 7 days, p95 CPU < 20%, network < 20%,
  and (A1 only) memory < 20% (REAL, Oracle docs). Always Free instances must be created in the home region, and
  "out of host capacity" errors can occur (REAL, Oracle docs). Arm means images must be aarch64. Whether Oracle's
  free-tier terms permit commercial use is UNVERIFIED (REQUIRES EXTERNAL CONFIRMATION).
- Copilot verifies whether an account and capacity exist. If not, buy nothing. Run demos locally and treat
  production hosting as blocked until the owner decides.
- Vercel Hobby is restricted to non-commercial personal use (REAL: Vercel's own Hobby plan docs, read 2026-09-29).
  Do not use it for a paying client.
- A domain name for HTTPS may cost money (small). Treat it as a critical-execution exception and ask the owner (D6).
- Reuse the existing `docker-compose.yml` and `Caddyfile` where they fit.

## 8. Test matrix (minimum)

Intake validation · consent stored · idempotent duplicate · abuse limits · deterministic reply · disclosure and
opt-out present · forbidden-claim lint · STOP/opt-out permanent · re-consent required · guard blocks every path ·
follow-up scheduled / retried / cancelled / not duplicated after restart · booking "requested" vs "confirmed" ·
BOOKED only via owner action · summary matches seeded data · no PII in logs · tokens scoped to one lead ·
state and outbox survive restart.

**PILOT-READY** (never "successful") means: one real inbound path, one real reply path, qualification,
follow-up, booking workflow, escalation, permanent STOP, owner summary, persistence, restore drill passed,
and no new paid infrastructure. Commercial truth comes only from the first real paying customer.

## 9. Decision gates *(Claude proposals — HYPOTHESIS thresholds)*

- **Day 10 (2026-10-08):** fewer than 3 real owner conversations held → the problem is outreach, not product.
  Stop building; the owner does conversations.
- **Day 14 (2026-10-12):** conversations held but none names slow lead response as a real cost → change the
  customer segment or the offer.
- **Day 21 (2026-10-19):** start S4+ even without a commitment only if the owner explicitly approves.
- **Day 30 (2026-10-28):** no paid pilot → kill rule triggers.

## 10. Owner-only decisions

- **D1** Allow narrow Forge Bot tables plus substrate Events (section 4.1), or require full mapping onto existing records.
- **D2** Approve the AGENTS.md split (G0.3).
- **D3** Confirm the v0 channel after Phase 1 learns where leads actually arrive.
- **D4** Pilot price and terms; banking and legal receipt of payment.
- **D5** Lawyer review of privacy and pilot terms.
- **D6** Hosting target and domain spend.
- **D7** Repo visibility and history-scan findings (G0.1).

## 11. Agents must not

Expand the global-network blueprint · add collectors or research features · add WhatsApp, Viber, Messenger or an
LLM · create a second status document · delete branches or rewrite history without owner approval · contact a
real person · treat test data as evidence · declare commercial success · state a hypothesis as fact.