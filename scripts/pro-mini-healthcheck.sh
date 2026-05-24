#!/bin/sh
# Pro/Mini git sync healthcheck.
#
# Read-only. Prints local, peer, and GitHub heads plus launchd/sync-script
# readiness. Intended for AGENTS.md session-start checks and operator triage.

set -u

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT" 2>/dev/null || exit 1

HOST=$(hostname)
USER_NAME=$(whoami)

case "$HOST" in
  Nuzantara)
    NODE="Pro"
    PEER_ALIAS="mini"
    PEER_NODE="Mini"
    PEER_REPO='~/Desktop/nuzantara'
    ;;
  Mini-Pro2|mini-pro2)
    NODE="Mini"
    PEER_ALIAS="pro"
    PEER_NODE="Pro"
    PEER_REPO='~/Desktop/nuzantara'
    ;;
  *)
    NODE="Unknown"
    PEER_ALIAS=""
    PEER_NODE="Unknown"
    PEER_REPO='~/Desktop/nuzantara'
    ;;
esac

short() {
  printf '%s' "$1" | cut -c1-10
}

print_kv() {
  printf '%s=%s\n' "$1" "$2"
}

LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
LOCAL_SHORT=$(short "$LOCAL_SHA")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
DIRTY_COUNT=$(git status --short 2>/dev/null | wc -l | tr -d ' ')

print_kv "machine" "$NODE"
print_kv "host" "$USER_NAME@$HOST"
print_kv "repo" "$ROOT"
print_kv "branch" "$BRANCH"
print_kv "local_head" "$LOCAL_SHORT"
print_kv "dirty_count" "$DIRTY_COUNT"

ORIGIN_SHA=$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}' || true)
if [ -n "$ORIGIN_SHA" ]; then
  print_kv "origin_main" "$(short "$ORIGIN_SHA")"
else
  print_kv "origin_main" "UNREACHABLE"
fi

if [ -z "$PEER_ALIAS" ]; then
  print_kv "peer" "UNKNOWN_HOST"
else
  PEER_HOST=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$PEER_ALIAS" 'printf "%s@%s" "$(whoami)" "$(hostname)"' 2>/dev/null || true)
  if [ -z "$PEER_HOST" ]; then
    print_kv "peer" "$PEER_NODE:UNREACHABLE"
    PEER_SHA=""
  else
    print_kv "peer" "$PEER_NODE:$PEER_HOST"
    PEER_SHA=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$PEER_ALIAS" "cd $PEER_REPO && git rev-parse HEAD" 2>/dev/null || true)
    if [ -n "$PEER_SHA" ]; then
      print_kv "peer_head" "$(short "$PEER_SHA")"
    else
      print_kv "peer_head" "UNKNOWN"
    fi
  fi
fi

if [ -n "${ORIGIN_SHA:-}" ] && [ "$LOCAL_SHA" = "$ORIGIN_SHA" ]; then
  ORIGIN_OK="yes"
else
  ORIGIN_OK="no"
fi

if [ -n "${PEER_SHA:-}" ] && [ "$LOCAL_SHA" = "$PEER_SHA" ]; then
  PEER_OK="yes"
else
  PEER_OK="no"
fi

if [ "$ORIGIN_OK" = "yes" ] && [ "$PEER_OK" = "yes" ]; then
  print_kv "heads_aligned" "yes"
else
  print_kv "heads_aligned" "no"
fi

if [ "$NODE" = "Pro" ]; then
  if [ -x "$ROOT/scripts/pro-mini-git-sync-hook.sh" ]; then
    print_kv "post_commit_sync_script" "ok"
  else
    print_kv "post_commit_sync_script" "missing_or_not_executable"
  fi
elif [ "$NODE" = "Mini" ]; then
  if launchctl list 2>/dev/null | grep -q 'com.nuzantara.git-pull-main.5min'; then
    print_kv "mini_pull_launchagent" "loaded"
  else
    print_kv "mini_pull_launchagent" "not_loaded"
  fi

  if [ -x "$HOME/scripts/mini-git-pull.sh" ]; then
    print_kv "mini_pull_deployed_script" "ok"
  else
    print_kv "mini_pull_deployed_script" "missing_or_not_executable"
  fi
fi

LOG_FILE="$HOME/.openclaw/logs/git-sync.log"
if [ -f "$LOG_FILE" ]; then
  LAST_SYNC=$(grep 'OK head=' "$LOG_FILE" 2>/dev/null | tail -1 || true)
  if [ -n "$LAST_SYNC" ]; then
    print_kv "last_sync_ok" "$LAST_SYNC"
  else
    print_kv "last_sync_ok" "none"
  fi
else
  print_kv "last_sync_ok" "log_missing"
fi

if [ "$BRANCH" = "main" ] && [ "$PEER_OK" = "yes" ] && [ "$ORIGIN_OK" = "yes" ]; then
  exit 0
fi

exit 1
