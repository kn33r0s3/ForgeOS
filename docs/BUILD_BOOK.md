# HAMI BUILD BOOK


---

## PART 0 — READ THIS FIRST

### 0.1 Honest framing (owner and agents)
1. **No honest plan can promise "mass money" in 15 days from zero audience.** Revenue needs trust, distribution, and a method that repeats. This book builds those preconditions as fast as reality allows and measures every step. It separates **commitments** (things we control, which must be done) from **outcomes** (things reality decides, which are tracked, never faked).
2. **The author of this book could not read the live code.** The GitHub pages available to the author were stale or blocked. Part 2 is built from audit reports produced by agents (Batches 1–14, the selection audit, the Step 1–2 recovery reports). **Day 1 starts with a Truth Pass that verifies every claim in Part 2 against the repository.** Where the repo disagrees with this book, the repo wins and the book is corrected in place.
3. **Nothing here is permission to contact people, spend money, publish claims about named entities, open the Forge Bot form, or touch credentials.** Those stay with the owner (Part 5, tiers).

### 0.2 The five laws (every agent, every session)
1. **One Hami.** It began at commit `07baf91a1900cf3e27ce0bae9fead126801da3b3`. Evolve it in place. Before adding a file, route, service or table, name the existing one that already carries the same meaning and why it cannot change. No `*_v2`, `new_*`, parallel engines, aggregators of aggregators.
2. **Evidence beats confidence.** Never promote hypothesis → fact, requested → booked, estimated → actual, test → real, reported → verified. A model's output is a hypothesis until a fetched source or a real-world result supports it.
3. **Consent before contact.** Machines never contact strangers. People enter the system only through opt-in, with purpose, retention and withdrawal stated plainly.
4. **Science, not a product company.** Hami's core asset is a register of claims with evidence levels, including killed hypotheses. A method counts only after it works in two different places. Experiments are never Hami's identity, hero, menu or footer.
5. **One writer at a time.** Exactly one agent edits the repository. Others may read, audit, review. Two checkouts of the same repo (e.g. `~/Downloads/ForgeOS` and `~/workspace/repos/ForgeOS`) must never both have uncommitted work.

### 0.3 How agents use this book
Read Parts 0–5 once at session start, then work from Part 6 (workstreams) and Part 7 (calendar). The work queue is `docs/CAPABILITY_QUEUE.md` (existing seam). Every task is recorded there with the IDs in this book (e.g. `W3-04`). Do not create a second queue.

---

## PART 1 — MISSION, SCOPE, IDENTITY (FROZEN)

**Mission (from `docs/ORIGIN.md`, unchanged):** expand the frontier of what can be understood, discovered, created, coordinated, and accomplished in reality.
**Public line (already live):** "Discover what matters. Understand it. Act on it." Built in Kathmandu, serving everywhere equally.
**Operating principle:** Hami grows like a science. Vision scope is unbounded; action scope is bounded by understanding, authorization, verification, and fair value-sharing.
**Substrate:** six primitives only — ENTITY, RELATION, EVENT, EVIDENCE, CAPABILITY, ACTION. No new primitives.
**Not Hami:** a SaaS idea generator, an inbox tool, a seller CRM, a chatbot, an AI wrapper, a directory, a lead-gen gimmick. Do not edit the mission wording. Do not run another mission pass.

**Progress ladder (use these levels in every report):**
1 Seen · 2 Talked (a real person told us) · 3 Tried (we helped once) · 4 Verified (result checked independently) · 5 Paid or shared (value moved fairly) · 6 Repeated (worked with a different person) · 7 Transferred (same method worked in a different domain).
Level 7 is how Hami becomes bigger than any experiment.

---

## PART 2 — GROUND TRUTH TO VERIFY ON DAY 1

Treat each line as a claim to confirm or correct in the Truth Pass (task `W0-01`).

**Deployment**
- Production: `haminp.vercel.app` and `forge-os-ebon.vercel.app` (same deployment). Vite/TanStack frontend plus FastAPI backend on Vercel; PostgreSQL on Neon; GitHub Actions CI (backend, frontend, gitleaks); every push to `main` deploys.
- Public site: honest status block (Revenue Rs 0, Outcomes 0, Experiment 1 proposed, no seller agreed). Menu: Home, Findings, Unknowns, Experiments, About. Terms and Privacy pages exist.
- `/api/health` returns only status, ready, version, time, db.

**Forge Bot (consent-first inquiry path)**
- Built and tested: consent-scoped contact record, one-time manage token (opt-out, delete), HMAC suppression, 5 submissions/visitor/hour limit, 30-day deletion for unactioned inquiries, owner email via SMTP (test email proven to arrive), owner console at `/owner` (readiness panel, leads panel, lifecycle REQUESTED → REPLIED → BOOKED → COMPLETED, erase).
- Intake is **closed** (`FORGE_BOT_INTAKE_ENABLED` and `FORGE_BOT_LIVE` false). Activation requires the owner to write exactly `ACTIVATE FORGE BOT LIVE`; closing requires `CLOSE FORGE BOT`.
- No customer-facing sender exists, by design. Acknowledgement is shown on the page; replies are human.

