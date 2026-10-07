#!/bin/sh
# Renovation: ONE command that checks everything. Stops at the first failure.
# Usage: sh scripts/check_all.sh   (from the repo root)
set -e
cd "$(dirname "$0")/.."

echo "==> typecheck"
npm run typecheck

if grep -q '"lint"' package.json; then
  echo "==> lint"
  npm run lint
else
  echo "==> lint skipped (no lint script)"
fi

echo "==> build"
npm run build

echo "==> backend tests"
cd backend
if [ -d .deps ]; then
  DEPS="$PWD/.deps"
else
  # Fall back to the main checkout's installed deps (same requirements.txt).
  DEPS="/home/hatch/workspace/repos/ForgeOS/backend/.deps"
fi
PYTHONPATH="$DEPS:$PWD" python3 -m pytest tests/ -q

echo "ALL CHECKS PASSED"
