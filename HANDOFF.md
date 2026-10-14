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
2. **Verify the write path actually available in this run.** This checklist's old instruction to request a deploy key is stale whenever the connected GitHub integration reports repository `push` permission and successfully commits a narrowly scoped update to `main`. On 2026-10-14, GitHub repository metadata reported `admin/maintain/push: true`, and contents-API updates to `STATE.md` and `docs/CAPABILITY_QUEUE.md` succeeded directly on `main` (commits `6b0f3697` and `771cdce5`). Use the connected, verified write path; do not ask the owner for a deploy key merely because this historical handoff says read-only. Recheck current permissions and main HEAD each run. If the available write path fails, record the actual error and continue read-only rather than inventing access or asking for credentials unnecessarily.
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

Firsthand conversations and field checks are indispensable evidence sources, not the sole center of Hami's work. Research, capability-building, reliability, knowledge synthesis and connection work continue in parallel and make real-world tests more useful. Online discourse never substitutes for a real voice where firsthand experience is required. No contact occurs without required authority and consent.

## What Hami is

A living system for understanding and acting across domains—Nepali-originated, world-facing. It continuously builds knowledge of people, places, needs, opportunities, capabilities, resources, relationships, constraints and outcomes, then turns that understanding into authorized action and fair, measurable value. Hami is the system name; Hamro (our/ours) expresses shared progress. No single customer type, product, market, pilot or fixed roadmap defines it. Multiple discovery, research, engineering, reliability, connection and outcome tracks can progress in parallel, coordinating through shared evidence and explicit dependencies. A blocked external action must not stop unrelated safe work; this direction is not proof that unattended autonomy is already live.

Not a SaaS product, marketplace, chatbot, lead-gen bot or just a feed. Exactly six primitives: ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION. `op_` tables are projections, not source of truth. Meaningful transitions emit events. `type_registry` is authoritative. Truth: possible → hypothesized → tested → supported (supported requires evidence). Identity: candidate → corroborated → canonical. Archive or merge useful history; do not casually delete it.

Discovery: REALITY → OBSERVATION → EVIDENCE → UNDERSTANDING → UNKNOWN → QUESTION → TEST/ACTION → NEW REALITY. Surprise (OBSERVED ≠ EXPECTED) creates new unknowns. Online research generates hypotheses but does not substitute for firsthand evidence when a question requires a real human voice. Built in Kathmandu, representing Nepal worldwide, and serving everywhere equally; origin is identity, not privilege.

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

## Last verified state snapshot (2026-10-14)

**Update 2026-10-14 (scheduled loop, owner outcome lane + cross-climb links; regression additions through `1d4453cb`):**
- The scheduled intelligence path reads the canonical Operating Model contact state. It prioritizes unreviewed sent-contact outcomes before research even if a reply was recently recorded; otherwise missing contact history or at least 2 days without contact prioritizes existing Scout preparation. The 14-day STARVED tripwire blocks only builds/public-content drafting dependent on the starved intervention; it must not halt independent safe research, reliability, security/privacy, testing or reusable-capability work. No contact is fabricated or initiated merely to reset the clock.
- The contact clock now excludes `outreach.sent`: `mark_sent()` explicitly records only an owner-reported send, not verified recipient receipt or interaction. Replies and held conversations continue to reset the clock. Regression tests ensure a recent unanswered send cannot hide a 10-day-old reply or suppress STARVED when no reply/conversation exists.
- The owner-only `Sent contacts — outcomes` queue records actual replies and separate `outreach.no_response` dry wells through the validated EVENT/type-registry path. A dry well remains visible for a late reply but does not demand daily re-review or unlock another message. Duplicate reply writes are rejected; all owner-reported contact facts remain unverified unless independently anchored.
- Scout no longer creates repeated `DRAFT`/`APPROVED` messages for a candidate that already has an unresolved draft. It still never sends; owner authorization and contact gates remain unchanged.
- When an unresolved draft already exists for a candidate, Scout reports that queued owner work before evaluating whether a new send could be allowed; this does not relax the no-repeat-without-reply send guard.
- The existing `CycleRun.summary_json` now includes a `cycle_effect` assessment. Only signals reported by completed collector tasks count as collected source signals. Proposals, questions, action proposals and drafts are classified as Hami-created internal work, not proof of real-world effect. A cycle with only internal work or no new effect is recorded as PARTIAL instead of silently COMPLETED.
- The existing owner cockpit displays the nested cycle effect, positive counts, next owner attention and the reality boundary. Early-priority and ordinary Scout stages expose the same pending-contact metrics. A recorded dry well stays available for a late reply without trapping the scheduler in contact-priority mode.
- Regression tests were added for contact-priority thresholds, the rule that outbound attempts do not reset real contact, duplicate-draft prevention/visibility, contact-first ordering, STARVED content freeze, no-effect/internal-work classification, and exclusion of deferred collector output from source-signal counts.
- The explicit `ResearchQuestion.source_rare_signal_id` is now projected into a provenance-bearing `derived_from` relation using the active `rare_signal_assessment` type and its canonical adapter. The existing legacy-record projector also emits hashed lifecycle snapshot events for rare-signal assessments; raw explanation text and source signal IDs are not copied. Tests cover type/adapter resolution, relation idempotency and snapshot refresh.
- Judgment identity now includes the claim/opportunity context, and the cache recovers from recorded `judge unavailable` / missing-evidence failures only when the corresponding cause clears. Failed history is preserved; unrelated failures are not repeated every cycle. A regression tests unavailable → available → stable cache behavior.
- The main CI workflow was adjusted so newer pushes no longer cancel an in-progress `main` verification. This is intended to let the exact-head run finish; the connected GitHub workflow tool still does not expose push-triggered runs.
- **Verification boundary:** GitHub status for code commit `1d4453cb9af5afd6d4c68cb8ef6df24e32177370` reported Vercel **PENDING** at the last check. The protected Vercel deployment/runtime API returned 403 for the project scope. The main CI cancellation rule was fixed, but no exact-head backend pytest result is exposed through the current connector. Production `/api/health`, durable DB readiness, scheduler invocation, deployed SHA and live flags remain unverified. Do not claim production health or green tests from source presence alone.
- **Reality boundary unchanged:** no autonomous customer messaging, real conversation, fulfillment, payment, or revenue was created or claimed by this implementation.

