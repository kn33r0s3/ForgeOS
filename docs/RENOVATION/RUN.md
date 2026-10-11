# RUN — portable commands and dated observations (updated 2026-10-11)

## Start / stop the app

```bash
# Fresh checkout: start.sh installs into this checkout's backend/.deps when needed.
# Do not copy absolute dependency paths from historical machine-specific logs.
./start.sh
./stop.sh
```

Historical observation from 2026-10-08 (not a current runtime verification):
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

Runs in order and stops at first failure: `npm run typecheck`, lint, build,
then the backend pytest suite. It uses this checkout's local `.venv`/`venv`
or `python3` and conditionally adds this checkout's `backend/.deps`; it no longer
depends on another developer's absolute filesystem path.

## Backend tests only

```bash
cd backend
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH="$PWD/.deps:$PWD" python3 -m pytest tests/ -q
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