**Engine and history (from audits)**
- No mechanism chooses Hami's next frontier. Local rankers exist: `src/lib/forge/assistant.ts::ripenessQueue()` (WTP hypothesis → desk-doable → age), `operating_v4.py` (owner-created Bets/Probes, 3 live Bets max, kill rules, proof levels), legacy `opportunity_engine`/`money_engine`/`decision_engine` (speed to money, penalize uncertainty).
- `docs/UNKNOWN_MAP.md` has D1–D83; `src/lib/unknowns.ts` is generated only to D70 (bug).
- Discovery machinery is duplicated and partly gated: `discovery_engine.py`, `curiosity_engine.py`, `cognitive_worker`, PR #15 remnants. Recovery Steps 1–2 merged (PR #18): `/api/scheduled/intelligence` deployed and authenticated; natural cron execution not yet observed. Step 3 (convergence) is pending.
- The first "own intelligence" layer failed because of poor data, not missing code. External collectors (e.g. GDELT, Semantic Scholar) returned HTTP 429. **Rate limits must never be recorded as "no discovery".**
- Legacy research/opportunity stack is gated off by default (`FORGEOS_LEGACY_INTELLIGENCE_ENABLED`). Do not delete it; archive only with proof.

**Known bugs and gaps from audits (verify, then fix in order of risk)**
1. Validation errors may echo submitted values (PII reflection).
2. Public Work board (`/domain`), booking requests, `/signals/public-request`, `/analyze` lacked rate/size limits.
3. Money dashboard and execution-action reads were public (confirm fixed).
4. Mobile overflow on `/discoveries` and `/feed` (confirm fixed).
5. Unknown paths returned HTTP 200 (soft 404).
6. Owner-email delivery has no retry drain or failure alert.
7. Documentation drift in STATUS, SPEC, MAPPING, CAPABILITY_QUEUE.
8. Repo history contains database snapshots (scanned: no email/phone-like values found; still do not rewrite history without owner approval).
9. The repo is public (owner decision pending on private).

**Lessons from this project's history (do not repeat)**
- A prototype (inbox) leaked onto the homepage and footer and made Hami look like an inbox company.
- Several parallel "operating" versions (v2–v5) accumulated.
- Tests were edited to match behavior; branch protection was relaxed to merge.
- A large response-authorization seam (27 reason codes) was built before any real lead existed.
- Two agents edited two checkouts at once.

---

## PART 3 — NEPAL CONTEXT PACK

Sourced facts (record source and date in any public use; re-verify before publishing):

| Fact | Source |
|---|---|
| 14.8 million active social media user identities, Oct 2025 (may not equal unique people) | DataReportal "Digital 2026: Nepal" (Kepios) |
| 15.4 million internet users, 49.6% penetration, start of 2024; 87.7% of internet users used social media | DataReportal "Digital 2024: Nepal" |
| Remittances Rs 2.36 trillion ($16.19B) in FY2025/26, +37.1%, more than the Rs 1.964T budget implemented that year | Nepal Rastra Bank via OnlineKhabar English, 2026-08-26 |
| New foreign-employment labour approvals 406,519 in FY2025/26 (vs 505,957 prior year); re-entry 385,783 | same |
| Remittances were about 24% of GDP in 2020 | World Bank series via FRED |
| Digital payments Rs 98.43T in FY2024/25 (+71%); QR payments Rs 956B; e-commerce platforms Rs 266B | NRB via MEA Tech Watch / Himalpress |
| About 2.9 million merchants accepting QR in FY2024/25 | NRB Payment Systems Oversight Report via Himal Press |
| Privacy: Individual Privacy Act 2075 (2018) requires informed consent and stated purpose; no data protection authority; consent not defined; Data Act 2079 (2022) also regulates data | Pioneer Law, Lex Mundi, DataGuidance (secondary sources) |
| A compliance vendor reports that the Data Act requires government approval for official surveys. **UNVERIFIED — counsel must confirm before any survey of the public.** | Clym (secondary) |
| Headlines (Oct 2026): Bhotekoshi/Trishuli flood recovery; legal gap leaves Rasuwa flood families unable to register deaths of missing relatives; festival-season airfare and road concerns | OnlineKhabar English |

**What this suggests (hypotheses, not findings):**
- Nepal's economic life runs through three rails: **social media for discovery and trade, QR/wallets for payment, remittance for household income.** Value leaks where these rails meet people who cannot verify, compare, or coordinate (fees, fraud, information lag, status opacity).
- Remittance and foreign employment are enormous and sensitive. They are rich domains for **verification and information** work, and dangerous domains for intermediation. Hami must not recruit, place workers, or move money without licensing review.
- Users are mobile-first, Nepali-language-first for trust, and sceptical of unfamiliar institutions. Reciprocity (sharing results back) builds trust faster than marketing.
- **Calendar:** Dashain and Tihar fall in or near this window (agents must confirm dates). Offices and businesses will be slow; family travel and remittance activity will be high. Plan people-experiments around that, not against it.

**Legal map (agents compile; counsel decides):** Individual Privacy Act 2075; Individual Privacy Regulation 2077; Data Act 2079; Electronic Transactions Act; payment and settlement rules from Nepal Rastra Bank; foreign-employment licensing rules; consumer and advertising rules. Task `W9-01` produces a plain-language checklist with every item marked VERIFIED / UNVERIFIED. Agents are not lawyers and do not give legal conclusions.

---

## PART 4 — THE 30-DAY OBJECTIVE AND SCOREBOARD

**Objective:** by Day 30, Hami runs a daily autonomous discovery-and-experiment loop, has a consent-based participation channel with real people, has recorded real evidence (including killed hypotheses), has replicated at least one method in two domains, and has put its first revenue lane through a real test.