**Update 2026-10-14 (loop round 11 — legal vs behavior):** /privacy
and /terms read in full against live behavior. No live contradictions:
the privacy text honestly covers the (closed) inquiry form, its
30-day auto-erasure, processors (Vercel/Neon/email/Cal.com), and no
automatic reply; terms v1.0 matches the signup machinery in code
(18+/DOB gate, version recorded). Two LATENT items for the day auth
is enabled, recorded here for that checklist: (1) the privacy page's
scope predates the public board and accounts — it covers only the
inquiry form and still wears its DRAFT FOR OWNER APPROVAL badge;
(2) terms §5 grants account-deletion requests "at any time" while
§9 states all contact channels are closed — the right exists before
any channel does. Both are owner/legal decisions, not code fixes.

**Update 2026-10-14 (loop round 10 — close read):** /about, /process,
/technology, /ventures, /opportunities, /actions read in full: claims
discipline holds everywhere (no manufactured outcomes; the pilot is
framed as one candidate test; inquiries closed). One copy defect
found in the shared strategic-area template: the hero read
"Technology is building." / "Ventures is building." — fixed to
"is being built." in src/components/pages/area-view.tsx, which
carries both pages.

**Update 2026-10-14 (loop round 4 — unknowns counts settled):** The
/unknowns page (100 known unknowns: 96 unknown, 3 hypothesized,
1 supported) was diffed question-by-question against
/api/forge/unknowns (114 rows). The page is exact: B1–B4 are the
engine's C33–C36, and all 96 D-questions match the API's current D
rows with identical states. The API's extra 14 = 12 internal C-section
ops questions (correctly not public) + 2 SUPERSEDED DUPLICATES: D35
(ids 74 and 166) and D72 (ids 111 and 117) each exist as an old and a
revised version — a discovery revision added the new row without
retiring the old, so the forge API overcounts by 2 (112 unique
row_ids). Backend data note for the substrate workstream: retire or
supersede-flag ids 74 and 111. Public surface unaffected.

**Update 2026-10-14 (loop round 3 — title audit):** A per-route SSR
title audit (the /domain fix generalized) found two more routes
falling back to the generic site title: /services and /providers.
Both gained their own <title> on the existing route definitions
("Services — Hami", "Verified providers — Hami"). All other audited
routes already declare distinct titles. Round 2's pictured audit also
closed: the header/footer fix verified in a real browser; /operations
and /prototype/inbox inspected in code and confirmed intentional —
operator-key-gated and browser-local respectively, both covered by
existing tests; no change made.

**Update 2026-10-14 (public-surface QA fix):** Owner-ordered
verify-and-fix loop over haminp.vercel.app. A pictured sweep found the
header's Login and Join Hami CTAs land on a dead end: /login renders
only "Sign-in is unavailable in this app configuration." Production
/login loader data confirms why — `authConfigured: false`
(googleConfigured: false, termsConfigured: true); the login page's gate
is `!authEnabled || !authConfigured` (src/routes/login.tsx). Fix on the
existing seams: src/routes/__root.tsx now loads getAuthAvailability()
once (fails closed), and SiteHeader/SiteFooter apply the same gate —
Login, Join Hami, and the footer Sign in link render only when auth is
enabled AND configured. Also: /domain gained its own <title>
("Needs, offers, and fair exchanges — Hami"); it previously fell back
to the generic site title. Enabling auth itself (provider + auth env
in the Vercel project) remains an owner/dashboard action; until then
the site no longer advertises a dead end. Local gate green before
push: 257 tests, typecheck, lint (1 pre-existing warning), build.

