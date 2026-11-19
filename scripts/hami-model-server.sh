#!/bin/zsh
# hami-model server launcher — runs the pilot server with the Mac venv python.
# The venv is created by Order 025 (torch + tokenizers install).
# Refuses to start if the venv python is missing — no fallback, no other model.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="/Users/nirojpaudyal/Downloads/hami-model/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "hami-model: venv python not found at $VENV_PY — run the Order 025 install step" >&2
  exit 1
fi
exec "$VENV_PY" "$DIR/hami-model-server.py"
