# 007 — Route every outward action through the decision service (ONE FRONT DOOR)

- **Finding:** docs/GATES_INVENTORY.md (18 Nov 2026, scanned from code). Five bypasses. The decision service is `execute_through_gate` in `backend/app/services/execution_engine.py:1149`. It covers 10 repo-local operations only and has NO send operation, so no sender passes through it today. The outbox/dispatcher (`backend/app/services/integration_outbox.py` + `integration_dispatcher.py`) is the single funnel for sends that use it, but three call sites skip it and one GET route sends without any key check.
- **Owner:** Copilot
- **Input:** docs/GATES_INVENTORY.md §12 (the five bypasses) + the files named below
- **Output:** the five fixes below + a re-run of the backend suite proving 0 failures + a one-line record per fix in docs/CAPABILITY_QUEUE.md
- **Verify:** `env -u DATABASE_URL -u FORGEOS_TEST_DATABASE_URL python3.11 -m pytest -q backend/tests` shows 0 failures; grep proves no direct `telegram_transport.send_owner_message` call remains outside `integration_dispatcher.py`; GET `/scheduled/cycle` requires the owner key; every `PUBLIC_WRITE_PATHS` entry has a written reason.
- **If blocked:** if a fix needs a design decision (not a bug fix), record it in the queue entry and move to the next fix; do not change any flag default (all stay `false`/empty); do not send anything; do not commit, push, or deploy.
- **Verification result:** complete. The focused gated-delivery set passed **30 tests**; the required full backend suite passed **1,380 tests, 2 skipped, 0 failures** (18 existing warnings). `git diff --check` passed, the only application call to `telegram_transport.send_owner_message` is in `integration_dispatcher.py`, `/scheduled/cycle` retains its `CRON_SECRET` check and requires `X-API-Key`, and the reason-map test covers every unchanged public-write path. Provider calls were mocked; no message was sent. No flag default changed; no commit, push, or deployment was made.
- **Independent verification by Muse (18 Nov, from evidence):** backend suite re-run fresh, 1,380 passed, 2 skipped, 0 failures, 0 errors (JUnit /tmp/verify-007-junit.xml). Gates tests 14/14 pass (was 12/14). npm run gates GREEN. GATES.md generated (83 lines, Status GREEN). WHO_DID_WHAT.md generated (1,857 lines, 1,847 commits, all UNKNOWN). Hook installed. Note: npm test has 1 pre-existing failure (features.test.ts, /services/$slug, old commits, not 007). Moved to done/ in BOTH mirrors.

## Fix 1 — Telegram direct send, API webhook reply
- **File:** `backend/app/api/owner_control.py:84`
- **Bypass:** calls `telegram_transport.send_owner_message` directly, skipping the outbox/dispatcher.
- **Fix:** enqueue the reply via `integration_outbox.enqueue` (same integration_name `telegram_owner`, operation `send_telegram_owner`) and let `integration_dispatcher.py:292` deliver it. Do not call the transport directly.

## Fix 2 — Telegram direct send, owner "ask" flow (x2)
- **File:** `backend/app/services/owner_control.py:263` and `:294`
- **Bypass:** both call `telegram_transport.send_owner_message` directly, skipping the outbox/dispatcher.
- **Fix:** enqueue both via `integration_outbox.enqueue` (same integration_name/operation as Fix 1). Do not call the transport directly.

## Fix 3 — GET /scheduled/cycle sends email/SMS with no key check
- **File:** `backend/app/api/scheduled.py:340` (GET /cycle), `:423` (daily summary email), `:911` (retry queued), `:934` (daily SMS)
- **Bypass:** a GET that causes outward sends (email + SMS) is not guarded by `api_key_middleware` (`backend/app/security.py:145`), which only guards POST/PUT/PATCH/DELETE. Anyone who can call GET /scheduled/cycle triggers owner notifications.
- **Fix:** require the owner key on GET `/scheduled/cycle` (use the existing `require_owner_api_key` dependency, `backend/app/security.py:79`). Keep the route a GET (do not change its method) but make it key-gated. Do not open any new path.

## Fix 4 — Decision service has no send operation
- **File:** `backend/app/services/execution_engine.py` (`Operation` enum + `execute_through_gate` at :1149)
- **Bypass:** the gate covers only 10 repo-local ops. There is no SEND_EMAIL / SEND_SMS / SEND_TELEGRAM operation, so no sender can pass through it.
- **Fix:** add three operations to the `Operation` enum — `SEND_EMAIL`, `SEND_SMS`, `SEND_TELEGRAM` — with the same gate discipline as the existing ops (HALT fail-closed, known-operation check, idempotency key computed by the gate, refusal recorded). Then route `integration_dispatcher.py`'s actual sends through `execute_through_gate` (one gate call per delivery, principal `integration_dispatcher`, scope = the integration name). A refused send must NOT be delivered and must be recorded as a refusal. Do not change the 10 existing operations' semantics. Do not change any flag default.

## Fix 5 — PUBLIC_WRITE_PATHS has no written reasons
- **File:** `backend/app/security.py:25-42`
- **Bypass:** the allowlist entries are bare strings with no reason attached. The gate rule requires each entry to carry a written reason.
- **Fix:** add a `PUBLIC_WRITE_REASONS` dict next to `PUBLIC_WRITE_PATHS` mapping every path to one plain-English sentence stating why it is public (use the reasons in docs/GATES_INVENTORY.md §10). Every path in the set must have an entry; no path may be added or removed.
