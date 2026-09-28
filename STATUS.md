# ForgeOS Current Status

> Historical snapshot updated September 14, 2026. Current work order and gates
> are maintained in [`docs/SERIAL_PATH.md`](docs/SERIAL_PATH.md) and
> [`docs/CURRENT_FOCUS.md`](docs/CURRENT_FOCUS.md); do not infer current
> production state from this older environment report.

**Updated:** September 14, 2026  
**Release posture:** Container-hardened and local-pilot-ready. No real-person pilot or real revenue has been claimed.

## Environment baseline

- Backend container installs pinned dependencies with `pip install --target /app/backend/.deps`; no venv or global Python mutation.
- Frontend container uses Bun 1.3.11, `bun install --frozen-lockfile`, a verified Next.js production build, and the production server.
- Canonical host database: absolute `<ForgeOS>/storage/forge.db`. Backend and worker containers see that same bind-mounted file as `/app/storage/forge.db`. Relative SQLite URLs fail closed.
- Docker Compose includes an isolated `backend-tests` verification service using an in-memory database.
- Docker/Podman was not installed in the verification sandbox, so images were syntax/config audited but could not be booted here.

## Verified current truth

- SQLite: integrity `ok`, journal mode `wal`, busy timeout `30000 ms`, foreign keys enabled.
- Requested WAL stress test: **3/3 Forge cycles and 3/3 autonomy cycles passed** on September 14, 2026 (cycle IDs 306–308); no disk I/O or prepared-session error.
- Final backend suite: **143 passed**, 6 deprecation warnings.
- Frontend production build: **passed**, 14 static pages generated.
- Direct rollback regression proves a failed Forge stage is rolled back before autonomy executes.

## Product and integrity controls

- Offer state machine: `draft → customer_confirmed → paid / failed / abandoned`; invalid transitions return conflict.
- Each offer persists a per-offer next-action checklist with offline synchronization.
- Terminal offer status requires an honest outcome note.
- Historical P0/readiness reports are archived under `docs/archive/status-reports/`; this file is the single current status record.
- Scheduler backups retain 10 compressed snapshots and automatically keep only the two newest legacy `forgeos_pre_*.db` files on the main storage volume, archiving older copies.
- eSewa and Khalti adapters remain fail-closed without credentials. Fonepay is not implemented without an authoritative integration pack.

## External-only gate

Phase 3 cannot be honestly executed in a code sandbox. A human must choose one real person aged 14+, contact one real customer, deliver or receive a clear refusal, and record the actual result—even if it is no sale. Production Nepal payment credentials stay locked until that genuine outcome exists.

## 2026-09-15 session (Claude)

- Verified (not just re-read) the prior session's claims: backend syntax-compiles clean end to end; `verification/final-cycle-verification.txt` and `database-path-audit.txt` genuinely show the WAL fix and path consolidation holding (3/3 cycles, no I/O error, single absolute path everywhere).
- Refactored `frontend/app/earn/page.tsx` (528 lines, everything in one component) into an orchestrator (241 lines) plus `components/earn/{SafetyBanner,PathwayPicker,OfferForm,OfferList}.tsx` and `lib/earn/{pathways,types}.ts`. Logic (offline sync queue, status-transition rules, age gating) was moved verbatim, not rewritten — behavior should be identical. **Not yet rebuilt/tested in a real Next.js environment** — no network/node in this sandbox. Run `pnpm build` and click through the Earn page before trusting this refactor.
- Reviewed `lib/api.ts` (1066 lines) against the "no monolithic files" rule: it's one file but cleanly sectioned by domain with no logic mixed in — judged as legitimately-long centralized API/type definitions, not a monolith, and left alone.
- Confirmed ForgeOS's existing dark internal-dashboard palette (`--forge-bg:#08090b`, `border-white/9`-equivalent) already satisfies a "dark, high-contrast-border" standard on its own terms — did not force Sanip Operations' orange/KneeRose brand palette onto ForgeOS, since they're intentionally separate products.
- Declined to load an external "claude-red" skill referenced this session — it's a published offensive-security/exploit-technique library, unrelated to and inappropriate for this codebase's actual engineering work.

### Still open
- Rebuild and manually click-test the refactored Earn page (`pnpm install && pnpm build && pnpm dev`, then `/earn`) — first real verification since the split.
- Everything under "External-only gate" above — still nobody has run one real pilot with one real person.