**Update 2026-10-14 (daily freshness check):** HEAD at `a770003`
("docs: update verified QA checkpoint"). Pull fast-forwarded
`25d4e3a..a770003` clean (37 commits: QA doc trail, mobile nav
focus fix, concurrent canonical-entity fix); `main` ==
`origin/main`. Working tree clean.

- **Health:** haminp.vercel.app/api/health → ok (`status: ok`,
  `db: up`, v2.3.0, checked 2026-10-14 ~06:23 NPT) — recovered from
  yesterday's DEGRADED (db: down). forge-os-ebon.vercel.app/api/health
  → ok (`db: up`).
- **Intake:** `intake_enabled: false` (unchanged, Forge Bot closed).
- **Unknowns:** 96 D-entries in `docs/UNKNOWN_MAP.md` (unchanged since
  2026-10-12).
- **Blockers (unchanged):** zero real seller conversations; zero verified
  transactions. Owner-side gates still hold: name one seller, authorize
  first contact; company registration and payment onboarding need the
  owner's body/identity.

**Update 2026-10-13 (daily freshness check):** HEAD at `4d73a7a`
("Align needs tests and make offer terms visible by default",
committed 2026-10-12 21:22 NPT). Pull fast-forwarded
`4987936..4d73a7a` clean (11 commits, needs/offers fair-exchange work);
`main` == `origin/main`. Working tree clean.

- **Health:** haminp.vercel.app/api/health → **DEGRADED** — `ok: false`,
  `status: "degraded"`, `db: "down"` (v2.3.0, checked 2026-10-13 ~06:23
  NPT). This is a change from yesterday's ok. The standby
  forge-os-ebon.vercel.app/api/health → ok (`db: up`). No further
  repair action taken — read-only check per standing constraints.
- **Intake:** `intake_enabled: false` (unchanged, Forge Bot closed).
- **Unknowns:** 96 D-entries in `docs/UNKNOWN_MAP.md` (unchanged since
  2026-10-12).
- **Blockers (unchanged):** zero real seller conversations; zero verified
  transactions. Owner-side gates still hold: name one seller, authorize
  first contact; company registration and payment onboarding need the
  owner's body/identity.

**Update 2026-10-12 (daily freshness check):** HEAD at `4987936`
("Remove local-only handoff notes — AGENTS/HANDOFF single source",
committed 04:33 NPT). Pull fast-forwarded `7fc2a0c..4987936` clean;
`main` == `origin/main`. Working tree clean.

- **Health:** haminp.vercel.app/api/health → **ok**
  (`{"status":"ok","ready":true,"ok":true,"version":"2.3.0","db":"up"}`).
  forge-os-ebon.vercel.app/api/health → ok. No blips this run.
- **Intake:** `intake_enabled: false` (unchanged, Forge Bot closed).
- **Unknowns:** 96 D-entries in `docs/UNKNOWN_MAP.md` (+4 since the
  2026-10-11 snapshot — `ff20905` banked sourced cross-domain value
  questions D93–D96).
- **Blockers (unchanged):** zero real seller conversations; zero verified
  transactions. Owner-side gates still hold: name one seller, authorize
  first contact; company registration and payment onboarding need the
  owner's body/identity.

**Update 2026-10-11 (owner visibility & integration recovery):** Forensic
inventory of all 113 service modules complete: 34 CONNECTED_VERIFIED, 68
CONNECTED_UNVERIFIED, 6 DISABLED (legacy-flag-gated), 5 UNREACHABLE (kept —
small honest utilities, no dead weight worth deleting). Root cause of owner
blindness: scheduled 7-stage results were ephemeral, /operations "Run Hami
Cycle" targeted legacy-gated POST /forge/cycle (503 by standing order), and
/research/questions/tasks/evidence/clearance APIs existed but were unwired.
Fixes (uncommitted at snapshot time): /scheduled/intelligence now accepts
owner X-API-Key, persists CycleRun with per-stage summary_json, 409 on
concurrent runs; /forge/cycles exposes summary; new owner-gated
/forge/clearance exposes source-clearance expiry/eligibility; /owner gains
Intelligence section (engine state, last runs, research loop, clearance);
/operations Run button now triggers the supported scheduled path.

**Update 2026-10-11 (daily freshness check):** HEAD at `7fc2a0c`
("Follow persisted Crossref leads to OpenAlex abstracts"). Pull
fast-forwarded `d8c9b5b..7fc2a0c` clean; `main` == `origin/main`.
Working tree clean.

