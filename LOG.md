# Hami Run Log

Append-only. Record what was checked, what changed, evidence, failures and the next unblocked action. Never edit old entries to make outcomes look better.

## 2026-10-14 — operating charter bootstrap

- Read the canonical ForgeOS/Hami main branch and its existing HANDOFF.md, STATUS.md, docs/CAPABILITY_QUEUE.md, activation/decision-rights context, deployment records, scheduled-job configuration, and owner-notification implementation.
- Verified main at commit 1107abd3b3f3f0d4139f59bdf93c9b3d63febe7a during this pass. Vercel reported a READY production deployment for that exact SHA and the project alias list includes haminp.vercel.app.
- Exact-main backend CI was not green at snapshot time: the parent commit 42beaf0 had 16 failed backend tests (1,126 passed, 2 skipped); the backend job for 1107abd was still in progress. Other observed checks for 1107abd were successful. Follow up against the exact resulting SHA.
- Confirmed that the owner SMS digest implementation added in 1107abd is behind a disabled-by-default flag and requires a durable PostgreSQL database and Twilio configuration. No successful real SMS or handset receipt was verified.
- No social account/API connection, public content publication, customer message, seller conversation, payment, or revenue was verified or created in this run. No activation flag or credential was changed.
- Added the requested BRAIN/STATE/QUEUE/LOG continuity files as one direct-to-main documentation bootstrap. Existing CI/history and the six-primitive model are preserved; these files do not claim that any external operation is live.
- Next action: inspect the exact latest-main backend test failure output and correct the policy/test mismatch without weakening the real authorization boundaries.

## 2026-10-14 — owner Version 2 charter sync and source audit

- Canonical main refreshed before editing: base commit 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c. docs/BRAIN.md was Version 1 and stopped at section 14, materially behind the owner-provided canonical Version 2.
- Restored sections 15–33, amended sections 4, 8 and 13, and included updated sections 16, 21, 24 and 28. Added a Git blob content hash over the exact charter text with its own hash line omitted; a read-back hash check passed before commit.
- Source review opened Kathmandu Post reporting on the E-commerce Act (effective date April 15, 2025 and registration deadline July 18), Bhandari Law's summary, the Department of Commerce official Act listing, WhatsApp Business Messaging Policy updated September 23, 2026, Nepal Rastra Bank payment licensing materials and reporting on Meta's Groups API retirement. January 2026 reporting on E-commerce Guidelines/ICT standards was also found. The full official Act text was not extractable; official 2026 guidelines, legal applicability to Hami, current Meta Page app permissions and TikTok permissions remain open.
- On parent base dba7d5b064de72dc505bed3603254b3e2acdeb96, frontend tests, typecheck, evidence triage, route smoke, secret scan, lint, build and repository guards passed while backend tests were running. Main then advanced to 6f080dad3cfea3db2c55e4a2317f9d0081d0ff7c; current exact-head checks must be verified separately. Full CI green is not claimed.
- Prior Vercel read showed READY only for the parent deployment at a generated hostname; current deployed SHA, assignment to haminp.vercel.app and live API/database/flag state remain UNKNOWN. No credentials, cost caps, feature flags, authorizations or customer-facing actions were changed.
- No real seller conversation, message, recovered sale, payment, revenue or publication is asserted or created.
- Owner-only decisions outstanding: written L11 cost caps and standing approved costs; written continuity contact; whether to test missed-inquiry and compliance-help hypotheses in parallel; and the qualified Nepali lawyer/accountant for open legal/payment questions.
- Next action: confirm all required checks on exact current main, then reconcile custom-domain/runtime evidence. Only then execute Wave 0/1 steps permitted by Version 2.


## 2026-10-14 — ForgeBot provider guard, privacy copy and verification refresh

