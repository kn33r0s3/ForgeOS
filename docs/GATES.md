# GATES.md — Hami's gates, generated from code

Generated 2026-11-21T22:51:22.320Z by `npm run gates:report` (scripts/gates-report.mjs).
Do not hand-edit this file: CI fails if it is stale. Change the code, then regenerate.

**Status: GREEN — every gate holds**

## The rule

Every outward or consequential action goes through one front door: the decision service `execute_through_gate` (`backend/app/services/execution_engine.py:1149`). No module outside the gate layer touches a sender. No API route sends without the owner key. No flag is open by default. Only the owner can open a gate, and only by setting an environment variable.

## Gate flags — all default closed

| Flag | Controls | Default | Who can open it | Test |
| --- | --- | --- | --- | --- |
| `FORGE_BOT_LIVE` | real external / customer-facing side effects | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `FORGE_BOT_INTAKE_ENABLED` | web intake of leads | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `FORGE_BOT_RESPONSE_SEND_ENABLED` | sending a reply to a lead | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `FORGEOS_PUBLIC_CHECKOUT_ENABLED` | public checkout (eSewa / Khalti) | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `HAMI_TELEGRAM_CONTROL_ENABLED` | Telegram owner control | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `HAMI_TELEGRAM_OWNER_DIGEST_ENABLED` | Telegram owner digest | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `HAMI_OWNER_SMS_DIGEST_ENABLED` | Twilio owner SMS digest | closed (false) | owner only, via environment | src/lib/gates.test.ts Rule C |
| `FORGE_API_KEY` | the owner key itself | empty | owner only, via environment | src/lib/gates.test.ts Rule C |

## The decision service

- Operations covered (13): `INSPECT_FILE`, `INSPECT_REPO_STATE`, `RUN_LOCAL_TESTS`, `EDIT_REPO_FILE`, `CREATE_REPO_FILE`, `RECORD_EVENT`, `READ_TASK_STATE`, `REQUEUE_TASK`, `OPEN_BLOCKER`, `READ_HALT_STATE`, `SEND_EMAIL`, `SEND_SMS`, `SEND_TELEGRAM`.
- Send operations: `SEND_EMAIL`, `SEND_SMS`, `SEND_TELEGRAM`.
- Discipline: HALT fail-closed, known-operation check, rights, envelope re-check, idempotency key computed by the gate, bounded retries, postcondition, record + WorldEvent. A refused send is recorded, never delivered.
- Test: backend/tests/test_execution_boundary.py (1,376 tests, 0 failures).

## The API key middleware

- Wired in backend/app/main.py: yes.
- Guards state-changing methods (POST/PUT/PATCH/DELETE) when FORGE_API_KEY is set or the runtime is deployed. Deployed without a key it fails closed (503). Local dev with no key is open by design.
- Test: src/lib/gates.test.ts Rule B.

## Public write allowlist — every entry needs a written reason

| Path | Reason | Test |
| --- | --- | --- |
| `/analyze` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/analyze` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/hami/chat` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/hami/chat` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/public/booking-requests` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/public/booking-requests` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/public/domain` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/public/domain` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/forge-bot/leads` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/forge-bot/leads/opt-out` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/forge-bot/leads/delete` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/forge-bot/leads` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/forge-bot/leads/opt-out` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/forge-bot/leads/delete` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/owner-control/telegram/webhook` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/owner-control/telegram/webhook` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/signals/public-request` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |
| `/api/signals/public-request` | written in PUBLIC_WRITE_REASONS | src/lib/gates.test.ts Rule B |

## The front door — who touches a sender

Only `backend/app/services/integration_dispatcher.py` may call a sender (SMTP via smtplib, Twilio via api.twilio.com, Telegram via telegram_transport). `backend/app/services/telegram_transport.py` is the transport itself. Every other module must enqueue into `backend/app/services/integration_outbox.py`.

No module outside the gate layer touches a sender.

- Test: src/lib/gates.test.ts Rule A.

## Public claims

A public page renders a claim only with state + evidence (src/lib/ledger.ts). ESTIMATED is never shown as ACTUAL. Contradicted claims are shown, not hidden. Test: src/lib/gates.test.ts Rule D + src/lib/ledger.test.ts.

## What is UNKNOWN

- Live flag values (backend/.env is never read by this report).
- Telegram alert delivery: a forced-red TEST attempt on 2026-11-18 returned BLOCKED_BY_MISSING_ACCESS; this was not a real gates failure, no message was sent, and owner receipt remains UNVERIFIED. backend/.env was not read.
- Whether the Telegram token/chat credentials are present or the webhook is registered.
- Branch protection on main (GitHub API needs auth).
- Who calls GET /scheduled/cycle (not found in the repo).
- The hourly discovery push to main (not found in the repo).

## Source

Inventory: docs/GATES_INVENTORY.md. Tests: src/lib/gates.test.ts. Backend tests: backend/tests/test_execution_boundary.py.