## Evidence

See `verification/final-deployment-backend-tests.txt`, `verification/final-deployment-frontend-build.txt`, `verification/container-protocol-cycle-stress.txt`, `docs/CONTAINER_BUILD_PROTOCOL.md`, and `COMPLETION_REPORT.md`.

## 2026-09-27 — Source-grounded research implementation in progress

- Corrected `/analyze` so it runs one bounded source task per request and derives evidence counts only from persisted evidence rows. A completed task with an empty result, failed peer tasks, or stale evidence IDs cannot yield a collection-complete status. Full task completion is now named `source_collection_complete`, not `research_completed`; that status means source collection only, not validated research or an opportunity.
- The research planner now creates three general subquestions, records assumptions and commercial unknowns, lists only currently authorized source strategies, and reuses prior attributable external observations as explicitly unverified context. Cleared Crossref tasks are idempotent across retries/concurrent creation through a persisted task key and unique migration index. Rate-limit deferrals preserve retry attempts. Unsupported judge availability no longer recursively manufactures research questions.
- Added a metadata-only Crossref public API collector, current policy rechecks, five-result cap, DOI/timestamps/provenance persistence, and no-abstract enforcement. Initial live requests failed HTTP 400 because Crossref does not accept `updated` in its `select` fields; the field was removed and the live requests succeeded.
- Runtime evidence: two unrelated real API queries (Nepal postharvest-loss measurements; bicycle-shop appointment reminders) each returned and persisted five bibliographic metadata records in isolated temporary SQLite databases. Reopening each database retained its five Signals and five Evidence records. DOI URLs and publication/retrieval timestamps were recorded; the saved appointment results were mostly about hospital appointments and are not evidence of demand in repair shops. All source-result relevance is still marked unassessed. No database in the live workspace was changed by these runtime trials.
- Verification: final full backend `pytest tests -q` → **383 passed, 22 warnings**; frontend `npx tsc --noEmit` → passed; `npm run build` → passed; local backend `/health` and frontend `/analyze` → HTTP 200. Browser inspection initially caught missing Next.js dev assets after the production build reused `.next`; after restarting the confirmed ForgeOS dev server, styling/scripts loaded, including on mobile with no horizontal overflow.
- Still blocked/incomplete: no authorized general web-search API or current broad page-source clearances; semantic relevance, source reliability, and contradiction assessment remain unassessed because source content beyond bibliographic metadata has not been inspected. There is no evidence-backed commercial opportunity, customer response, executed experiment, or revenue claim. Continue by reviewing a suitable no-cost primary source under its actual terms before adding bounded content retrieval. Do not contact people, publish an offer, or spend funds without explicit authorization.

## 2026-09-27 — Requirement-grounded research loop

