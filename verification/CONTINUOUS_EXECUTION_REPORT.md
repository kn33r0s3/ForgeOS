# ForgeOS Continuous Execution Report

**Repository:** ForgeOS Nepal-first project  
**Execution mode:** authoritative uploaded archive, local-first verification  
**Result:** implementation and verification pass complete for the current code-controlled milestone

## Changes completed

The existing architecture was preserved. No engine or database was replaced, no historical rows were deleted, and no provider credentials were invented.

The truth audit was extended to expose canonical signal count, canonical quality distribution and average, evidence provenance coverage, failed/completed/running cycle counts, pending actions, queued tasks, and integration-outbox health. The existing dashboard now renders these values alongside raw signals, duplicates, inferred patterns, opportunity hypotheses, human validation, actual outcomes, and actual revenue.

One unresolved data-quality issue was found in the canonical database: two signal rows referenced the same TechCrunch canonical URL while only one was marked as a duplicate. The newer row was linked to the older canonical row using the existing `is_duplicate_of` and `quality_flags` fields. The historical row remains in the database; no deletion occurred.

A repeatable `backend/scripts/truth_audit_report.py` was added. It checks SQLite integrity, foreign-key violations, duplicate canonical identities, stale running cycles, provenance coverage, and status distributions. A copy-only `backend/scripts/recovery_verify.py` was added for backup and restore validation.

## Verified database reality

| Metric | Verified value |
|---|---:|
| Raw signal rows | 11,847 |
| Canonical signal rows | 171 |
| Duplicate signal rows | 11,676 |
| Canonical average quality | 79.27 |
| Evidence rows | 17,815 |
| Cycle rows | 300 |
| Running cycles | 0 |
| Failed cycles | 16 |
| Completed cycles | 284 |
| Actual revenue | 0.0 |
| Real outcomes | 0 |
| Reality learning events | 0 |
| Integration outbox rows | 0 |

The raw signal count is deliberately not presented as validated knowledge. The current canonical evidence stream is 171 signals with a measured average quality of 79.27. The 16 failed cycles remain visible as failures and were not converted into success.

## Verification results

- Full backend suite: **121 passed**.
- Truth-audit, HTTP, and integration-outbox focused tests: **13 passed**.
- Backend compilation: **passed**.
- Runtime HTTP smoke test: **passed**, HTTP 200.
- Runtime truth payload: **passed**, including canonical signals, quality, failed cycles, zero running cycles, and zero actual revenue.
- Frontend dependency installation: **passed**, npm reported zero vulnerabilities.
- Frontend production build: **passed**, 13 static routes generated.
- Copy-only backup: **passed**.
- Copy-only restore: **passed**.
- Restored database integrity: **passed**.
- Restored signal count: **11,847**.
- Canonical database modified by recovery test: **no**.
- Final truth report: **passed with zero unresolved anomalies**.

## External-world boundary

Code-controlled work is complete for this pass. The first real economic cycle still requires a real person and real-world interaction:

```text
real signal → evidence → opportunity → decision → action
→ real human interaction → actual result → economic measurement → learning
```

ForgeOS cannot truthfully create the customer conversation, payment, delivery, or refusal inside the repository. Until that event occurs, the system must continue to show zero actual revenue and zero real outcomes.

The next operator action is therefore not another simulated feature. It is to run one Nepal-first `/earn` offer with one real person, record the actual result, and use that result to update the opportunity and learning system.

## Durable EARN milestone

The Nepal-first EARN workspace now uses ForgeOS as its durable source of truth when the backend is reachable while retaining localStorage fallback when it is not. Offers are scoped to a client-generated opaque workspace token whose SHA-256 hash is stored; no exact age, contact identity, OTP, PIN, citizenship number, or payment credential is stored.

The backend now provides `GET /earn/offers`, `POST /earn/offers`, and `PATCH /earn/offers/{id}/status`. Status transitions are enforced server-side: `draft` must become `customer_confirmed` before `paid`; terminal states cannot be rewritten. The primary database was migrated additively to include `earning_offers`; no historical rows were deleted.

The EARN frontend syncs drafts and status updates when online and retains them locally when offline. It no longer presents a direct draft-to-paid path. The current project includes dedicated EARN API regression tests covering workspace scoping, persistence, valid progression, rejected direct payment, and terminal-state protection.

Latest verification after this milestone:

- Full backend suite: **124 passed**.
- Frontend production build: **passed**.
- Backend compilation: **passed**.
- EARN table migration: **passed**.
- Truth audit: **zero unresolved anomalies**.
- SQLite integrity: **passed**.

## Offline sync reliability milestone

The EARN workspace now maintains an explicit local sync queue for failed offer creates and status updates. Queue entries survive page reloads in localStorage and retry on initial online load and the browser `online` event. Local identifiers are preserved across server synchronization so a status change made while disconnected can be applied after the offer is created remotely.

The frontend build passed after this change, and the complete backend suite remained green at 124 passing tests. The queue is deliberately limited to offer metadata and status transitions; it never stores payment credentials or claims a payment occurred merely because synchronization succeeded.

## Real Nepal payment integration milestone

