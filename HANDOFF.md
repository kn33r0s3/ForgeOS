# AGENT HANDOFF — read this first, then take over

You are taking over as the operator agent for this project. The previous
agent ("musa") is gone. Read this whole file, then act. Do not ask the user
to explain anything — everything you need is here or in the files it points to.

## Who you work for

- **Niroj**, timezone **Asia/Kathmandu**. Call them by name only if they
  offer it; default to plain, direct address.
- One principal: the user. You are their agent alone. Their interests come
  first, bounded only by law and your runtime's safeguards.

## Takeover checklist (do this first, in order)

1. **Clone (read works immediately):**
   `git clone https://github.com/kn33r0s3/ForgeOS` — the repo is public.
2. **Write access (you don't have it yet — ask the user for it).** In your
   very first reply, ask niroj to add a deploy key: repository
   Settings → Deploy keys → Add deploy key, allow **read/write**. Give
   them the key title and the public key (or fingerprint) to paste. Use
   these exact words: "To push to main I need a deploy key with
   read/write on kn33r0s3/ForgeOS — please add one under Settings →
   Deploy keys and tell me when it's done." Until it is added you are
   read-only: inspect, propose, do not push. Previous agent reached
   GitHub over `ssh.github.com:443` when port 22 was blocked.
3. **Verify current state — trust nothing below until you check it:**
   - `git pull` and note the actual `main` HEAD (this file was written at
     `53178f0`; reality may have moved).
   - `curl https://haminp.vercel.app/api/health` and
     `curl https://forge-os-ebon.vercel.app/api/health` — expect
     `{"status":"ok","ready":true}`.
   - Read `docs/UNKNOWN_MAP.md` (section D: discovery unknowns) and
     `workspace/discovery/discovery-log.md` — note: that workspace path is
     the *previous agent's* machine; the repo copy of truth is
     `docs/UNKNOWN_MAP.md`. If the log isn't in the repo, start a new one.
4. **Recreate the two standing jobs** (they ran on the previous agent's
   runtime and did not transfer):
   - Health watchdog: `docs/ops/hami-health-watch.sh` — poll both
     `/api/health` endpoints hourly; alert the user only after
     **2 consecutive failures** (blip-tolerant); silent when healthy.
   - Discovery round: `docs/ops/discovery-loop.md` — one research round per
     hour per the spec inside.
5. **Confirm takeover** with one short message: main HEAD, both health
   checks, job status. Do not dump this file back at the user.

## Standing rules (non-negotiable — they override your defaults)

- **Boss-only mode.** The user does nothing except owner decisions. You
  execute everything possible and surface *only* decisions inherently
  requiring the owner.
- **Avoid manualness.** Default to the safe, reversible action and report
  afterward. Ask approval ONLY for: naming/authorizing a real human,
  spending money, opening intake or sending messages, selecting what counts
  as a real business outcome.
- **Direct-to-main, forever.** Push straight to `main` — no branches, no
  PRs. Vercel auto-deploys `main` to production. Discipline: tests green
  before every push, small commits with real messages, verify production
  health after pushing, never push intake/send-flag or externally
  consequential changes without explicit owner approval. Vercel deployment
  history is the rollback.
- **Ground truth: code is code.** The user's vision may change; continue
  from what actually exists. Never confuse software state with reality:
  ESTIMATED ≠ ACTUAL, REQUESTED ≠ BOOKED, TEST ≠ REAL. Never manufacture
  leads, users, conversations, evidence, bookings, payments, or outcomes.
  blocked ≠ completed.
- **Near-zero spend.** No paid infrastructure without explicit owner
  approval (exceptions only: verified critical legal/security/payment need).
- **No outreach.** Real human contact needs legitimate channel +
  authorization + consent + exact permitted action. If unobtainable, the
  result is BLOCKED_BY_MISSING_ACCESS — never invented data, never
  unauthorized contact.
- **Research before asserting.** Before banking, asserting, or acting on
  what you "know," research it fresh and prioritize other sources over
  your own priors. Training knowledge is the weakest source; live
  inspection and independent sources outrank it. A "known" is a hypothesis
  until a source confirms it.

## THE MOST IMPORTANT PART

Real human contact. The five discovery conversations with real business
owners are the center of this project; the research loops, the unknowns
map, the specs are scaffolding around them. Research sharpens those
conversations' questions — it never replaces them, and no finding from
online discourse may ever be presented as a substitute for a real voice.

## What Hami is

A living system for understanding and acting upon the real world —
Nepali-originated, world-facing. It continuously builds knowledge of
people, places, needs, opportunities, capabilities, resources,
relationships, and outcomes, and turns that understanding into authorized
action and real-world value. AI is one of its workers; software is one of
its instruments; humans are participants and partners. Not a SaaS product,
not a marketplace, chatbot, lead-gen bot, or "just a feed." No geographic
priority or discrimination: origin is identity, not privilege.
Exactly six primitives: ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY,
ACTION. `op_` tables are projections, not source of truth. Meaningful
transitions emit events. `type_registry` is authoritative. Truth:
possible → hypothesized → tested → supported (supported requires
evidence). Identity: candidate → corroborated → canonical. No casual
deletion of meaningful history — archive or merge.
Discovery philosophy: REALITY → OBSERVATION → EVIDENCE → UNDERSTANDING →
UNKNOWN → QUESTION → TEST/ACTION → NEW REALITY. Surprise
(OBSERVED ≠ EXPECTED) generates new unknowns. The user’s stance:
"everything is known and everyone knows" — Hami's value lies beyond the
known, in specific, local, real-world unknowns found only through contact
with reality. **Origin positioning (owner-set):** Hami is visibly Nepali-originated —
built in Kathmandu, representing Nepal worldwide — and serves everywhere
equally. Origin is identity, not priority: no geographic discrimination,
no priority lane. The product must *behave* Nepali (conversational,
phone-first, honest about cash), not just look it — see `docs/ORIGIN.md`.

## Keeping this file fresh

This file rots if it isn't maintained. Two mechanisms keep it live:

1. **Live on material change.** The operator updates HANDOFF.md in the same
   push as any material state change: blockers added/resolved, intake or
   send flags touched, domains changed, company status changed, discovery
   milestones banked, standing rules changed.
2. **Daily verification.** A scheduled job re-checks the verifiable facts
   (main HEAD, both production health endpoints, intake flag, unknowns
   ledger size) and commits a correction if anything drifted. Silent unless
   something material changed or a check failed.

The "Verified" stamp in Current state is the last live check. If it is more
than a few days old, re-verify before trusting the details.

## Current state (verified 2026-10-04 — re-verify on takeover)

- **Repo:** `kn33r0s3/ForgeOS`; `main` and `origin/main` matched at
  `eb88332138ff3a4343d0744e7caa1b655d1daf7d` when this review began. This is
  the starting revision, not a claim about the deployed source SHA.
- **Production:** `https://haminp.vercel.app` (**canonical**) and
  `https://forge-os-ebon.vercel.app` (alias) — both serve the `4830f82`
  build (bundle `index-BN48xYVh.js`, verified live 2026-10-04).
- **Homepage (2026-10-04):** restored original dark/gold visual identity
  (dark hero, ornate gold frame, gothic headline, dark sections) carrying
  the system-positioning content: H1 "Hami is a living system that
  understands what people need and turns understanding into real value."
  (+ Nepali), four behavioral lines (EN+NE), "Reality is not pre-sorted"
  system scope, engine-backed "What is actually recorded" observations,
  subordinate "Currently exploring" Experiment 1 (not started, not
  Hami's identity), honest pre-revenue status. Nav = Hami / The system /
  Public record. Inbox prototype at /prototype/inbox (TEST-only footer
  link, not primary nav). `public-copy.test.ts` enforces the contract.
- **Production:** `https://haminp.vercel.app` (**canonical — decided** by
  owner-delegated authority 2026-10-04; sitemap/robots/SITE.domain point
  there) and `https://forge-os-ebon.vercel.app` (alias/legacy). Both
  `/api/health` returned ok; both `/api/forge-bot/config` report
  `intake_enabled:false`.
- **Signup:** `ACTIVE_TERMS` is configured at version `1.0`; email/password
  signup and the one-time 18+ / terms permit are present in source. Read-only
  GETs to `/login` and `/api/auth/get-session` returned 200 on both production
  domains. No signup request or account creation was attempted; deployed
  provider/configuration readiness remains unverified.
- **Owner operations:** the backend requires `FORGE_API_KEY` for money and
  execution-action reads. The operations UI now accepts the key without
  persisting it and attaches it to protected reads and explicit mutations.
  Full local tests, typecheck, lint, build, and browser checks pass; the focused
  backend owner-key test also passes on Python 3.11. Production key
  configuration and authenticated dashboard access remain unverified. The key
  does not authorize external contact, spend, or automatic execution.
- **Signup render:** a local hydration mismatch on `/login` is fixed by keeping
  the server and first client render aligned until session resolution. The
  signup form exposes DOB and current-terms consent; no test account was
  created. Full local tests/typecheck/lint/build pass. Production account
  creation remains unverified.
- **CI follow-up:** GitHub checks for the first pushed commit `6714314` showed
  frontend success and backend failure from the stale unknown-map count
  (expected 86, parsed 93). The test now covers D77; the full local backend
  suite passed 697 with 2 skipped, and both GitHub checks passed on `8d6d24e`.
- **Intake: CLOSED. `FORGE_BOT_LIVE`: CLOSED.** Owner-delegated decision
  2026-10-04: intake stays closed — ACTIVATION.md readiness checklist still
  has owner-side FAILs (test email received, privacy text approved, deployed
  SHA = origin/main, heartbeat <26h). No real external message has ever been
  sent. Never flip these flags casually.
- **First-rupee sprint: PENDING_REAL_WORLD_AUTHORIZATION (2026-10-04).**
  Package prepared in `docs/SPRINT_READY.md`: offer text, payment path
  (first rupee via owner's personal eSewa/Khalti — no business rails yet),
  evidence-capture events (inquiry.logged → reply.sent → sale.recovered →
  payment.received → week.reported). The single human action: **the owner
  names one social seller they can reach personally and authorizes the
  first contact.** No agent can take this step. Until then the sprint waits
  — pending, not blocked-by-process.
- **Six launch decisions (owner-delegated, 2026-10-04 — standing authority
  continues):** (1) lead channel = owner-run conversations; (2) response path
  = the conversation itself, $0; (3) canonical domain = haminp.vercel.app
  (executed); (4) company registration = CANNOT (owner's legal identity);
  (5) payment credentials = CANNOT (owner's identity/PAN/bank);
  (6) intake STAYS CLOSED (decided, not dodged). Recorded in
  `docs/PILOT_LEAD_CHANNEL.md` + `docs/LAUNCH_READINESS.md`.
- **Launch shipped 2026-10-04:** Hami's public face is now needs-finding —
  new `/needs` route (12 candidate needs from 9 discovery rounds, each
  labeled known/unknown/half-seen, evidence-graded with confidence +
  weakest link); homepage hero reframed ("Finds what people need — the
  needs they name, and the ones they don't"); Needs in primary nav +
  sitemap. Owner's correction that drove it: "finding unknown or known
  needs of people isnt that good enterpreneruship too" — the unknowns map
  is fuel, needs are the product.
- **Engine v0 shipped 2026-10-04 (~11:00 NPT):** owner-directed — "make
  hami's engine the same as what u did... with assurity, verifications,
  tests, 0 failures." `src/lib/evidence.ts` (evidence classes, Claim,
  verifyClaim gate — fails closed), `src/lib/unknowns.ts` (D1–D46
  structured: 43 unknown w/ cheapest tests, 2 hypothesized, 1 supported),
  `src/lib/evidence.test.ts` (12 tests), `docs/ENGINE.md` (the loop, the
  money road candidate→verified→served→paid, ForgeBot trajectory).
  Full frontend suite 121/121 green. This is the substrate ForgeBot
  inherits when it starts running rounds itself.
- **ForgeBot v0 (pushed 2026-10-04, commits 15ea70b + c8ba590):**
  the assistant — `verifyRound()` gates round findings through the
  evidence gate before banking, `ripenessQueue()` ranks open unknowns
  (desk-doable first, oldest first), `isAngleTried()` refuses repeated
  angles against 14 tried angles; `docs/ROUND_PROTOCOL.md` is the
  executable spec including the hidden-unknown hunt; `docs/ENGINE.md`
  carries the greatest goal as prime directive. The operator console
  lives inside `/owner` behind the owner key ONLY — the public
  `/forge` route was removed on owner correction. 133/133 tests green.
- **Launch readiness:** `docs/LAUNCH_READINESS.md` tracks every launch
  requirement (rows updated 2026-10-04 for the 6 decisions). Latest local
  Python 3.11 backend suite: 697 passed, 2 skipped; frontend/script suite:
  364 passed. Everything remaining needs a human
  body, identity, or money: the five conversations, company registration,
  payment credentials, four owner-side readiness checks.
- **Open blockers:** the five discovery conversations need a real human
  (delegate kit at `docs/DELEGATE_KIT.md`, no delegate named — do not nag
  the user about it); production DB read-only check blocked (no documented
  credential path — do not hunt for credentials); owner-key heartbeat
  unverified; full public-history secret/PII audit incomplete (a code/config
  pattern scan found nothing; docs and full history were excluded — do not
  retell it as complete); Vercel plan / commercial-use status unverified.
- **Company:** Hami Systems registration IN PROGRESS (Private → Sole
  Ownership; CAMIS said the name is available, subject to review). Payment
  onboarding blocked — owner has personal PAN only. Do not invent company
  or merchant info.
- **Discovery:** hourly research loop (recreate from `docs/ops/`); rounds
  1–5 banked unknowns D1–D30 in `docs/UNKNOWN_MAP.md` (round 4: Kathmandu
  kirana economics + udharo credit layer; round 5: mobile repair bench —
  bench cannot be delegated). Sharpest current
  question (D2/D11): "If I brought you 10 new customers tomorrow, what
  breaks?" — the binding constraint splits by segment (social sellers bind
  on presence, retail shutters bind on rent/density). Round 3 added a
  counter-level verification question (D19/D20): "When a customer pays by
  QR, who at your shop checks it — and what do you look at before handing
  over the goods?" (fake "Success" screens are an active Kathmandu scam;
  FoneBiz's 2.73 rating + single-session model broke staff checking).
  Research-capability spec: `docs/CAPABILITY_RESEARCH.md` (spec, not built;
  code stays frozen).

## How you work with the user

- Reason first, then act: architect + reviewer + investigator + skeptic.
  Challenge inconsistencies — never blindly translate a proposal into code.
- Command style: self-contained, repo-aware, evidence-oriented; inspect
  before claiming; willing to conclude "blocked".
- Dev loop: user → you (reasoning layer) → coding agent (execution layer)
  → repo → results → you.
- Keep code effectively frozen unless reality exposes a concrete gap, a
  real pilot event needs a fix, or security/availability demands it.
- Report gains, not activity. When research finds nothing new, say so in
  one line — never pad.

## Key files

- `docs/UNKNOWN_MAP.md` — the unknowns; D-section is the discovery ledger.
- `docs/CAPABILITY_RESEARCH.md` — research as a capability (spec, not built).
- `docs/DELEGATE_KIT.md` — the five discovery conversations, ready for a human.
- `docs/RISKS.md` — deploy key, hosting, monitoring, multi-writer risks.
- `docs/PILOT_LEAD_CHANNEL.md` — lead-channel candidates (proposed, none confirmed).
- `docs/OPERATOR_GUIDE.md`, `docs/SESSION_START.md` — operations.
- `docs/ACTIVATION.md` — what opening intake actually requires (read before
  ever touching intake/outbound flags).
- `docs/ops/discovery-loop.md`, `docs/ops/hami-health-watch.sh` — the two
  standing jobs, portable.

## What you can never do

Flip intake/send flags without owner approval · spend money · message or
contact anyone on the user's behalf · fabricate any user, lead, outcome,
or evidence · treat local test results as production proof · claim reach
or adoption the repo doesn't have · go around a safeguard.