- Refreshed `main` and inspected the owner workspace implementation at source SHA `1e6875d88e5011f464bafbfb1f45e9c59d3599ea`. The private owner workspace change is live in a Vercel production deployment for that exact source SHA; Vercel reported READY and aliases include `haminp.vercel.app` and `forge-os-ebon.vercel.app`. Subsequent run-log/continuity edits trigger fresh deployments, so these are dated observations, not a claim that later documentation SHAs are already deployed.
- Found a real fail-open UI issue: the owner chat previously blocked OpenAI explicitly but could still enable asking from an unfamiliar provider if it reported `READY`. Fixed the existing provider gate so only `mock` with `READY`/`MOCK` or `ollama` with `READY` can answer; unapproved provider names remain disabled with a clear no-request message.
- Corrected the chat badge/disclosure: chat is temporary page-session state; a question is sent to Hami's owner API to answer, but this panel does not add that chat to Hami's knowledge records. It still warns against pasting private contacts, conversations, payment details or passwords. The existing `POST /api/forge/ask` implementation was inspected; this UI does not save the conversation as a record, does not create EVIDENCE/ACTION, and does not send messages.
- Added/updated regression assertions in the existing `src/lib/features.test.ts` covering the provider allowlist, Ollama's provider-specific READY pairing, the unapproved-provider blocked message, and the actual request/storage disclosure. Assertions were read back from main; **test execution on the exact latest SHA has not been verified**.
- Direct-to-main commits for the fix/test were: `20fa72f`, `dc6397a`, `b33ff14`, `2341260`, and `1e6875d`. The last aligns the expected test copy with the actual UI. The separate commits resulted from the connected GitHub file-write interface; avoid further rapid code commits that cancel CI runs.
- CI truth: the GitHub status connector exposes a Vercel context only and the available Actions-run retrieval did not return main-push runs. The last retrievable full run on `c18b3b1` had frontend tests, typecheck, evidence triage, route smoke, secret scan, lint, build and repository guards pass, but backend tests were cancelled by a superseding commit. Exact-head full Actions CI remains **UNVERIFIED**.
- Vercel runtime/log fetch returned 403 for the protected project/team scope. A separate live `/api/health`, database-readiness, activation-flag, scheduler-execution and provider-reachability read therefore remains unavailable. Vercel READY/alias metadata is not runtime proof. Latest observed Vercel deployment for `1e6875d` was `dpl_8YLQQE2sroyVSaqp8pEnd53njNbX`, READY, aliasError null.
- No environment flag, credential, permission, owner stage, provider send, public publishing, paid inference, intake, outbound message or customer-facing action was changed or invoked. No actual lead, conversation, sale, payment or revenue was created or claimed.
- Next work: regain verifiable exact-head CI/runtime results, and keep moving on safe internal capability work while those access issues are documented. Intake, publishing, customer contact and spend remain gated.


## 2026-10-14 — hands-off ForgeBot and verification integrity

- Refreshed the current main head before writing: `751d5851f9c4142627d048a129c751376b8ade0e`; target BRAIN and verifier workflow blobs were re-read and match the versions audited here.
- The bilingual content loop is still draft-only and provenance-linked: open persisted research questions create bilingual `content_asset` ENTITY records with a `derived_from` RELATION and `content_draft_created` EVENT. Tests cover idempotency and exclusion of contact/private-number material; no publication or customer message was created by that loop.
- The earlier independent verifier for `b47f7ba` honestly recorded failure with 252/254 frontend tests passing; deployed SHA match and authenticated owner-cycle read passed. Follow-up commits updated copy guards and added provider/privacy safety checks. Exact-head full CI remains unverified.
- The last specifically verified Vercel source/alias metadata was READY for source `1e6875d88e5011f464bafbfb1f45e9c59d3599ea`; main later advanced beyond it. Protected runtime reads returned 403, so latest-source deployment, live flags, cron execution, persistence and provider delivery remain unknown.
- This update documents the owner operating target: ForgeBot handles routine planning, content, scheduling, officially supported posting, inbound messages, monitoring and learning. No owner hand-posting or routine approval loop. The only continuing owner dependencies are hard owner-authority decisions and one-time integrations; the relevant dispatch stays closed until verified.
- The proposed HALT/STOP correction and verifier timeout guard are not recorded as implemented unless the corresponding BRAIN/workflow blobs are present at the resulting main commit.
- No secrets, spend, OAuth grants, activation flags, sender permissions, intake state or customer dispatch were changed. No public post, customer message, real seller conversation, recovered sale, payment or revenue was created or claimed.
- Next action: land the charter/timeout safety update only on an exact main-head lease, then verify the new commit's checks and deployed source before enabling any publishing.


## 2026-10-14 — research-integrity correction