ForgeOS now contains production-oriented eSewa and Khalti adapters based on their official integration flows. eSewa support includes HMAC-SHA256 checkout signing, production checkout URL configuration, transaction lookup, and signed callback verification. Khalti support includes production initiate and lookup calls using the provider authorization key and NPR-to-paisa conversion.

Credentials are environment-only: `ESEWA_MERCHANT_CODE`, `ESEWA_SECRET_KEY`, `KHALTI_SECRET_KEY`, and related endpoint settings are documented in `backend/.env.example` and are not present in the repository or archive. The API fails closed with a provider-configuration error when credentials are absent. A successful redirect or API response is not itself recorded as revenue; callers must verify the provider status before recording a paid outcome.

The complete backend suite passed with **128 tests**, the frontend production build passed, callback tamper rejection passed, and both providers correctly fail closed without configured credentials.

## 2026-09-27 continuing milestone — evidence-grounded public research

### Failure found and corrected

`POST /analyze` previously treated any completed task as completed research, even if no evidence was stored or other tasks failed. Crossref requests also selected an unsupported `updated` field and received HTTP 400. In addition, research-task uniqueness was only an application-level lookup, prior-evidence lookup could raise when one Signal had multiple Evidence rows, and the general planner generated retries for legacy sources that are not currently cleared.

The response now reports persisted evidence and task state, uses `source_collection_complete` only when every planned task points to persisted evidence, and explicitly says collection is not commercial validation. Each task has a deterministic idempotency key enforced by an additive unique index. The planner chooses currently cleared Crossref tasks while leaving blocked legacy rows intact. The evidence lookup selects the latest linked record; failed/no-judge comparison does not recursively add questions. The Crossref field list now matches the API's available fields, and HTTP failure responses retain a bounded provider detail.

### Actual external-source runtime checks

The live Crossref `/works` API returned five bibliographic records for each of two unrelated questions:

- Nepal smallholder postharvest-loss measurements: included a 2025 paper titled “Assessing Drivers of Storage Decision-Making to Prevent Postharvest Loss Among Smallholder Ginger Farmers in Palpa District, Nepal” (`https://doi.org/10.1177/21582440251367083`).
- Bicycle repair-shop appointment reminders: returned several hospital appointment-reminder papers and other weak matches, not repair-shop demand evidence.

Both runs used `collector_runner` and separate temporary SQLite files. Each wrote **5 Signals + 5 Evidence rows**, including DOI URLs, publication/retrieval timestamps, registry metadata provenance, and `metadata_only=true`; after closing and reopening each SQLite file the counts remained **5 Signals + 5 Evidence**. The files were temporary and were removed after inspection. No live project database was written. Crossref results are discovery records, not article contents, proof of demand, or supported claims; relevance remains unassessed.

The first Crossref API calls failed because of the unsupported selected field; after correction, both live queries returned records. The permitted field list excludes abstracts and full text. The source gate remains at one request per minute.

### Verification

- Final `cd backend && ../.venv/bin/python -m pytest tests -q` after adding exact-token/publication-age assessment → **383 passed, 22 warnings**.
- `cd frontend && npx tsc --noEmit` → passed.
- `cd frontend && npm run build` → passed.
- Local backend `/health` and frontend `/analyze` → HTTP 200.
- Browser check found a dev/build `.next` output collision (missing CSS/chunks); after restarting only the confirmed ForgeOS Next.js dev process, the page rendered with styling and all checked CSS/JS assets returned HTTP 200.
- The page displays exact-token overlap and publication age. Reliability, semantic relevance, contradiction assessment, and claim support remain explicitly unassessed/not inferred. Mobile inspection at 390px found no horizontal overflow.
- `git diff --check` → clean at the time of verification.

### Current limit and next work

ForgeOS now accepts unfamiliar questions, decomposes them into general subquestions, creates durable permitted research tasks, retrieves actual public bibliographic metadata, persists provenance, resumes after database reopen, and refuses to call task completion a validated opportunity. It does **not** yet assess semantic relevance, source reliability, freshness, or contradictions; it has no authorized general public-web search integration. The repair-shop search produced mostly hospital studies, so there is no evidence-backed repair-shop opportunity to report. No person was contacted; no offer was published; no transaction, customer, or revenue was fabricated.

Next: review an appropriate no-cost primary public source's current terms before enabling content retrieval. General web discovery remains blocked until an authorized source/integration is available. A real validation experiment still requires the owner's explicit authorization and a real human response.

## 2026-09-27 RESULT — source-grounded requirements and honest stopping

### Failure corrected

The previous planner had three generic Crossref queries, considered a task with any Evidence row completed, and had no persisted relation between a source result and the particular unknown it could address. Crossref bibliographic metadata could therefore look like research progress without representing what it did or did not establish. Opportunity-from-pattern also had an unconditional manual creation path that could accept a pattern without a persisted source trail.

### Implemented

