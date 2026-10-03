#!/usr/bin/env bash
# Hami production health watchdog.
# Polls both production /api/health endpoints. Silent when healthy.
# Wakes a worker only after 2 consecutive failing polls (blip-tolerant).
#
# PORTABILITY NOTE: the silent/wake/log functions and $HATCH_HOOK_RUNTIME
# come from the Muse hook runtime. On another runtime, replace them:
#   silent <msg>  -> do nothing (healthy, stay quiet)
#   wake <title>  -> alert the operator/user with <title> + JSON payload
#   log <kind>    -> append the JSON payload to a local run log
# State file semantics: any writable path works; keep the
# "2 consecutive failures before alerting" rule.
set -euo pipefail
# Muse hook runtime provides silent/wake/log; on other runtimes, define
# them yourself (see PORTABILITY NOTE above) or run with shims.
if [ -n "${HATCH_HOOK_RUNTIME:-}" ] && [ -f "$HATCH_HOOK_RUNTIME" ]; then
  source "$HATCH_HOOK_RUNTIME"
fi
# Fallbacks when no hook runtime is present: stay quiet when healthy,
# print the alert payload when waking, append observations to a log file.
if ! command -v silent >/dev/null 2>&1; then
  silent() { :; }
fi
if ! command -v wake >/dev/null 2>&1; then
  wake() { echo "WAKE: $1 $2" >&2; }
fi
if ! command -v log >/dev/null 2>&1; then
  log() { echo "[$(date -u +%FT%TZ)] $1 $2" >> "$STATE_DIR/hami-health-watch.log"; }
fi

STATE_DIR="$HOME/hooks/state"
STATE_FILE="$STATE_DIR/hami-health-failures"
mkdir -p "$STATE_DIR"

failures=0
if [ -f "$STATE_FILE" ] && [ "${HATCH_HOOK_DRY_RUN:-0}" != "1" ]; then
  failures=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
  case "$failures" in ''|*[!0-9]*) failures=0 ;; esac
fi

down=""
for domain in haminp.vercel.app forge-os-ebon.vercel.app; do
  body=$(curl --fail --silent --show-error --max-time 15 "https://$domain/api/health" 2>/dev/null || true)
  status=$(printf '%s' "$body" | jq -r '.status // empty' 2>/dev/null || true)
  if [ "$status" != "ok" ]; then
    down="$down $domain"
  fi
done

if [ -z "$down" ]; then
  if [ "${HATCH_HOOK_DRY_RUN:-0}" != "1" ]; then
    echo 0 > "$STATE_FILE"
  fi
  silent "both production domains healthy" '{"domains":["haminp.vercel.app","forge-os-ebon.vercel.app"]}'
fi

failures=$((failures + 1))
if [ "${HATCH_HOOK_DRY_RUN:-0}" != "1" ]; then
  echo "$failures" > "$STATE_FILE"
fi
log "observation" "{\"down\":\"$down\",\"consecutive_failures\":$failures}"

if [ "$failures" -ge 2 ]; then
  wake "production health check failing" "{\"down\":\"$down\",\"consecutive_failures\":$failures}"
else
  silent "transient failure, waiting for confirmation" "{\"down\":\"$down\",\"consecutive_failures\":$failures}"
fi