- The last console snapshot was evidence of stored records and run logs, not proof of a self-directed reasoning loop. The user-reported `business, llc, media, science, springer, systematic` cluster traced to a real weakness: the Pattern Engine included metadata-origin signals and its background-label condition depended on certain keywords appearing.
- Added Pattern Engine filtering for Crossref/OpenAlex and explicitly metadata-only signals. It now annotates legacy patterns only when every recorded origin resolves to research metadata; records and their provenance are retained, never casually deleted.
- Corrected the research task state machine: the source collection step is recorded as collection-only; the evaluation step begins as pending with an explicit not-evaluated reason. Metadata-only claim evaluation is skipped with an explicit reason. Only invocation of the judgment/comparison pipeline marks evaluation completed.
- Removed phantom model selection from the collection worker. A selected tool-registry entry did not mean a model was invoked; the step now records `reasoning_status=not_invoked` and only records the source collector as used.
- Added regression tests for the metadata pattern false positive / historic annotation and for collection-only vs uninvoked reasoning/evaluation. Code was prepared from exact-main file blobs; execution is pending. No real external research request, human conversation, customer send, payment or revenue was created by this patch.
- Next required steps: guard-write to the exact current main head, inspect the exact commit's CI, and implement a genuinely invoked non-MOCK evaluation provider followed by the unknown-to-decisive-test mechanism.


## 2026-10-14 — fix the universal-scope copy regression and refresh exact-head evidence

- Refreshed canonical `main` at `f44245d767b4c00ac97de20658051dee7d66832c` and read the exact `src/routes/about.tsx`-contract test. On earlier exact-head run `38459590518` for `a03e95f`, the root frontend suite failed only because the old test expected “One seller, one week” and “Experiment 1”. The current About page deliberately says the current seller pilot is one possible bounded test of Hami's value loop—not Hami's identity or domain limit.
- Updated the regression to assert the new universal framing, “One real-world test”, “No seller has agreed yet”, and the “when earned” state. Kept the existing assertions that the inbox prototype is not public product identity. No product copy was reverted or weakened.
- Exact source history also now contains the research-integrity correction (metadata-only Crossref/OpenAlex records no longer seed economic-problem patterns; legacy records are annotated rather than deleted; collection-only work is not presented as model reasoning/evaluation), plus the scheduled-intelligence dormancy gate. These changes need full exact-SHA verification: the run on `83263db` had frontend jobs cancelled after a superseding push and its backend/independent verifier were still in progress at the last read; `6bfc989` was superseded before full verification.
- The latest source deployment for `f44245d` was BUILDING at the last Vercel metadata read; previous source `a03e95f` was READY and assigned Hami's production aliases. Vercel runtime/log reads remain 403. No current health, activation, database durability, cron execution or provider delivery is asserted.
- Scheduled-intelligence safety changes remain on main: PostgreSQL cross-replica locking; Vercel/SQLite durable-storage rejection; mandatory initial/final `CycleRun` persistence; explicit non-completion for failed/ambiguous/unexpected owner-SMS outcomes; and scheduled dormancy handling. Added backend regressions cover lock acquisition/contention/failure, ephemeral SQLite, missing run records and SMS status classification. Exact current-head backend result remains unverified.
- No credentials, flags, permissions, spending, publication, customer messaging, intake, external research requests, seller conversations, sales or revenue were changed, invoked or claimed by this source/copy update.
- Next: refresh current `main`, let the new exact-head root/backend jobs and independent verifier finish, then fix only evidenced failures and reconcile deployment/runtime truth.


## 2026-10-14 — Telegram owner control source and setup checklist

- Added `docs/OWNER_CONTROL_TELEGRAM.md` (commit `56d91fae64f206db53200a4f4084a25bf1d28105`).
- Committed source in `b43241ff0a5388e28cfb4b0fc31ba736469b460f`: Telegram owner transport and webhook, secret-header comparison plus exact private chat/user allowlist, runtime safe-mode and ASK operational projections, owner-console ASK routes, Telegram outbox delivery, and a daily owner-inactivity check.
- Generic customer SMS/email sends check `FORGE_BOT_LIVE`, persisted safe mode and the seven-day authenticated-owner-contact rule before dispatch and immediately before provider I/O. An unreadable state blocks dispatch. Existing Twilio sender implementation/config was not changed.
- One-time ASK codes are random, delivered directly and stored only as hashes; expiry/failure limits apply. High-impact ASKs require owner-console authentication plus the code. Approved Actions do not execute automatically. Telegram digest is OFF by default and PostgreSQL-only.
- GitHub Actions for the exact source SHA started; results were pending at this snapshot. Tests are not yet claimed green. Production config, webhook registration, PostgreSQL durability and real handset delivery are unverified.
- No production flags/credentials changed; no Telegram, seller or buyer message was sent; no sale or revenue is claimed.
- Next action: inspect exact-head CI results and repair demonstrated failures without enabling production sending.


