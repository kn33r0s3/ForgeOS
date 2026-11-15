#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.livekit-scale.yml"
COMPOSE=(docker compose --project-directory "$ROOT_DIR" -f "$COMPOSE_FILE")
PUBLISHERS="${LIVEKIT_PUBLISHERS:-20}"

usage() {
  cat <<'USAGE'
Usage: scripts/livekit-scale-test.sh {start|test|stop|status}

Required environment:
  LIVEKIT_URL          LiveKit WebSocket URL (wss://... for LiveKit Cloud)
  LIVEKIT_API_KEY      LiveKit project API key
  LIVEKIT_API_SECRET   LiveKit project API secret

Optional environment:
  LIVEKIT_ROOM=forgeos-scale-test
  LIVEKIT_PUBLISHERS=20
  LIVEKIT_SUBSCRIBERS=10000
  LIVEKIT_TEST_DURATION=5m
  LIVEKIT_JOIN_RATE=100
  LIVEKIT_LAYOUT=speaker
  LIVEKIT_VIDEO_RESOLUTION=low

Commands:
  start  Start publisher containers in the shared room.
  test   Start publishers, then run the simulated subscriber load test.
  stop   Stop and remove only this harness's containers and network.
  status Show this harness's container status.
USAGE
}

require_credentials() {
  : "${LIVEKIT_URL:?Set LIVEKIT_URL (wss://... for LiveKit Cloud)}"
  : "${LIVEKIT_API_KEY:?Set LIVEKIT_API_KEY}"
  : "${LIVEKIT_API_SECRET:?Set LIVEKIT_API_SECRET}"
}

case "${1:-}" in
  start)
    require_credentials
    "${COMPOSE[@]}" up -d --scale "livekit-publisher=$PUBLISHERS" livekit-publisher
    ;;
  test)
    require_credentials
    "${COMPOSE[@]}" up -d --scale "livekit-publisher=$PUBLISHERS" livekit-publisher
    "${COMPOSE[@]}" --profile load-test run --rm --no-deps livekit-load-test
    ;;
  stop)
    "${COMPOSE[@]}" down --remove-orphans
    ;;
  status)
    "${COMPOSE[@]}" ps --all
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
