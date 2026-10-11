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
if [ -x .venv/bin/python ]; then
  PYTHON="$PWD/.venv/bin/python"
elif [ -x venv/bin/python ]; then
  PYTHON="$PWD/venv/bin/python"
else
  PYTHON=python3
fi

if [ -d .deps ]; then
  DEPS="$PWD/.deps"
else
  DEPS=""
fi
PYTHONPATH="${DEPS:+$DEPS:}$PWD${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" -m pytest tests/ -q

echo "ALL CHECKS PASSED"