- Added requirement-level persisted plan state to `ResearchQuestion` (an existing record), covering bibliographic discovery, incidence, alternatives/costs, disconfirmation, and buyer willingness to pay. The capability registry now declares exact endpoint, operation, allowed fields, requirement coverage, and provenance requirements. Only active Crossref metadata can satisfy `bibliographic_discovery`; expired GovInfo and all uncleared sources are refused.
- Research tasks persist their requirement ID, source registry ID, evidence kind, query, parent task, and follow-up depth. The per-question task budget is five; a metadata title can create one deterministic narrow follow-up. Empty/failed tasks remain unresolved and retry within the existing attempt limit. A requirement with no authorized source gets an explicit terminal reason. No requirement is marked satisfied without an actual content assessment.
- Evidence assessment persists source identity, canonical URL, registry provenance, retrieval/publication timestamps, exact-token overlap and publication age. Lexical overlap does not become semantic relevance; metadata-only records remain `metadata_only_lead`, reliability/semantic relevance/contradictions remain unassessed absent inspected content, and claim support remains `not_inferred`.
- Only persisted explicit contradiction relationships are reported as contradictions. Crossref metadata is excluded from claim judgments and economic opportunity generation. Pattern opportunities now require attributable source Evidence; experiment proposals require a research response whose requirements are all evidence-grounded.
- Worker task claims use a conditional DB state update; recovery only requeues stale running tasks, and current work holds its lease. No new domain table or substrate primitive was added.

### Actual runtime evidence and limits

An isolated local FastAPI runtime accepted an unfamiliar postharvest-loss question at `POST /analyze` (HTTP 200), called the currently authorized Crossref `/works` API, and persisted **5 Evidence records and 5 external Signals** with DOI, timestamps, registry identity, and metadata-only provenance. One result was “Assessing Drivers of Storage Decision-Making to Prevent Postharvest Loss Among Smallholder Ginger Farmers in Palpa District, Nepal.” This is a bibliographic lead only: no abstract/full text was retrieved, and no conclusion about measured losses is asserted. A title-specific follow-up task was also persisted. After closing and reopening SQLite, the question's requirement plan, completed collection task, five evidence rows, and planned follow-up remained present.

All four commercial/content requirements remain terminal-unresolved because there is no current authorized capability to answer them. No opportunity, customer, demand, competitor price, market size, willingness to pay, external response, transaction, or revenue was fabricated. No external contact, offer, or spend was made.

### Verification record

- `cd backend && ../.venv/bin/python -m pytest tests/test_grounded_research_loop.py tests/test_research_planner.py tests/test_research_agenda.py tests/test_research_task_engine.py tests/test_research_evidence_assessment.py tests/test_crossref_collector.py tests/test_public_value_flow.py tests/test_verified_research.py tests/test_experiment_api.py tests/test_intelligence_fabric.py tests/test_opportunity_quality.py tests/test_phase1_provenance_and_identity.py -q` → **107 passed, 10 warnings**.
- `cd backend && ../.venv/bin/python -m pytest -q` → **396 passed, 22 warnings**.
- Root `npm run typecheck` and `cd frontend && npx tsc --noEmit` → passed. Production build → passed in the isolated output directory. `git diff --check` → clean.
- Existing local API `/health` and public Next.js `/analyze` returned HTTP 200. Fresh isolated Crossref `/analyze` and `/health` returned HTTP 200. Integrated-browser rendering showed the Analyze UI and no page errors; at 390px the document width was 390px.

### Remaining blocker and next capability

The runtime source-authorization boundary is exact: no reviewed capability permits retrieving article/page contents or broad public-web results. Crossref clearance permits bibliographic fields only; GovInfo clearance is expired. A current terms/policy review and bounded authorization for a specific content source is required before semantic relevance, reliability, factual support, contradictions, or evidence-grounded opportunity conclusions can legitimately be assessed. The next capability is source-specific primary-content clearance plus a content assessor constrained to that declared scope. Do not simulate it.

## 2026-09-27 RESULT — final research-loop regression and runtime verification

- Implemented capability: the existing research planner marks bibliographic discovery satisfied only when persisted Crossref evidence includes DOI/URL, retrieval timestamp, and matching registry provenance. Metadata remains a discovery lead, never support for the underlying paper or a market claim.
- Files changed in this final verification pass: `backend/app/services/research_planner.py`, `backend/tests/test_grounded_research_loop.py`, `STATUS.md`, `docs/CAPABILITY_QUEUE.md`, and this report. Earlier implementation files are listed in the preceding RESULT card.
- Tests/checks: focused suite **107 passed, 10 warnings**; full backend **396 passed, 22 warnings**; root typecheck, frontend TypeScript check, production build, and `git diff --check` passed.
- Live/runtime evidence: a fresh isolated Crossref-backed `POST /analyze` returned HTTP 200 and persisted five Evidence records and five external Signals. Only bibliographic discovery was satisfied; four content/commercial requirements remained terminal-unresolved. Restarting the API against the same SQLite file preserved one question, two tasks, five Evidence records, six Signals, and the requirement plan; restarted `/health` returned HTTP 200. Existing local `/health` and `/analyze` returned HTTP 200. The browser UI rendered without page errors or horizontal overflow at 390px.
- Claims deliberately NOT made: no paper-content finding, customer demand, market size, buyer willingness to pay, validated opportunity, customer, experiment, external response, transaction, or revenue.
- Remaining blocker / exact next capability: obtain and record review/authorization for a bounded substantive-content source, including exact target, operation, permitted fields, clearance evidence/expiry, rate and redirect limits, and provenance requirements. No person was contacted and no external action was authorized or executed.

