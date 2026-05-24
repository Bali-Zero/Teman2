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
    if ssh -o ConnectTimeout=8 -o BatchMode=yes mini \
      'cd ~/Desktop/nuzantara && /bin/bash ~/scripts/mini-git-pull.sh' \
      >> "$LOG_FILE" 2>&1; then
      REMOTE_HEAD=$(ssh -o ConnectTimeout=8 -o BatchMode=yes mini \
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
    if git push pro main >> "$LOG_FILE" 2>&1; then
      REMOTE_HEAD=$(ssh -o ConnectTimeout=8 -o BatchMode=yes pro \
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
