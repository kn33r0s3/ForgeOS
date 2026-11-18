# 004 — Fix the 13 repo test failures

- **Finding:** CAPABILITY_QUEUE.md test-suite entry (18 Nov 15:48): backend 1,376 tests, 13 failures, 0 errors, 2 skipped. All 13 cluster in three safe-mode/runtime-control files: test_execution_boundary (6), test_integration_dispatcher (6), test_owner_control (1). JUnit at /tmp/forgeos-backend-junit.xml.
- **Owner:** Copilot
- **Input:** the JUnit file + the three failing test files
- **Output:** fixes + a re-run recorded in docs/CAPABILITY_QUEUE.md
- **Verify:** re-run the backend suite and confirm the JUnit shows 0 failures; the queue entry names the fix per failure
- **If blocked:** if a failure needs a design decision (not a bug fix), record it in the queue entry and move to the next failure; do not change the autonomy gate semantics without owner approval

- **Status:** DONE. The focused modules passed 36/36. The full command
  `env -u DATABASE_URL -u FORGEOS_TEST_DATABASE_URL python3.11 -m pytest -q backend/tests --junitxml=/tmp/forgeos-backend-junit.xml`
  passed **1,376 tests, 0 failures, 0 errors, 2 skipped**; JUnit agrees
  (testsuite tests="1376" errors="0" failures="0" skipped="2", 17:31:03 +0545).
  (Muse verified the JUnit directly; the "1,374" first written here was a miscount.)
- **Fixes:** registered `gate_refusal`, `gate_execution`, and `blocker_opened`;
  changed the T07 fixture to the registered `state_changed` event type;
  namespaced gate audit idempotency keys and isolated writes with a savepoint
  so repeated keys cannot roll back the blocker; updated dispatcher tests to
  modify the fixture's singleton and explicitly set safe mode; replaced the
  null owner-control reason with `initial_default_safe`.
- **Safety:** no authorization policy changes, production database use,
  commit, push, or deployment. Exact-head CI was absent at the initial check.
