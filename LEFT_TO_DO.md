# ForgeOS — left to do (from the Claude session on 2026-09-14)

I don't have network access or a working Python venv in my sandbox, so I
could read and edit code but could NOT run the backend, run the test
suite, or run a real cycle. Everything below is either (a) done and
needs your verification, or (b) not started.

## Done in this pass — verify these

1. **Confirmed the P0.1 session-poisoning fix was already correct.**
   `backend/scripts/run_daily_cycle.py` already calls `_rollback_if_needed()`
   between the forge-cycle stage and the autonomy-cycle stage. I read it
   line by line — this part is genuinely fixed, not just claimed fixed.
   No code change needed here.

2. **Added WAL mode + busy_timeout to `backend/app/database.py`.**
   The actual `sqlite3.OperationalError: disk I/O error` in
   `logs/daily_cycle_log.jsonl` (all 3 entries, all from 2026-09-12) is
   most consistent with SQLite's default rollback-journal mode taking an
   exclusive lock while the scheduler, the worker, and a manual cycle run
   all touch `forge.db` around the same time. I switched to WAL mode
   (readers + one writer can coexist) and set `busy_timeout=30000` so a
   transient lock retries for 30s instead of failing immediately.
   **This is untested** — I could not run it. It's the standard fix for
   this exact error signature, but you need to actually run a cycle and
   confirm the error is gone, not just trust that it should work.

3. **Added a startup log line** printing the resolved absolute SQLite
   path. `verification/truth-audit-current.json` was pointing at
   `/home/ubuntu/ForgeOS_master/ForgeOS/storage/forge.db` while other
   reports from the same day reference `forgeos-work/forgeos-original-renewed`
   and the relative `storage/forge.db` — three different-looking paths in
   one day's worth of reports. This log line makes it immediately obvious
   next time two databases are silently diverging, instead of finding out
   from a table-count mismatch after the fact.

4. **Removed `fix_all.py`, `fix_schema.py`, `opencode.json.backup`** from
   the repo root — confirmed `backend/app/migrations.py` still covers the
   column-repair logic these scratch scripts were hand-patching, so
   they're dead weight now.

## Not done — do these next, in order

### Right now, before anything else
- [ ] **Run a real cycle and check the log.**
  ```bash
  cd backend && python -m scripts.run_daily_cycle --times 3
  tail -c 2000 ../logs/daily_cycle_log.jsonl
  ```
  If you still see `disk I/O error`, the WAL change didn't fix it and the
  real cause is something else (full disk, a Docker bind-mount filesystem
  that doesn't support SQLite locking at all, or two processes writing
  the same file from different containers/hosts). Check `df -h` on the
  volume and confirm nothing else has `forge.db` open
  (`lsof storage/forge.db` on the host, or the container).

- [ ] **Settle the canonical database path for real.** Grep the whole repo
  for every place a path to `forge.db` gets built — `docker-compose.yml`,
  `.env`, `start.sh`, `backend/app/config.py` — and confirm they all
  resolve to the exact same absolute file. The new startup log line will
  show you the resolved path each time something boots; if you see two
  different paths across two terminals, that's your bug, not a
  coincidence.

- [ ] **Run the full test suite fresh** and record one number as current
  truth, replacing the "111 / 128 / 137" ambiguity across the existing
  reports:
  ```bash
  cd backend && python -m pytest tests/ -q
  ```

### Once the cycle is verified stable
- [ ] Earn workspace status progression: `draft → customer_confirmed →
  paid / failed / abandoned` per offer (per `docs/CURRENT_FOCUS.md`).
- [ ] Per-offer "next real action" checklist.
- [ ] Run one pilot with one real person — not simulated, not seeded.
- [ ] Record the honest outcome, including "no sale" if that's what
  happens. Your own rules say that's a valid result.

### Only after that produces a real result
- [ ] Expand earning pathways or connect live eSewa/Khalti/Fonepay
  credentials. Not before — this is explicit in
  `docs/NEPAL_FIRST_PRODUCT_PLAN.md` and I agree with the ordering.

### Housekeeping, lower priority
- [ ] Decide a retention policy for the `storage/forgeos_pre_*.db` backup
  files — there are four of them now. Keep the most recent one or two,
  archive the rest somewhere off the main volume.
- [ ] The report sprawl (`P0_1..4_*.md`, `INSPECTION_REPORT.md`,
  `INTEGRATION_AUDIT.md`, `RELEASE_REPORT.md`, `SETUP_COMPLETE.md`,
  `LIVE_REPORT.txt`) is useful history but bad as "current status" —
  consider one `STATUS.md` that gets overwritten each session, with the
  rest moved into an `archive/` folder.
