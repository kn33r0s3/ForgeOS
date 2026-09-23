#!/usr/bin/env bash
# ForgeOS — one-command Docker or constrained native startup.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FORGEOS_ENABLE_WORKER="${FORGEOS_ENABLE_WORKER:-false}"
FORGEOS_DEPS_DIR="${FORGEOS_DEPS_DIR:-$PWD/backend/.deps}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$PWD/storage/forge.db}"
export PYTHONPATH="$FORGEOS_DEPS_DIR:$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$FORGEOS_DEPS_DIR/bin:$PATH"

mkdir -p storage logs
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; echo "✓ Created backend/.env"; fi
if [ ! -f frontend/.env.local ]; then cp frontend/.env.local.example frontend/.env.local; echo "✓ Created frontend/.env.local"; fi

echo "[database] canonical native SQLite URL: $DATABASE_URL"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Docker detected — canonical container DB: /app/storage/forge.db -> $PWD/storage/forge.db"
  if [ "$FORGEOS_ENABLE_WORKER" = "true" ]; then exec docker compose --profile worker up --build; fi
  exec docker compose up --build
fi

command -v python3 >/dev/null || { echo "❌ Need python3"; exit 1; }
command -v bun >/dev/null || { echo "❌ Need Bun 1.3+"; exit 1; }

if [ ! -d "$FORGEOS_DEPS_DIR/sqlalchemy" ]; then
  echo "Installing backend dependencies into $FORGEOS_DEPS_DIR ..."
  rm -rf "$FORGEOS_DEPS_DIR"
  python3 -m pip install --target "$FORGEOS_DEPS_DIR" -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "Installing locked frontend dependencies with Bun..."
  (cd frontend && bun install --frozen-lockfile)
fi

echo "Starting backend on :8000 ..."
(cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000) > logs/backend.log 2>&1 &
echo $! > logs/backend.pid
sleep 2
if ! kill -0 "$(cat logs/backend.pid)" 2>/dev/null; then
  echo "❌ Backend failed to start:"; cat logs/backend.log; exit 1
fi

if [ "$FORGEOS_ENABLE_WORKER" = "true" ]; then
  echo "Starting worker (explicitly enabled)..."
  (cd backend && python3 worker.py 1800) > logs/worker.log 2>&1 &
  echo $! > logs/worker.pid
else
  echo "Worker disabled for safe application startup."
  rm -f logs/worker.pid
fi

echo "Building frontend for production..."
(cd frontend && bun run build) > logs/frontend-build.log 2>&1
echo "Starting production frontend on :3000 ..."
(cd frontend && bun run start --hostname 127.0.0.1 --port 3000) > logs/frontend.log 2>&1 &
echo $! > logs/frontend.pid

echo "✓ ForgeOS is up — frontend http://localhost:3000, API http://localhost:8000/docs"
trap './stop.sh' INT TERM
wait
