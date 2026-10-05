# DEAD-WORK AUDIT — 2026-10-05

> Read-only report. Nothing was deleted. Knip (TS/JS) + vulture (Python) +
> route-link check + endpoint cross-reference + 30-day restore check.
> Classification: KEEP / ARCHIVE / NEEDS OWNER DECISION.

## Counts

- Knip unused files flagged: **62**
- Knip false positives (verified referenced): **~40** (docs/archive already archived, QA toolchain scripts referenced by tests, service files knip doesn't trace)
- Genuine orphans needing a decision: **8**
- Vulture unused variables: **16** (all false positives — `cls` in classmethods, unused signal args)
- Orphaned routes (no inbound link): **0** — checker passes
- Backend routers never called from frontend `src/`: **13 of 18**
- Files deleted in last 30 days: **12 source files** (intentional migration) + pycache

## Knip-flagged files — verified classification

### KEEP (verified referenced or intentional)

- `scripts/browser-guard.mjs`, `scripts/browser-smoke.mjs`, `scripts/preview-thumbnail.mjs` — referenced by `browser-smoke-verdict.test.mjs`, `brand-check.mjs`, `check-auth-invariant.mjs`, `preview.mjs`. QA toolchain.
- `server/middleware/grok-pwa.ts` — referenced in `vite.config.ts`.
- `src/lib/auth/popup.server.ts` — referenced in `auth/client.ts`, `vite.config.ts`.
- `src/components/pages/project-form.tsx` — referenced in `content.test.ts`.
- `src/components/ui/textarea.tsx` — unused UI kit component; standard to keep.
- `src/lib/app-data/*` — partially referenced (`client.server.ts`, `server-only.ts`, `preview-host-bridge.ts`).
- `services/evidence-triage/*` — separate service with own package; knip doesn't trace it.
- `docs/archive/legacy-frontend/*` (35 files) — already archived; keep as history.
- `scripts/qa-system.mjs` — no inbound refs found, but touched 2026-10-04 (active). KEEP pending confirmation.

### ARCHIVE (safe to move to docs/archive; nothing imports them)

- `scripts/sync-unknowns-json.mjs` — added 2026-10-04 (0dc9c7c), never referenced.
- `sanipops_clean/river-cinder-bamboo-otter-main/scripts/*` (2 files) — vendored snapshot, untouched since 2026-09-24.
- `public/__grok/install/styles.css` — install artifact, untouched since 2026-10-01.
- `scripts/grok-pwa-shared.d.mts` — type shim, superseded.

### NEEDS OWNER DECISION

- `src/lib/forge/cli.ts` — added 2026-10-04 (b599c90), no inbound references. Purpose unclear.
- `src/lib/unknowns-api.ts` — added 2026-10-04 (5c1dad8), no inbound references. May be superseded by features work.
- `src/lib/multiplayer/{index,p2p}.ts` — only self-referenced; P2P/multiplayer has no surface. Prototype or dead?
- `src/lib/app-data/{index,readiness,use-connector-readiness}.ts` — unreferenced trio; siblings are used.

## Vulture (Python) — 16 findings, all false positives

`cls` in classmethods (12× in schemas), unused signal-handler args
(`frame`, `signum` in cycle_scheduler.py), unused kwargs (`flush_context`,
`instances` in world_graph.py). No dead Python files or functions found.
No action taken.

## Orphaned routes — 0

`scripts/check-orphaned-routes.mjs` passes: all 38 routes are connected or
intentionally hidden. (The earlier /actions orphan was fixed 2026-10-05.)

## Backend endpoints never called from frontend

Frontend `src/` calls: `/api/auth`, `/api/forge-bot/*`, `/api/forge/*`
(subset), `/api/health`, `/api/rtc`, `/api/signals/public-request/config`.
Routers with no frontend callers: earn, intelligence, rare-signals, lessons,
observer, orchestrate, payments, products, repair-shop, scheduled, signals,
substrate, workers, world (13). These serve scheduled jobs, the owner
console backend, or future surfaces — **NEEDS OWNER DECISION** before any
removal. None removed by this audit.

## Restore check — last 30 days

Anything that existed and no longer appears:

- `d3420b2` (2026-10-01): deleted `src/App.tsx`, `src/main.tsx`, `src/types.ts`,
  `src/lib/forgeApi.ts`, `src/lib/forgeApi.test.ts`, and 7 tab components
  (`ApiExplorerTab`, `BeliefsTab`, `DecisionsTab`, `Navbar`, `OpportunitiesTab`,
  `OverviewTab`, `SignalsTab`, `WorkersTab`). **Intentional:** old pre-router
  SPA structure replaced by the TanStack Router structure. Nothing lost —
  the route files cover the same surfaces.
- `f99008d` (2026-09-30): deleted `backend/app/__pycache__/*.pyc`. Build
  artifacts. Intentional.

No feature present in features.json has disappeared. No "why did that
disappear" mysteries remain.
