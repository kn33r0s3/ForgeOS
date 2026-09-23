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
