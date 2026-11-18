# 008 — Wire the gates alert into the daily cycle + verify the Telegram channel

- **Status:** scheduled-cycle wiring and local checks are verified; end-to-end owner delivery is blocked by `BLOCKED_BY_MISSING_ACCESS`. No alert was sent, so owner confirmation is pending.
- **Finding:** backend/app/services/gates_alert.py is built (step 7) but NOT wired into the daily cycle, and the Telegram channel's end-to-end delivery is UNVERIFIED (the transport exists; whether the bot is connected is UNKNOWN — backend/.env was never read).
- **Owner:** Copilot (after queue/007 lands; do not start while 007 is running)
- **Input:** backend/app/services/gates_alert.py (run_gates_alert) + backend/app/api/scheduled.py (the daily cycle, GET /cycle)
- **Output:** the alert called from the daily cycle + a verification that a test alert reaches the owner + a one-line record in docs/CAPABILITY_QUEUE.md
- **Verify:** (1) `python3 -m py_compile backend/app/services/gates_alert.py` passes; (2) the daily cycle calls run_gates_alert and, on green, sends nothing extra; (3) a test alert (forced red, or a dry-run) is enqueued via the outbox and the dispatcher delivers it to Telegram — prove it from the delivery row (status SUCCEEDED) and the owner's confirmation, not from the enqueue alone; (4) if the channel cannot deliver, the result records blocked_by=BLOCKED_BY_MISSING_ACCESS and nothing is faked.
- **If blocked:** if the Telegram bot is not connected (no token / no owner chat id / webhook not registered), record blocked_by=BLOCKED_BY_MISSING_ACCESS in the queue entry and in docs/GATES.md's UNKNOWN section, and do NOT claim the alert works. Do not read backend/.env values. Do not send anything except the one test alert the owner approves. Do not commit, push, or deploy. Do not change any flag default.
- **Verification result:** daily-cycle wiring is in place. `python3.11 -m py_compile backend/app/services/gates_alert.py backend/app/api/scheduled.py backend/tests/test_scheduled_cycle.py` passed; `env -u DATABASE_URL -u FORGEOS_TEST_DATABASE_URL python3.11 -m pytest -q backend/tests/test_scheduled_cycle.py backend/tests/test_integration_dispatcher.py` passed (**64 passed**); `node --experimental-strip-types --test src/lib/gates.test.ts` passed (**14/14**); `node scripts/gates-report.mjs` reported **GREEN**. A forced-red TEST invocation returned `BLOCKED_BY_MISSING_ACCESS`; owner-channel readiness was false, so it returned before enqueueing. No alert was sent and owner receipt remains **UNVERIFIED**. `backend/.env` was not read; no flag default changed; no commit, push, or deployment was made.

## Wiring (in the daily cycle, scheduled.py)
- After the daily maintenance + legacy cycle succeed, call `gates_alert.run_gates_alert(db, repo_root)` with the repo root.
- On green: do nothing (stay silent).
- On red + notified: log the delivery id.
- On red + blocked_by: log BLOCKED_BY_MISSING_ACCESS and record it in the cycle response (so the daily check surfaces it).
- Do not change the /cycle auth (CRON_SECRET) or the owner-key gate from 007.