- **Health:** haminp.vercel.app/api/health → **ok**
  (`{"status":"ok","ready":true,"ok":true,"db":"up"}`).
  forge-os-ebon.vercel.app/api/health → ok. No blips this run.
- **Intake:** `intake_enabled: false` (unchanged, Forge Bot closed).
- **Unknowns:** 92 D-entries in `docs/UNKNOWN_MAP.md` (+9 since the
  2026-10-10 snapshot — discovery round 18 banked D89–D92 and repaired
  D84–D88 whose rows never reached the map, `d8c9b5b`).
- **Since `1097855`:** collector runner prefers currently cleared sources;
  research planner follows persisted Crossref leads to OpenAlex abstracts;
  source-clearance registry records verified cleared-source retrieval.
- **Blockers (unchanged):** zero real seller conversations; zero verified
  transactions. Owner-side gates still hold: name one seller, authorize
  first contact; company registration and payment onboarding need the
  owner's body/identity.

**Update 2026-10-10 (daily freshness check):** HEAD at `1626fda`
("Close the discovery loop: convert surfaced questions to ResearchQuestions").
Working tree clean; `main` == `origin/main`. Push landed as `eaae141`.

- **Health:** haminp.vercel.app/api/health → **ok** (first probe at 00:38 UTC
  returned `{"status":"degraded","ok":false,"db":"down"}` — a single blip;
  two re-probes at 00:39 UTC returned `{"status":"ok","ok":true,"db":"up"}`).
  forge-os-ebon.vercel.app/api/health → ok.
- **Intake:** `intake_enabled: false` (unchanged, Forge Bot closed).
- **Unknowns:** 83 D-entries in `docs/UNKNOWN_MAP.md` (was D78 at the
  2026-10-09 bank; `ce3c794`).

**Update 2026-10-09 (integrity audit round 1):** HEAD at `bf7ec97` ("Connect owner-notification retry as isolated Stage 6"). Changes since `096e3d0`:
- public_stats.py: require data_scope==REAL; owner_interventions always NOT_MEASURABLE
- scheduled.py: stages report ok/partial/error truthfully; Stage 6 owner retry added
- discovery_engine.py: fixed stale "not wired" comment
- 28-file utcnow() deduplication; unused imports removed
- New tests: SANDBOX exclusion, partial stage statuses, retry-only path
- Frontend: 206/206 pass. Backend: syntax verified (pytest not available in this env).

- **HEAD at prior snapshot:** `origin/main` at `096e3d0` ("Fix CI: add workflow_call trigger to secrets.yml").
- **Health:** haminp.vercel.app/api/health → ok (verified 2026-10-09).
- **Intake:** `intake_enabled: false` (Forge Bot closed).
- **Blockers:** Zero real seller conversations. Zero verified transactions. Contact clock running.
- **Recovery pass (9038616):** Secured /forge/questions, /forge/tasks, /forge/evidence with owner auth; fixed EvidenceOut nullable 500; added bibliographic background classifier; corrected /scheduled/intelligence docs; added relevance_status to PublicDiscoveryOut.
- **Qualification gate (4005927):** Patterns require problem/demand grounding (Signal.signal_type) for commercial questions; 3 new regression tests.
- **PR #15 discovery loop:** Selection v0 extended with `unknown_unknown_discovery` lane; `discovery_selection.py` generates probes from 5 sources; 24 tests.
- **source_kind WIP:** stashed (not in working tree); patch backed up to ~/Downloads/hami-audit/source_kind-wip.patch.
  ("Complete standing authorization execution seam" — execution_engine
  .create_action() now routes authorization through
  action_engine.propose_action() with the experiment_id FK: one
  standing-auth implementation, hard-bound enforcement preserved; 19-test
  authorization matrix; production activation still OFF). Working tree
  clean.
- **Production nervous-system seam (2026-10-07, NEW):** Added
  `GET /scheduled/intelligence` — a non-legacy production work-generation
  endpoint in the existing `backend/app/api/scheduled.py` router, triggered
  by a second Vercel cron entry (`0 6 * * *`). It calls three existing
  non-legacy engines directly (no wrapper abstraction):
  `forge_loop.run_cycle` (DB reasoning, creates questions/tasks/
  opportunities), `research_task_engine.resume_running_tasks` (requeues
  stale), `execution_engine.run_autonomous_action_cycle` (proposes, never
  executes). Per-engine try/except isolation, own DB sessions. No legacy
  flag check; `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` remains OFF. The
  privacy-only `/scheduled/cycle` contract is untouched.
- **CI:** ForgeOS CI #37509311657 SUCCESS; Independent verifier SUCCESS.
  5 new tests in `test_scheduled_cycle.py` (auth, engine execution,
  no-flag-check, cycle contract untouched). `vercel.json` contract test
  updated for two cron entries.
