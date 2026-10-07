# RENOVATION — FINAL REPORT

Strict separation is used throughout: **FACT** (verified by tool output),
**OBSERVATION** (seen during the work, not independently re-verified),
**HYPOTHESIS** (inference, marked as such), **RECOMMENDATION** (suggested
action, not taken).

---

## 1. Start and end state

**FACT:**
- Starting point: `origin/main` at `7008111` ("Doctrine: EARNING is the gate
  to consequential real-world action"), detached HEAD in a fresh worktree
  `~/workspace/repos/ForgeOS-renovation`. Tag `pre-renovation` created at
  the start commit.
- No `renovation` branch was ever created (owner's explicit direct-to-main
  rule, reconfirmed in the spec update).
- Final commit: `4849188` ("renovation: final verification", amended with
  this report's final gate numbers), pushed to `origin/main`. Full chain:
  `7008111` → `30b1830` (phase 0) → `e2bcda6` (phase 1) →
  `8962b23` (phase 2) → `cdd774b` (phase 3) → `7b19a0d` (phase 4) →
  `4849188` (final verification).
- The main checkout at `~/workspace/repos/ForgeOS` (local main `9933559`,
  divergent with unpushed development work) was never committed to or
  pushed from. Verified before every push via `git rev-parse
  --show-toplevel`.
- Files changed across the 5 commits: 77 (16 docs/RENOVATION notebooks,
  5 config/meta, 4 new backend modules, 2 new test files, 2 new frontend
  lib files, 2 new scripts, 1 new CI workflow, remainder modified in
  place).

## 2. Architecture findings

**FACT:**
- The canonical substrate is EXACTLY six primitives; no seventh was added.
  No new database tables were created. Exactly one model class exists for
  each of Evidence, Action, Outcome, Customer, ForgeCapability, WorldEvent
  (verified by grep over `backend/app/models.py`). No Bet table exists —
  bets remain projections through the existing entity seam.
- Two label axes coexist and are NOT competing sources of truth:
  `data_scope` (REAL | SANDBOX — environment axis, pre-existing) and the
  new `source_kind` (REAL | TEST | MOCK | HYPOTHESIS — epistemic axis,
  `backend/app/evidence_source.py`). A row can be `data_scope=REAL` +
  `source_kind=MOCK` (real environment, pretend data). Documented in
  `docs/RENOVATION/DECISIONS.md`.
- No duplicate truth/proof system was introduced: `public_stats.py`
  aggregates (no models), `evidence_source.py` defines labels (no models).
  The four-value rule is enforced in application code
  (`evidence_source.validate` + `action_engine.record_outcome`), NOT via
  DB CHECK constraints — the repo's additive-only migration framework
  cannot add constraints to existing tables, and split enforcement would
  be worse. Documented.
- New files and their justifications (repo AGENTS.md hard rule):
  - `backend/app/evidence_source.py` — no existing module defined the
    four labels (AGENTS.md named them, `data_scope` is a different axis).
  - `backend/app/services/public_stats.py` — no existing seam computed
    public-safe aggregates (orchestrator rollups are internal and mix
    scopes).
  - `backend/app/settings.py` — startup REQUIRED gate; config.py holds
    values, this holds the refuse-to-start mechanism.
  - `src/lib/sandbox-banner.ts` — no existing banner; framework-free so it
    is unit-testable under the repo's `node --test` setup.

**OBSERVATION:**
- The codebase was already heavily instrumented for honesty before this
  work: `data_scope` on 8+ tables, ACTUAL vs ESTIMATED column comments,
  verification_state on Outcome, the AGENTS.md bootstrap rule. The
  renovation added the missing epistemic axis, not the concept.

**HYPOTHESIS:**
- The `source_kind` default of MOCK (fail-closed) may cause genuinely real
  outcomes written through legacy direct-`Outcome(...)` call sites to be
  labeled MOCK until those call sites are updated. This is the intended
  conservative direction, but a future audit of direct Outcome
  constructions could promote the verified ones.

## 3. Baseline vs final test results

**FACT:**
- Baseline (Phase 1, commit `e2bcda6`, backend suite):
  **883 passed, 2 skipped**.
- Final gate (`scripts/check_all.sh` = `npm test` → `npm run typecheck` →
  `npm run lint` → `npm run build` → backend pytest, run 2026-10-08
  ~03:10 NPT on the exact final tree):
  **npm test ✓, typecheck ✓, lint ✓, build ✓, backend 899 passed,
  2 skipped — ALL CHECKS PASSED.**
- Delta: +16 new tests (6 safety-net + 10 truth-labels); the one
  accidentally deleted test was restored (see §4), so the arithmetic is
  exact: 883 + 16 = 899.

**OBSERVATION:**
- The full backend suite takes ~6 minutes; the frontend checks take ~2.

## 4. Failures (all resolved)

**FACT:**
1. `ruff --fix` removed `ai_engine` from an import in
   `opportunity_engine.py` that `test_opportunity_quality.py`
   monkeypatches → 1 failure. Fixed by restoring the import with
   `# noqa: F401` + explanatory comment. Lesson recorded: auto-fix output
   must always be followed by the full suite.
2. My `/health` change broke 6 exact-equality assertions (4 in
   `test_health_readiness.py`, 1 in `test_api_ingress_alias.py`, 1 in
   `test_vercel_config_contract.py`). Updated to the playbook-mandated
   new shape per the playbook's own "rewrite them" pattern.
3. **Self-caught during this final verification:** an edit to
   `test_health_readiness.py` accidentally deleted the
   `def test_health_details_requires_owner_key_and_preserves_diagnostics`
   line, merging its body into the previous test (suite stayed green,
   count dropped by 1). Found by diffing test-function counts
   baseline-vs-final. Restored; file re-verified (7 passed, ruff clean).
   This is exactly the class of silent damage the spec's final review
   exists to catch.

**HYPOTHESIS:**
- No other silent test deletions exist: the per-file function-count diff
  across all of `backend/tests/` shows no other delta.

## 5. Security findings

**FACT:**
- Secret scan (Phase 1): file NAMES only, never values. No secret values
  were copied into any note. One `.env`-shaped filename pattern was noted
  by name; nothing to redact.
- `.env.example`: 52+ names, zero values (verified).
- New `.github/workflows/secrets.yml` runs gitleaks on push/PR; the file
  contains no values or allowlists.
- PII: log mask for Nepali mobiles/emails added and tested; no PII was
  found in logs during the work.
- Auth: unchanged. No auth code was modified; `/health/details` still
  requires the owner key (test restored in §4.3).
- No new network calls, no credentials added, no money moved, no person
  contacted.

## 6. Deployment findings

**FACT:**
- `vercel.json` untouched. No deployment config changed.
- Production verified by FETCHED ARTIFACT (never from a local build):
  `curl -s https://haminp.vercel.app/api/health` returned
  `{"status":"ok","ready":true,"ok":true,"version":"2.3.0","time":"2026-10-07T20:55:00.135208+00:00","db":"up"}`
  plus an `X-Request-Id` response header. The `ok`/`version`/`time`/`db`
  keys and the header exist ONLY in the pushed commits — the live deploy
  is running the new code.
- Deployed-SHA confirmation: the only endpoint exposing
  `VERCEL_GIT_COMMIT_SHA` (`/forge-bot/owner/readiness`) is owner-key
  gated; the SHA could not be independently confirmed from public
  endpoints. The artifact evidence above is the basis for the deploy
  claim.
- `scripts/smoke_prod.sh` (read-only: `/api/health`, `/`, `/experiments`
  must answer 200) exits 0 against the local app; not run against
  production (no write risk either way — it is curl-only).

## 7. Public-surface findings

**FACT:**
- Homepage and all public routes/components untouched (no `src/routes/`
  or `src/components/` files in the diff).
- Public identity was NOT reduced to an inbox tool, chatbot, lead
  generator, or SaaS dashboard: no public copy changed; the new
  `sandbox-banner` is an unmounted lib module (reusable piece + test),
  not wired into any page.
- `public_stats()` has NO API route — it is a service function only. No
  new public numbers are exposed anywhere.
- ESTIMATED≠ACTUAL, REQUESTED≠BOOKED, TEST≠REAL, MOCK≠REAL,
  HYPOTHESIS≠EVIDENCE: `public_stats()` counts only
  `source_kind=REAL` + `verification_state=VERIFIED` rows; the 15/15
  non-REAL fixture test asserts zeros; the banner labels pretend data.
  No public surface mixes them.

**OBSERVATION:**
- The repo's standing state is zero verified real outcomes (consistent
  with MEMORY.md: real-world verification "fails honestly while zero
  real outcomes exist"). This work created zero production records of
  any kind.

## 8. Evidence/truth findings

**FACT:**
- Migration (`source_kind` on outcomes/experiments/customer_events/
  evidence): purely additive, driven by the repo's metadata-based
  framework; old rows backfill to `MOCK` via `DEFAULT 'MOCK'` DDL;
  idempotency proven by test (run twice, second run adds nothing). No
  tables/columns dropped, no data deleted or rewritten — nothing in
  Phase 4 met any STOP condition.
- `record_outcome` refuses `source_kind=REAL` without
  `verification_state=VERIFIED` (clear ValueError, tested); the
  verified-revenue bridge labels REAL only where it already demands
  proof (source + reference + prior human outcome).
- `owner_interventions_per_real_transaction()` returns the string
  `"NOT MEASURABLE"` (never `0`) with zero real transactions — the
  repo's own AGENTS.md rule, now implemented and tested.
- Synthetic separation: no `FORGEOS_SYNTHETIC_DB` routing exists in
  code (only the name, now reserved in `.env.example`); README's
  "separate database for synthetic inputs" is aspirational. Downstream
  SANDBOX labeling proven through the existing seam
  (`record_outcome(data_scope="SANDBOX")` → outcome + LearningEvent
  stay SANDBOX, tested).
- Zero fabricated customers/revenue/outcomes: all fixtures live in
  isolated in-memory test DBs, labeled TEST/MOCK/HYPOTHESIS.

## 9. Questions requiring owner decision

**FACT:** `docs/RENOVATION/OWNER_QUESTIONS.md` contains one entry
(pre-existing, Phase 0: the playbook's referenced txt files were never
provided). No new owner questions arose. Per the spec update, the
"AGENTS.md mixes in an App Builder contract" premise is VERIFIED FALSE
(zero mentions) — recorded as "no issue found" in DECISIONS.md, NOT
written as an owner question.

## 10. Changes intentionally NOT made

**FACT:**
- `git checkout -b renovation` — direct-to-main rule.
- `.github/workflows/check.yml` — `forgeos-ci.yml` already runs the
  identical matrix.
- Error-response body reshape to `{"error":{...}}` — kept the
  established `{"detail"}` contract (asserted by 7 test files);
  traceability via `X-Request-ID` header instead.
- `source_kind` on the `signals` table — its epistemic labeling is the
  existing source_type/reliability machinery; out of scope, noted as
  future work.
- DB CHECK constraint for the four labels — framework cannot add
  constraints to existing tables; application-level enforcement instead.
- Wiring the SANDBOX banner into private console pages — needs a
  browser session; reusable piece + test delivered for that follow-up.
- Any `storage/`, `attachments/`, `frontend/`, `logs/`, `screenshots/`
  creation — verified absent, left absent.

## 11. Recommended next actions

**RECOMMENDATION:**
1. Audit direct `models.Outcome(...)` call sites (5 known:
   `action_engine`, `approval_outcome_bridge`, `outcome_learning`,
   `repair_shop` ×2) and set explicit `source_kind` where the data is
   genuinely real — they currently default to MOCK (safe, but possibly
   under-labeling).
2. Wire `sandboxBannerHtml()` into the private console pages that render
   SANDBOX-scoped data (needs a browser pass).
3. Decide whether `FORGEOS_SYNTHETIC_DB` should become real routing or
   stay a reserved name; either way the SANDBOX-entry seam must remain
   mandatory.
4. Consider promoting `public_stats()` to a public route (e.g.
   `/api/public/stats`) ONLY when the first real verified outcome
   exists — until then it honestly returns zeros.
5. Keep `scripts/check_all.sh` as the pre-push gate; consider adding
   the ruff check to it now that `backend/ruff.toml` exists.

---

*Report generated 2026-10-08 from worktree `~/workspace/repos/ForgeOS-renovation`
at commit `7b19a0d`, verified against `origin/main`. Standing files
(MEMORY.md etc.) were not modified by this work.*