## 2026-09-27 RESULT — Semantic Scholar clearance review stopped at source boundary

- Inspected the repository's canonical source registry, collector base/Crossref adapter, task runner, requirement planner, Evidence model, and clearance tests. The registry requires explicit reviewed policy references, exact endpoint and fields, provenance obligations, redirects, expiry, and database-backed rate reservations; no new table is needed.
- Official source review: Semantic Scholar Graph API docs, product/API rate guidance, API license (`https://www.semanticscholar.org/product/api/license`), and API robots endpoint (`https://api.semanticscholar.org/robots.txt`, HTTP 404). License terms state S2 Data is governed by accompanying data licenses and underlying third-party content licenses and require attribution to “Semantic Scholar”. The requested paper-search fields do not expose per-record abstract licensing.
- Live check: one request to `https://api.semanticscholar.org/graph/v1/paper/search` using the requested field list and query “appointment scheduling algorithm” returned HTTP **429**. The response body/abstract was not displayed or retained; no retry was made. `SEMANTIC_SCHOLAR_API_KEY` is unset.
- Result: no collector, active clearance, persisted evidence, or requirement satisfaction was added. This is an explicit stop at the legal/licensing and provider-access boundary, not a successful integration. No Python/backend/frontend tests were run because no executable source was changed. Documentation changes only; run `git diff --check` after this record.
- Files updated for the source review: `docs/PUBLIC_SOURCES.md`, `STATUS.md`, `docs/CAPABILITY_QUEUE.md`, and this report.
- Exact unblock: establish per-item abstract rights and permission for ForgeOS storage/use under the S2 Data and underlying content licenses, satisfy attribution/product compatibility, and obtain usable access or provider-approved retry after the observed 429. Then implement clearance/collector/tests and retry the real runtime verification. Until then abstract evidence is not authorized and research requirements stay unresolved.

## 2026-09-27 RESULT — World Bank Indicators API v2 macro source

- Implemented the registry entry `world-bank-indicators-v2`, `WorldBankCollector` under the existing `backend/app/services/collectors/` abstraction, collector-runner dispatch, requirement-scoped macro evidence eligibility, and regression tests. No new physical domain table, migration, or logical primitive.
- The collector restricts calls to HTTPS `GET` for `/v2/indicator/{id}` and `/v2/country/{country}/indicator/{id}`; validates country, indicator and year scope; caps a range at 21 annual points; fails closed if live robots/terms recheck fails; and reserves a persistent registry request slot at least one second apart for each API request. Observation records are filtered to declared identity/value/date/unit/source fields; metadata preserves source name, source organization and source note for attribution.
- Attribution behavior observed: the data response for the tested observation had `source: null`; the indicator metadata response supplied `source: World Development Indicators` and a `sourceOrganization` string listing UN population projections, national statistical offices, and Eurostat. The stored record marks `third_party_sources_indicated: true`, does not infer legal ownership, and states that the World Bank dataset-level CC BY 4.0 default is not an indicator-specific license determination.
- Planner evidence gate: matched, attributable, numeric, country/indicator/year-scoped data can satisfy `macro_demographics`, `population_baseline`, or `economic_indicator`. It cannot satisfy buyer willingness to pay, product demand, customer pain/problem incidence, alternatives/prices, or localized market demand; such requirements remain unresolved with explicit macro-vs-micro reasons.
- Tests: `cd backend && ../.venv/bin/python -m pytest tests/test_world_bank_collector.py -v` → **7 passed, 1 warning**. The existing `test_evidence_provenance.py` file does not exist, so ran `cd backend && ../.venv/bin/python -m pytest tests/test_grounded_research_loop.py tests/test_phase1_provenance_and_identity.py tests/test_legacy_evidence_substrate_adapter.py -v` → **34 passed, 9 warnings**. Full suite `cd backend && ../.venv/bin/python -m pytest tests/ -v` → **403 passed, 22 warnings**.
- Live isolated query: HTTPS metadata and observation requests for `NPL / SP.POP.TOTL / 2022` persisted one Evidence row and one Signal in `/tmp/forgeos-world-bank-final-live.db`. Evidence source ID `NPL:SP.POP.TOTL:2022`, value `29715436`, content `Country: Nepal, Indicator: Population, total, Year: 2022, Value: 29715436`. Provenance includes the canonical API request URL, retrieval timestamp, source registry ID, WDI source identity, full source organization attribution, `traceable: true`, and explicit third-party/license caveats. Closing/reopening the database preserved one Evidence and one Signal.
- Runtime: local backend `/health` and frontend `/` both returned HTTP 200. `git diff --check` passed.
- Claims deliberately NOT made: this national population estimate does not demonstrate buyer/customer demand, willingness to pay, local market size, customer pain, opportunity validation, or revenue. Semantic Scholar remains separately blocked and unchanged.

## 2026-09-27 RESULT — World Bank third-party license gate and ILOSTAT clearance review