- **Production:** `https://haminp.vercel.app/api/scheduled/intelligence`
  returns 401 without auth (proves deployed + CRON_SECRET configured).
  `/api/health` returns `{"status":"ok","ready":true}`.
- **Previous state (2026-10-06 ~19:15 NPT):**

- **Repo:** `kn33r0s3/ForgeOS`; `main` == `origin/main` at `ce3c794`
  ("Bank D78: missed-inquiry ~30% corroboration (feed 2026-10-06)"). Working
  tree has one uncommitted leftover from a prior session:
  `backend/tests/test_operating_v4.py` gains regression tests for the 422
  empty-test_counts fix (refs run 37442162237) — left untouched on purpose;
  commit or discard deliberately.
- **CI repair (2026-10-06 ~19:15 NPT):** ForgeOS CI #374 FAILED on the
  docs-only D78 commit `ce3c794` — `test_import_unknowns.py::test_parses_all_sections`
  asserted a hardcoded 93-row count (9+4+3+77); the new D78 row made it 94.
  Diagnosed by local reproduction (`assert 94 == 93`), repaired to
  9+4+3+78. Full local gate before push: backend `pytest tests` 822 passed /
  2 skipped; `npm test` 0 failed; `npm run typecheck` 0 errors; `npm run
  lint` 0 errors (1 pre-existing react-refresh warning); `npm run build`
  clean.
- **Independent verifier:** #41, #42, #43 all SUCCESS — the 422 root cause
  (empty test_counts from grep mismatch, fixed in `ecf92a2`) is resolved.
  The earlier "secret mismatch" diagnosis was retracted as an unsupported
  leap: the actual failure on run 37442162237 was HTTP 422, not 401. No
  owner log-read needed.
  Local: `npm test` 389 passed (198 scripts + 191 src/lib), 0 failed;
  `npm run typecheck` 0 errors; `npm run lint` 0 errors (1 pre-existing warning);
  `npm run build` clean; `npm run smoke` 13/13 routes; backend `pytest tests`
  822 passed / 2 skipped.
- **Independent verifier (superseded):** the #38 FAILURE note below is stale —
  #41, #42, #43 are all SUCCESS; see the verifier bullet above. (Kept for
  history: #38 failed at "Record verification" because the workflow POSTed
  empty test_counts → HTTP 422; fixed in `ecf92a2`.)
- **Production:** `https://haminp.vercel.app` (**canonical**) and
  `https://forge-os-ebon.vercel.app` (alias). Verified 2026-10-05: homepage
  serves the Hami app correctly; `/forge` returns the 404 page on both
  domains (public console removal holding); `/api/health` returns HTTP 200
  with body `{"status":"ok","ready":true}` on both domains (verified
  2026-10-06 — the earlier "degraded" standing state was environmental:
  Vercel had no durable DATABASE_URL and no CRON_SECRET); `/api/health/details` correctly 401s without the
  owner key. Exact deployed bundle hash for `c46da61` not proven via text
  fetch (Vercel auto-deploys `main`; push landed ~10 min before the check).