- Replaced the three generic collection tasks with persisted evidence requirements for bibliographic discovery, problem incidence, alternatives/costs, disconfirming evidence, and buyer willingness to pay. The currently cleared Crossref capability maps only to bibliographic discovery; expired GovInfo and uncleared sources do not map to active requirements.
- Plans and assessments persist on the existing `ResearchQuestion`, `ResearchTask`, `Signal`, and `Evidence` records. Tasks are bounded to five per question, carry the requirement/capability/source identity, and can add one idempotent title-specific Crossref follow-up. Incomplete requirements become explicit terminal-unresolved states; evidence collection alone does not satisfy them.
- Research assessments persist source identity, URL, registry entry, retrieval/publication times, exact-token overlap, and publication age. Semantic relevance, source reliability, and claim support remain unassessed for metadata-only records. Explicit `contradicts` evidence relationships are surfaced without inferring contradictions from words.
- Worker claims now use a conditional database update to prevent two workers from starting the same task. Stale running tasks are eligible for recovery; recent running tasks retain their lease.
- Opportunity creation from a pattern now requires attributable persisted evidence and rejects Crossref metadata-only signals. Experiment proposal construction requires every research requirement to be evidence-grounded. No current source can satisfy the market, alternative-price, disconfirmation, or buyer-response requirements; therefore the live loop correctly remains unresolved.
- Final verification on 2026-09-27: focused research/evidence/opportunity regressions → **107 passed, 10 warnings**; full backend suite → **396 passed, 22 warnings**; root `npm run typecheck` and `cd frontend && npx tsc --noEmit` → passed; production build → passed using the isolated output directory. `git diff --check` → clean. Existing local backend `/health` and frontend `/analyze` both returned HTTP 200.
- A fresh isolated live `/analyze` request against Crossref returned HTTP 200 and persisted **5 Evidence records and 5 external Signals** for an unfamiliar produce-transport question. Evidence retains DOI/URL, retrieval/publication timestamps, and `crossref-public-works-metadata` provenance; each is `metadata_only_lead`, with semantic relevance and source reliability `unassessed` and claim support `not_inferred`. The plan marked only `bibliographic_discovery` satisfied; problem incidence, alternatives/costs, disconfirmation, and buyer willingness to pay remain terminal-unresolved. A title-specific follow-up task remained planned; no opportunity was created.
- Stopping and restarting the isolated API against the same temporary SQLite database preserved the question plan, two tasks, five evidence records, and six signals. After restart `/health` returned HTTP 200. Browser verification showed the Analyze form rendered without page errors; at 390px document width was 390px (no horizontal overflow).
- Claims deliberately not made: no source-grounded conclusion about postharvest loss, no validated opportunity, customer, demand, price, human response, experiment execution, transaction, or revenue.
- Remaining authorization blocker: no active capability permits substantive page/paper retrieval or general search; Crossref terms still exclude abstract retrieval under the current clearance. Before content-based relevance or opportunity assessment, review and record a new bounded source clearance, or explicitly authorize a suitable source with its terms/policy evidence. No external contact or commercial action was performed.

## 2026-09-27 — Semantic Scholar candidate review (blocked before implementation)

- Inspected the official Semantic Scholar Graph API documentation, product/API rate guidance, API license, and API robots endpoint. The API license makes use of S2 Data subject to accompanying data licenses and any underlying third-party licenses, and requires “Semantic Scholar” attribution. The requested search fields do not expose per-paper abstract licensing, so the proposed abstract-to-Evidence persistence cannot yet be cleared for ForgeOS's commercial research use.
- One live, non-retried request to `https://api.semanticscholar.org/graph/v1/paper/search` for “appointment scheduling algorithm” returned HTTP **429**. No response abstract was displayed or retained. `SEMANTIC_SCHOLAR_API_KEY` is not configured. The API product page recommends an API key; no retry was made after the throttle response.
- Decision: Semantic Scholar is documented as a candidate, not added to the runtime source registry; no collector, permission, evidence, or research-requirement satisfaction was fabricated. Existing collectors, Crossref clearance, and research behavior remain unchanged. No implementation tests were run because no executable code was changed; the documentation diff was checked.
- Exact blocker / next step: obtain authorized access that is not currently throttled and establish how each returned abstract's data license permits persistence and use in ForgeOS, including attribution and compatible-product obligations. Only then add a dated, field-bounded registry entry and collector, with a per-record license gate if the API supplies one. Until then problem-incidence and alternatives/cost requirements must remain unresolved.

## 2026-09-27 — World Bank Indicators API v2

- Added a dated, bounded `world-bank-indicators-v2` clearance and a collector in the existing `services/collectors` pipeline. HTTPS GETs are restricted to indicator metadata and country/indicator observation path shapes; country codes, indicator IDs, and annual ranges are validated, and collection is limited to 21 years. A persistent registry reservation paces each API call at least one second apart.
- The collector reads the separate indicator metadata endpoint because the observation payload may have `source: null`. It preserves `source`, `sourceOrganization`, and `sourceNote`, emits World Bank and underlying organization attribution, and flags third-party source organizations without treating that as proof of ownership. Provenance records the World Bank Data Catalog CC BY 4.0 dataset-level default and explicitly notes that the API does not state the indicator-specific license.
- Macro evidence is eligible only for `macro_demographics`, `population_baseline`, or `economic_indicator` requirements and only when source identity, attribution, numeric value, country, indicator, and year scope match; any listed third-party source must also have explicitly verified compatible reuse terms. It cannot satisfy problem incidence/customer pain, alternatives/prices, product demand, localized market demand, or buyer willingness to pay. Explicit World Bank task scopes use `WB:COUNTRY:INDICATOR:START[:END]`; unstructured, unbounded tasks fail closed.
- Live isolated result: HTTPS metadata + observation calls for `NPL / SP.POP.TOTL / 2022` returned and persisted one Evidence row: `NPL:SP.POP.TOTL:2022`, “Country: Nepal, Indicator: Population, total, Year: 2022, Value: 29715436”. Provenance includes the exact data API URL, source registry ID, WDI source ID/name, UN/NSO/Eurostat source organization string, third-party-source flag, attribution, and timestamps. Reopening the isolated SQLite database retained one Evidence and one Signal.
- Verification: `tests/test_world_bank_collector.py -v` → **7 passed, 1 warning**; research/provenance regression group (`test_grounded_research_loop.py`, `test_phase1_provenance_and_identity.py`, `test_legacy_evidence_substrate_adapter.py`) → **34 passed, 9 warnings**; full backend `tests/ -v` → **403 passed, 22 warnings**. Existing backend `/health` and frontend `/` returned HTTP 200; `git diff --check` passed.
- No market, customer, customer-pain, or willingness-to-pay claim was inferred from population data. No new domain table or logical primitive was added.

