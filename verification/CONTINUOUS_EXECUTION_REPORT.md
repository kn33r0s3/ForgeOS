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
