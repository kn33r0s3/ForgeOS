# RUN — exact commands that were really run (2026-10-08)

## Start / stop the app

```bash
# Fresh checkout: backend/.deps does not exist; reuse the main checkout's
# installed deps (identical requirements.txt) or let start.sh pip-install.
FORGEOS_DEPS_DIR=/home/hatch/workspace/repos/ForgeOS/backend/.deps ./start.sh
./stop.sh
```

Observed 2026-10-08:
- Backend serves on :8000. `curl http://localhost:8000/docs` → 200.
  `curl http://localhost:8000/api/health` → `{"status":"ok","ready":true}`.
  `/health` also returns 200 once the server is up.
- `start.sh` exited 1 on this machine: its built-in readiness probe polls
  only ~10s and the backend needed longer (migrations + startup). The
  backend became healthy shortly after. The web frontend (:8080) was not
  verified this run because start.sh stopped before launching it.
- `./stop.sh` exits 0; port 8000 refuses connections afterwards.
- Pre-existing startup warning (informational): SQLAlchemy
  "Cannot correctly sort tables ... unresolvable cycles" between
  actions/claims/decisions/experiments/learning_events/options/outcomes/
  rare_signal_assessments/research_questions (mutually dependent FKs).

## Run all checks

```bash
sh scripts/check_all.sh
```

Runs in order, stops at first failure: `npm run typecheck`,
`npm run lint` (if the script exists), `npm run build`, then the backend
pytest suite (uses `backend/.deps` if present, else the main checkout's).

## Backend tests only

```bash
cd backend
PYTHONPATH=/home/hatch/workspace/repos/ForgeOS/backend/.deps:$PWD python3 -m pytest tests/ -q
```

## Web build only

```bash
npm run build
```

## Typecheck / lint only

```bash
npm run typecheck
npm run lint
```