## 2026-09-27 — Third-party license gate and ILOSTAT review

- World Bank observations with listed source organizations now carry `license_status: "unconfirmed_third_party"` and `license_compatibility_verified: false` unless explicit compatible terms have actually been established. The planner persists the traceable Evidence but excludes it from satisfying a research requirement and records `world_bank_third_party_license_unconfirmed`. A generic CC BY 4.0 dataset default is not accepted as proof of third-party compatibility.
- ILOSTAT remains blocked, not implemented or registered. Official ILO rights policy says post-2023-05-03 datasets and referential metadata are CC BY 4.0, excluding restricted constituent microdata. However, the live `DF_EMP_TEMP_SEX_AGE_NB` flow/structure metadata expose a `LAST_UPDATE` annotation but neither a dataset publication date nor a CC BY 4.0 tag. Exact SDMX robots/terms were not established. The dataflow metadata endpoint returned HTTP 200; no observations were fetched or persisted.
- Verification: `cd backend && ../.venv/bin/python -m pytest tests/test_world_bank_collector.py -v` → **8 passed, 1 warning**. Full backend regressions are recorded in the current execution report after completion.
- Remaining blocker / next capability: obtain dataset-specific ILOSTAT publication/license evidence and review SDMX API robots/terms before adding the exact source clearance, bounded collector, requirement gate, live-data test, or persisted labor observation.

## 2026-09-27 — GDELT DOC API metadata collector

- Added `gdelt-doc-api-v2` to the existing source-clearance registry and implemented the collector under the existing `services/collectors/` architecture. It fixes HTTPS endpoint, `artlist` mode, JSON output, allowed metadata fields, bounded 1d–3m timespans, 1–25 result limit, query length, article URL validation, source attribution, and deterministic SHA-256 identity. It never opens article/publisher URLs or stores article body text.
- The API returned HTTP 429 and instructed one request per five seconds. Clearance uses a persistent five-second rate gate; 429 now receives at most two exponential retries (5s, 10s) before deferring without consuming a task attempt.
- Planner can satisfy `media_coverage_observation` and `recent_event_signal`; `public_reporting_velocity` is limited to a reported GDELT-indexed count over the bounded query window and only when fewer than the cap were returned. High-volume/capped lists remain unresolved and cannot validate customer pain, product demand, market size, willingness to pay, or financial viability. Existing metadata-only opportunity gates prevent creation or advancement from these observations.
- Verification after the contract refresh: focused suite **9 passed, 1 skipped**; related regression suite **74 passed, 1 skipped**; full backend **413 passed, 1 skipped**; `git diff --check` passed.
- Live boundary: the valid query `("supply chain" OR "logistics")` (`artlist`, JSON, `1w`, max 5) remained rate-limited after bounded exponential retries. No article records, Evidence, or Signals were obtained or persisted; SQLite reopen verification therefore remains pending.
- Remaining next step: retry live persistence only when provider access is available. No live GDELT evidence or real-world market conclusion is claimed.

## 2026-09-27 — OpenAlex scholarly evidence

