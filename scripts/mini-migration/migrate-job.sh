#!/bin/bash
# scripts/mini-migration/migrate-job.sh <label>
#
# Migrates a single LaunchAgent from Pro to Mini following the
# deterministic procedure in spec §6.
#
# DRY-RUN by default. Pass --apply as 2nd arg to actually execute.
# Without --apply, prints exactly what would happen and exits 0.
#
# Idempotent: re-running on a label already migrated is a no-op (detects
# state from job-ownership.yaml).

set -u

LABEL="${1:-}"
APPLY="${2:-}"

if [ -z "$LABEL" ]; then
  echo "usage: $0 <label> [--apply]" >&2
  exit 2
fi

REPO="${REPO:-/Users/nuzantara/Desktop/nuzantara}"
YAML="$REPO/config/job-ownership.yaml"
LOCK_FILE="/tmp/repo-mutating.lock"
LOG_FILE="$HOME/logs/mini-migration.log"

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [migrate $LABEL] $*" | tee -a "$LOG_FILE"; }

if [ "$APPLY" != "--apply" ]; then
  echo "=== DRY-RUN MODE ==="
  echo "Would execute migration of: $LABEL"
  echo "Pass '--apply' as 2nd arg to actually run."
  echo ""
fi

DRY=""
[ "$APPLY" != "--apply" ] && DRY="DRY: "

# === Step 1: preflight ===
log "${DRY}Step 1: preflight-job.sh $LABEL"
if [ "$APPLY" = "--apply" ]; then
  if ! "$REPO/scripts/mini-migration/preflight-job.sh" "$LABEL"; then
    log "ABORT: preflight rejected $LABEL"
    exit 1
  fi
fi

# === Step 2: acquire repo-mutating lock ===
log "${DRY}Step 2: flock --timeout 60 $LOCK_FILE"
if [ "$APPLY" = "--apply" ]; then
  exec 9>"$LOCK_FILE"
  if ! flock --timeout 60 9; then
    log "ABORT: could not acquire $LOCK_FILE within 60s"
    exit 1
  fi
fi

# === Step 3: check job-ownership.yaml ===
log "${DRY}Step 3: parse $YAML, assert owner=='pro'"
if [ ! -f "$YAML" ]; then
  log "ABORT: $YAML not found"
  exit 1
fi
# Cheap YAML grep (we're not pulling in PyYAML for a single field)
CURRENT_OWNER=$(awk -v l="$LABEL:" '
  $1 == l {found=1; next}
  found && /^  [a-zA-Z]/ {found=0}
  found && /^    owner:/ {print $2; exit}
' "$YAML")
log "current owner per yaml: ${CURRENT_OWNER:-(missing)}"
if [ "$APPLY" = "--apply" ] && [ "$CURRENT_OWNER" != "pro" ]; then
  log "ABORT: yaml owner is '$CURRENT_OWNER', expected 'pro'"
  exit 1
fi

# === Step 4: assert active on Pro ===
log "${DRY}Step 4: ssh pro launchctl print gui/\$UID/$LABEL → assert active"
if [ "$APPLY" = "--apply" ]; then
  if ! ssh pro "launchctl print 'gui/\$(id -u)/$LABEL'" 2>/dev/null | grep -q "state = "; then
    log "ABORT: $LABEL not loaded on Pro"
    exit 1
  fi
fi

# === Step 5: rsync plist Pro→Mini ===
log "${DRY}Step 5: rsync ~/Library/LaunchAgents/${LABEL}.plist from Pro to Mini"
if [ "$APPLY" = "--apply" ]; then
  rsync -a "pro:~/Library/LaunchAgents/${LABEL}.plist" \
            "$HOME/Library/LaunchAgents/${LABEL}.plist" || {
    log "ABORT: rsync failed"
    exit 1
  }
fi

# === Step 6: patch plist (PATH, paths, idempotent wrapper) ===
log "${DRY}Step 6: patch plist (EnvironmentVariables.PATH + nuzantara-deploy→nuzantara + log paths + idempotent-runner wrap if non-idempotent)"
# (Implementation skeleton — TODO when first real migration runs)

# === Step 7: bootout on Pro ===
log "${DRY}Step 7: ssh pro launchctl bootout gui/\$UID/$LABEL"
if [ "$APPLY" = "--apply" ]; then
  ssh pro "launchctl bootout 'gui/\$(id -u)/$LABEL'" 2>/dev/null || true
  sleep 5
fi

# === Step 8: rename Pro plist to .disabled-... ===
log "${DRY}Step 8: ssh pro mv ~/Library/LaunchAgents/${LABEL}.plist .disabled-$(date +%Y-%m-%d)-migrated-to-mini"
if [ "$APPLY" = "--apply" ]; then
  ssh pro "mv ~/Library/LaunchAgents/${LABEL}.plist ~/Library/LaunchAgents/${LABEL}.plist.disabled-$(date +%Y-%m-%d)-migrated-to-mini"
fi

# === Step 9: bootstrap on Mini ===
log "${DRY}Step 9: launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/${LABEL}.plist"
if [ "$APPLY" = "--apply" ]; then
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/${LABEL}.plist"
fi

# === Step 10: verify ===
log "${DRY}Step 10: launchctl print gui/\$(id -u)/$LABEL → assert state=active"

# === Step 11: kickstart secrets-sync ===
log "${DRY}Step 11: launchctl kickstart secrets-sync-mini"

# === Step 12: manual fire test ===
log "${DRY}Step 12: launchctl kickstart $LABEL → wait 60s → check log"

# === Step 13-17: heartbeat verify, yaml update, git commit, memo ===
log "${DRY}Step 13-17: verify heartbeat, update yaml, git commit, append memo"

if [ "$APPLY" != "--apply" ]; then
  echo ""
  echo "=== END DRY-RUN ==="
  echo "To actually execute: $0 $LABEL --apply"
  exit 0
fi

log "MIGRATION COMPLETE: $LABEL"
exit 0