## 2026-10-14 — many climbs, one Hami (state/queue alignment)

- Updated STATE, QUEUE and HANDOFF to agree with Brain v3 and the public About page: many connected workstreams can progress concurrently; a local external gate is not a system-wide pause.
- Added portfolio-scheduler implementation and acceptance criteria to QUEUE using current research/task/evidence/action seams. No new semantic primitive or duplicate subsystem is authorized.
- The broader mission does not prove unattended execution: exact-head CI, scheduler invocation, durable state and runtime effects must be observed independently.
- No customer contact, publishing, spend, credentials, permissions, payment, or revenue was created or changed by this source update.

## 2026-10-14 — contact loop truth, owner outcome lane and cycle effect

- Reused the existing Operating Model clock, Scout queue and `CycleRun`; no parallel engine, ontology, or contact queue was introduced.
- The contact clock now resets on an owner-recorded recipient reply or held conversation, not merely on `outreach.sent` (which does not prove receipt). Contact preparation remains a soft priority after 2 days/no history; the existing 14-day STARVED freeze remains the hard build boundary.
- The canonical priority distinguishes (1) an unreviewed sent contact needing an owner outcome note, (2) a recorded dry well still open to a late reply, and (3) ordinary evidence/value work. A dry well remains visible but cannot monopolize the scheduler; no-response does not permit another outbound message.
- Added owner-only pending-reply API/UI. Replies and no-response notes write through `world_graph.create_event` with stable idempotency keys; `outreach.no_response` is in the core event registry. Duplicate reply recording is rejected. All contact outcomes remain owner-reported unless independently verified.
- Scout avoids duplicate unresolved drafts, surfaces existing work before the send guard, and reports pending replies, unreviewed outcomes and recorded dry wells. Both early-priority and ordinary scheduled Scout paths persist those fields.
- Existing `CycleRun.summary_json` records cycle effects separately from stage status. Only completed collection outcomes contribute source-signal counts; internal work is not treated as external proof. No-effect/internal-work-only cycles are PARTIAL and include a next-owner-attention cue. The owner cockpit renders that summary.
- Regression tests added/updated for the contact clock, contact priority vs starvation, dry-well continuity, late replies, duplicate reply guards, canonical event registration, both Scout schedule paths and honest effect classification. They were inspected in source but not executed in this environment; exact-head backend pytest/CI remains unverified.
- Latest fetched commit at this log update was `b042755c942ca944b2d87bce3adce1c0e8a06d15`; Vercel status was PENDING and protected runtime reads returned 403. Production health, durable database, deployed SHA, scheduler invocation, active flags and provider delivery remain UNKNOWN.
- No outbound message was sent, no customer reply was fabricated, no production flag/credential/permission was changed, and no revenue or fulfillment is claimed.

## 2026-10-14 — cross-climb provenance and judgment recovery

- Closed one explicit ResearchQuestion source-link gap: `source_rare_signal_id` now resolves to the existing `RareSignalAssessment` model through the active `rare_signal_assessment` core type and canonical adapter. The question-source adapter creates a directed, idempotent `derived_from` relation with both legacy source refs and `payload_copied: false`; it no longer increments unresolved links for this known FK.
- Added rare-signal assessments to the existing legacy-record projection. The projector records hashed safe lifecycle snapshots (status, frequency/score dimensions, existing related IDs and timestamps), only stores the hash and field-name list in the event, and never copies the explanatory payload or source signal IDs. Snapshot changes are versioned by the existing idempotency-key/event pattern.
- Fixed bounded judgment-cache recovery: a cached failed “judge unavailable” or “missing evidence IDs” result can be retried only after that specific cause clears. The prior failed judgment remains in history; successful follow-up becomes the newest cache result. Unrelated evaluation failures are reused rather than generating repeated failures each cycle.
- Added regressions for typed rare-signal relation provenance/idempotency, safe rare-signal snapshot continuity and refresh, and unavailable-judge recovery with preserved failure history.
- Main CI concurrency was adjusted so a running `main` verification is not cancelled by each newer push. This should permit a full verification run to finish, but the available connected workflow tool does not expose push-triggered runs.
- **Verification remains unconfirmed:** Vercel status for code commit `1d4453cb9af5afd6d4c68cb8ef6df24e32177370` was PENDING at the last check; the connected Vercel project/runtime API returned 403. The backend pytest suite was not run in this tool environment. Source/test presence is not a passed test, and no live health, scheduled production execution, external contact, payment or revenue is claimed.