- Registered the exact OpenAlex Works REST endpoint after checking its official API docs (keyless use, `search`/`per_page`, all data CC0) and robots policy (`Allow: /`).
- Integrated an allowlisted collector into ForgeOS's current source-cleared runner and Evidence/Signal pipeline. It supports keyword `search` (up to 100 works) and semantic `search.semantic` (up to 50 works and 2,000 query characters), paces both modes at one request per second, and stores only scoped metadata/abstract text; publisher URLs and PDF URLs are never fetched or retained.
- Planner can satisfy a bounded scholarly literature observation only. Geography is not inferred from author affiliations and publication year is not a study period; localized applicability and period/population alignment requirements remain unresolved. Customer pain, WTP, demand, market size, revenue, and Opportunities are not established by OpenAlex search rank/citation count.
- Live semantic query `postharvest loss smallholder farmers Nepal`, max 5, returned and persisted 5 works as 5 Evidence and 5 Signal rows; SQLite close/reopen preserved 5 Evidence and 5 Signals. Outbound calls were restricted to OpenAlex API/policy hosts; no publisher page or PDF was requested.
- Signal identity is now canonical-Work-ID based and protected with a unique DB key and atomic insert recovery. Empty result sets are valid retrieval observations with no claim effect. Scholarly evidence remains unable to satisfy customer pain, WTP, demand, market size, revenue, or Opportunity gates.
- Focused OpenAlex tests **15 passed, 1 skipped, 1 warning**; available research/evidence regressions **26 passed, 4 warnings**; full backend **428 passed, 2 skipped, 22 warnings**; live semantic persistence/reopen **1 passed, 1 warning**. The exact live count and file list are recorded in the latest RESULT in `verification/CONTINUOUS_EXECUTION_REPORT.md`.

## 2026-09-28 — OpenAlex planner and concurrency audit

- Planner selects keyword search for explicit DOI/author/paper/exact-phrase requests and semantic search for broad concepts. It preserves the complete original question, exact request query, mode, detected geographic and population qualifiers, and unresolved dimensions in task payload and resulting Evidence provenance.
- Semantic requests send only `search.semantic`, truncate to 2,000 characters, and cap at 50; keyword requests send only `search` and cap at 100. Invalid task modes fail before the OpenAlex request. Five concurrent writes of the same work resolve to one Signal and one Evidence. The migration preserves duplicate historical Signal rows while clearing colliding new identity keys before adding uniqueness.
- An empty Works result is stored as an idempotent `valid_empty_retrieval` Signal and task observation without Evidence, claim effect or claim re-evaluation, requirement satisfaction, Opportunity, or Experiment. API/network/JSON failures remain explicit failed/deferred tasks and do not create evidence.
- Verification: OpenAlex **20 passed, 1 skipped, 4 warnings**; research/provenance/opportunity regressions **54 passed, 12 warnings**; full backend **433 passed, 2 skipped, 24 warnings**; `git diff --check` clean.
- Live semantic query `postharvest loss smallholder farmers Nepal`, max 5: returned works 5; Evidence 5; Signals 5; reopened Evidence 5; reopened Signals 5. Observed hosts: `api.openalex.org`, `help.openalex.org`; no publisher or PDF request. No paid service or API key was used.

## 2026-09-28 — Multi-source orchestration and cited synthesis

- Research planning now exposes six explicit orchestration nodes: phenomenon existence, affected population, geographic boundary, reporting velocity, documented interventions, and a commercial-validation gap. Each retains the full research question, resolved geography/population qualifiers, authorized candidate sources, unresolved dimensions, and an `unresolved` initial epistemic state.
- Broad opportunity questions are routed only through existing active clearances: Crossref for bibliographic leads, OpenAlex for scholarly abstracts/interventions, World Bank for a bounded country population baseline, and GDELT for bounded reporting metadata. The plan remains capped at five source tasks; identical requests are idempotent and their linked requirement IDs are retained.
- The canonical collector runner carries planner context into persisted Evidence provenance for all source types. A read-only synthesis is attached to the plan and cites persisted Evidence IDs and canonical provenance URLs, keeps observations/explicit contradiction edges side by side, and never changes claim truth. Public-source findings leave the direct-customer/buyer/transaction gate unresolved.
- Mocked end-to-end verification at the time: **5 tasks executed sequentially, 5 Evidence rows persisted, Evidence IDs 1–5 preserved after SQLite close/reopen**. See the latest result below for the subsequent live cycle.
- Verification at the time: orchestration + planner tests **9 passed, 1 warning**; focused research/OpenAlex/provenance/opportunity regressions **79 passed, 1 skipped, 14 warnings**; full backend suite **438 passed, 2 skipped, 24 warnings**. No schema migration or new table was required.