- World Bank hardening: observations whose indicator metadata lists a source organization are marked `license_status: "unconfirmed_third_party"` and `license_compatibility_verified: false` because the API and reviewed Data Catalog policy do not establish compatible item-specific terms. Such records remain attributable and persisted, but `world_bank_requirement_eligibility()` rejects them; the planner carries the explicit `world_bank_third_party_license_unconfirmed` terminal reason and does not attach them as requirement-supporting evidence. The dataset-level CC BY 4.0 default is not treated as proof of third-party rights.
- ILO review: official ILO rights and permissions (`https://www.ilo.org/rights-and-permissions`) grants CC BY 4.0 for ILO datasets/referential metadata published or made available from 2023-05-03, but excludes restricted constituent/partner microdata and does not automatically license earlier datasets. Live metadata for `https://sdmx.ilo.org/rest/v1/dataflow/ILO/DF_EMP_TEMP_SEX_AGE_NB/latest?references=children` returned HTTP 200 for “Employment by sex and age”; structure metadata also returned HTTP 200 and contained a `LAST_UPDATE` annotation (`27/09/2026 07:13:04`). Neither response supplied a dataset publication date or explicit CC BY 4.0 tag. An update date is not assumed to be the original publication date. SDMX robots and API-specific terms were not established.
- Endpoint probing: malformed candidate data key returned HTTP 500 (`ORA-01745`); wildcard candidate keys returned HTTP 404 (“No data is found”). No observation payload was obtained, persisted, or represented as evidence. ILOSTAT was not added to the runtime source registry; no collector or ILOSTAT tests were added because the source-specific publication/license and permission gate remains unresolved.
- Tests: `cd backend && ../.venv/bin/python -m pytest tests/test_world_bank_collector.py -v` → **8 passed, 1 warning**. Research/provenance regression group (`tests/test_world_bank_collector.py`, `tests/test_grounded_research_loop.py`, `tests/test_phase1_provenance_and_identity.py`, `tests/test_legacy_evidence_substrate_adapter.py`) → **42 passed, 9 warnings**. Full backend `cd backend && ../.venv/bin/python -m pytest tests/ -q` → **404 passed, 22 warnings**. Problems diagnostics reported no errors in changed Python files; `git diff --check` passed.
- Runtime checks: local backend `GET /health` → HTTP 200; frontend `GET /analyze` → HTTP 200. Backend `GET /analyze` returned HTTP 405, as that route requires its documented POST method; no backend analyze POST was issued in this incremental license-review task.
- Files changed for this task: `backend/app/services/collectors/world_bank.py`, `backend/app/services/research_evidence_assessment.py`, `backend/app/services/research_planner.py`, `backend/tests/test_world_bank_collector.py`, `docs/PUBLIC_SOURCES.md`, `STATUS.md`, `docs/CAPABILITY_QUEUE.md`, and this report.
- Claims deliberately NOT made: no ILO labor observation or labor baseline was collected, persisted, or verified; no World Bank third-party statistic clears any commercial research requirement without item-specific compatible license evidence; no customer pain, localized demand, willingness-to-pay, opportunity, or revenue claim was made.
- Remaining blocker / exact next capability: establish the ILO dataset's qualifying publication date and explicit CC BY 4.0 applicability, and verify SDMX robots/API terms. Only then register the exact source, implement its bounded public-aggregate collector and labor-only evidence gate, and run the live persistence/reopen test.

## 2026-09-27 RESULT — GDELT DOC API bounded metadata collector

- Refreshed implementation: `gdelt-doc-api-v2` uses the existing clearance, `services/collectors/`, task runner, Observer, Signal, and Evidence path. The HTTPS request is fixed to `artlist` + JSON with a bounded query/timespan and 1–25 record cap. Only `url`, `title`, `seendate`, `domain`, `language`, and `sourcecountry` are retained. SHA-256 identity remains URL + timestamp + query, so repeated queries deduplicate while separate article URLs remain separate observations. Publisher pages and article bodies/images are never fetched.
- Clearance and provenance: five-second persistent pacing, source attribution URL, requested GDELT reuse tag, and metadata-only provenance are recorded. HTTP 429 now receives at most two exponential retries (5s and 10s, respecting longer numeric Retry-After values up to the 30s retry ceiling); persistent throttling defers the task without consuming an attempt.
- Live verification: the first refreshed request used `"supply chain" OR agriculture`; GDELT returned the syntax message `Queries containing OR'd terms must be surrounded by ().` The corrected query was `("supply chain" OR "logistics")`, `artlist`, JSON, `1w`, max 5. After bounded 5s/10s backoff the API remained rate-limited and the opt-in test skipped. **0 article records, 0 Evidence, and 0 Signals** were obtained or persisted, so the isolated SQLite close/reopen assertions could not run. No further live request was made.
- Epistemic/opportunity controls: attributable records may satisfy `media_coverage_observation` or `recent_event_signal`. `public_reporting_velocity` is restricted to an uncapped count of GDELT-indexed articles for the declared query/time window; a capped set stays unresolved. None of these metadata observations can establish article claims or commercial demand, or create/advance an Opportunity. Distinct article records retain separate provenance.
- Tests: focused `tests/test_gdelt_collector.py -v` → **9 passed, 1 skipped, 1 warning**. Combined GDELT + registry + research-loop + opportunity + Crossref + public-value regressions → **74 passed, 1 skipped, 8 warnings**. Full `cd backend && ../.venv/bin/python -m pytest tests/ -v` → **413 passed, 1 skipped, 22 warnings**. The opt-in live persistence test skipped on provider rate limiting; mocked parser, deduplication, opportunity, velocity-boundary, and retry tests passed. `git diff --check` passed.
- Runtime: existing backend `GET /health` → HTTP 200; frontend `GET /analyze` → HTTP 200.
- Files changed: `backend/app/services/collectors/gdelt.py` (new), `backend/tests/test_gdelt_collector.py` (new), `backend/app/services/source_clearance_registry.py`, `backend/app/services/collector_runner.py`, `backend/app/services/research_evidence_assessment.py`, `backend/app/services/research_planner.py`, `docs/PUBLIC_SOURCES.md`, `docs/CAPABILITY_QUEUE.md`, `STATUS.md`, and this report.
- Claims deliberately NOT made: no actual GDELT article observation was persisted or verified; article text claims, event truth, business demand, customer pain, market size, willingness to pay, financial viability, or opportunity are not established by this run.
- Remaining blocker / next capability: GDELT provider authorization/rate capacity. On a future provider-approved/unthrottled request, run the opt-in SQLite persistence/reopen check once. Do not retry the endpoint in a tight loop or treat coverage count as reporting velocity or commercial proof.