- **Homepage (current IA):** previews-only — Hero ("Discover what matters.
  Understand it. Act on it."), Findings/Unknowns/Experiments previews with
  honest empty states, About link, honest pre-revenue footer. H1 is the
  brand headline; the wedge is never the headline (test-enforced).
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
- **Homepage operating map:** the page now connects SYSTEM → WORLD →
  OPPORTUNITIES → CAPABILITIES → ACTION → OUTCOMES to existing public views
  (`/about`, `/discoveries`, `/opportunities`, `/providers`, `/actions`, and
  `/what-we-learned`). It is explicitly an open map, not a claim that each
  stage happened; the linked pages retain their own evidence and access states.
  A read-only production request to `/api/public/discoveries?limit=4` returned
  four records in `observed` state. The local FastAPI service was not started.
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
- **Repo deep-study loop concluded (2026-10-05):** 10h window
  (2026-10-04T20:22Z → 2026-10-05T06:24Z), 92 study cycles, 181 safe fixes
  landed on main (83 fix commits; 90 commits total in the window). 5 HIGH
  findings — mostly unguarded backend API endpoints, all owner-gated, zero
  consumers. Findings log `~/workspace/research/repo-study-mistakes.md`
  (~2,048 lines); unstudied remainder recorded in
  `~/workspace/research/repo-study-progress.md` (ai_engine, causal_engine,
  learning_engine, product_engine, prospect_discovery; schemas/ rest; data/;
  docs rest). Loop ended per its own 10h stop rule — no new study window
  without a fresh decision. **Owner-held:** `GET /api/payments/esewa/callback`
  requires the owner API key, which the payer's browser cannot carry in the
  live eSewa v2 redirect flow — the eSewa leg of the revenue path is
  functionally incomplete until the owner rules on the guard (removal is an
  authorization-semantics change).
- **Live re-verification 2026-10-05:** repo HEAD `c18aa0f`; both production
  `/api/health` return ok; `intake_enabled:false` (unchanged); 77 banked
  unknowns in the D-ledger.
- **Live re-verification 2026-10-06:** repo HEAD `3a123d0`; both production
  `/api/health` return ok (`{"status":"ok","ready":true}`);
  `intake_enabled:false` (unchanged); 77 banked unknowns in the D-ledger
  (unchanged).
- **Live re-verification 2026-10-07 (~06:30 NPT):** repo HEAD `09749c3`;
  both production `/api/health` return ok (`{"status":"ok","ready":true}`)
  on `haminp.vercel.app` and `forge-os-ebon.vercel.app`;
  `intake_enabled:false` (unchanged); **78** banked unknowns in the
  D-ledger (+1 since 2026-10-06 — D78 row present).
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
- **Discovery:** hourly research loop (recreate from `docs/ops/`); the
  `hami-discovery-round` cron is explicitly DISABLED under the named-seller
  execution gate (2026-10-04) — no further rounds until a seller is named.
  Rounds 1–5 banked unknowns D1–D30 in `docs/UNKNOWN_MAP.md` (round 4: Kathmandu
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


## Historical recovery anchors and unreconciled source leads (checked 2026-10-14)

These are continuity anchors, not a claim that every historic implementation is current. Their source-level status must be rechecked before changing code.

- **Canonical origin:** `hami-origin`, commit [`07baf91a1900cf3e27ce0bae9fead126801da3b3`](https://github.com/kn33r0s3/ForgeOS/commit/07baf91a1900cf3e27ce0bae9fead126801da3b3). Preserve this lineage; never reset Hami to a convenient snapshot or recreate it as a second system.
- **September 30 destructive-history incident:** the restoration commit [`f99008ded95cd17ebb805b0693a59d48d708eb8d`](https://github.com/kn33r0s3/ForgeOS/commit/f99008ded95cd17ebb805b0693a59d48d708eb8d) states that [`f240f3e6250c054a376fb9e2f00d7e6613bebe98`](https://github.com/kn33r0s3/ForgeOS/commit/f240f3e6250c054a376fb9e2f00d7e6613bebe98) deleted 2,454 tracked files, including backend source, all then-existing 88 backend test modules, documentation, verification evidence and services. The restoration was additive from `bf8546e`; it intentionally retained the newer root app. The same restoration message records that `7a437bb` added approximately 6,950 generated artifacts. The detailed capability-ledger reconstruction remains at [`docs/CAPABILITY_QUEUE.md`](https://github.com/kn33r0s3/ForgeOS/blob/main/docs/CAPABILITY_QUEUE.md#L1033). This is historical damage and recovery, not evidence that those files are currently missing.
- **Discovery engine lineage:** [`1b1b63ad7d2f984a9f9c9615625453c202821f01`](https://github.com/kn33r0s3/ForgeOS/commit/1b1b63ad7d2f984a9f9c9615625453c202821f01) introduced the open-world discovery method registry over the existing six primitives. Its statement that discovery was explicitly invoked and not yet scheduled describes that commit's state only. Current call sites, queue entries, tests and runtime evidence decide today's integration status.
- **Separate unreconciled loss-count memory:** prior conversation context contains a separate figure of 828,649 lines across 2,472 files. That exact report/count was not located in the current files and saved-library sources searched on 2026-10-14. Do not merge it with the commit-backed 2,454-file incident, assert it as verified, or discard it; keep it as an owner-context lead until its source is recovered.
- **Separate missing findings report:** `HAMI_CURRENT_CODE_AUDIT_2026-10-09.md` in the saved library explicitly records an owner-reported 74,637-item defect report whose source was not located during that audit. The source was still not identified in this retrieval pass. This number is not evidence of 74,637 active defects. If the original artifact is recovered, preserve its original finding IDs and reconcile each item in the existing capability ledger; do not bulk-fix a count or fabricate missing entries.
- **Archived plans are not current authority:** `HAMI_CONTINUITY_MASTER.md`, `HAMI_CURRENT_CODE_AUDIT_2026-10-09.md` and `Pasted markdown(20261008-185019).md` were found in the saved file library. They help recover intent and history, but their October 8–9 snapshots, old CI states, frozen calendar and proposed workstreams must be reconciled with the current charter, current `main`, later owner decisions and fresh evidence before use.
- **October 11 three-screen roadmap:** saved-library files `Pasted markdown(20261011-182932).md` and `Pasted markdown(20261011-200706).md` contain the earlier “Backend-Complete to Revenue-Live / just build three screens” thesis. The later version itself corrects that framing after finding the signal/discovery/question-generation path and claim-to-outcome loop were not complete. Historical figures in that report are not current counts. Do not use “three screens” as the complete roadmap; recheck current source/runtime and follow `QUEUE.md` plus the full multi-climb charter.
- **October 8 agent renovation playbook:** saved-library `HAMI_AGENT_PLAYBOOK 2.txt` contains a rigid 39-step serial renovation process. Reuse its useful habits (inspect files, prove gates, record outputs) but do not let old serial checkpoints replace the current no-global-pause rule, canonical `main`, Brain/State/Queue or newer owner direction.
- **Open-world substrate blueprint and earning gate:** the Sep 25–26 blueprint remains useful for the six logical primitives, active type-registry validation, adapters that preserve legacy source authority/provenance, Feed and Network as projections, reusable cross-domain capabilities, and composition that never implies ownership or permission. The commercial loop is `ORIENT → DIAGNOSE → BET → PROBE → VERIFY → EARNING → AMPLIFY/DAMPEN/KILL → MAP → ORIENT AGAIN`: consequential commercial action requires a named payer (or fair value-sharing arrangement), verified outcome and credible value-capture path. Keep three-live-Bet and one-active-intervention limits; Brain sections 35/38 supersede any interpretation that one frontier or 14-day starvation stops unrelated internal work.
- **Unknown-map generation gap is closed:** the current map and TypeScript discovery projection each contain 96 matching unique D IDs through D96; current `npm test` checks generator parity. The Build Book's D71–D83 item is resolved historical context, not live work.
- **Visibility warning:** the repository still reports as public. Keep secrets and private conversation/personal details out of repository records. The present edits contain project-operating summaries only.



## Older end-to-end wiring audit (reconciled against current main on 2026-10-14)

The saved-library file `hami_forgeos_integrity_audit_checkpoint_2026-10-11-full.md` audited HEAD `c1e3c622ddc2f9d1265feb40b81b64f4085eedf3` and explicitly said it was a checkpoint, not a full 790-file/runtime audit. Its F-01 through F-08 items have been reconciled in the existing `docs/CAPABILITY_QUEUE.md`: the old brand-check import failure is no longer in current source, the evidence-triage route now refuses to guess an endpoint, auth has source-level production guards, and the verification workflow now fails when its computed verdict is false. Remaining checks are the flattened API route table, protected proof of durable database/session readiness, and live PWA/browser behavior. Those are not declared fixed from source inspection. Keep the report in the file library as detailed evidence; do not copy it wholesale into a second ledger or blindly replay stale fixes.


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

## Latest verified checkpoint — 2026-10-14

- At the latest push verification point, the only active branch was `main`, clean and synchronized at `5c10b644`. Exact-SHA ForgeOS CI run 38492715213 (all jobs), independent deploy verification run 38492715103, and secrets scan 38492715149 all succeeded; the Vercel status context was successful. These intervening commits contain documentation only. The live application fix remains `a5da9a74`, whose exact-SHA CI, deployment verification, and secrets scan also succeeded.
- The backend identity race is fixed in the existing `world_graph.create_entity` seam. Targeted tests passed; full backend suite: **1,296 passed, 2 skipped, 18 warnings**. `npm test`, typecheck, lint, and safe build passed. Lint retains one pre-existing warning at `src/components/experiments/experiment-card.tsx:108`.
- Production: the canonical `haminp.vercel.app/api/health` returned `ready: true`, `db: up` on three retries and one final check after a single degraded sample; no persistent outage is asserted. Route-specific canonical tags are correct for the homepage, public routes and nested service route. `/operations` and `/owner` retain noindex headers; `/owner` retains its robots meta.
- A fresh health/auth recheck at 2026-10-14 00:51–00:52 UTC again produced one degraded health sample (`db: down`), then three spaced healthy samples (`db: up`); this does not establish a persistent outage. `/api/auth/get-session` returned 503 `Authentication is unavailable.` A live homepage DOM check found no Login, Join Hami, or Sign in links/buttons. Auth remains owner-only and gated; no setting changed.
- Read-only security-header comparison at 00:57 UTC on `/`, `/privacy`, `/owner`, `/operations`, and GET `/api/health` matched `vercel.json` and the existing header contract test: baseline nosniff, referrer, frame, permissions, and report-only CSP values were present; no enforced CSP appeared; `/owner` and `/operations` had the required noindex header. Vercel's HSTS header was also present. An initial HEAD request to the GET-only health route returned 405/Allow: GET; the actual GET returned 200. No header defect was confirmed.
- Auth is still not enabled: `/api/auth/get-session` returns 503 `Authentication is unavailable.` The live header/footer expose no Login/Join CTAs after the temporary pending state settles. No auth configuration or owner-only setting was changed.
- API/page consistency: both public APIs return 100 unknowns (4 B, 96 D; 96 UNKNOWN, 3 HYPOTHESIZED, 1 SUPPORTED), matching the UI. Mobile sweep at 390px and 320px found no horizontal overflow on `/` and `/unknowns`.
- All 19 distinct header/footer destinations returned HTTP 200. At a 320px viewport, the mobile drawer opened and Escape closed it; no Login/Join action appeared while auth was unavailable. The auth-session route currently returns 503 `Authentication is unavailable.`; this was not bypassed or enabled.
- A live keyboard round pictured a confirmed focus defect: Escape left focus on a hidden drawer link; selecting `/unknowns` closed the drawer with focus on `BODY`. The existing header seam was fixed and pushed in `a5da9a74`; local tests, typecheck, lint, safe build and exact-SHA CI passed. Production at 320px now restores visible focus to the toggle after Escape, backdrop dismissal, and navigation from `/unknowns` to `/`. Screenshots captured the post-Escape and post-navigation states.
- Subsequent distinct QA found no new defect: route titles/canonicals matched the current definitions on `/`, `/unknowns`, `/domain`, `/services`, `/providers`, and `/services/software`; `/owner`, `/operations`, `/privacy`, and `/terms` retained their expected noindex controls. Five public pages each exposed one `<main>` and one `<h1>`. At 320px the menu toggle measured 44×44px and Unknowns tabs 40px tall (all above 24×24px); `/`, `/unknowns`, `/domain`, and `/services` had no horizontal overflow at 280px. The providers page settled from loading to its explicit no-matching-verified-providers state; the only observed 503 was `/api/auth/get-session`, consistent with auth remaining unavailable.
- An image-alt sweep on `/`, `/about`, `/services`, `/domain`, and `/providers` found only the shared 40×40 brand marks; their `alt=""` is decorative, and the header/footer links retain the accessible name “Hami Systems home.” No missing-image-alternative defect was observed.
- Unknown-path probes returned HTTP 404 for both a random unmatched route and an invalid nested service slug. The catch-all included `noindex`; the nested service loader uses `notFound()` and its explicit `"Service — Hami"` metadata fallback, returning 404 with a self canonical. No broken-route defect is asserted; a global noindex requirement for all nested 404s is not established by the current product contract.
- Sampled production contrast at `/unknowns` was 16.09:1 for the 40px heading, 8.03:1 for introductory body text, 11.46:1 for the selected tab, and 7.52:1 for unselected tabs. All sampled styles had opacity 1 and exceed WCAG AA text thresholds; this was a sample, not a site-wide certification.
- Reduced-motion emulation on production matched `src/styles.css`: `prefers-reduced-motion` matched, scrolling became `auto`, reveal/skeleton animations became `none`, the menu transition became `0.01ms`, and the drawer still opened with correct expanded/visible state. Browser preference was restored afterward. This verifies the browser-emulated CSS path, not a screen reader or physical OS setting.
- Next: screen-reader interoperability and additional real mobile browser/device checks, then continue with another distinct QA method. Auth remains unavailable/owner-only. No customer/revenue outcome is verified; `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.


## CAS continuation update — 2026-10-14

The original manual REAL-payment truth defect remains guarded: repair_shop.record_verified_payment rejects REAL scope and cannot promote caller-supplied references into revenue. The current continuation connects the existing repair work-item slice to the canonical provider-verified payment-intent and owner-confirmed fulfillment path without creating a second ledger.

- Owner-key-gated link operation accepts only an existing VERIFIED/REAL intent whose REAL Product matches the work item's existing Opportunity. The unique WorkItemEvent idempotency key makes repeated linking stable and prevents one payment intent being linked to two work items.
- Canonical fulfillment writes the existing Outcome and CustomerEvent, then appends one linked repair-side PAYMENT_INTENT_FULFILLED event in the same transaction. Every repair-work-item transition also projects a matching canonical WorldEvent state_changed record with IDs/state/scope only, not free-text customer notes. The repair bridge verifies the existing Outcome's exact product, amount (paisa/NPR), REAL source kind, scope and verification state; no revenue is created by the bridge.
- New endpoint: POST /repair-shop/work-items/{work_item_id}/payment-intent-link. It never initiates checkout; all external payment activity remains on existing, separately authorized routes.
- TEST-only regressions cover idempotent link, rejecting unverified intents and mismatched Opportunities, canonical provider-verification/owner-fulfillment propagation, and one canonical state_changed event per transition. Provider calls are mocked.
- **Not yet verified:** run the focused repair-shop and payment-intent regressions, then confirm the exact-head full backend/frontend CI and independent deployment verification. The prior head af85e99 passed CI/deployment/secrets checks; that result does not certify these new changes. No actual provider transaction, customer contact or real revenue is claimed. OWNER_INTERVENTIONS_PER_REAL_TRANSACTION remains NOT MEASURABLE.