## 2026-10-14 — owner-control safety hardening

- Continued from the Telegram setup checkpoint rather than stopping at implementation notes.
- Wired the owner-control API into the existing authenticated owner cockpit: persistent safe mode, recent owner contact, Telegram/digest config visibility (not delivery proof), public gates, pending ASK choices, code entry, and a resume-review request that does not automatically execute anything.
- Tightened generic customer SMS/email delivery to require durable PostgreSQL safety state when live sending is enabled. Added regression tests for rejection of an otherwise-open ephemeral SQLite state and persistence of safe mode when health readiness is degraded. Provider transport tests explicitly simulate durable backing state.
- Found and corrected a second workflow cancellation source: `verify-deploy.yml` also shared one pending-run group across all main commits. Its concurrency is now scoped by `github.sha`, like main CI.
- CI for the exact current revision was queued/pending when inspected; tests are **not** reported green. No production credentials, IDs or flags were changed; Telegram remains disabled, no webhook was registered, no real message/payment or revenue was created.

## 2026-10-14 — public front door: an immediate useful action

- **Observed gap:** the homepage foregrounded Hami's architecture and a proposed experiment. Its honest status showed no participants or verified outcomes; visitors had explanation, but no immediate practical output.
- **Changed in place:** the homepage's primary action now jumps to a browser-only next-step brief builder; the second goes to the existing public needs/offers/trades board. No new route, ontology, database, paid dependency, provider, or narrow product identity was added.
- **Utility behavior:** visitors enter a desired outcome, present obstacle, optional existing resources, and success condition. The page assembles a structured brief with a smallest reversible test, evidence checklist, decision rule and first action. The brief can be copied or reset. Visitor text is not posted to an API or persisted by this component. Copy failure has a manual-selection fallback.
- **Truth and safety:** the UI identifies the result as a planning aid, not a verified answer or completed test. No visitor submission, contact, match, participant, real-world outcome, payment, or revenue was created or claimed.
- **Source/test commits:** homepage utility db3fe74a99e76c42ef59b6ee6ced7ff91a693892; privacy/action regression contract 16a3b1e94da3139c44a5e12f54d85d00aad122eb.
- **Verification:** exact-current-main test/build execution and the deployed page's visual/functional behavior remain **UNVERIFIED** at this log entry. Source presence is not passing tests or production proof.
- **Next:** verify current-head frontend tests, typecheck, lint, and deployment; then obtain real consented usability feedback and measure whether visitors complete a concrete next step. Continue independent evaluator and durable-cycle work; this does not satisfy Hami's real-outcome objective.


## 2026-10-14 — review and reversal of the generic homepage brief

- **Decision:** removed the browser-only next-step brief from the active homepage and removed the test whose acceptance criterion only asserted that the brief existed. Commits: `ba774da43aad9ea9cdfdc9a1c536267041269d08` and `5cfe8e6a216bf6a1214641226ea27c9c95208cbb`. The original prototype commits remain reachable; no force-push or history deletion was done.
- **Reason:** it was a static planning template that bypassed Hami's evidence, entity/capability relationships, authorization path, and outcome ledger. It offered a generic output but did not demonstrate a distinct Hami capability or let the system learn whether value was realized. Good local privacy alone did not make it the right product direction.
- **Correction to earlier entries:** the prior description of the brief builder as the next public-value improvement is superseded. It is not active UI and must not be described as deployed, verified, or validated.
- **Broader acceptance gate:** public usefulness must emerge from Hami's existing shared substrate: sourced observation → evidence/uncertainty → relevant cross-domain connection → feasible and authorized next action → observed result → updated understanding. Prove the engine path and limitations before designing its public surface. A proposal is not a match, a match is not agreement, a plan is not execution, and execution is not realized value.
- **Work continuing in parallel:** exact-head CI, persisted scheduled-cycle/effect proof, evaluator truth boundaries, and provenance-preserving cross-climb links remain the higher-priority engineering queue. The latest exact-head workflows must be checked after these commits; no green verdict is implied by the revert.
- **Reality unchanged:** no user study, public submission, participant, external contact, payment, transaction, verified outcome, or revenue was created by the prototype or its removal. This log corrects direction; it is not commercial evidence.