### 4.1 Commitments (we control these; all must be done)
| ID | Commitment | By |
|---|---|---|
| C1 | The Cycle (Part 6, W3) runs daily unattended with a plain-English daily report | Day 10 |
| C2 | ≥ 20 desk experiments completed, each with a pre-registered prediction and kill rule, a source for every fact, and a verifier pass; ≥ 5 killed or changed | Day 15 |
| C3 | ≥ 3 method cards; ≥ 1 method run in two domains (replication) | Day 15; ≥ 3 replications by Day 30 |
| C4 | Participation pages live: join, consent, withdraw, results shared back, Nepali and English | Day 12 |
| C5 | Owner console shows autonomy log, cycle stats, experiments, participants (counts only), budget meter | Day 12 |
| C6 | Autonomy tiers and CI guards active; zero Tier-3 violations | Day 5 |
| C7 | Truth Pass, Step 3 convergence, Selection v0 merged | Day 5 |
| C8 | First weekly public "Findings" published (owner-approved) and repeated weekly | Day 12 |
| C9 | Day-15 and Day-30 review documents published in the repo and on the Findings page | Day 15, Day 30 |

### 4.2 Outcomes (reality decides; stretch hypotheses, never promises)
| ID | Outcome | Day 15 | Day 30 |
|---|---|---|---|
| O1 | Consenting participants who completed a human experiment | 10–30 | 50–150 |
| O2 | Opt-in contributors/readers (email) | 50–200 | 300–1,000 |
| O3 | Real conversations with owners/partners (logged) | ≥ 5 | ≥ 15 |
| O4 | Verified real-world outcomes (level 4) | ≥ 1 | ≥ 3 |
| O5 | Revenue received from independent payment evidence | possible, not expected | ≥ Rs 1 is the real milestone; amount is a result, not a target |

**Adjustment rule:** if any outcome is under the low end at its checkpoint, do not push harder on the same channel. Run the Part 9 admission test on a different channel or question. If two checkpoints in a row show no new verified fact, stop and review (Part 11).

### 4.3 Revenue stance
- Revenue is earned by applying verified results. It never defines Hami. Counting rules: payment only counts when independent payment evidence exists (provider receipt, bank/QR record, or owner-verified statement); estimates, quotes, bookings and test data never count.
- **Candidate revenue lanes (hypotheses; the selection engine ranks them, nothing is hardcoded):**
  - **L1 Outcome-fee interventions** (e.g. recovered sales for a micro-seller, fee only on verified recovery).
  - **L2 Verification and information services** (claim-vs-registry checks, status clarity) funded by partners, institutions or fees.
  - **L3 Coordination capability** (handoffs, commitments with proof) for small operators.
  - **L4 Institutional research/verification contracts** (associations, cooperatives, NGOs, financial firms).
  - Mass revenue needs either many small repeatable payments or a few large contracts. The Revenue workstream (W7) builds the unit-economics sheet from real data only, never invented figures.

---

## PART 5 — OPERATING SYSTEM FOR AGENTS

### 5.1 Autonomy tiers
| Tier | What | Decision |
|---|---|---|
| 0 | Nightly tests, dependency patch/minor updates, docs-drift fixes, regenerating generated files, health checks, desk experiments (read-only, public sources, no contact) | Automatic |
| 1 | Small fixes in allowed paths (tests, docs, small bug fixes) | Auto-merge only if every required check passes |
| 2 | Public copy, menus, privacy/terms wording, retention, auth/keys, config, migrations, publishing any Finding, new participation experiment, any claim naming a person or organization | Owner "yes" (one tap) |
| 3 | Secrets, deleting production data, spending, messages to people, opening Forge Bot intake, payments, history rewrite, legal conclusions | Owner only, exact phrase when specified |

A change touching both production code and tests is Tier 2. Deleting a test or shrinking assertions is Tier 2.

### 5.2 Session boot sequence (mandatory)
1. Read `AGENTS.md`, `docs/ORIGIN.md`, this book, `docs/CAPABILITY_QUEUE.md`.
2. `git fetch`, `git status`, `git log --oneline -20`; confirm no other agent has uncommitted work; identify HEAD and `origin/main`.
3. For the task: find the existing seam (grep, `git log --follow`, `git log -S`), read its tests, and write the lineage note (5.3).
4. Only then plan the change.

### 5.3 Lineage note (in every PR description, plain English)
`Request · Existing seam (file:function) · Why it can carry this · New files (each with why the existing one cannot) · Tests added · What changed · What is still unknown · Tier`.

### 5.4 Task loop
`pick next task from queue → lineage note → tests first → smallest change → run SQLite and Postgres tests → typecheck/lint/build → PR (small) → CI → merge per tier → verify production read-only → append report → next`.
Tasks larger than about 6 non-test files or more than 1 new file must be split first.

### 5.5 Reports and rituals
- **Daily (agent):** one GitHub issue "Daily Hami report": what changed, what was learned (new verified facts, killed hypotheses), what failed, cost today, what needs the owner (max 5 items, each yes/no with a default).
- **Owner (≤ 15 minutes per day):** answer the yes/no items; send approved outreach; talk to people when scheduled.
- **Day 5, 10, 15, 20, 25, 30:** review the scoreboard (Part 4) in writing in the repo.
- **Handoff note** at the end of every session (Part 10.7).

### 5.6 Cost and safety controls
- Budget meter (Part 6, W3): daily and monthly caps from owner decision O1. At cap, the engine pauses and reports. Default cap is zero; with zero, only deterministic (non-model) steps run.
- Kill switch: one environment flag stops the Cycle; the owner console shows its state.
- Never print secrets. Never commit database copies. Env pulls go to temp files outside the repo with mode 600 and are deleted.
- Never relax branch protection to merge. If a merge is blocked, report it.

---

## PART 6 — WORKSTREAMS

Each task: ID · description · seam · acceptance · tier. Agents may reorder within a sprint but never skip acceptance.

