# Decisions (what I chose and why)

## Rules I read (AGENTS.md, in my own words)

1. ForgeOS exists to drive owner dependency to zero: fewer owner actions per REAL economic outcome, while keeping authorization, evidence, privacy, legal, and platform boundaries intact. More infrastructure or synthetic activity is not autonomy.
2. No paid software or infrastructure before the first real customer revenue, except a verified legal, security, payment, or critical-execution requirement.
3. Never contact a person, publish an offer, spend money, or simulate prospect conversations without the owner's explicit authorization.
4. REAL, TEST, MOCK, and HYPOTHESIS must never be mixed. Tests never count as customer or revenue evidence, and OWNER_INTERVENTIONS_PER_REAL_TRANSACTION is NOT MEASURABLE until a real transaction is verified — never zero.

## README loop (in my own words)

OBSERVE → VERIFY → UNDERSTAND → DECIDE → ACT → MEASURE → LEARN → repeat.
Intelligence comes from the full evidence-to-learning loop, not from any single
model or score. Tests never count as customer evidence.

## Renovation working notes

- 2026-10-08: Executing the renovation playbook (Phases 0–4) as working
  discipline in a fresh worktree of origin/main. The playbook's
  `git checkout -b renovation` step is SKIPPED per the owner's standing
  direct-to-main rule (no branches, always); work happens directly on the
  worktree HEAD and pushes HEAD:main. The `pre-renovation` tag is kept as
  the rollback bookmark.
- 2026-10-08: docs/RENOVATION/HAMI_AGENT_PLAYBOOK.txt and playbook_cli.py
  do not exist in this repo (verified by listing docs/RENOVATION after
  creation). Noted in OWNER_QUESTIONS.md; the playbook content lives in
  the agent's context instead. Not creating them: nothing in the repo
  references them.
- 2026-10-08: The playbook's suggested owner question "AGENTS.md mixes
  ForgeOS rules with an App Builder sandbox contract — should they be
  split?" is FALSE. Verified: zero mentions of "app builder" in AGENTS.md
  (case-insensitive grep). No question written; recording the correction
  here instead.
- 2026-10-08: The playbook's "TEN STOP SIGNS" are not present in the
  provided source, so docs/RENOVATION/HAMI_RULES.md is not created from
  them. The four rules above plus the standing doctrine serve instead.

## Phase 2 notes (2026-10-08)

- Skipped `docs/RENOVATION/HAMI_RULES.md`: the playbook step says to copy
  "the TEN STOP SIGNS from the top of this playbook", but they are not
  present in the provided source. Per safety rule 6 the copy step is
  skipped rather than inventing ten rules. The four AGENTS.md rules above
  serve as the working rules.
- Skipped `archive/` + `git mv opencode.jsonc.bad`: the file does not
  exist in this repo (verified). Nothing to archive; nothing deleted.
- Skipped `git rm --cached logs screenshots`: neither directory exists.
  Skipped `attachments/` handling: directory does not exist.
- Skipped `frontend/LEGACY.md`: `frontend/` does not exist (legacy
  dashboard is `docs/archive/legacy-frontend/` per README).
- `.env.example` created from 52 env names found by code grep; values
  absent (verified by grep). `.nvmrc` = 22, `.python-version` = 3.12.
- `scripts/check_all.sh` runs typecheck → lint → build → backend tests,
  stops at first failure; backend deps fall back to the main checkout's
  `.deps` (identical requirements.txt) when the worktree has none.
- App start test: backend healthy on :8000 (`/docs` 200,
  `/api/health` ok). `start.sh` exited 1 because its ~10s readiness probe
  is shorter than backend startup on this machine; backend became healthy
  right after. Web frontend (:8080) not verified this run. `./stop.sh`
  exits 0 and frees the port.

## Phase 3 notes (2026-10-08)

- Skipped creating `.github/workflows/check.yml`: the existing
  `.github/workflows/forgeos-ci.yml` already runs the identical matrix
  (Node 22: npm ci, test, typecheck, lint, build, smoke; Python 3.12:
  pip install, pytest) on push/PR. A second workflow would be a parallel
  structure doing the same job, forbidden by the continuity law. Verified
  by reading forgeos-ci.yml (not assumed).
- Error-shape step adapted: the playbook wants
  `{"error": {"code", "message", "request_id"}}`, but the repo's live
  contract is `{"detail": ...}`, asserted by existing tests (7 test files).
  Changing the shape would break contracts; changing the tests to match
  would be altering tests to satisfy the playbook. Instead: keep `detail`,
  ADD `request_id` to error responses. Uniformity + traceability without
  breaking the contract.

## Phase 3 notes continued (2026-10-08)

- Ruff `--fix` is NOT fully safe: it removed `ai_engine` from an import in
  `opportunity_engine.py` because the name looked unused, but
  `test_opportunity_quality.py` monkeypatches
  `opportunity_engine.ai_engine`. One test failed; the import was restored
  with a `# noqa: F401` comment explaining why. Lesson: auto-fix output
  must always be followed by the full suite, which is what caught it.
