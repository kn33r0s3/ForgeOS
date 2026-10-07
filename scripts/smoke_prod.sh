#!/bin/sh
# Renovation: smoke-test a deployment. Read-only: curls only.
# Usage: sh scripts/smoke_prod.sh <BASE_URL>
# Exits non-zero unless /api/health, / and /experiments all answer 200.
set -u
BASE_URL="${1:?usage: sh scripts/smoke_prod.sh <BASE_URL>}"
fail=0
for path in /api/health / /experiments; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 20 "$BASE_URL$path")
  echo "$path -> $code"
  if [ "$code" != "200" ]; then
    fail=1
  fi
done
exit $fail
