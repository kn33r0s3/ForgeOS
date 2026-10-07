# Renovation map (look before you touch — notes only, nothing changed)
Mapped 2026-10-08 against origin/main @ 7008111. SEEN = opened/read, GUESS = inferred.

## Folders

- `.agents/` — SEEN: agent configuration/prompts directory.
- `.grok/` — SEEN: grok skills and reference docs.
- `.vscode/` — SEEN: editor configuration.
- `backend/` — SEEN: FastAPI app (`app/`), tests (`tests/`), `worker.py`, `Dockerfile`.
- `docs/` — SEEN: operating docs (OPERATING_MODEL.md, UNKNOWN_MAP.md, CAPABILITY_QUEUE.md, ...).
- `migrations/` — SEEN: SQL migrations (`0001_auth.sql`, `0002_user_personal_context.sql`, `0003_auth_terms_consent.sql`, `auth/`).
- `public/` — SEEN: static web assets.
- `sanipops_clean/` — SEEN: contains `river-cinder-bamboo-otter-main`, no README; belongs to Hami? UNKNOWN. DO NOT TOUCH.
- `scripts/` — SEEN: node build/test/ops scripts (migrate.mjs, check-orphaned-routes.mjs, ...).
- `server/` — SEEN: `middleware/`, grok identity type defs. Platform part. DO NOT TOUCH.
- `services/` — SEEN: `evidence-triage/` (node service), `forge-bot/`.
- `src/` — SEEN: root Vite web app (`routes/`, `components/`, `lib/`).
- `verification/` — SEEN: deployment verification reports and baselines.
- `storage/` — NOT PRESENT (verified: `ls` fails). Skipped.
- `attachments/` — NOT PRESENT. Skipped.
- `frontend/` — NOT PRESENT. Skipped (legacy dashboard lives at `docs/archive/legacy-frontend/` per README).
- `logs/` — NOT PRESENT. Skipped.
- `screenshots/` — NOT PRESENT. Skipped.

## Deploy

vercel.json in plain words:
- `web` service: Vite framework, root folder `.`, build `npm run build`.
- `api` service: FastAPI, root `backend/`, entrypoint `app.main:app`.
- Crons: `/api/scheduled/cycle` daily `0 0 * * *`; `/api/scheduled/intelligence` daily `0 6 * * *`.
- Rewrites: `/api/auth/*` → web service; `/api/*` → api service; `/*` → web service.

## Frontends

- Hami public site text: "Awaiting a participant" found in `src/routes/index.tsx`; "reality loop" in `src/routes/about.tsx`, `src/routes/index.tsx`; "Honest status" in `src/routes/index.tsx`. → skipped, found.
- ROOT APP ROUTES (from `src/routes/`): `$`, `__root`, `about`, `actions`, `api/*`, `bot-qualification-demo`, `climb`, `contact`, `discoveries`, `domain`, `experiments`, `feed`, `forge-bot-intake`, `group.*`, `index`, `login`, `needs`, `operations`, `opportunities`, `owner`, `privacy`, `process`, `prototype.inbox`, `providers`, `request-a-project`, `request`, `requests.$id`, `services.$slug`, ... (30 files).
- `frontend/` is NOT PRESENT — skipped. Legacy dashboard is `docs/archive/legacy-frontend/` (Next.js, archived per README).
- `server/` — SEEN: middleware + grok identity types. Platform part. DO NOT TOUCH.
- `scripts/` — SEEN: build/test/ops scripts. `scripts/grok-pwa-*` are platform parts. DO NOT TOUCH those.
- Hard-coded local addresses: `src/lib/app-data/client.server.ts` (localhost/127.0.0.1/[::1] dev-host check), `src/lib/auth/server.ts` (allowed hosts incl. localhost:8080), `src/lib/auth/gate-identity.server.ts` (preview gate at 127.0.0.1:6014). All dev/preview scoping, not production endpoints.

## Backend

`backend/`: `Dockerfile`, `app/`, `requirements.txt`, `requirements-optional.txt`, `scripts/`, `tests/`, `worker.py`.

README "Architecture (backend)" 13 layers vs `backend/app/services/`:
1. Observer + Collectors — EXISTS (`collectors/`)
2. Signal quality — EXISTS (`signal_quality.py`, `signal_processor.py`)
3. Pattern engine — EXISTS (`pattern_engine.py`)
4. Belief + Evidence — EXISTS (`belief_engine.py`)
5. Reality checker / memory — EXISTS (`reality_checker.py`, `reality_memory.py`)
6. Opportunity engine — EXISTS (`opportunity_engine.py`, `opportunity_monitor.py`)
7. Economic intelligence — EXISTS (`economic_intelligence.py`, `economic_validation.py`)
8. Decision engine — EXISTS (`decision_engine.py`)
9. Autonomy / policy — EXISTS (`autonomy_engine.py`)
10. Execution engine — EXISTS (`execution_engine.py`)
11. Experiment runners — EXISTS (`experiment_runner.py`, `experiment_service.py`)
12. Learning engine — EXISTS (`learning_engine.py`, `outcome_learning.py`)
13. Forge loop + worker — EXISTS (`forge_loop.py`, `worker.py`)