- Error-shape step: kept the established `{"detail": ...}` contract
  (asserted by 7 test files) and added traceability via the `X-Request-ID`
  response header (honored if sent, minted otherwise) plus the request id
  in every access log line. Changing bodies would have broken contracts;
  changing tests to match would have been altering tests for the playbook.
- `settings.py` REQUIRED list is honestly empty: the app starts on its
  SQLite fallback with zero env vars, so nothing is genuinely required.
  The gate mechanism (clear `Missing setting: NAME` line + refuse to
  start, never printing values) is real and tested with a test-only name.
- `/health` keeps its existing `status`/`ready` keys (production health
  check depends on them) and adds the four contract keys
  `ok`/`version`/`time`/`db`.
- PII log masking: CPython logger-level filters do NOT apply to
  propagated records, so the filter attaches at handler level via
  `_install_pii_filter()` at startup. The test unit-tests the filter
  object directly (deterministic).

## Phase 4 notes (2026-10-08)

### Existing labels found (read before touching)
- models.py already has `data_scope` (REAL | SANDBOX) on experiments,
  outcomes, learning events, lessons, products, customer events. That is an
  ENVIRONMENT axis, not an epistemic one — it cannot say TEST vs MOCK vs
  HYPOTHESIS. The playbook's `source_kind` is a different axis; both stay.
- AGENTS.md's bootstrap rule names REAL/TEST/MOCK/HYPOTHESIS but defines
  them nowhere in code; AGENTS.md also already mandates
  OWNER_INTERVENTIONS_PER_REAL_TRANSACTION with NOT MEASURABLE semantics —
  Phase 4 implements exactly that rule.
- The migrations framework (migrations.py) is ADDITIVE ONLY and
  metadata-driven: adding the column to models.py auto-migrates old SQLite
  DBs. ALTER DDL renders `DEFAULT 'MOCK'` from the Python-side default, so
  old rows backfill to MOCK (fail-closed: public numbers count REAL only).
  NOT NULL is enforced on fresh create_all DBs; migrated old DBs get the
  DEFAULT backfill (framework never rewrites constraints). Idempotency is
  proven by test (run twice, second run adds nothing).
- The four-value rule (REAL|TEST|MOCK|HYPOTHESIS) is enforced in
  application code (evidence_source.validate + record_outcome), not via a
  DB CHECK constraint — the additive framework cannot add constraints to
  existing tables, and split enforcement would be worse.

### Scope decision
source_kind added to the four tables public_stats reads or that hold
evidence: Outcome, Experiment, CustomerEvent, Evidence. Signal (raw
observations) deliberately left out — its epistemic label is the existing
source_type/source reliability machinery; expanding there is future work,
not this phase.

### New-file justifications (repo AGENTS.md hard rule)
1. backend/app/evidence_source.py — SEAM INSPECTED: models.py data_scope
   (wrong axis), AGENTS.md bootstrap rule (names only, no code).
   WHY INSUFFICIENT: no module defines the four labels; stuffing them into
   config.py mixes deploy config with epistemics. NEW CAPABILITY: the
   single canonical REAL/TEST/MOCK/HYPOTHESIS definition + validation.
2. backend/app/services/public_stats.py — SEAM INSPECTED: orchestrator.py
   internal rollups, economic_validation.py, revenue miner.
   WHY INSUFFICIENT: none answers "what may we show the public"; the
   existing rollups mix scopes. NEW CAPABILITY: REAL+proof-only public
   aggregates + the NOT MEASURABLE intervention metric.
3. src/lib/sandbox-banner.ts — SEAM INSPECTED: src/components/* (React
   components, not covered by npm test's src/lib glob).
   WHY INSUFFICIENT: no existing banner; a component couldn't be unit
   tested under the repo's node --test setup. NEW CAPABILITY:
   framework-free reusable SANDBOX banner markup with a passing test.

### Enforcement seams (modified in place, per continuity law)
- action_engine.record_outcome: new source_kind param (default MOCK) +
  verification_state param (default REPORTED); REAL without VERIFIED is
  refused with a clear ValueError. Existing callers unchanged (MOCK default).
- approval_outcome_bridge verified-revenue path: labels its outcome REAL —
  that function already demands proof (source + reference + prior human
  outcome), so the label is honest.

### Synthetic DB
- No FORGEOS_SYNTHETIC_DB or synthetic-DB routing exists anywhere in code;
  only FORGEOS_TEST_DATABASE_URL. README's "separate database for synthetic
  source inputs" is aspirational. Per the playbook, the env NAME is now
  reserved in .env.example with a comment saying routing is not wired.
  Downstream SANDBOX labeling is proven through the existing seam:
  record_outcome(data_scope="SANDBOX") → outcome + LearningEvent both stay
  SANDBOX (test).