## 2026-09-27 RESULT — OpenAlex scholarly evidence and abstract discovery

- Terms and access: OpenAlex's official API reference (`https://help.openalex.org/api/`) was checked; it documents keyless basic use, the Works list endpoint, `search` and `per_page`, and states “all data is CC0.” `https://api.openalex.org/robots.txt` returned `200` with `User-agent: *` and `Allow: /`. The source registry records these references and runtime rechecks the robots policy and CC0 statement.
- Integration: registered `openalex-public-works-cc0` at exact `https://api.openalex.org/works` in the source-clearance registry; added the collector under the established `backend/app/services/collectors/` pattern, dispatched via the existing task runner and Observer into Evidence/Signal. Persistent source pacing is one request per second; request sizes are 1–50 works. Requests specify only `id`, `doi`, `title`, `publication_year`, `cited_by_count`, `authorships`, `concepts`, `primary_location`, `open_access`, and `abstract_inverted_index`. Deterministic external identity is SHA-256 of OpenAlex ID plus query.
- Abstract/data controls: positional abstracts are reconstructed from JSON. Stored fields include work ID, DOI when valid, title, year (no synthetic exact publication date), citation count, bounded author/institution country and concept summaries, minimal safe location/open-access summaries, and abstract text. `pdf_url`/`oa_url` and publisher landing links are discarded. No external PDF or publisher HTML request occurs. Provenance marks CC0, exact request/query, traceability, abstract reconstruction, and geography/temporal status as unassessed.
- Epistemic controls: scholarly records can satisfy only `scholarly_evidence`, `prior_research`, `documented_intervention`, or `literature_existence`. A discovered abstract documents that literature exists; it does not establish an intervention's efficacy. Author-affiliation country is not the study population/geography and publication year is not study period. Local-applicability and study-context requirements remain unresolved; customer pain, buyer willingness to pay, demand, market size, revenue and opportunity gates are not resolved by abstracts, citation counts or retrieval relevance. OpenAlex-derived signals are excluded from opportunity creation and advancement.
- Live isolated persistence: executed query `postharvest loss smallholder farmers Nepal` with `search` and `per_page=5`; the live integration test passed. Each returned work was persisted to a temporary SQLite database as an Evidence/Signal pair, the database was closed and reopened, and both table counts were verified unchanged. Pytest's captured success output did not print the numeric returned record count; the test asserts returned count is at most five and exact Evidence/Signal count equality. Per-record OpenAlex ID, title, CC0 provenance, and abstract-reconstruction status were checked live; parser unit tests also check optional DOI, publication year, citation count, concepts, and authorship. The temporary database was cleaned up after verification.
- Tests: focused OpenAlex + `tests/test_grounded_research_loop.py -v` → **21 passed, 1 skipped**; related clearance/opportunity/provenance regressions → **53 passed**. Full `cd backend && ../.venv/bin/python -m pytest tests/ -v` → **422 passed, 2 skipped, 22 warnings**. The two full-suite skips are opt-in live-source tests; the OpenAlex live test was separately enabled and passed. Focused collector tests cover field projection/no PDF URLs, custom User-Agent, one-second persistent rate gate, max-50 bounds, malformed-index rejection, 429 exponential retry, idempotency across distinct research tasks, planner locality/time mismatch unresolved, non-commercial boundaries, and opportunity exclusion. `git diff --check` passed.
- Files changed for OpenAlex: `backend/app/services/collectors/openalex.py` (new), `backend/tests/test_openalex_collector.py` (new), `backend/app/services/source_clearance_registry.py`, `backend/app/services/collector_runner.py`, `backend/app/services/research_evidence_assessment.py`, `backend/app/services/research_planner.py`, `backend/app/services/opportunity_engine.py`, `docs/PUBLIC_SOURCES.md`, `docs/CAPABILITY_QUEUE.md`, `STATUS.md`, and this execution report.

## 2026-09-27 RESULT — OpenAlex keyword/semantic and atomic identity hardening