### W0 — Continuity and safety rails (Days 1–5)
- **W0-01 Truth Pass.** Verify every claim in Part 2 with commands and file references; write `docs/TRUTH_PASS.md`; correct this book where wrong. Acceptance: every claim marked CONFIRMED / CORRECTED / UNKNOWN with evidence. Tier 0.
- **W0-02 Origin tag.** Tag `07baf91` as `hami-origin` and the current main as `pre-sprint-baseline`; create archive branch from baseline. Acceptance: tags exist. Tier 3 for push (owner approves once).
- **W0-03 Autonomy rails.** `docs/AUTONOMY.md`, CODEOWNERS for Tier 2 paths, required checks, guard scripts: (a) fail on files named `*_v[0-9]*`, `new_*`, `*_new`; (b) fail if an experiment/prototype/inbox link appears in home hero, top menu or footer; (c) fail if tests are deleted or assertions shrink without a `tier-2-approved` label; (d) fail if the PR lacks the lineage note. Acceptance: each guard has a failing-case test. Tier 2.
- **W0-04 Dependency and nightly workflows.** Dependabot (patch/minor, grouped), nightly full suite plus production read-only crawl plus `intake_enabled=false` check plus heartbeat age; post-deploy smoke test. Acceptance: workflows green and issue "Daily Hami report" updated. Tier 1.
- **W0-05 Bug sweep from Part 2** (items 1–7), one small PR each, in risk order. Acceptance: each has a regression test. Tier 1/2 as listed.
- **W0-06 Doc drift.** Fix STATUS, SPEC, MAPPING, CAPABILITY_QUEUE to match code; keep unverified items marked. Tier 1.

### W1 — Discovery convergence (Steps 3A/3B) (Days 1–6)
Seams: `discovery_engine.py` (load-bearing), `curiosity_engine.py`, `cognitive_worker`, PR #15 remnants, `/api/scheduled/intelligence`, ResearchTask collection.
- **W1-01 Step 3A audit** (no code): mechanism-by-mechanism matrix, lineage, source failure behavior (429, timeout, empty, malformed), fetched-source vs model-output marking, edge-by-edge proof table with DISCONNECTED marks, minimal 3B change list. Back up the uncommitted `source_kind` work as a patch before anything else. Acceptance: report plus plain-English summary plus one owner decision with a default.
- **W1-02 Step 3B implementation:** connect/extend/absorb into `discovery_engine.py`; recovered grounded sources get tests; failure of a source is recorded as `SOURCE_UNAVAILABLE` and never as "no discovery"; every finding links to Evidence with provenance; model-origin findings are `UNCONFIRMED`. No new discovery state machine, no aggregator, no deletion without the five conditions. Acceptance: tests for each recovered source, provenance, idempotency, no fabricated findings, legacy flag OFF stays safe, existing tests green. Tier 2.
- **W1-03 Observe cron.** After merge, confirm the natural scheduled invocation and report exactly what ran. Never claim "operational" without the invocation log. Tier 0.

### W2 — Selection v0 (Days 3–8)
Seams: `operating_v4.py` (Bet/Probe/Horizon), `assistant.ts::ripenessQueue()`, `value-tiers.ts`, `UNKNOWN_MAP.md` → `unknowns.ts`.
- **W2-01** Fix the D71–D83 generation gap; parity test.
- **W2-02** Unmapped value = `UNASSESSED` (never tier 1); WTP hypothesis and desk-doability alone cannot win.
- **W2-03** Candidate admission gates (falsifiable claim, named disconfirming test, kill rule, consent/permission check, bounded cost and harm); candidates failing a gate are blocked, not low-scored.
- **W2-04** Ranked slate (default 3 using the existing live-Bet cap: one fast test, one exploration in a new domain, one best by merit), labels High/Medium/Low/Unassessed for stake, transfer, capability gain, upside; cost, time-to-evidence, reversibility, harm. Speed floor: at least one candidate yields first evidence within 7 days. Model-proposed factors are `UNCONFIRMED` until the owner confirms. Owner-only endpoint and a read-only "Next experiments" panel in `/owner`.
- **W2-05** Owner-editable frontier record replaces the hardcoded small-purchase constant (keep old text as initial value). Commercial rankers are labelled the exploitation lane and kept out of global selection.
- **W2-06** Resolve the `ARCHITECTURE.md` vs `AGENTS.md` segment conflict: `AGENTS.md` wins; no segment is named the active bet. Acceptance: the 10 tests from the selection audit. Tier 2.

