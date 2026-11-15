#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.livekit-scale.yml"
COMPOSE=(docker compose --profile manual-cloud-opt-in --project-directory "$ROOT_DIR" -f "$COMPOSE_FILE")

usage() {
  cat <<'USAGE'
Usage: scripts/livekit-scale-test.sh {stop|status}

Cloud publisher startup and load testing are disabled in this helper.
Only cleanup and inspection are exposed. Do not invoke the manual Compose
profile without explicit owner authorization and LiveKit written approval.
USAGE
}

case "${1:-}" in
  start|test)
    echo "Blocked: LiveKit Cloud publishers and load tests are disabled. No Cloud execution or spend is authorized." >&2
    exit 1
    ;;
  stop)
    LIVEKIT_CLOUD_MANUAL_OPT_IN=cleanup-only "${COMPOSE[@]}" down --remove-orphans
    ;;
  status)
    LIVEKIT_CLOUD_MANUAL_OPT_IN=cleanup-only "${COMPOSE[@]}" ps --all
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
