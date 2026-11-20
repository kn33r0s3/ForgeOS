#!/bin/bash
# hami-loop.sh — Hami's never-stop loop.
# Owned by Niroj. Runs under launchd KeepAlive + caffeinate -i.
# Every 60s: writes heartbeat.txt, works queue/, flags the planner when empty.
# Queue items: *.sh = shell task (run it, log it, move to done/ on exit 0).
#              *.md = agent task (Copilot/Nyx/Muse pick it up; loop only logs it).
# Never reads keys, tokens, or .env values. Never sends mail or spends money.
set -u
# run_with_timeout <seconds> <cmd...> — macOS has no `timeout(1)`, so run the
# command in the background and kill it after <seconds>. Returns the command's
# exit code (non-zero on timeout). Same helper as the live ~/hami/hami-loop.sh.
run_with_timeout() {
  local limit="$1"; shift
  "$@" &
  local pid=$!
  ( sleep "$limit"; kill "$pid" 2>/dev/null ) &
  local watcher=$!
  wait "$pid"; local rc=$?
  kill "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return "$rc"
}
ROOT="$HOME/Downloads/ForgeOS"
LOGDIR="$ROOT/logs"
QUEUEDIR="$ROOT/queue"
DONEDIR="$ROOT/done"
mkdir -p "$LOGDIR" "$QUEUEDIR" "$DONEDIR"
exec >> "$LOGDIR/loop.log" 2>&1
echo "[$(date -u +%FT%TZ)] hami-loop started pid $$"
while true; do
  date -u +%FT%TZ > "$ROOT/heartbeat.txt"
  ran=0
  for f in "$QUEUEDIR"/*.sh; do
    [ -e "$f" ] || continue
    base=$(basename "$f" .sh)
    echo "[$(date -u +%FT%TZ)] running queue task: $base"
    if run_with_timeout 600 bash "$f" > "$LOGDIR/$base.log" 2>&1; then
      echo "[$(date -u +%FT%TZ)] done: $base (exit 0)"
      mv "$f" "$DONEDIR/$base.sh"
    else
      rc=$?
      echo "[$(date -u +%FT%TZ)] FAILED: $base (exit $rc) — left in queue"
      touch "$QUEUEDIR/$base.failed"
    fi
    ran=1
  done
  pending=$(ls "$QUEUEDIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$ran" -eq 0 ] && [ "$pending" -eq 0 ]; then
    touch "$ROOT/queue/NEED-PLANNER"
    echo "[$(date -u +%FT%TZ)] queue empty: planner flag set"
  else
    rm -f "$ROOT/queue/NEED-PLANNER"
    [ "$pending" -gt 0 ] && echo "[$(date -u +%FT%TZ)] $pending agent task(s) pending in queue/"
  fi
  sleep 60
done
