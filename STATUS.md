# ForgeOS Current Status

> Historical snapshot updated September 14, 2026. Current work order and gates
> are maintained in [`docs/SERIAL_PATH.md`](docs/SERIAL_PATH.md) and
> [`docs/CURRENT_FOCUS.md`](docs/CURRENT_FOCUS.md); do not infer current
> production state from this older environment report.

**Updated:** September 14, 2026  
**Release posture:** Container-hardened and local-pilot-ready. No real-person pilot or real revenue has been claimed.

## Environment baseline

- Backend container installs pinned dependencies with `pip install --target /app/backend/.deps`; no venv or global Python mutation.
- Frontend container uses Bun 1.3.11, `bun install --frozen-lockfile`, a verified Next.js production build, and the production server.
- Canonical host database: absolute `<ForgeOS>/storage/forge.db`. Backend and worker containers see that same bind-mounted file as `/app/storage/forge.db`. Relative SQLite URLs fail closed.
- Docker Compose includes an isolated `backend-tests` verification service using an in-memory database.
- Docker/Podman was not installed in the verification sandbox, so images were syntax/config audited but could not be booted here.

## Verified current truth

- SQLite: integrity `ok`, journal mode `wal`, busy timeout `30000 ms`, foreign keys enabled.
- Requested WAL stress test: **3/3 Forge cycles and 3/3 autonomy cycles passed** on September 14, 2026 (cycle IDs 306–308); no disk I/O or prepared-session error.
- Final backend suite: **143 passed**, 6 deprecation warnings.
- Frontend production build: **passed**, 14 static pages generated.
- Direct rollback regression proves a failed Forge stage is rolled back before autonomy executes.

## Product and integrity controls

- Offer state machine: `draft → customer_confirmed → paid / failed / abandoned`; invalid transitions return conflict.
- Each offer persists a per-offer next-action checklist with offline synchronization.
- Terminal offer status requires an honest outcome note.
- Historical P0/readiness reports are archived under `docs/archive/status-reports/`; this file is the single current status record.
- Scheduler backups retain 10 compressed snapshots and automatically keep only the two newest legacy `forgeos_pre_*.db` files on the main storage volume, archiving older copies.
- eSewa and Khalti adapters remain fail-closed without credentials. Fonepay is not implemented without an authoritative integration pack.

## External-only gate

Phase 3 cannot be honestly executed in a code sandbox. A human must choose one real person aged 14+, contact one real customer, deliver or receive a clear refusal, and record the actual result—even if it is no sale. Production Nepal payment credentials stay locked until that genuine outcome exists.

## 2026-09-15 session (Claude)

- Verified (not just re-read) the prior session's claims: backend syntax-compiles clean end to end; `verification/final-cycle-verification.txt` and `database-path-audit.txt` genuinely show the WAL fix and path consolidation holding (3/3 cycles, no I/O error, single absolute path everywhere).
- Refactored `frontend/app/earn/page.tsx` (528 lines, everything in one component) into an orchestrator (241 lines) plus `components/earn/{SafetyBanner,PathwayPicker,OfferForm,OfferList}.tsx` and `lib/earn/{pathways,types}.ts`. Logic (offline sync queue, status-transition rules, age gating) was moved verbatim, not rewritten — behavior should be identical. **Not yet rebuilt/tested in a real Next.js environment** — no network/node in this sandbox. Run `pnpm build` and click through the Earn page before trusting this refactor.
- Reviewed `lib/api.ts` (1066 lines) against the "no monolithic files" rule: it's one file but cleanly sectioned by domain with no logic mixed in — judged as legitimately-long centralized API/type definitions, not a monolith, and left alone.
- Confirmed ForgeOS's existing dark internal-dashboard palette (`--forge-bg:#08090b`, `border-white/9`-equivalent) already satisfies a "dark, high-contrast-border" standard on its own terms — did not force Sanip Operations' orange/KneeRose brand palette onto ForgeOS, since they're intentionally separate products.
- Declined to load an external "claude-red" skill referenced this session — it's a published offensive-security/exploit-technique library, unrelated to and inappropriate for this codebase's actual engineering work.

### Still open
- Rebuild and manually click-test the refactored Earn page (`pnpm install && pnpm build && pnpm dev`, then `/earn`) — first real verification since the split.
- Everything under "External-only gate" above — still nobody has run one real pilot with one real person.


## Evidence

See `verification/final-deployment-backend-tests.txt`, `verification/final-deployment-frontend-build.txt`, `verification/container-protocol-cycle-stress.txt`, `docs/CONTAINER_BUILD_PROTOCOL.md`, and `COMPLETION_REPORT.md`.