### W3 — The Cycle: autonomous experiment engine (Days 4–10, hardened by Day 20)
Seams: `backend/scripts/run_daily_cycle.py`, `services/cycle_scheduler.py`, `/api/scheduled/*`, `discovery_engine.py`, `ai_engine.py` provider switch, Evidence/WorldEvent, heartbeat (`state_changed` events), owner console.
Design (one loop, extend in place):
1. **SELECT** top admitted unknowns from the slate (W2).
2. **DESIGN** ≥ 3 candidate tests; choose the cheapest that can falsify; write prediction, kill rule, cost, harm, who/what is touched.
3. **CLASSIFY**: **Class A** read-only desk tests (public sources, registries, public datasets, document analysis, calculation) run automatically. **Class B** needs a person (interview, mystery check, participant experiment) → draft goes to the owner's approval queue (Tier 2). **Class C** (contact, money, publishing about named entities) is never automatic (Tier 3).
4. **EXECUTE** Class A with fetchers that record URL, fetch time, content hash, status code; honor robots.txt and site terms; throttle; never scrape private or login-gated content.
5. **VERIFY** with an independent pass: re-fetch, check each quoted/derived number against the source, search for contradicting sources, assign evidence level. Anything unsupported is dropped and logged as rejected.
6. **RECORD** Evidence + WorldEvent with provenance; update the unknown's state; create child unknowns with a parent link; write or update a **method card** (recipe, domains where it worked/failed, failure causes).
7. **DECIDE** continue / kill / escalate to Class B.
8. **REPORT** the plain-English daily report; update the budget meter.
Rules: two stages of model use only when budget allows (E0 deterministic first; E1 model-assisted second). Model output is `UNCONFIRMED` until step 5 passes. Sources that fail (429, timeout, empty, malformed) are recorded as `SOURCE_UNAVAILABLE`, never as "nothing found". A cycle that produces no new verified fact and no killed hypothesis for two days raises a hole alarm (Part 11).
- **W3-01** Specify the cycle in `docs/CYCLE.md` (the one cycle; no second document).
- **W3-02** Implement steps 1–3, 6–8 deterministic (no model); run against the local test database; owner-triggered "Run cycle now" in `/owner`.
- **W3-03** Fetcher with provenance, throttle, robots, failure taxonomy; tests with recorded fixtures.
- **W3-04** Verifier pass (deterministic checks first: URL fetchable, number present in source, date plausible); model-assisted verification only with budget.
- **W3-05** Method cards (stored in the existing Evidence/Event/Capability representation, not a new table).
- **W3-06** Schedule: daily via existing Vercel cron route; add a heartbeat; owner kill switch; budget meter. Hourly only after owner approves a GitHub Actions secret setup and budget.
- **W3-07** Model-assisted design and verification behind the provider switch, budget-capped, with an offline mock for tests.
Acceptance: Day 10 — a cycle runs unattended for 3 consecutive days producing a daily report; every recorded fact has a source URL, fetch time and hash; the test suite proves that a failed source never yields "no discovery"; the kill switch stops it within one run. Tier 0 for the runs; Tier 2 for the code.

### W4 — Desk experiment pack (zero contact; start Day 6)
These are **candidates**. The selection engine admits them; agents must first verify that each source exists, is public, and is lawful and polite to use. Record the finding "source not usable" as a result. Report aggregates; do not name or shame any business or person (Tier 3 for any named statement).

| ID | Domain × leak | Question | Prediction (kill if false) | Candidate public sources (verify) |
|---|---|---|---|---|
| DX-1 | Foreign employment × information gap | Do agencies that advertise a license number match the official licensed-agency list? | At least 20% of sampled ads lack a checkable license number; kill if fewer than 30 ads have numbers or the register is unusable | Official foreign-employment department register; public agency websites/pages |
| DX-2 | Remittance × lost money | How wide are published fee/exchange-rate spreads across licensed remittance channels on the same day? | A spread of more than 1% exists on a given day; kill if rates are not published or not comparable | Public rate pages of licensed providers; central bank published rates |
| DX-3 | Public systems × information gap | Do 5 high-traffic official service instructions disagree across official pages or stale snapshots? | At least 2 of 5 have a material inconsistency; kill if none after review | Official service pages; web archive snapshots |
| DX-4 | Disasters × information lag | In the recent flood events, how long between public hydrology readings and public news/alert pages? | Median lag exceeds 30 minutes; kill if readings are not time-stamped | Public hydrology/meteorology pages; news timestamps |
| DX-5 | Money × coordination | Is QR merchant coverage uneven relative to population by region? | Coverage differs by 3× or more between regions; kill if no regional data | Central bank payment reports; census/population tables |
| DX-6 | Trust × information gap | Are registered cooperatives verifiable against the cooperative registry, and do names collide? | Name collisions or missing entries appear; kill if no register access | Cooperative department register |
| DX-7 | Food × information gap | What is the wholesale-to-retail price spread for 10 staples on a given day? | A spread above 30% exists for at least 3 items; kill if retail data is unobtainable without prohibited scraping | Wholesale market daily price lists; public retail price notices |
| DX-8 | Public systems × coordination | Are tender awards concentrated in a few suppliers? | Top 5 suppliers take over 25% by value in a sample; kill if no machine-readable data | Public procurement portal |
| DX-9 | Energy × wasted resources | How much generation is reported as spilled versus exported or consumed in a recent period? | Reported spill is non-trivial; kill if no figures | Public utility annual/operational reports |
| DX-10 | Knowledge × information gap | For 10 widely shared claims about studying/working abroad, can each be traced to an official source? | At least 4 cannot be traced; kill if sample cannot be assembled | Public posts (aggregated), official ministry/regulator pages |
| DX-11 | Money × trust | Do published digital-payment provider licence lists match providers advertised in app stores/sites? | Mismatches exist; kill if lists are unusable | Central bank licensed-provider lists; app listings |
| DX-12 | Labour × coordination | How many days elapse between a public vacancy notice and a stated closing date, and do they overlap with festivals? | Notice periods under 7 days are common; kill if no data | Public vacancy notices |

**Replication rule:** pair DX-1 with DX-6 and DX-11 as one method ("claim versus official register") run in three domains. Success in two or more domains is the first method card marked level 7.
**Output of each:** an evidence page with sources, hashes, the prediction, the result (including "killed"), and one new unknown.