- **Implementation:** `fetch_openalex_works` now accepts `Literal["keyword", "semantic"]`. Keyword requests use `search` with a 100-record ceiling; semantic requests use `search.semantic`, are limited to 50 works, and truncate normalized query text to 2,000 characters. Both use the persistent one-second source gate and a polite `mailto:research@forgeos.local` User-Agent. The collector remains HTTPS/API-only and requests the approved JSON field projection.
- **Identity/concurrency:** Signal identity is SHA-256 of `openalex:{canonical_work_id}` and is protected by a nullable unique `signals.identity_key` plus additive unique index. Signal inserts use a nested transaction and retrieve the winner after a uniqueness conflict; Evidence retains its unique idempotency key and uses equivalent atomic conflict recovery. Sixteen concurrent duplicate observations produced exactly one Signal and one Evidence. Mode/query provenance is retained; publisher, PDF, landing-page, and relevance-score URLs are discarded and never requested.
- **Empty/failure semantics:** A valid empty Works list is stored on the ResearchTask as a `valid_empty_retrieval` observation with `returned_works: 0` and `claim_effect: none`; it creates no Signal/Evidence and leaves scholarly/commercial requirements unresolved. HTTP 5xx, timeout, malformed JSON, and exhausted 429 retries remain explicit failed/deferred collection paths, never successful-shaped evidence.
- **Epistemic controls:** Both retrieval modes may support only literature-existence/scholarly observations. Neither mode, nor citations or relevance, satisfies buyer willingness to pay, customer pain, local market size, product demand, revenue, or commercial viability. Local population/geographic/temporal applicability stays unresolved; no Opportunity is created or advanced from these records.
- **Live semantic persistence:** Exactly one bounded Works retrieval was executed: query `postharvest loss smallholder farmers Nepal`, mode `semantic` (`search.semantic`), cap 5. **Returned Works Count: 5; Persisted Evidence Count: 5; Persisted Signal Count: 5; Reopened Database Evidence Count: 5; Reopened Database Signal Count: 5.** Every observed outbound destination was `api.openalex.org` or the authorized policy host `help.openalex.org`; no publisher page or PDF request was attempted. The temporary SQLite database was closed and reopened, and both counts matched.
- **Tests and checks:** Focused `test_openalex_collector.py` → **15 passed, 1 skipped, 1 warning**. Live semantic persistence/reopen test → **1 passed, 1 warning**. Research/provenance/opportunity regression selection (`test_grounded_research_loop.py`, `test_research_evidence_assessment.py`, `test_evidence_graph.py`, `test_evidence_relationship_substrate_adapter.py`) → **26 passed, 4 warnings**. The requested `test_evidence_provenance.py` path does not exist in this repository; these available provenance/evidence-focused suites were used instead. Full `backend/tests/` → **428 passed, 2 skipped, 22 warnings**. `git diff --check` → **passed**.
- **Files created/modified for this increment:** `backend/app/services/collectors/openalex.py`, `backend/app/services/collectors/base.py`, `backend/app/services/source_clearance_registry.py`, `backend/app/services/collector_runner.py`, `backend/app/services/observer_engine.py`, `backend/app/services/research_task_engine.py`, `backend/app/models.py`, `backend/app/migrations.py`, `backend/tests/test_openalex_collector.py`, `docs/PUBLIC_SOURCES.md`, `docs/CAPABILITY_QUEUE.md`, `STATUS.md`, and this report.
- **Operating boundary:** The API is keyless and the integration requires no paid service or credentials; no publisher content was accessed. OpenAlex search, semantic proximity, citation counts, and empty results do not establish or simulate market demand, claim truth, or commercial validation.

## 2026-09-28 RESULT — OpenAlex planner, provenance, and concurrency audit

