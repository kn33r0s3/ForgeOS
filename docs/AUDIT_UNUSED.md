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

- `src/lib/forge/cli.ts` — manual CLI/tooling harness with its own `cli.test.ts`; not imported by the app or invoked by the deployed scheduled worker. Preserve it as tested operator tooling. The autonomous/scheduled v1 round remains PLANNED / NOT WIRED; don't mark the CLI itself as an active autonomous worker.
- `src/lib/unknowns-api.ts` — older `/api/forge/unknowns` Claim projection client, with no current UI caller. Preserve it as a reference, not a second active public Unknowns source: `docs/UNKNOWN_MAP.md` → generated backend JSON/`src/lib/unknowns.ts` remains the current canonical projection path. Any future DB-owned migration needs an explicit source-of-truth decision.
- `src/lib/multiplayer/{index,p2p}.ts` — only self-referenced; P2P/multiplayer has no surface. Prototype or dead?
- `src/lib/app-data/{index,readiness,use-connector-readiness}.ts` — no current Hami page imports this trio. It belongs to the preview-host connector compatibility path, not the public economic-intelligence loop. Preserve while host integrations still reference sibling modules; do not report it as a live Hami customer feature.

## Vulture (Python) — 16 findings, all false positives

`cls` in classmethods (12× in schemas), unused signal-handler args
(`frame`, `signum` in cycle_scheduler.py), unused kwargs (`flush_context`,
`instances` in world_graph.py). No dead Python files or functions found.
No action taken.

## Orphaned routes — 0

`scripts/check-orphaned-routes.mjs` passes: all 38 routes are connected or
intentionally hidden. (The earlier /actions orphan was fixed 2026-10-05.)

## Backend API surface map (checked 2026-10-11)

This is a source-level call-site map, not a live-runtime guarantee. A backend
router without a browser caller may be intentionally scheduled or internal; it
is not automatically dead code.

**Directly connected to current Hami surfaces**
- `/api/public/*` — the public data loaders in `src/lib/content.ts` read the
  canonical feed, domain/work records, providers/service listings, discoveries,
  matches, connections, trust, alerts and UNKNOWN_MAP projection. These reuse
  backend public projections rather than browser-owned fake records.
- `/api/auth/*` — Better Auth route handler under `src/routes/api/auth/$.ts`.
- `/api/forge-bot/*` — owner inquiry/readiness console in `src/routes/owner.tsx`;
  public Forge Bot intake remains hidden/closed.
- `/api/forge/*` — owner runtime/cycle/research/source-clearance projection in
  `src/routes/owner.tsx`; not the standalone TypeScript CLI.
- `/api/orchestrate/overview`, `/api/products`,
  `/api/products/channels`, and `/api/payments/status` — read-only private
  commercial panel in `src/routes/owner.tsx`. Product and channel writes remain
  owner-keyed backend operations; payment visibility is configuration-only.
- `/api/opv4/*` — `src/components/owner/operating-v4.tsx`, rendered inside
  the same owner console with the entered owner key.
- `/api/scout/*` — `src/components/owner/scout-queue.tsx`, owner-keyed
  candidate/draft/DNC/experiment controls; not automatic outreach.
- `/api/residue/*` — `src/components/owner/purchase-journey.tsx`, owner-keyed
  buyer journey and residue records.
- `/api/signals/public-request/config` — `/request` renders the actual
  closed/open gate. A closed result or unavailable gate must not be interpreted
  as a live intake channel.

**Legacy workspace boundary — not a current public Hami journey**
- `/earn/offers` is consumed only by `docs/archive/legacy-frontend/`'s optional archived Next.js dashboard; no active root Vite route imports that client. It stores its own `EarningOffer` working rows and only emits canonical EVENT/OUTCOME records when a status is closed as paid/failed/abandoned. It is not currently a complete public Hami transaction flow, and `workspace_key` is a lightweight client-generated scope token, **not full authentication**. Its read token has been moved from the URL query to `X-Workspace-Key` to reduce URL-log exposure. The active deployed write guard still requires the owner API key for state changes, so the archived client must not be marketed as an operational deployed intake or revenue flow. Preserve the old implementation, but classify it as **legacy / owner decision**, not as a verified live Hami capability.

**Scheduled or internal modules without a direct browser control surface**
- `/api/scheduled/cycle` and `/api/scheduled/intelligence` — declared in
  `vercel.json` as cron endpoints. They should not be triggered merely by
  page navigation; production cadence/run success requires separate evidence.
- `earn`, `intelligence`, `rare-signals`, `lessons`, `observer`,
  `workers`, `substrate`, and `world` — no direct UI call was found in
  this pass for these router modules. Their internal service/worker call paths
  still need endpoint-by-endpoint tracing before classifying any endpoint as
  inactive. Keep them; do not expose broad substrate or worker controls publicly.
- `repair-shop` — no public UI caller; previously identified for an owner
  business decision. A route inventory cannot settle whether the repair-shop
  business is a Hami bet, so it remains unpromoted rather than being wired into
  the public catalogue by assumption.

The prior “13 routers have no frontend caller” grouping was incorrect for the
current code: `orchestrate`, `products`, `payments`, and `signals` do have
direct current consumers, and owner-only components consume `opv4`, `scout`,
and `residue`. No endpoint or historical implementation was removed by this
audit. Lack of a direct browser caller is a finding to trace, not permission to
delete code or turn an internal API into a public page.

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