### W5 — Participation platform (consent-first; Days 5–12)
Goal: real people join, take part, can leave, and see results. No dark patterns, no accounts required, Nepali first, low bandwidth.
Seams to extend: `/experiments`, `/unknowns`, existing sensor-contributor consent path, Forge Bot privacy services (manage token, HMAC suppression, retention, rate limit), `/owner` console, Terms/Privacy pages.
- **W5-01 Participation ladder:** Reader (subscribe to weekly Findings) → Contributor (submit a public observation with source) → Participant (join a specific experiment) → Partner (repeat). Each rung adds one consent and nothing else.
- **W5-02 Open Experiments page:** each experiment in plain language: what we're testing, why, risks, what we collect, how long we keep it, how to withdraw, what you get back. Join button → consent record (version, timestamp, purpose, provenance) → one-time manage token. Adults only (18+ checkbox; no minors' data).
- **W5-03 Contributor flow:** a public observation requires a source link; the Cycle verifies it; contributors see the verification result.
- **W5-04 Reciprocity:** every participant gets the experiment's result written in plain Nepali and English; results are published without personal data.
- **W5-05 Weekly Findings email (opt-in):** double opt-in; unsubscribe link in every email; sending only through the existing SMTP path; the owner approves each edition (Tier 2) until trust in the pipeline is established.
- **W5-06 Abuse and privacy:** rate limits, size caps, honeypot, generic validation errors, no raw IP stored (keyed hashes only), retention per experiment stated on the page, deletion within 7 days of request, erase path tested.
- **W5-07 Metrics:** counts only (visitors, joins, completions, withdrawals) in the owner console; no individual tracking.
Acceptance: end-to-end test with a local mail sink; consent text approved by the owner; the legal checklist (W9-01) has no unresolved red item for the experiments that are live. Tier 2.

### W6 — People experiments (human-in-the-loop; start Day 8)
Each is Class B. Each has a written one-page protocol before launch: question, prediction, kill rule, who, consent, data, risk, stop condition.
- **PX-1 Reply-speed check (owner-run).** Message 10 Kathmandu sellers as an ordinary customer asking availability and price; log time of first reply. Decision rules: if 7 or more of 10 reply within 30 minutes, slow replies is not the leak (kill or change); if 5 or more take more than 3 hours or never answer, the hypothesis lives and the next step is one consenting seller for one week. Thresholds are starting points.
- **PX-2 Remittance pain conversations.** 10 consenting senders or recipients, open questions about their last transfer (cost, delay, trust, what they did when it went wrong). No account numbers, no documents. Stop immediately if someone is distressed.
- **PX-3 Business-owner conversations (the five conversations).** Open questions only, no pitch; log the four-line surprise note after each.
- **PX-4 Observation contributors.** Public call to submit verifiable observations; measures whether strangers participate without incentives.
- **PX-5 One-question poll (only after legal confirmation).** Anonymous, no personal data; skipped if counsel says official approval is needed.
Interview bank (use open questions): What took most time or money last month that you wish didn't? Tell me about the last time something went wrong. What have you already tried? Who do you ask when stuck? If you had a free week of help, what would you hand off?
**Surprise log (every conversation):** who and when · what surprised you · what you expected · one new question. The Cycle ingests these as Evidence at level 2 and spawns unknowns.
Owner decides every contact (Tier 3). Agents prepare scripts, consent text and logging, never send.

### W7 — Revenue rails and outcome ledger (Days 8–25)
- **W7-01 Outcome ledger** using the existing owner-console lifecycle and `approval_outcome_bridge`: states REQUESTED → REPLIED → BOOKED → COMPLETED → VERIFIED → PAID. Each transition needs evidence; TEST never becomes REAL. No new canonical entity.
- **W7-02 Payment rails:** first rail is manual with independent proof (QR/wallet/bank receipt recorded by the owner); existing eSewa/Khalti adapters stay fail-closed until the owner approves provider accounts (Tier 3).
- **W7-03 Value-share rules** (plain language, per lane): fee only on verified value, stated before work, with the right to refuse; template in Nepali and English; legal review before first use.
- **W7-04 Unit-economics sheet** built only from logged real data (time per experiment, cost per cycle, conversion at each ladder rung); every empty cell says UNKNOWN.
- **W7-05 First lane test:** the lane ranked highest by the selection engine is run once with one consenting counterparty; success means a level-4 verified outcome, with level 5 counted only on independent payment evidence.
- **W7-06 Scale rule:** no automation of any revenue step until the method has been done by hand twice (level 6).
Never: invent revenue, count quotes, count bookings, or show "traction" the ledger does not support.

### W8 — Consent-based distribution (Days 6–30)
Goal: people find Hami because it is useful and trustworthy, not through spam.
- **W8-01 Findings as content:** each weekly Finding becomes a plain-language page (Nepali and English), a shareable card, and a short post draft. The owner approves publishing (Tier 2).
- **W8-02 Channel plan:** Facebook page and groups where posting is permitted, TikTok short explainers, Viber/WhatsApp **opt-in** broadcast lists, a weekly email, university and youth clubs, professional associations, local media. Each channel has a hypothesis, a metric and a kill rule.
- **W8-03 Partner list:** agents draft a list of 30 candidate partner types and organizations with a one-line reason each; the owner picks 10 and makes the contact (Tier 3). Agents write the outreach drafts; never send.
- **W8-04 Rules:** no fake accounts, no purchased followers, no automated unsolicited messages, no comment spam, platform terms respected, every claim sourced.
- **W8-05 Nepal calendar:** map Dashain/Tihar and the school/exam/work calendar; schedule releases accordingly.