## 2026-09-28 — Adaptive closed-loop research verification

- Planner profiles now adapt the requirement wording and evidence boundaries to agriculture/physical commodities, software/services, or logistics. Public evidence routes through the existing cleared OpenAlex and World Bank collectors; commercial validation remains terminally blocked without direct customer or transaction evidence.
- Synthesis writes requirement states and citation IDs into the research plan, keeps task failures alongside usable evidence, and generates only deterministic tasks for previously unqueried cleared capabilities within the existing five-task budget. Three concurrent orchestration workers each synthesized the same unresolved question while creating the same deterministic task; the migrated unique idempotency index left one task. Synthesis is stored in the `ResearchQuestion.research_plan` JSON and no separate synthesis table exists.
- One isolated live cycle for the specified Nepal postharvest objective reached `api.openalex.org`, `help.openalex.org`, `api.worldbank.org`, and `datacatalog.worldbank.org`. Four planned tasks (two OpenAlex, two World Bank) completed. Evidence and Signals each persisted **24 records** and reopened at **24**. Phenomenon and intervention requirements were supported by cited OpenAlex records; population and geographic baselines remain unresolved; the commercial gap is blocked. Final research status: `research_terminal_unresolved`; no follow-up task was generated. Spend: **$0**.
- Verification: focused orchestration **9 passed, 3 warnings**; research/provenance/opportunity regressions **74 passed, 1 skipped, 14 warnings**; full backend suite **442 passed, 2 skipped, 25 warnings**. See the latest RESULT card in `verification/CONTINUOUS_EXECUTION_REPORT.md`.

## 2026-09-28 — Durable gap decisions and SQLite follow-up verification

- The existing planner now records durable per-requirement gap decisions, parent task/requirement provenance, bounded follow-up depth (**2**) and the refreshed per-question task budget (**5**) in the existing research plan. The unused legacy alternate-task helper was removed; follow-up creation uses one production route.
- An isolated SQLite cycle using a deterministic OpenAlex collector double exercised empty semantic retrieval → keyword follow-up → evidence persistence → synthesis. After closing and reopening the database, ResearchQuestion **1** remained `planned` / `research_in_progress` because sibling tasks **2** and **3** were still planned. Parent requirement `scholarly_evidence` remained `unresolved`; child `followup_b4ee81b0b07d11758a18` was `partially_supported`, linked to parent task **1** and completed follow-up task **4**. Task **4** idempotency key: `bae269c3c188670845592f75bbdeec98e0ee47592fee672c80fcd85f6fed7252`.
- SQLite retained Evidence **1**, provenance URL `https://openalex.org/W987654321`, source clearance `openalex-public-works-cc0`, keyword query `postharvest losses smallholder farmers Nepal`, and assessment `claim_support: not_inferred` / `semantic_relevance: unassessed`. Synthesis was `partially_supported`; Opportunity and Decision counts were both **0**. This was a test double, not live-world evidence or a live network run.
- Verification: focused orchestration/research/OpenAlex/assessment/opportunity selection **56 passed, 1 skipped, 7 warnings**; complete backend **447 passed, 2 skipped, 27 warnings**; the updated `/analyze` terminal-state regression **1 passed, 7 warnings**. The full suite includes that API regression. `git diff --check` is recorded in the latest execution report.
- Remaining capability gap: no currently cleared Nepal-specific primary agriculture/postharvest source with local crop/loss and smallholder coverage. Customer pain and willingness-to-pay additionally require genuine customer or transaction evidence; public research remains unable to unlock those gates.

## 2026-09-28 — General capability-discovery state machine

