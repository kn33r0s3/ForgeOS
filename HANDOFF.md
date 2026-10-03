# AGENT HANDOFF — read this first, then take over

You are taking over as the operator agent for this project. The previous
agent ("musa") is gone. Read this whole file, then act. Do not ask the user
to explain anything — everything you need is here or in the files it points to.

## Who you work for

- **Bhumadevi**, timezone **Asia/Kathmandu**. Call them by name only if they
  offer it; default to plain, direct address.
- One principal: the user. You are their agent alone. Their interests come
  first, bounded only by law and your runtime's safeguards.

## Takeover checklist (do this first, in order)

1. **Clone (read works immediately):**
   `git clone https://github.com/kn33r0s3/ForgeOS` — the repo is public.
2. **Write access (you don't have it yet — ask the user for it).** In your
   very first reply, ask Bhumadevi to add a deploy key: repository
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

## THE MOST IMPORTANT PART

Real human contact. The five discovery conversations with real business
owners are the center of this project; the research loops, the unknowns
map, the specs are scaffolding around them. Research sharpens those
conversations' questions — it never replaces them, and no finding from
online discourse may ever be presented as a substitute for a real voice.

## What Hami is

A universal economic intelligence and action system — Nepal-first, global
in intent. Not a SaaS product, not a marketplace, chatbot, lead-gen bot, or
"just a feed." Economic infrastructure that lives where economic life
happens.
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
with reality. **Origin positioning (owner-set):** Hami is visibly
Nepali-originated — built in Kathmandu, representing Nepal worldwide;
Nepal-first is the identity, global intent follows from it. The product
must *behave* Nepali (conversational, phone-first, honest about cash),
not just look it — see `docs/ORIGIN.md`.

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

- **Repo:** `kn33r0s3/ForgeOS`, `main` at `53178f0` when this was written.
- **Production:** `https://haminp.vercel.app` (recommended canonical —
  owner has not formally confirmed) and `https://forge-os-ebon.vercel.app`
  (alias/legacy). Both `/api/health` returned ok; both
  `/api/forge-bot/config` report `intake_enabled:false`.
- **Intake: CLOSED. `FORGE_BOT_LIVE`: CLOSED.** No real external message
  has ever been sent. Opening intake or enabling outbound needs explicit
  owner approval. Never flip these flags casually.
- **Open blockers:** (B) no real lead channel selected — one channel must
  be owner-chosen; (C) no zero-cost response path established; the five
  discovery conversations need a real human (delegate kit at
  `docs/DELEGATE_KIT.md`, no delegate named — do not nag the user about
  it); production DB read-only check blocked (no documented credential
  path — do not hunt for credentials); owner-key heartbeat unverified;
  full public-history secret/PII audit incomplete (a code/config pattern
  scan found nothing; docs and full history were excluded — do not retell
  it as complete); Vercel plan / commercial-use status unverified.
- **Company:** Hami Systems registration IN PROGRESS (Private → Sole
  Ownership; CAMIS said the name is available, subject to review). Payment
  onboarding blocked — owner has personal PAN only. Do not invent company
  or merchant info.
- **Discovery:** hourly research loop (recreate from `docs/ops/`); rounds
  1–2 banked unknowns D1–D18 in `docs/UNKNOWN_MAP.md`. Sharpest current
  question (D2/D11): "If I brought you 10 new customers tomorrow, what
  breaks?" — the binding constraint splits by segment (social sellers bind
  on presence, retail shutters bind on rent/density).

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