### W9 — Trust, privacy, legal (Days 1–15, continuous)
- **W9-01 Legal checklist** (plain language) covering Part 3 legal map; every line VERIFIED / UNVERIFIED; unresolved items become a short question list for a Nepali lawyer (owner decision O6).
- **W9-02 Privacy page** matching actual behavior (collection, purposes, who sees data, retention periods per experiment, deletion, opt-out). Owner approves wording.
- **W9-03 Ethics protocol** for human experiments: consent, no harm, no vulnerable-group data without specific safeguards, stop rules, complaint path.
- **W9-04 Naming rule:** findings about named people or organizations are Tier 3; default is aggregate reporting.
- **W9-05 Incident procedure:** how to pause an experiment, notify participants, delete data, and record what happened.

### W10 — Owner console and reporting (Days 6–15)
Extend `/owner` (React, mobile friendly): readiness; Cycle status, last run, budget meter; Next experiments (W2); approval queue (Tier 2 items with yes/no and a default); participants (counts); outcomes ledger; autonomy log; daily report link. The owner key stays in memory only.

### W11 — Reliability, cost, cleanup (continuous)
- Backups: pg_dump drill plus restore proof; record the Neon restore window from official documentation.
- Alerting: failed or old owner-email deliveries; heartbeat age over 26 hours; health failure → GitHub issue (emails the owner).
- Cleanup plan (from the Batch 8 triage): Step 0 tag and archive branch first; then one small group per step (docs archive, legacy frontend after the Compose decision, unknown folder after provenance check, legacy stack behind its flag). **Archive, never delete; every step reversible with `git revert`.** No cleanup step runs before Day 15 unless it blocks a task.
- Keep Opportunity/Money rankers as the exploitation lane only.

---

## PART 7 — CALENDAR

| Days | Focus | Exit check |
|---|---|---|
| 0 | Owner decisions O1–O5 (Part 8); this book placed in the repo | Book committed |
| 1–2 | W0-01 Truth Pass; W0-02 tags; W0-03 rails start; W1-01 Step 3A | Truth Pass merged; 3A report |
| 3–5 | W0-03/04/05; W1-02 (3B); W2-01..03 | C6, C7 done |
| 4–8 | W3-01..04 (Cycle deterministic core) | Local cycle produces a report |
| 5–8 | W2-04..06; W5-01..03; W9-01..02 | Slate visible; consent pages in review |
| 6–10 | W3-05..06; W4 first 6 desk experiments; W10 | C1 by Day 10 |
| 8–12 | W5 complete; W6 protocols; PX-1 and PX-3 start; W8-01 first Findings | C4, C5, C8 |
| 10–15 | W4 remaining; method cards; replication DX-1/6/11; W7-01..03 | C2, C3 |
| 15 | **Sprint 1 review** | C1–C9 status plus O1–O4 numbers in `docs/REVIEW_DAY15.md`; decide Sprint 2 slate |
| 16–22 | Scale what worked: more participants on the best experiment; W3-07 model-assisted steps if budget approved; W7-04..05 first lane test | ≥ 2 replications |
| 22–28 | W7 outcomes; W8 channel doubling on the best channel; W11 hardening; first cleanup steps | Reliability checks pass |
| 30 | **Sprint 2 review** | `docs/REVIEW_DAY30.md`; next 30 days chosen by the selection engine |

Dashain/Tihar: confirm the dates on Day 1; shift W6 conversations and W8 outreach to the days when people are reachable; use the quiet days for engine work.

---

## PART 8 — OWNER DECISIONS (each has a default; silence = default after 48 hours, except Tier 3)

| ID | Decision | Default |
|---|---|---|
| O1 | Monthly AI usage cap | Zero (deterministic steps only) until the first week of Cycle results; then owner sets a number |
| O2 | Approve autonomy tiers | Approve as written in 5.1 |
| O3 | Selection defaults | 7-day speed floor; slate of 3 (1 fast, 1 exploration, 1 best); `AGENTS.md` wins over `ARCHITECTURE.md` |
| O4 | Privacy/consent text | Agents draft; owner approves |
| O5 | Forge Bot activation | Stays closed until the owner writes `ACTIVATE FORGE BOT LIVE` |
| O6 | Lawyer review (privacy, surveys, foreign-employment boundary, payments) | Agents prepare the question list; owner arranges a lawyer |
| O7 | Payment rail | Manual QR/wallet/bank receipts first |
| O8 | Partner outreach | Owner picks 10 from the agents' list and sends |
| O9 | Publishing | Findings publish in weekly batches after owner approval |
| O10 | Repository visibility | Make private |
| O11 | Contact address and custom domain | Keep the private mailbox; no public address |
| O12 | Dashain schedule | Owner states available days |
| O13 | Sprint 2 slate | Chosen at Day 15 from evidence |

---

## PART 9 — EXPERIMENT TEMPLATES, ADMISSION TEST, EVIDENCE GRADES

### 9.1 Experiment admission test (all five answers required, or it is not an experiment)
1. What general capability does Hami gain if it works?
2. What do we learn if it fails?
3. Cost in money and hours; time to first evidence (target under 7 days).
4. Who could be harmed, and how is consent obtained?
5. Which real source or person is checked this week?

### 9.2 Experiment card
`ID · Domain × leak type · Unknown (one sentence) · Prediction (can fail) · Kill rule · Cheapest test · Class (A/B/C) · Sources or people · Consent and harm note · Output · Transfer: where else this method could run, and what would change · Status`

### 9.3 Evidence grades
L0 model/agent output only · L1 secondhand report · L2 firsthand report (person told us) · L3 fetched public source, checked · L4 independently verified (second source, official record, or direct observation) · L5 external anchor (payment record, signed outcome, regulator record). Agent-written content is capped at L0 until the verifier raises it. Never present L0–L2 as fact on a public page.

