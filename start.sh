#!/usr/bin/env bash
# ForgeOS — one-command Docker or constrained native startup.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FORGEOS_ENABLE_WORKER="${FORGEOS_ENABLE_WORKER:-false}"
FORGEOS_ENABLE_SCHEDULER="${FORGEOS_ENABLE_SCHEDULER:-true}"
FORGEOS_USE_DOCKER="${FORGEOS_USE_DOCKER:-false}"
FORGEOS_DEPS_DIR="${FORGEOS_DEPS_DIR:-$PWD/backend/.deps}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$PWD/storage/forge.db}"
export PYTHONPATH="$FORGEOS_DEPS_DIR:$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$FORGEOS_DEPS_DIR/bin:$PATH"

mkdir -p storage logs
if [ ! -f backend/.env ]; then
  if [ -f backend/.env.example ]; then cp backend/.env.example backend/.env; echo "✓ Created backend/.env"; else echo "⚠ backend/.env.example not found — create backend/.env manually if the backend needs env vars"; fi
fi
if [ ! -f docs/archive/legacy-frontend/.env.local ]; then
  if [ -f docs/archive/legacy-frontend/.env.local.example ]; then cp docs/archive/legacy-frontend/.env.local.example docs/archive/legacy-frontend/.env.local; echo "✓ Created legacy frontend environment"; else echo "⚠ legacy-frontend .env.local.example not found — skipping"; fi
fi

echo "[database] canonical native SQLite URL: $DATABASE_URL"

if [ "$FORGEOS_USE_DOCKER" = "true" ] && command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Docker detected — canonical container DB: /app/storage/forge.db -> $PWD/storage/forge.db"
  if [ "$FORGEOS_ENABLE_SCHEDULER" = "true" ] || [ "$FORGEOS_ENABLE_WORKER" = "true" ]; then
    exec docker compose --profile worker up --build
  fi
  exec docker compose up --build
fi

command -v npm >/dev/null || { echo "❌ Need npm"; exit 1; }

PY="python3"
if [ -x backend/venv/bin/python ]; then
  PY="$PWD/backend/venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PY="$(command -v python3.11)"
elif command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
fi

if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "❌ ForgeOS requires Python 3.9+ for the backend and scheduler (found: $("$PY" --version 2>&1))"
  exit 1
fi

if [ ! -d "$FORGEOS_DEPS_DIR/sqlalchemy" ]; then
  echo "Installing backend dependencies into $FORGEOS_DEPS_DIR ..."
  rm -rf "$FORGEOS_DEPS_DIR"
  "$PY" -m pip install --target "$FORGEOS_DEPS_DIR" -r backend/requirements.txt
fi
echo "Starting backend on :8000 ..."
(cd backend && exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) > logs/backend.log 2>&1 &
echo $! > logs/backend.pid
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "❌ Backend failed health check:"; cat logs/backend.log; exit 1
fi

if [ "$FORGEOS_ENABLE_SCHEDULER" = "true" ]; then
  echo "Starting canonical cycle scheduler..."
  (cd backend && exec "$PY" -m scripts.scheduler --every 1800 --backup-every 21600 --backup-keep 10) > logs/scheduler.log 2>&1 &
  echo $! > logs/scheduler.pid
else
  echo "Cycle scheduler disabled."
  rm -f logs/scheduler.pid
fi

if [ "$FORGEOS_ENABLE_WORKER" = "true" ]; then
  echo "Starting task worker (explicitly enabled)..."
  (cd backend && exec "$PY" worker.py 1800) > logs/worker.log 2>&1 &
  echo $! > logs/worker.pid
else
  rm -f logs/worker.pid
fi

echo "Starting public root app on :8080 ..."
(exec npm run dev) > logs/public-app.log 2>&1 &
echo $! > logs/public-app.pid

echo "✓ ForgeOS is up — public app http://localhost:8080, API http://localhost:8000/docs"
trap './stop.sh' INT TERM
wait
