#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down 2>/dev/null || true
fi

if [ -f logs/backend.pid ]; then
  kill "$(cat logs/backend.pid)" 2>/dev/null || true
  rm -f logs/backend.pid
fi
if [ -f logs/worker.pid ]; then
  kill "$(cat logs/worker.pid)" 2>/dev/null || true
  rm -f logs/worker.pid
fi
if [ -f logs/scheduler.pid ]; then
  kill "$(cat logs/scheduler.pid)" 2>/dev/null || true
  rm -f logs/scheduler.pid
fi
if [ -f logs/frontend.pid ]; then
  kill "$(cat logs/frontend.pid)" 2>/dev/null || true
  rm -f logs/frontend.pid
fi
if [ -f logs/public-app.pid ]; then
  kill "$(cat logs/public-app.pid)" 2>/dev/null || true
  rm -f logs/public-app.pid
fi

echo "ForgeOS stopped."
