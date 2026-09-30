#!/bin/sh
set -eu
if [ -d "/workspace" ]; then
  cd /workspace
else
  cd "$(cd "$(dirname "$0")" && pwd)"
fi
# :8081 is QA-only — a revive must never inherit a stale built-output preview.
node scripts/preview.mjs stop || true
if curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8080/; then
  exit 0
fi
nohup npm run dev >>/tmp/app-startup.log 2>&1 &
