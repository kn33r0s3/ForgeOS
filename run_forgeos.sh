#!/usr/bin/env bash
set -e

# ------------------------------------------------------------
# One-click setup & live-reload for SanipOps & ForgeOS Engine
# ------------------------------------------------------------
# Usage:   cd ~/Downloads/ForgeOS && ./run_forgeos.sh
# ------------------------------------------------------------

log() { echo "[ForgeOS] $*"; }

# 1. Ensure pm2 is installed globally
if ! command -v pm2 >/dev/null 2>&1; then
  log "pm2 not found -- installing globally..."
  npm install -g pm2
fi

# Change to project root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
log "Working directory: $ROOT_DIR"

# 2. Install node modules if missing
if [ ! -d node_modules ]; then
  log "Installing Node project dependencies..."
  npm ci
else
  log "Node dependencies already installed."
fi

# 3. Setup Python Virtual Environment for FastAPI Backend
if [ ! -d backend/venv ]; then
  log "Creating Python virtualenv for ForgeOS Engine..."
  PYTHON_EXE="/opt/homebrew/bin/python3.11"
  if ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
    PYTHON_EXE="python3"
  fi
  "$PYTHON_EXE" -m venv backend/venv
  backend/venv/bin/pip install -r backend/requirements.txt
else
  log "Python virtualenv already ready."
fi

# 4. Write environment variables
cat > .env.local <<EOF
VITE_OLLAMA_BASE_URL=http://localhost:11434
VITE_AI_MODEL=gpt-oss:20b
DATABASE_URL=sqlite:///$ROOT_DIR/storage/forge.db
EOF
log "Created .env.local configuration."

# 5. Register launchd daemon (non-fatal)
LAUNCHD_FLAG_FILE="$HOME/.forgeos_pm2_launchd"
if [ ! -f "$LAUNCHD_FLAG_FILE" ]; then
  log "Setting up pm2 launchd service (runs on login)..."
  pm2 startup launchd -u "$(whoami)" --hp "$HOME" > /dev/null 2>&1 || true
  touch "$LAUNCHD_FLAG_FILE"
fi

# 6. Safe process cleanup (only stop processes matching this project)
if pm2 list | grep -q forgeos-backend; then
  pm2 delete forgeos-backend || true
fi
if pm2 list | grep -q forgeos; then
  pm2 delete forgeos || true
fi

# Safe port check for 8000
if lsof -i :8000 >/dev/null 2>&1; then
  PIDS=$(lsof -t -i :8000)
  for P in $PIDS; do
    CMD=$(ps -p $P -o command= 2>/dev/null || true)
    if [[ "$CMD" == *"uvicorn"* ]] || [[ "$CMD" == *"python"* ]]; then
      log "Stopping project backend process $P on port 8000..."
      kill -9 $P || true
    fi
  done
fi

# Safe port check for 8080
if lsof -i :8080 >/dev/null 2>&1; then
  PIDS=$(lsof -t -i :8080)
  for P in $PIDS; do
    CMD=$(ps -p $P -o command= 2>/dev/null || true)
    if [[ "$CMD" == *"vite"* ]] || [[ "$CMD" == *"node"* ]]; then
      log "Stopping project dev process $P on port 8080..."
      kill -9 $P || true
    fi
  done
fi

# 7. Start Python FastAPI Engine via PM2 inside backend directory
log "Starting ForgeOS Python Engine (FastAPI on port 8000)..."
pm2 start "venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000" --name forgeos-backend --cwd "$ROOT_DIR/backend"

# 8. Start TanStack Start Frontend via PM2
log "Starting SanipOps Dev Server (Vite on port 8080)..."
pm2 start npm --name forgeos --cwd "$ROOT_DIR" -- run dev --time

# 9. Save PM2 state
pm2 save

log "✅ SanipOps with ForgeOS Engine is live at http://localhost:8080"
log "✅ Backend API running at http://127.0.0.1:8000"