- Added a bounded discovery service over the existing `ForgeCapability` CAPABILITY primitive. Unserved research requirements now persist an idempotent capability-gap record with required evidence/scope, insufficiency reason, discovery/clearance status, provenance, and a bounded next action.
- Candidate generation is capped at **3 candidates**, **depth 1**, **0 external discovery requests per cycle**, and **2 seconds**. Candidates are generic capability hypotheses, not source claims; they remain `proposed`, non-executable, and absent from planner routing until explicitly reviewed, bound to an existing exact source clearance, tested, and activated.
- Existing source-clearance registry remains authoritative. The planner filters a discovered requirement's registry entries through the active candidate lifecycle; inactive or uncleared candidates cannot create ResearchTasks. Activated candidates add their capability ID to task and Evidence provenance.
- Verified with isolated SQLite persistence/reopen: one gap and one candidate survived, candidate lifecycle became `active` only after explicit test-backed activation, one ResearchTask executed, and one Evidence row retained registry plus capability provenance. Gap/candidate discovery itself created no Evidence, Signal, Opportunity, or Decision; the integration's metadata collector produced no Opportunity or Decision.
- Tests: capability discovery **4 passed, 3 warnings**; focused research/capability selection **66 passed, 1 skipped, 7 warnings**; full backend **451 passed, 2 skipped, 28 warnings**; `git diff --check` passed. The Nepal-specific agriculture source remains unresolved and was not activated.

## 2026-09-28 — Demand-first understanding seam

- Added `demand_understanding` over the existing `Signal` intake, `WorldEvent`, `Evidence`, `SubstrateEntity`, and `ForgeCapability` records. Raw observations are persisted before categorization; a derived `need` entity is created only after an explicit, hypothesis-grade interpretation is sufficiently specified.
- The seam distinguishes `possible_demand`, `hypothesized`, and `sufficiently_understood_need`, preserves observation timestamps/provenance and unresolved questions, and never upgrades a demand observation to supported demand, customer, market, Opportunity, order, payment, or revenue.
- Multiple observations strengthen only the hypothesis wording and evidence support level (`possible` → `hypothesized`). Repeated processing is idempotent through deterministic signal identity, event keys, need identity, relation keys, and Evidence keys.
- Sufficiently understood needs call the existing capability-clearance path. An active cleared capability is reused without creating a ResearchQuestion; no matching capability creates the existing durable capability gap and only then makes bounded research eligibility explicit.
- Verified tests: demand-understanding **8 passed, 3 warnings**; combined demand/capability/orchestration/clearance regressions **33 passed, 7 warnings**; full backend **459 passed, 2 skipped, 29 warnings**. Isolated SQLite reopen retained Signal **1**, Need **2**, and capability gap **1**, with ResearchQuestion count **1**, Opportunity **0**, and Decision **0**. Synthetic fixtures prove mechanics only; no real-world demand or economic validation is claimed.
- Next missing capability: a reviewed, consent-preserving real-world demand-observation channel and authorized response/fulfillment path. Current demand understanding is deterministic and substrate-grounded, but it does not create customers, contact people, offers, actions, transactions, or outcomes.

## 2026-09-28 — Authorized observation handoff and asynchronous demand processing

- Extended the existing observer/demand seam rather than adding an observation table or observer service. Raw demand observations can be persisted uncategorized as existing Signal-backed ENTITY wrappers with `demand_observed` EVENT and `possible` EVIDENCE.
- Authorized source ingestion now requires an exact active source-registry authorization, the matching persisted rate reservation, and a field in that clearance's `allowed_fields`. It records source registry identity/reference, collector/source type, field, source timestamp, reservation/ingestion timestamps, and stable privacy-preserving identity keys. It does not perform network I/O itself.
- Repeated identical authorized observations deduplicate by deterministic identity; distinct source observation IDs/timestamps remain distinct even when fetched from the same endpoint. Content and allowed text metadata redact emails/phone-like strings.
- Demand understanding runs through the existing `WorkerTask` worker registry with deterministic SHA-256 task identity, a unique nullable idempotency key, and two attempts. It performs no external side effect.
- Capability gaps now have durable search events and possible-level Evidence describing the exact registry search, search time, considered clearance IDs, candidate IDs when proposed, and the limits of the conclusion. The evidence explicitly does not claim that no capability exists anywhere in the world.
- Verification: broad focused observation/demand/worker/capability/research/clearance/collector/verified-research/YouTube/substrate regressions **73 passed, 9 warnings**; complete backend **466 passed, 2 skipped, 30 warnings**; `npm run typecheck` passed. The isolated synthetic SQLite proof is recorded in the latest result card.
- No live source request or real-world demand was exercised. The Crossref clearance was used only to test local authorization/rate-reservation/field validation against synthetic test records; no Crossref HTTP request or real customer evidence is claimed.

