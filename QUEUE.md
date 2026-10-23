# Hami Execution Queue

## P0 — Owner-only access and verifier authorization

- Vercel Authentication is enabled for **All Deployments**. Password protection remains disabled. Both maintenance flags are false for production, and project metadata confirms the latest ready production SHA at `haminp.vercel.app`.
- The existing sensitive Vercel `FORGE_API_KEY` variable was populated with the fresh owner key (64 hexadecimal characters); never write the key into this queue. Owner enters it in the existing `/owner` console.
- Exact latest production before this queue update: deployment `dpl_ECr1vGF6DyHS6AkZ4kUxTeZaLVaS`, SHA `8c8ec9841392c9c8f608c84e3fb7d0be57d053be`. CI run `39958241795` passed every job; secret scan `39958241796` passed.
- Independent verifier `39958241898` failed waiting for a valid deployed SHA because its requests lacked a Vercel protection bypass. A project-scoped bypass was created for CI; the workflow now requires two GitHub Actions secrets: `FORGE_API_KEY` (same value as current owner key) and `VERCEL_AUTOMATION_BYPASS_SECRET`. The connector cannot write GitHub Actions secrets, so the owner must set/update these at [GitHub Actions secrets](https://github.com/kn33r0s3/ForgeOS/settings/secrets/actions), then manually rerun the independent verifier. Do not disable SSO or embed secrets in source.
- Direct unauthenticated HTTP verification could not run from this execution container because DNS resolution to the production alias failed. We have configuration and deployment readback, not an observed anonymous 401/403 response.
- Marketing gate: keep online promotion closed until real use demonstrates a convincing networked solution across the intended participant groups.

## P1 — Resolve legal/operational eligibility before any paid sprint

- The old “No regulator” statement and the exclusion of registered sellers are corrected. The Department lists the [Electronic Business (E-Commerce) Act, 2081](https://doc.gov.np/content/324/electronic-business--e-commerce--act--2081/) and an [Urgent Notice Regarding Mandatory Listing](https://doc.gov.np/content/470/urgent-notice-regarding-mandatory-listing-e-commerce-2083-05-01/) dated 2 Bhadra, 2083. The sources' existence does not settle application to Hami.
- Obtain qualified Nepali lawyer/accountant answers on seller registration/listing, Hami's potential intermediary/platform status, contractual and complaint duties, privacy/data handling, tax/invoicing, and whether/where Hami may receive fees before company registration.
- Price/revenue share, legal/company/tax matters, contact with non-opted-in people, spend and new customer-facing sending types remain owner-only. No commercial offer, customer DM handling or fee request before review and explicit owner approval.
- Exploratory interviews remain non-commercial discovery; seller self-report is not legal proof. If the legal route cannot be cleared, continue other value research rather than simulate compliance.

## P2 — Evaluate multilingual matching relevance

- Shared Unicode tokenization and IDF/distinctive-overlap ranking are implemented and green under exact-head CI above.
- The six-language benchmark's Precision@1/MRR assertions are synthetic TEST-only metrics, not production semantic relevance. Later evaluation needs appropriately consented/source-grounded examples and known outcome labels.

## Verification boundary — 2026-10-15 NPT

- The `ce9994b` route truncation is retained in history; current exact head follows restoration at `55e2dd0` and passed CI, secret scan and deployment verification.
- No external contact, publication, commercial offer, payment or REAL revenue occurred. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` remains **NOT MEASURABLE**.

## P1 — Evaluate multilingual retrieval quality

- Unicode Nepali/Devanagari, Romanized Nepali, short terms, CJK bigrams, IDF-weighted retrieval and distinctive-overlap public ranking are implemented in source revision `7e56d1bb`. Full CI run [38660540063](https://github.com/kn33r0s3/ForgeOS/actions/runs/38660540063) passed all nine jobs; the follow-up continuity-only main head `3292fbe2` also has successful CI [38661260750](https://github.com/kn33r0s3/ForgeOS/actions/runs/38661260750) and independent deploy verification [38661260867](https://github.com/kn33r0s3/ForgeOS/actions/runs/38661260867).
- Next measure top-k ranking against a frozen set of permitted, source-grounded examples across Nepali, Romanized Nepali, English, code-switching and a no-space script. Lexical rank must not be described as semantic relevance or proof.

## Current verification gate — 2026-10-15 NPT

- Baseline before this patch: main `3292fbe2acc38c1ba199b91725514ad6ffd8ffb6`; exact-head CI, secret scan and independent deploy verification were successful.
- The shared-catalog optimization and query-count regression are committed directly on the existing `main` line; confirm full exact-head CI and deploy verification before calling the patch verified. No local test run is claimed.
- Recurring natural scheduler effects, genuine model-inference quality and REAL customer/payment/revenue outcomes remain unverified. `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` is **NOT MEASURABLE** until a qualifying real transaction is verified.
- `feature/governed-offers` remains a zero-ahead, 554-behind reference with no unique commits; the available connected actions do not expose branch deletion.

## P0 — Complete CAS payment-to-work-item integration

The manual repair-shop payment endpoint remains fail-closed for REAL scope. The existing provider-verified payment-intent and owner-confirmed fulfillment path is linked to RepairWorkItem through the existing WorkItemEvent audit/idempotency seam and a matching canonical state_changed EVENT: link only an already VERIFIED REAL intent whose Product belongs to the work item's canonical Opportunity; mirror fulfillment only when the canonical REAL/VERIFIED Outcome matches amount/currency/product; do not start checkout from this endpoint or add a second revenue ledger. Focused regressions and full exact-head CI passed on `d15d70600391aa789dcf9f57c27377b65975f85d` ([CI 38553479899](https://github.com/kn33r0s3/ForgeOS/actions/runs/38553479899); [deployment verifier 38553479859](https://github.com/kn33r0s3/ForgeOS/actions/runs/38553479859)). The real provider/customer flow remains unexercised; retain the REAL fail-closed boundary and do not initiate a live transaction or claim revenue without the required authorization and genuine provider-verified evidence.

## P0 — Verify difference-guided learning in the existing loop

- **Outcome integrity:** legacy BeliefExperiment reports remain HYPOTHESIS-only; generic write-back requires a matching verified REAL Outcome and explicit target evidence. Target attribution, replay safety, wrong-opportunity and ambiguous-outcome checks are covered by the existing closed-loop regression.
- **Direct provenance increment:** existing LearningEvent now has a nullable `outcome_id`; historical rows remain NULL. Outcome writers in action_engine, outcome_learning and money_engine link each new event to the exact Outcome. REAL learning requires the supplied matching verified Outcome or exactly one eligible outcome; it refuses to guess between multiple outcomes.
- **Tests added:** wrong Experiment/Outcome binding is rejected; a single verified outcome can be unambiguously associated; report-only outcome_learning replays one existing event; product LearningEvent retains its exact Outcome ID while remaining MOCK/REPORTED.
- **Runtime truth boundary:** `apply_learning_to_system` still has no production caller in source audit; direct provenance supports a safer future bridge but does not prove general learning runs autonomously. Keep that capability **UNPROVEN** until the production path is wired and observed.
- **Next step:** use outcome_id to connect one existing safe, canonical consumer only where its target is explicit; preserve the evidence gate and no-new-ontology rule.


## P0 — Verify and extend the multi-climb intelligence loop

1. **[VERIFIED 2026-10-14] Exact-head CI and production identity.** On canonical `main` SHA `d15d70600391aa789dcf9f57c27377b65975f85d`, ForgeOS CI run [38553479899](https://github.com/kn33r0s3/ForgeOS/actions/runs/38553479899) passed all nine jobs: backend-tests, frontend-tests, build, typecheck, lint, route-smoke, evidence-triage-tests, repository-guards and gitleaks. Independent deploy verification [38553479859](https://github.com/kn33r0s3/ForgeOS/actions/runs/38553479859) confirmed production reported the same deployed SHA, the protected owner-cycle read succeeded with its payload suppressed, and the verification record was accepted; secrets scan [38553479786](https://github.com/kn33r0s3/ForgeOS/actions/runs/38553479786) passed. Older pending/failure records below describe older SHAs only. This does not establish recurring scheduled work, model quality, every database guarantee, real-world outcome or revenue. Reopen the gate if `main` advances without a matching exact-head run.
2. **Prove non-starvation end to end.** Confirm tests cover several independent ResearchQuestions, repeated tasks for one question, an uncleared high-priority source, bounded limits and idempotent reruns. Then observe a real persisted scheduled run and its CycleRun/effect accounting; scheduled code or Vercel READY metadata alone is insufficient.
3. **Finish the evaluation and Claim-truth boundary.** Code now requires explicit judgment labels, at least two distinct provider/model configurations for agreement, the same evaluated Evidence context, versioned cache keys and ineligible legacy judgments. Claim creation is observed-only; collector metadata cannot self-label Evidence; generic state changes need existing graph evidence; contradictory history cannot be erased by later support. Verify unavailable/failed judges, legacy cache, target Claim state transitions and genuinely missing Evidence separately on exact-head CI; runtime tests remain unverified.
4. **Implement cross-climb learning by reference.** Progress: the explicit `ResearchQuestion.source_rare_signal_id` now resolves to an active `rare_signal_assessment` canonical entity and creates an idempotent `derived_from` relation with provenance and `payload_copied: false`; safe lifecycle snapshots are also projected through the existing legacy-record adapter. Regression tests cover source linkage and snapshot refresh. Continue auditing the remaining explicit Evidence/Claim/Capability dependencies without a second ontology, copying payloads or upgrading truth through projections.
5. **Connect a genuine evaluator to decisive tests.** Collection can be collection-only; provider/model selection is not invocation. Existing multi_judge is the canonical evaluation path. The default provider path now filters model-visible evidence to explicit REAL/public/consent-not-required source rows and binds each judgment's evidence_ids to the items actually sent. The local Ollama tool cannot report available on Vercel or for non-loopback hosts. Next: exact-head tests, a genuine local invocation, then measured Nepal-first evaluation against the NLUE baseline. No synthetic evidence and no broadened external permissions.
6. **Bound and resume execution.** Preserve source gates, action-time authorization, task/run idempotency, cost/concurrency limits and recoverable partial failures. Blocked customer-facing/legal/provider actions must not freeze independent safe work; systemic incidents contain dependent tracks.
7. **Wire proposal-only cognition without reactivating the legacy queue.** The existing daily-cycle runner now calls `run_pending_cognitive_tasks`: bounded completed-task scan, one question per slot first, explicit local-Ollama selection, Vercel refusal, and owner agent-run checks. Outputs remain PROPOSED. Regressions are committed; exact-head CI and a real local-model run remain unverified.

## P0 — Make research quality and execution truthful

1. **Prevent metadata from becoming fake discoveries.** Crossref/OpenAlex catalog records and any explicitly metadata-only source may remain stored for research, but must not seed recurring economic-problem patterns. Existing records whose entire source lineage is metadata must be labeled as background, not deleted. Verify the regression test against the Springer/LLC keyword-bag failure.

2. **Stop reporting selection/collection as reasoning.** Collector tasks must list only source adapters actually used, and must say collection-only completion. The `evaluate` step stays pending/skipped unless a real claim-judge pipeline ran. Lexical overlap may triage results but never becomes semantic relevance, verified claim support, or a research conclusion.

3. **Historical CI note (2026-10-12):** the earlier `a03e95f` run exposed a stale linear-climb copy assertion. The assertion has since been updated for the broader About page. Do not confuse that historical finding with current-head CI status. Verify current full CI and independent deployment checks; never relax authorization, consent, privacy or epistemic states.

4. **Runtime verification remains open.** Recent Vercel runtime/project reads returned 403 and deployment metadata has been BUILDING while main advances. Current health, database durability, activation flags and scheduled invocation remain UNKNOWN. Recheck the exact source deployment and use an authorized route to verify health plus one persisted scheduled run. Keep external activation closed while unknown.

## P1 — Remove routine owner work by building the real ForgeBot loop

3. **Convert unknowns into decisive tests.** Build from existing unknown-map entries and their registered cheapest-test notes: exact protocol, sample, time/cost, falsifier, decision threshold, provenance and hard gates. This is the next capability step after the research evaluator is real; do not fabricate results or create contact without consent.

4. **End starvation without making the owner the worker.** Track days since a verified REAL conversation. If it exceeds the threshold, create internal contact-debt work and rank inbound/content experiments by information value. Do not generate cold mass outreach or a manual-posting chore; ForgeBot owns approved-channel operations.

5. **Make daily orchestration durable.** Reuse the existing scheduled intelligence/cycle endpoints, worker and outbox seams; verify a real scheduled invocation and persisted result, not merely that a cron declaration exists. Each run reads BRAIN/STATE/QUEUE, takes the top unblocked action, logs evidence, and updates STATE/LOG. Failures must be isolated and visible.
6. **Build the bilingual content loop without narrowing Hami's mission.** Research the actual discovery log and approved public sources; generate Nepali and English drafts that test competing real-need hypotheses, not just seller-reply messaging. Store drafts and provenance in existing substrate/projection seams rather than adding a parallel semantic model. No fabricated success claims.
7. **Implement governed hands-off publishing through official channel APIs.** Reuse an existing connected channel if one is actually verified; otherwise identify the minimum one-time account/OAuth dependency. Align a narrowly scoped pre-approved-content action with the charter's bot-then-notify-owner right, with explicit per-content-type and destination allowlists, idempotency, audit events, takedown/kill-switch handling, and hard owner-only gates for new message types, channels, audiences, claims, spend or permissions. Do not reinterpret generic provider_publish/outreach permission or publish without an ALLOWED authorization and verified channel credentials.
8. **Close the consented inbound loop.** Capture inbound consent and opt-out state, answer only through approved templates and the verified channel, create traceable seller/entity/event/evidence records, and onboard consenting participants. Intake and customer sends stay closed until all activation criteria are evidenced. No cold or mass outbound.
9. **Finish and independently verify owner control.** Telegram source is committed: webhook secret-header check, exact owner chat/user allowlist, persisted HALT safe mode, hashed expiring ASK codes and owner-console second factor for high-impact ASKs. Verify exact-head CI, deployed SHA, durable PostgreSQL, owner-authorized configuration, webhook receipt and observed handset delivery before calling it live. Telegram digest stays OFF by default. Existing SMS sender code is untouched; provider acceptance is not handset-delivery proof.
10. **Run the separate QA adversary and recovery drills.** Test blocked dispatch cannot send, stale/revoked authorization fails closed, duplicate delivery cannot repeat after ambiguous outcome, owner commands require the verified number and confirmation code, and backup/restore works. Do not let the implementation agent mark its own checks sufficient.

## P2 — Advance the nearest commercial proof gate

11. **Measure the first REAL recovered sale.** The Phase 1 kill criterion is ten genuine seller conversations with no recovered sale. Do not fabricate conversations to satisfy it. Track actual owner minutes, consent, reply time, recovered sale, costs and independently supported REAL rupees. If the thesis dies, record it and pivot to the evidence from discovery.
12. **Gate external expansion; not internal progress.** New live markets, transaction paths and customer-facing actions need their own evidence and owner authorization. Internal research, capability construction, reuse, reliability work and exploration of other domains continue in parallel. Keep the broad intelligence mission; narrow only each test, never Hami's identity.

## Global stop conditions

No non-consensual contact, no spend without approval, no legal/company/tax commitment without the owner, no invented results, no permission self-escalation, no casual deletion, no public activation while tests or live readiness are unknown. When blocked, record the legitimate workaround and keep moving on unblocked internal work. Do not stop merely because a verification gate is blocked; continue source audits, non-external fixes, regression coverage and queue maintenance without claiming runtime success.


## P0 — Nepal-intelligified AI provider layer

Reuse the existing ai_engine and cognitive_provider seams; no parallel model stack. The bounded cognitive worker supports schema-constrained local Ollama output only when AI_PROVIDER and COGNITIVE_PROVIDER both explicitly select ollama. Provider-visible evidence is limited to REAL third-party rows marked `not_required`, with valid HTTP(S) URLs and no `source_identity`; only bounded title/claim/URL excerpts are passed. Identified, first-hand, pending, denied, TEST, MOCK and HYPOTHESIS rows are withheld. The Python provider boundary exposes only available evidence IDs, not every linked ID. The local prompt treats source text as untrusted and distinguishes a source claim from established fact. Next: exact-head CI, one invocation on a real local model, then quality evaluation against the [2025 NLUE benchmark paper](https://aclanthology.org/2025.findings-ijcnlp.119/). Inspect the [Nepali instruction-tuned GGUF candidate](https://huggingface.co/mradermacher/NEPALI-LLM-INSTRUCT-GGUF) and the [Nepali NLP resource index](https://github.com/ghimiresunil/Curated-List-of-Nepali-NLP-Resources) for rights/provenance before use; review the [official AI Policy 2082](https://mocit.gov.np/content/13111/nationalai---policy---/) for governance inputs. MOCK remains default, paid inference remains inactive, and no benchmark quality claim is made; this engineering climb continues alongside CI repair.


## P0 — Make provider readiness reflect reality

`/ai/status` distinguishes MOCK, CONFIGURED, MODEL_AVAILABLE, MODEL_MISSING and AI_UNAVAILABLE. Ollama status requires a reachable loopback tags endpoint and installed configured model, but still does not prove generation; owner chat enables Ollama only on MODEL_AVAILABLE. Next prove one actual generation from a reachable local runtime and save measured latency/token metadata, then evaluate on Nepal-first tasks. Provider existence is not validated intelligence.


## P0 — Nepal-native real ForgeBot answers and metered provider expansion

The owner `/forge/ask` path only answers with an installed, reachable, zero-cost local Ollama model. Mock output cannot be returned as intelligence; inference failure returns unavailable rather than silently falling back to templates; paid OpenAI completions remain blocked until usage metering is connected to the shared global spend guard. The answer contract supports Nepali Devanagari, Romanized Nepali, English and code-switching, and treats retrieved knowledge as data rather than instructions. Next prove one real local inference, verify exact-head CI, then evaluate retrieval and answer quality on Nepal-first cases.


## P0 — Complete self-hosted model reachability without paid APIs

The code supports an authenticated HTTPS Ollama-compatible gateway via `OLLAMA_HOST` + `OLLAMA_API_KEY`; loopback HTTP remains local-runtime-only. Direct OpenAI tools have been removed until paid inference is metered through the shared spend guard. Next: configure a real gateway and secrets in deployment settings, confirm `/api/tags`, complete one actual generation, record usage/latency, and evaluate Nepal-first answers. Adapter support is not proof the gateway exists or works.


## P0 — Verify provider privacy boundary and actual inference

Remote model transport authorization (HTTPS plus bearer token) and internal-context sharing authorization are separate. HAMI_ALLOW_INTERNAL_CONTEXT_TO_SELF_HOSTED_OLLAMA remains false by default; /forge/ask must reject remote-context requests until the owner explicitly enables it. Successful calls produce sanitized request observations and a metadata-only EVENT. Next verify exact-head CI, configure a gateway only in deployment secrets, perform an actual inference, inspect the event without question/answer content, and evaluate the Nepal-first language/context set. No remote endpoint or inference is claimed live.


## P1 — Reconcile prior end-to-end wiring audit without replaying stale fixes

The 2026-10-11 single-instance integrity audit has now been spot-checked against current source and its F-01–F-08 dispositions are recorded in `docs/CAPABILITY_QUEUE.md`. After the current P0 exact-head CI and persisted scheduler gates, continue with the still-open route-alias inventory/test (F-06), authorized durable-PostgreSQL/auth readiness checks (F-04/F-05), and browser/runtime PWA verification (F-02). The old missing-import symptom (F-01), evidence-triage Docker-host default (F-03), and false-green verification workflow behavior (F-07) have corresponding source-level corrections now; re-open only if current tests/runtime reproduce a failure. Do not restore removed Grok machinery or revive the archived frontend.


## P1 — Forge Intelligence: evidence-first portfolio sweep (2026-10-16)

- Survey up to 100 **existing** UNKNOWN_MAP and open ResearchQuestion items for evidence freshness, source independence, contradiction, age, authorized source availability, local applicability, testability and blockers. A portfolio sweep is not a claim that 100 questions were independently researched in depth.
- Deeply investigate one highest-value untried item per run, then update the existing unknown/capability/continuity records with source URLs, certainty boundary and next test. No new watchlist or parallel intelligence engine.
- Existing execution is bounded: planner up to 20 open questions per cycle, collector up to five tasks per scheduled pass, with governed source checks and an eligible-question coverage pass. Do not blindly create hundreds of tasks; improve selection only with measured regression evidence.
- D96 has global mechanism evidence from official IEA reports but no specific project, jurisdiction, local relevance or proven Hami intervention. Next: one public operator queue + independent regulator/operator constraint record; if project-level evidence is unavailable, keep UNKNOWN.
- Baseline evidence: CI `38830657519`, secrets `38830657639`, independent deploy verifier `38830657531` were green for base `92dbd1f`; re-verify the new docs commit separately.
- No simulated data counts as real evidence; no one contacted, no content sent, no intake/activation/money action and no grid intervention. Natural scheduler effects and REAL customer revenue remain separate unverified claims.


## D96 evidence refinement — program-level coordination case, project-level cause UNKNOWN (2026-10-16)

- Official DESNZ/Ofgem letter (16 Apr 2026) records historic connection-agreement data errors causing NESO/network companies to rework studies/plans and delay reform. National Grid Electricity Distribution's published regional queue outcomes document approximately 20 GW removed from its former queue, with readiness/strategic-alignment/application pathways separated. NESO's January 2026 detailed-results publication plus FOI response establish that its openly available data is aggregated/zonal and individual project details can be withheld as commercially sensitive.
- This independently verifies a real **programme-level information/coordination problem**, not that a particular project's delay can be cleared without construction. Cheapest next test: compare dated public aggregate/zonal allocation and substitution tables against NGED regional queue totals and public dataset metadata, documenting discrepancies with both source references. No private or operational data requests and no operator contact.
- D96 remains UNKNOWN for a particular project's actual cause, safe headroom, Hami's achievable impact and value capture. Keep physical, contractual, procedural/data, and demand-flexibility causes distinct; do not add modeled capacity estimates with different scope.
- Source URLs: https://www.gov.uk/government/publications/connections-reform-delivery-update-and-battery-capacity/open-letter-from-desnz-and-ofgem-on-connections-reform-delivery ; https://connections.nationalgrid.co.uk/connections-reform/queue-formation ; https://www.neso.energy/document/374936/download ; https://www.neso.energy/document/378991/download

## P1 — CodinGame agent arena for ForgeBot (engineering capability; TEST-only evidence)

- Added `.grok/skills/codingame-agent/SKILL.md` on main at `cacf89e8054a82482a79fa6ccf736420196e8123`. This is Hami's governed adapter workflow, not a claim that CodinGame's official skill is installed or the account is connected.
- Existing seam checked: `.grok/skills/building-games/SKILL.md` is for browser Canvas/WebGL game construction, so the external agent-arena authorization and benchmark workflow is kept separate.
- Next: on a terminal-enabled agent/device, fetch and read https://www.codingame.com/llms.txt directly; install the official skill exactly as it instructs; start the official device flow only after owner approval; present the returned URL and user code verbatim. This chat environment cannot run a local shell or retrieve the Markdown endpoint, so no official skill install/device code has been fabricated.
- First execution gate: one owner-authorized connection, one platform-confirmed baseline bot run, retrievable logs, and one comparable candidate-vs-baseline result. Preserve source revision, game, opponent/seed, score, runtime, errors/timeouts and replay references.
- All game runs and scores are TEST evidence. They must never be represented as REAL seller outcomes, customer value, or revenue. No spend, public submission, external messaging, production activation, or permissions expansion without the existing approval gates.
- Do not add a parallel provider stack or canonical data primitives. Integrate benchmark events/evidence through existing Hami seams after inspecting the actual source APIs and authorization model. This work does not outrank the P0 owner-authorized real seller discovery dependency.