- **Planner selection and validation:** Requirement planning now selects keyword mode for explicit DOI, author/paper lookup, exact phrase, and named-entity requests; broad conceptual/intervention searches use semantic mode. Planner tasks persist the unreduced `original_research_question`, exact `derived_retrieval_query`, validated `search_mode`, detected `geographic_qualification` and `population_qualification`, and the `unresolved_dimensions` list. The same fields propagate into each persisted OpenAlex Evidence provenance record. Invalid task modes fail before a Works API request. Parameter construction is mutually exclusive: keyword requests send only `search`, semantic requests only `search.semantic`; semantic queries are bounded to 2,000 characters and 50 results, keyword to 100 results.
- **Database/migration/concurrency:** Five barrier-synchronized worker threads observing the same work concurrently produced one Signal and one Evidence, with no uniqueness crash. Signal identity remains deterministic SHA-256 of the canonical OpenAlex Work ID; no wall-clock value participates in primary identity. The additive nullable unique key preserves existing rows; for a legacy duplicate-key database, migration keeps all historical Signal rows, retains the key on the oldest row, clears only duplicate identity-key values, then adds uniqueness. Populated-database migration verification passed.
- **Empty/failure behavior:** An empty `results: []` now creates a distinct idempotent `valid_empty_retrieval` Signal and task observation, without Evidence, claim effect, claim re-evaluation, factual requirement satisfaction, Opportunity, or Experiment. The requirement remains unresolved/retryable rather than `research_completed`. HTTP 429, 5xx, timeout, DNS failure, and malformed JSON remain explicit deferred/failed task outcomes without fabricated evidence. Citation counts/concepts/relevance stay retrieval metadata and cannot establish commercial support or unlock opportunity gates.
- **Live semantic result:** Query: `postharvest loss smallholder farmers Nepal`; Mode: `semantic`; Returned Works Count: **5**; Persisted Evidence Count: **5**; Persisted Signal Count: **5**; Reopened DB Evidence Count: **5**; Reopened DB Signal Count: **5**; Observed Outbound Hosts: **[`api.openalex.org`, `help.openalex.org`]**. The live test asserted all outbound URLs were confined to those OpenAlex API/policy hosts. **0 publisher-page/PDF requests** occurred.
- **Tests and checks:** Focused OpenAlex suite: **20 passed, 1 skipped, 4 warnings**. The live semantic test, run separately with its opt-in enabled: **1 passed, 2 warnings**. Available research/provenance/opportunity regressions (`test_grounded_research_loop.py`, `test_phase1_provenance_and_identity.py`, `test_research_evidence_assessment.py`, `test_evidence_graph.py`, `test_evidence_relationship_substrate_adapter.py`, `test_opportunity_quality.py`, `test_experiment_lifecycle.py`): **54 passed, 12 warnings**. The specifically named `backend/tests/test_evidence_provenance.py` does not exist; the available provenance/evidence suites above were used instead. Full `backend/tests/`: **433 passed, 2 skipped, 24 warnings**. `git diff --check`: **passed**; Problems diagnostics: no errors in changed Python files.
- **Exact files changed for this increment:** `backend/app/services/research_planner.py`, `backend/app/services/collectors/openalex.py`, `backend/app/services/collector_runner.py`, `backend/app/services/observer_engine.py`, `backend/app/migrations.py`, `backend/tests/test_openalex_collector.py`, `docs/PUBLIC_SOURCES.md`, `docs/CAPABILITY_QUEUE.md`, `STATUS.md`, and this report.
- **Budget and epistemic boundary:** OpenAlex keyless access used no credentials, paid service, or paid quota; this run's API spend was **$0**. No publisher HTML, external PDF, or paywall content was accessed. Scholarly metadata, citation counts, semantic retrieval, and empty results remain unable to satisfy customer pain, buyer willingness to pay, product demand, market size, revenue, or commercial viability, and cannot create/advance an Opportunity or Experiment.

## 2026-09-28 RESULT — Multi-source research orchestration and synthesis

- **Decomposition and routing:** Added six bounded orchestration nodes: `phenomenon_existence`, `affected_population`, `geographic_boundary`, `reporting_velocity`, `documented_interventions`, and `commercial_validation_gap`. The example objective retains the exact original question plus `Nepal` and `smallholder farmers`. Routing uses only active registry capabilities: Crossref → bibliographic lead; OpenAlex → scholarly abstract/intervention; World Bank → country population baseline; GDELT → bounded reporting metadata. Customer validation has no public-source candidates.
- **Execution and persistence:** A mocked test-mode run planned and executed **5 tasks sequentially** across Crossref, OpenAlex, World Bank, and GDELT (two distinct OpenAlex retrieval requirements). It persisted **5 Evidence rows (IDs 1–5)**. The isolated SQLite database was closed and reopened; it retained **5 completed tasks and the same 5 Evidence IDs**. No live provider requests were made; observed outbound hosts: **[]**; external spend: **$0**.
- **Synthesis/citations:** The read-only synthesis cites persisted Evidence IDs and canonical provenance URLs. Test fixtures verified phenomenon citations to Evidence **1** (`https://openalex.org/W123`) and **3** (`https://doi.org/10.1234/example`), and a population citation to Evidence **2** (`https://api.worldbank.org/v2/country/NPL/indicator/SP.POP.TOTL`). Explicit contradiction edges and both records remain present as coexisting observations; no record is averaged or overwritten. The buyer-willingness-to-pay/commercial gap remains `unresolved`, and `opportunity_gate_unlocked` remains `false`.
- **Failure/completion boundary:** The runner remains the canonical execution path; task completion is separate from overall research completion. Synthesis is read-only, adds no claim truth transition, and cannot transform citation counts, macro population, or article-volume metadata into customer pain, willingness-to-pay, or commercial demand. No source clearance, table, or migration was added.
- **Verification:** `test_multi_source_orchestration.py` + `test_research_planner.py` → **9 passed, 1 warning**. Focused orchestration/OpenAlex/research/provenance/opportunity regressions → **79 passed, 1 skipped, 14 warnings**. Full `backend/tests/` → **438 passed, 2 skipped, 24 warnings**. `git diff --check` → **passed**.
- **Exact files created/modified:** `backend/app/services/research_planner.py`, `backend/app/services/collector_runner.py`, `backend/app/services/research_synthesis_engine.py` (new), `backend/tests/test_multi_source_orchestration.py` (new), `STATUS.md`, `docs/CAPABILITY_QUEUE.md`, and this report.
- **Result:** Multi-source public research is now planned and executed within the existing source-clearance and five-task budget; the synthesis preserves citations, source differences, explicit conflicts, and unresolved commercial gaps. The verified integration is mocked test mode, not live research evidence.