### 9.4 Method card
`Name · Recipe (steps) · Inputs · Domains tried (worked / failed / why) · Time and cost per run · Failure modes · Safeguards · Status (candidate / replicated / transferred)`

---

## PART 10 — PROMPT LIBRARY

### 10.1 Boot prompt (paste at the start of every session)
```
You are continuing the existing Hami. Do not start a project.
1. Read AGENTS.md, docs/ORIGIN.md, docs/BUILD_BOOK.md, docs/CAPABILITY_QUEUE.md.
2. git fetch; git status; git log --oneline -20. Confirm no other agent has uncommitted work.
3. Pick the next task from the queue by ID. Find the existing seam; trace its history
   with git log --follow and git log -S. Write the lineage note.
4. Tests first. Smallest change. No parallel code, no _v2, no new table or primitive.
5. Do not touch Tier 3 areas. Ask the owner only via the daily report, with a default.
6. End with the handoff note. Do not claim "done" without evidence.
```

### 10.2 Task prompt template
```
TASK <ID>: <title>. Tier <n>. Seam: <file:function>. Acceptance: <list>.
Rules: lineage note in the PR; tests first; SQLite and Postgres; small commits;
no secrets printed; no production writes except normal deploys; intake and
FORGE_BOT_LIVE stay closed. Report: Done / Blocked / Unknown with commit hashes.
```

### 10.3 Cycle design prompt (model stage, W3-07)
```
You are Hami's experiment designer. Input: one admitted unknown, its evidence so far,
and the method cards. Output JSON only: three candidate tests, each with prediction,
kill rule, cost, harm note, class (A/B/C), exact sources to fetch, and expected
transfer. Choose the cheapest test that can falsify the prediction. Do not state
facts. Every claim you make is a hypothesis labelled UNCONFIRMED.
```

### 10.4 Verifier prompt
```
You are Hami's verifier. Input: a finding with its source records (URL, fetch time,
hash, extracted text). For each factual statement: quote the supporting passage,
confirm numbers match, search the other sources for contradictions, and assign an
evidence grade. If you cannot find support, mark REJECTED. Never add information
that is not in the sources. Output JSON only.
```

### 10.5 Independent review prompt (second agent, read-only)
```
You are the reviewer. Do not edit files. For the given PR: does it modify the existing
seam or create a parallel one? Any new file without justification? Any test weakened?
Any Tier 2 or 3 path touched without approval? Any claim not supported by evidence?
Answer in plain English: APPROVE / CHANGES / BLOCK with reasons.
```

### 10.6 Daily report format
```
DAILY HAMI REPORT <date>
Verified today: <facts with grade and source>
Killed or changed: <hypotheses>
New unknowns: <ids>
Built: <PRs, tier>
Broken or blocked: <with evidence>
Cost today: <meter>
Needs the owner (max 5, each yes/no with default): ...
Unknown: <what we could not verify>
```

### 10.7 Handoff note (end of session)
```
HANDOFF: current HEAD, branch, uncommitted changes (none expected), next task ID,
what was learned, what to avoid, open owner decisions.
```

---

## PART 11 — RISKS AND STOP RULES

| Risk | Control |
|---|---|
| AI-generated findings that are wrong | Verifier gate; model output is UNCONFIRMED; public pages show only L3+ |
| Another duplicate engine appears | Guard scripts (W0-03); lineage note; reviewer prompt |
| An experiment becomes the front page | Guard (b); homepage identity review at each sprint review |
| Harm to participants or named entities | Ethics protocol; aggregate-only default; Tier 3 for named statements; stop on any complaint |
| Legal exposure (privacy, surveys, foreign employment, payments) | W9-01; counsel before sensitive launches; Hami does not recruit, place workers, or move money |
| Spend overrun | Budget meter, cap O1, kill switch |
| Source blocks or rate limits | Failure taxonomy; politeness; alternative public datasets; never "no discovery" on failure |
| Dashain slowdown | Calendar mapping; engine work on quiet days |
| Agent drift or session loss | Boot prompt; handoff notes; the repository is the memory |
| Vanity metrics | Scoreboard counts only verified facts, replications, consenting participants, independent payments |

**Stop and review immediately if:** two consecutive days produce no new verified fact and no killed hypothesis; the Cycle exceeds budget; a Tier 3 action occurred without approval; site health fails; any participant complains; one experiment's content appears in the hero, menu or footer; or two agents edited the same checkout.

---

## PART 12 — CHECKLISTS

**Definition of done (any task):** acceptance met; tests added and green on SQLite and Postgres; typecheck, lint, build green; lineage note present; Tier respected; production verified read-only after deploy; report appended; no secrets, no database copies committed.

**First 72 hours:**
1. Owner: place this book at `docs/BUILD_BOOK.md`; answer O1–O5 (defaults are fine).
2. Agent: W0-01 Truth Pass; W0-02 tags (owner approves push).
3. Agent: W1-01 Step 3A audit; back up `source_kind` work as a patch.
4. Agent: W0-03 guard scripts and CODEOWNERS (Tier 2 approval).
5. Agent: first Daily Hami report issue.
6. Owner: decide whether to run PX-1 (30 minutes); name 10 possible partners (O8); state Dashain availability (O12).

**Sources used for Part 3 (re-verify before any public use):** DataReportal Digital 2026 / 2024 Nepal; Nepal Rastra Bank reports via OnlineKhabar English (2026-08-26), B360 Nepal, Himal Press, MEA Tech Watch, Kathmandu Post; World Bank series via FRED; Pioneer Law, Lex Mundi, DataGuidance, Clym (privacy law summaries; secondary).

*End of book. The next edit to this file happens only at a sprint review.*