## Tests

Baselines (2026-10-08, origin/main @ 7008111 + renovation:start), saved in `docs/RENOVATION/`:
- backend `baseline_backend_tests.txt`: PASS (883 passed, 2 skipped, 33 warnings)
- typecheck `baseline_typecheck.txt`: PASS (`tsc --noEmit`, 0 errors)
- build `baseline_build.txt`: PASS (vite built OK)
- lint `baseline_lint.txt`: PASS (0 errors; 1 pre-existing react-refresh warning in `src/components/experiments/experiment-card.tsx`)

## Dirty files

- `.DS_Store`: none found (repo-wide find excluding node_modules/.git).
- `logs/`, `screenshots/`, `attachments/`: not present — skipped.
- `opencode.jsonc.bad`, `.node_modules.lock`: not present — skipped.
- Big files (>1M, excl. node_modules/.git/.vercel): `./docs/design/hami-home.png` only.

## Secret risk

File NAMES only (grep for API_KEY|SECRET|PASSWORD|TOKEN|postgres://|BEGIN PRIVATE KEY). No values copied anywhere:
`.github/workflows/forgeos-ci.yml`, `.github/workflows/verify-deploy.yml`,
`.grok/references/data-and-auth.md`, `.grok/skills/auth/*` (4 files),
`.grok/skills/og/references/custom-card.md`, `.grok/skills/xai-api/SKILL.md`,
`HANDOFF.md`, `backend/app/api/forge_bot.py`,
`backend/app/api/forge_bot_owner_notification.py`,
`backend/app/api/scheduled.py`, `backend/app/config.py`, `backend/app/main.py`.
All expected: workflows reference secret *names*, config reads env *names*.
No secret values appear in any note I made.

## Missing docs

- `docs/OPERATOR_GUIDE.md` — EXISTS
- `docs/FINAL_ARCHITECTURE.md` — MISSING
- `docs/FUTURE_BLUEPRINT.md` — MISSING (note: `docs/archive/legacy-docs/FUTURE_BLUEPRINT.md` exists per README)
- `STATUS.md` — EXISTS
- `COMPLETION_REPORT.md` — MISSING (note: `docs/archive/legacy-docs/COMPLETION_REPORT.md` exists per README)

## Cron job

`/api/scheduled/cycle` → `run_scheduled_cycle` in `backend/app/api/scheduled.py`:
- What it does: HMAC Bearer `CRON_SECRET` auth, then `run_daily_maintenance` (privacy maintenance); the legacy intelligence cycle runs only if `FORGEOS_LEGACY_INTELLIGENCE_ENABLED` (default off).
- Can it contact any person? No — privacy maintenance only, no messaging paths.
- Can it spend money? No — no spending paths.
- Note: second cron `/api/scheduled/intelligence` (`0 6 * * *`) also declared in vercel.json.

## Env names

Names only (from `os.environ`/`os.getenv`/`process.env`/`import.meta.env` across backend/src/server/services):
AI_FALLBACK_TO_MOCK, AI_PROVIDER, COGNITIVE_PROVIDER, COMMIT_SHA, CRON_SECRET,
DATABASE_URL, EMBEDDING_PROVIDER, ESEWA_FORM_URL, ESEWA_MERCHANT_CODE,
ESEWA_SECRET_KEY, ESEWA_STATUS_URL, FORGEOS_CLAIM_LINK_LIMIT,
FORGEOS_COLLECT_LIMIT, FORGEOS_EVIDENCE_FRESH_DAYS, FORGEOS_LIVE_GDELT_TEST,
FORGEOS_LIVE_OPENALEX_TEST, FORGEOS_RESUME_LIMIT,
FORGEOS_SUBSTRATE_EVIDENCE_BATCH, FORGEOS_SUBSTRATE_LINK_BATCH,
FORGEOS_TEST_DATABASE_URL, FORGE_API_KEY, FORGE_BOT_CONTACT_HMAC_KEY,
FORGE_BOT_LIVE, GITHUB_TOKEN, GIT_COMMIT_SHA, GROK_CONNECTORS_URL,
GROK_CONNECTOR_ACCESS_TOKEN, GROK_GATE_ORIGIN, GROK_PROJECT_ID, HOST, ...

## Questions

- Top 3 blockers from `docs/CAPABILITY_QUEUE.md`: (1) Owner readiness/maintenance heartbeat — BLOCKED/unverified, needs owner key. (2) Production database inspection — BLOCKED, no authorized credential procedure. (3) Customer-facing response — BLOCKED, no sender/channel configured; send flag defaults false.
- `sanipops_clean/` purpose: UNKNOWN (no README; single nested dir). Left untouched.
- `services/evidence-triage` (`forgeos-evidence-triage`, node, has Dockerfile): what deploys it — UNKNOWN.
- Skipped per safety rules (targets verifiably absent): `attachments/`, `frontend/`, `logs/`, `screenshots/`, `opencode.jsonc.bad`, `.node_modules.lock`, playbook `renovation` branch (direct-to-main stands), AGENTS.md-split owner question (premise false), TEN STOP SIGNS copy (not in source).
