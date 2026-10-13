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