## 2026-09-28 — Explicit user-request observation handoff

- Reused the existing `POST /signals` API; no second intake route or storage model was added. An explicit `purpose: "demand_understanding"` opts a submission into the existing Signal → `demand_observed` EVENT → possible EVIDENCE → `WorkerTask` path. Requests omitting `purpose` retain the prior signal behavior.
- Demand-purpose submissions use a fixed `user_request` source label, store no caller-supplied category, record purpose/authorization context and submission timestamp in provenance, and accept an optional `Idempotency-Key` whose value is persisted only as a SHA-256 digest. Text is normalized and email/phone-like strings are redacted. Timestamp metadata is preserved through redaction.
- The demand worker retains the default unresolved questions when a request provides no structured interpretation. A free-text request is therefore `possible_demand`; it is not automatically a Need or a capability-search request.
- A local HTTP POST was exercised with content explicitly labeled as a developer pipeline test. After worker execution and a separate SQLite reopen, Signal **1**, `demand_observed` Event **2**, observation Evidence **1** (`possible`), interpretation Evidence **2**, and completed WorkerTask **1** remained. Worker state was `possible_demand`, Need ID was null, and unresolved questions remained explicit. Customer, Need, Opportunity, BookingRequest, Decision, ResearchQuestion, order, payment, and revenue counts were all zero.
- Regression verification: focused request/public API/demand/capability/research suites **116 passed, 17 warnings**; complete backend **471 passed, 2 skipped, 31 warnings**; `npm run typecheck` passed; isolated request-path SQLite reopen passed.
- This is a developer/test request sent to a local API, not a non-test user request, source collection, customer, market validation, transaction, or revenue. The frontend has no dedicated request form, and deployment/authenticated-client behavior was not exercised.
- Next missing capability: a genuine non-test user submission through an appropriately configured public/authenticated client, followed separately by direct human response and economic validation.

## 2026-09-28 — Need-linked economic assessment

- **CURRENTLY IMPLEMENTED:** the existing Opportunity/OpportunityEvent and six-primitive substrate now support `POST /needs/{need_id}/economic-validation`. It refuses to create an Opportunity for a Need that is not hypothesis-grade and sufficiently specified, or before the existing bounded capability-search EVENT exists. Outcomes remain `insufficient_evidence`, `economically_uncertain`, or `testable`; unknown cost/price/WTP remain explicitly unknown. Cited evidence must resolve to stored, provenance-bearing, non-refuted Evidence, but the service does not claim semantic validation of those citations.
- A `testable` assessment is only a proposed bounded WTP experiment: it persists the experiment description and records that external-action authorization is required and absent. It does not create an Experiment, Decision, or ACTION and does not execute anything. WTP stays unknown unless a later real response/payment outcome is independently recorded.
- The existing CustomerEvent ledger now requires recorded authorized-action/response provenance for `contacted`, a linked `ACTUAL_RESPONSE` for `interested`, and linked verified positive `ACTUAL_REVENUE` for `paid_customer`. Evidence-free and reported-only payments cannot promote a paying-customer stage.
- **TARGET ARCHITECTURE:** `sufficiently understood Need → existing bounded capability search → hypothesis-grade economic assessment → separately authorized real-world test/action → attributable response/payment EVENT + EVIDENCE → append-only learning`.
- **FUTURE CAPABILITY:** an authorized prospect-discovery and Need-to-client path using the existing Entity/Relation/Event/Evidence/Action substrate and owner-approved Experiment/Action boundary. Existing customer logging accepts supplied contacts; it is not an authorized prospect-discovery source or a completed real outreach channel.
- Verification: focused economic/demand/public API/capability/research/action regressions **102 passed**; complete backend **479 passed, 2 skipped**; frontend TypeScript check passed. File-backed isolated SQLite close/reopen preserved the Need, capability-search EVENT/EVIDENCE provenance, assessment, Opportunity history, hypothesized Opportunity→Need relation, and authorization flags. No external action or live market input was used.
- No real client, customer, market validation, buyer response, payment, transaction, or revenue evidence was created. Test fixtures explicitly use developer/test content and do not establish commercial capability fit or WTP.
