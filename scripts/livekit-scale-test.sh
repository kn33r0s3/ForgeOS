#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.livekit-scale.yml"
COMPOSE=(docker compose --project-directory "$ROOT_DIR" -f "$COMPOSE_FILE")
PUBLISHERS="${LIVEKIT_PUBLISHERS:-20}"

usage() {
  cat <<'USAGE'
Usage: scripts/livekit-scale-test.sh {start|test|stop|status}

Prerequisite:
  Authenticate with LiveKit CLI and persist its config at ~/.livekit:
  docker run --rm -it -v "$HOME/.livekit:/root/.livekit" \\
    livekit/livekit-cli:v2.19.4 cloud auth

Optional environment:
  LIVEKIT_ROOM=forgeos-scale-test
  LIVEKIT_PUBLISHERS=20
  LIVEKIT_SUBSCRIBERS=25
  LIVEKIT_TEST_DURATION=1m
  LIVEKIT_JOIN_RATE=5
  LIVEKIT_LAYOUT=speaker
  LIVEKIT_VIDEO_RESOLUTION=low

Commands:
  start  Start publisher containers in the shared room.
  test   Start publishers, then run the simulated subscriber load test.
  stop   Stop and remove only this harness's containers and network.
  status Show this harness's container status.
USAGE
}

require_project_config() {
  if [[ ! -f "$HOME/.livekit/cli-config.yaml" ]]; then
    echo "Missing $HOME/.livekit/cli-config.yaml. Authenticate with LiveKit CLI first." >&2
    exit 1
  fi
}

case "${1:-}" in
  start)
    require_project_config
    "${COMPOSE[@]}" up -d --scale "livekit-publisher=$PUBLISHERS" livekit-publisher
    ;;
  test)
    require_project_config
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