## 2026-10-14 — Nepal-intelligified provider and evidence-permission guard

- Connected the bounded cognitive worker through the existing AI seam to schema-constrained local Ollama output. The output remains a bounded proposal, not evidence or executable permission; model identity and returned latency/token metadata are recorded.
- Added a strict model-visible evidence boundary: only bounded title/claim/URL metadata from explicitly REAL, third-party, consent-not-required rows is passed. Other evidence links remain preserved in provenance but the text is withheld from the provider prompt. A Vercel guard prevents a localhost Ollama endpoint from being mistaken for a reachable model in a serverless runtime.
- Added regression tests for Nepal script/context handling, model-visible evidence filtering, and Vercel-localhost refusal. Tests are committed but not yet confirmed passed by exact-head CI. MOCK remains the default, no real Ollama model has been invoked from this environment, and no paid provider was activated.
- Research baseline: [2025 NLUE paper](https://aclanthology.org/2025.findings-ijcnlp.119/); [Nepali instruction-tuned GGUF candidate](https://huggingface.co/mradermacher/NEPALI-LLM-INSTRUCT-GGUF); [curated Nepali NLP resources](https://github.com/ghimiresunil/Curated-List-of-Nepali-NLP-Resources); [Nepal AI Policy 2082](https://mocit.gov.np/content/13111/nationalai---policy---/); [Ollama structured-output schema documentation](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx). These are research leads, not quality results or legal conclusions.
- Exact-head CI / deployment workflows are queued behind an earlier active verification at time of this update. Do not claim green checks or production readiness without the matching SHA's final result.


## 2026-10-14 — default judgment evidence boundary and truthful Ollama availability

- Hardened the existing multi_judge seam instead of adding another evaluator. Default provider judges only receive bounded title, attributed claim, source excerpt and canonical URL from REAL third-party rows explicitly marked consent-not-required and linked to HTTP(S) URLs.
- Judgment cache keys and the persisted judgment evidence_ids now track only the rows actually supplied to the judge. The shared graph still preserves all original links; no private, pending-consent, TEST, MOCK or HYPOTHESIS content is added to provider prompts by default.
- The existing local Ollama tool now reports unavailable inside Vercel and for non-loopback/non-HTTP hosts, matching the cognitive adapter's runtime boundary and avoiding false readiness. Local invocation and exact-head CI remain unverified.


## 2026-10-14 — contain the cognitive provider context

- The cognitive provider boundary now withholds linked evidence rows that carry `source_identity`, even if their other fields look like public third-party material. Provider implementations receive only `available_evidence_ids`; the complete linked set remains internal for provenance and cannot be cited by a custom provider through the context object.
- The local prompt now treats objective and `evidence_context` fields as untrusted source data. It warns the model not to follow instructions embedded in titles/claims and not to treat source claims as independently verified facts.
- Updated the bounded-context fixture to use explicitly eligible REAL third-party records and expanded privacy regression coverage for an identified-but-public-looking record. Fixed the local provider test to assert the actual `script_context_hint` payload key.
- Added State/Queue notes describing the boundary. No customer or provider actions were enabled.
- **Verification truth:** exact-head CI has been repeatedly superseded while concurrent main commits continue. The latest known head at this entry was `a62bf98d99630a24517e852fb8dc3b1b4128949d`; tests and local-model invocation are not yet verified on the final head. Secrets scan had passed for earlier heads; the exact latest run must be checked before asserting success.


## 2026-10-14 — provider readiness no longer inferred from configuration

- Changed /ai/status so local Ollama reports MODEL_AVAILABLE only after a loopback /api/tags probe confirms the configured model is installed. Vercel, non-loopback hosts, missing models, unreachable endpoints and malformed responses do not appear ready. The probe is bounded to 1.5 seconds and hides raw exception details.
- External provider client construction reports CONFIGURED, not READY; network reachability and inference remain unverified. Mock explicitly reports MOCK and inference_verified=false.
- Updated owner ForgeBot chat gate and explanation. Added backend tests for Vercel, local model installed/missing, connection failure and external CONFIGURED state; frontend assertions verify the new gate/copy. Tests are committed, not yet verified green.
