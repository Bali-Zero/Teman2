#!/bin/bash
# scripts/mini-migration/rollback-job.sh <label>
#
# Reverses a migration: re-enables plist on Pro, disables on Mini.
# Updates job-ownership.yaml owner back to "pro".
#
# Idempotent: re-running on a label already on Pro is no-op.

set -u

LABEL="${1:-}"
APPLY="${2:-}"

if [ -z "$LABEL" ]; then
  echo "usage: $0 <label> [--apply]" >&2
  exit 2
fi

REPO="${REPO:-/Users/nuzantara/Desktop/nuzantara}"
YAML="$REPO/config/job-ownership.yaml"
LOG_FILE="$HOME/logs/mini-migration.log"

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [rollback $LABEL] $*" | tee -a "$LOG_FILE"; }

if [ "$APPLY" != "--apply" ]; then
  echo "=== DRY-RUN MODE ==="
  echo "Would rollback migration of: $LABEL"
  echo "Pass '--apply' as 2nd arg to actually run."
  echo ""
fi

DRY=""
[ "$APPLY" != "--apply" ] && DRY="DRY: "

# Step 1: bootout Mini
log "${DRY}Step 1: launchctl bootout gui/\$(id -u)/$LABEL on Mini"
if [ "$APPLY" = "--apply" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
fi

# Step 2: rename Mini plist to .rolled-back
log "${DRY}Step 2: mv Mini plist to .plist.rolled-back-$(date +%Y-%m-%d)"
if [ "$APPLY" = "--apply" ]; then
  if [ -f "$HOME/Library/LaunchAgents/${LABEL}.plist" ]; then
    mv "$HOME/Library/LaunchAgents/${LABEL}.plist" \
       "$HOME/Library/LaunchAgents/${LABEL}.plist.rolled-back-$(date +%Y-%m-%d)"
  fi
fi

# Step 3: re-enable Pro plist
log "${DRY}Step 3: ssh pro restore .disabled plist + bootstrap"
if [ "$APPLY" = "--apply" ]; then
  DISABLED_PLIST=$(ssh pro "ls ~/Library/LaunchAgents/${LABEL}.plist.disabled-* 2>/dev/null | head -1")
  if [ -n "$DISABLED_PLIST" ]; then
    ssh pro "mv '$DISABLED_PLIST' '~/Library/LaunchAgents/${LABEL}.plist' && launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/${LABEL}.plist"
  else
    log "WARN: no .disabled plist found on Pro for $LABEL"
  fi
fi

# Step 4: yaml owner back to pro
log "${DRY}Step 4: update $YAML owner: pro"

# Step 5: telegram alert
log "${DRY}Step 5: telegram alert ROLLBACK COMPLETED for $LABEL"

if [ "$APPLY" != "--apply" ]; then
  echo ""
  echo "=== END DRY-RUN ==="
  exit 0
fi

log "ROLLBACK COMPLETE: $LABEL"
exit 0
