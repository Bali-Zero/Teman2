#!/bin/sh
# Best-effort Pro/Mini post-commit sync.
#
# Policy:
# - main branch only
# - Pro commits: ask Mini to run its hardened pull script from Pro
# - Mini commits: push main to Pro (Pro has receive.denyCurrentBranch=updateInstead)
# - never fail the user's commit; log and verify instead

set -u

LOG_DIR="$HOME/.openclaw/logs"
LOG_FILE="$LOG_DIR/git-sync.log"
mkdir -p "$LOG_DIR"

log() {
  printf '[%s] [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$(hostname)" "$*" >> "$LOG_FILE"
}

run_with_timeout() {
  timeout_seconds="$1"
  shift

  "$@" &
  command_pid=$!

  (
    sleep "$timeout_seconds"
    if kill -0 "$command_pid" 2>/dev/null; then
      kill "$command_pid" 2>/dev/null || true
      sleep 2
      kill -0 "$command_pid" 2>/dev/null && kill -9 "$command_pid" 2>/dev/null || true
    fi
  ) &
  watchdog_pid=$!

  wait "$command_pid"
  status=$?
  kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true
  return "$status"
}

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$BRANCH" != "main" ]; then
  log "skip: branch=$BRANCH"
  exit 0
fi

LOCAL_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
HOST=$(hostname)

case "$HOST" in
  Nuzantara)
    log "pro->mini start local=$LOCAL_HEAD"
    if run_with_timeout 180 ssh -o ConnectTimeout=8 -o BatchMode=yes \
      -o ServerAliveInterval=10 -o ServerAliveCountMax=2 mini \
      'cd ~/Desktop/nuzantara && /bin/bash ~/scripts/mini-git-pull.sh' \
      >> "$LOG_FILE" 2>&1; then
      REMOTE_HEAD=$(run_with_timeout 30 ssh -o ConnectTimeout=8 -o BatchMode=yes \
        -o ServerAliveInterval=10 -o ServerAliveCountMax=2 mini \
        'cd ~/Desktop/nuzantara && git rev-parse --short HEAD' 2>/dev/null || echo "unknown")
      if [ "$REMOTE_HEAD" = "$LOCAL_HEAD" ]; then
        log "pro->mini OK head=$LOCAL_HEAD"
      else
        log "pro->mini WARN mismatch local=$LOCAL_HEAD mini=$REMOTE_HEAD"
      fi
    else
      log "pro->mini ERROR ssh/pull failed local=$LOCAL_HEAD"
    fi
    ;;

  Mini-Pro2|mini-pro2)
    log "mini->pro start local=$LOCAL_HEAD"
    if run_with_timeout 180 git push pro main >> "$LOG_FILE" 2>&1; then
      REMOTE_HEAD=$(run_with_timeout 30 ssh -o ConnectTimeout=8 -o BatchMode=yes \
        -o ServerAliveInterval=10 -o ServerAliveCountMax=2 pro \
        'cd ~/Desktop/nuzantara && git rev-parse --short HEAD' 2>/dev/null || echo "unknown")
      if [ "$REMOTE_HEAD" = "$LOCAL_HEAD" ]; then
        log "mini->pro OK head=$LOCAL_HEAD"
      else
        log "mini->pro WARN mismatch local=$LOCAL_HEAD pro=$REMOTE_HEAD"
      fi
    else
      log "mini->pro ERROR push failed local=$LOCAL_HEAD"
    fi
    ;;

  *)
    log "skip: unknown host=$HOST head=$LOCAL_HEAD"
    ;;
esac

exit 0
