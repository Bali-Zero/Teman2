#!/bin/bash
# Bidirectional memory sync Pro <-> Mini <-> Air-M5 (hub-and-spoke, hub=Pro) with conflict detection
# Cron: */5 * * * * /Users/nuzantara/scripts/mini-setup/memory-sync-bidirectional.sh >> ~/logs/memory-sync.log 2>&1
# Hub-and-spoke (Opzione A, 2026-06-01): UN solo daemon sul Pro cicla Mini E M5.
#   Mini e M5 NON si parlano direttamente — ogni ramo è 2-way Pro<->spoke, lock unico.
# NB: 'set -e' RIMOSSO 2026-06-01 — con 2 spoke un fallimento di uno (es. M5 in sleep)
#     NON deve abortire l'altro. Ogni ramo è fail-soft individualmente.

LOG_FILE="$HOME/logs/memory-sync.log"
MEM_PRO="$HOME/.claude/projects/-Users-nuzantara/memory"
MEM_MINI_USER="nuzantara"
MEM_MINI_PATH="/Users/nuzantara/.claude/projects/-Users-nuzantara/memory"
LOCK_FILE="/tmp/memory-sync.lock"
CONFLICT_DIR="$HOME/.claude/memory-conflicts"

# --- Air-M5 spoke (added 2026-06-01) ---
# M5 = user balizero, path memory diverso, SSH richiede IdentitiesOnly+IdentityAgent=none.
M5_ENABLED="${M5_SYNC_ENABLED:-true}"   # kill switch: M5_SYNC_ENABLED=false
M5_IP="192.168.0.20"
M5_TS="100.87.146.107"                  # tailscale fallback
M5_USER="balizero"
MEM_M5_PATH="/Users/balizero/.claude/projects/-Users-balizero/memory"
M5_SSH_OPTS="-o ConnectTimeout=5 -o IdentitiesOnly=yes -o IdentityAgent=none -o BatchMode=yes -i $HOME/.ssh/id_ed25519"

mkdir -p "$(dirname $LOG_FILE)" "$CONFLICT_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Lock to prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
  PID=$(cat "$LOCK_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    log "Already running (PID $PID), skipping"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log "=== Memory sync run (hub=Pro, spoke=Mini+M5) ==="

# Check Mini reachable — try LAN first, fallback to Tailscale
MINI_HOST="mini"
MINI_OK=1
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes mini "echo OK" &>/dev/null; then
  if ssh -o ConnectTimeout=5 -o BatchMode=yes mini-remote "echo OK" &>/dev/null; then
    MINI_HOST="mini-remote"
    log "Mini reachable via Tailscale (LAN unavailable)"
  else
    log "Mini unreachable (LAN+Tailscale), skip Mini branch (M5 branch still runs)"
    MINI_OK=0
  fi
fi

if [ "$MINI_OK" = "1" ]; then

# Step 1: Get file lists with checksums on both sides
log "Fetching Pro file checksums + mtime..."
PRO_LIST=$(cd "$MEM_PRO" && find . -type f -name "*.md" -exec md5 -q {} \; -exec stat -f "%m" {} \; -print | paste - - - | sort)

log "Fetching Mini file checksums + mtime..."
MINI_LIST=$(ssh "$MINI_HOST" "cd $MEM_MINI_PATH 2>/dev/null && find . -type f -name '*.md' -exec md5 -q {} \\; -exec stat -f '%m' {} \\; -print | paste - - - | sort" 2>/dev/null || echo "")

# Step 2: Find conflicts (md5 differ AND mtime delta < 60s = simultaneous edit)
# If md5 differs but mtime delta >= 60s, mtime newer wins (rsync --update handles).
log "Detecting conflicts (md5 differ + mtime delta <60s)..."
CONFLICTS=$(comm -12 \
  <(echo "$PRO_LIST" | awk '{print $3}') \
  <(echo "$MINI_LIST" | awk '{print $3}') | while read f; do
    PRO_HASH=$(echo "$PRO_LIST" | grep " $f$" | awk '{print $1}')
    PRO_MTIME=$(echo "$PRO_LIST" | grep " $f$" | awk '{print $2}')
    MINI_HASH=$(echo "$MINI_LIST" | grep " $f$" | awk '{print $1}')
    MINI_MTIME=$(echo "$MINI_LIST" | grep " $f$" | awk '{print $2}')
    if [ "$PRO_HASH" != "$MINI_HASH" ]; then
      DELTA=$(( PRO_MTIME > MINI_MTIME ? PRO_MTIME - MINI_MTIME : MINI_MTIME - PRO_MTIME ))
      if [ "$DELTA" -lt 60 ]; then
        echo "$f"
      fi
    fi
  done)

if [ -n "$CONFLICTS" ]; then
  log "⚠ Conflicts detected:"
  echo "$CONFLICTS" | while read f; do
    log "  CONFLICT: $f"
    # Save both versions for manual review
    BACKUP_NAME="$(basename $f)-conflict-$(date +%Y%m%d_%H%M%S)"
    cp "$MEM_PRO/$f" "$CONFLICT_DIR/PRO-$BACKUP_NAME" 2>/dev/null
    ssh "$MINI_HOST" "cat $MEM_MINI_PATH/$f" > "$CONFLICT_DIR/MINI-$BACKUP_NAME" 2>/dev/null
    log "    Backup saved: $CONFLICT_DIR/{PRO,MINI}-$BACKUP_NAME"
  done
  log "⚠ Skipping conflicting files. Resolve manually then re-run."
fi

# Step 3: Sync NON-conflicting files
# Strategy: newest mtime wins (rsync --update is approximate; we use timestamp)

log "Pro → Mini (newer files only, skip conflicts)..."
EXCLUDE_ARGS=""
if [ -n "$CONFLICTS" ]; then
  while read f; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$f"
  done <<< "$CONFLICTS"
fi
rsync -avz --update $EXCLUDE_ARGS \
  "$MEM_PRO/" "$MINI_HOST:$MEM_MINI_PATH/" 2>&1 | tail -5

log "Mini → Pro (newer files only, skip conflicts)..."
rsync -avz --update $EXCLUDE_ARGS \
  "$MINI_HOST:$MEM_MINI_PATH/" "$MEM_PRO/" 2>&1 | tail -5

# Step 4: Verify
PRO_COUNT=$(ls "$MEM_PRO"/*.md 2>/dev/null | wc -l | tr -d ' ')
MINI_COUNT=$(ssh "$MINI_HOST" "ls $MEM_MINI_PATH/*.md 2>/dev/null | wc -l")

log "Mini branch done: Pro=$PRO_COUNT files, Mini=$MINI_COUNT files"
fi  # end Mini branch (MINI_OK)

# ─────────────────────────────────────────────────────────────
# Air-M5 SPOKE — fail-soft, isolato dal ramo Mini (hub-and-spoke)
# ─────────────────────────────────────────────────────────────
sync_m5() {
  [ "$M5_ENABLED" != "true" ] && { log "M5 spoke disabled (M5_SYNC_ENABLED=false)"; return 0; }

  # reachability: LAN IP first, tailscale fallback
  local M5H="$M5_IP"
  if ! ssh $M5_SSH_OPTS "$M5_USER@$M5_IP" "echo OK" &>/dev/null; then
    if ssh $M5_SSH_OPTS "$M5_USER@$M5_TS" "echo OK" &>/dev/null; then
      M5H="$M5_TS"; log "M5 reachable via Tailscale (LAN unavailable)"
    else
      log "M5 unreachable (LAN+Tailscale), skip M5 branch"; return 0
    fi
  fi

  log "M5 branch: Pro <-> Air-M5 ($M5H)"
  local PRO_L M5_L M5_CONFLICTS
  PRO_L=$(cd "$MEM_PRO" && find . -type f -name "*.md" -exec md5 -q {} \; -exec stat -f "%m" {} \; -print | paste - - - | sort)
  M5_L=$(ssh $M5_SSH_OPTS "$M5_USER@$M5H" "cd $MEM_M5_PATH 2>/dev/null && find . -type f -name '*.md' -exec md5 -q {} \\; -exec stat -f '%m' {} \\; -print | paste - - - | sort" 2>/dev/null || echo "")

  # conflict detection (md5 differ + mtime delta <60s)
  M5_CONFLICTS=$(comm -12 \
    <(echo "$PRO_L" | awk '{print $3}') \
    <(echo "$M5_L" | awk '{print $3}') | while read f; do
      local ph pm mh mm
      ph=$(echo "$PRO_L" | grep " $f$" | awk '{print $1}'); pm=$(echo "$PRO_L" | grep " $f$" | awk '{print $2}')
      mh=$(echo "$M5_L"  | grep " $f$" | awk '{print $1}'); mm=$(echo "$M5_L"  | grep " $f$" | awk '{print $2}')
      if [ "$ph" != "$mh" ]; then
        local d=$(( pm > mm ? pm - mm : mm - pm ))
        [ "$d" -lt 60 ] && echo "$f"
      fi
    done)

  local EXC=""
  if [ -n "$M5_CONFLICTS" ]; then
    log "⚠ M5 conflicts (saved for manual review):"
    echo "$M5_CONFLICTS" | while read f; do
      log "  CONFLICT: $f"
      local bn="$(basename $f)-m5conflict-$(date +%Y%m%d_%H%M%S)"
      cp "$MEM_PRO/$f" "$CONFLICT_DIR/PRO-$bn" 2>/dev/null
      ssh $M5_SSH_OPTS "$M5_USER@$M5H" "cat $MEM_M5_PATH/$f" > "$CONFLICT_DIR/M5-$bn" 2>/dev/null
    done
    while read f; do EXC="$EXC --exclude=$f"; done <<< "$M5_CONFLICTS"
  fi

  log "Pro → M5 (newer only)..."
  rsync -avz --update $EXC -e "ssh $M5_SSH_OPTS" "$MEM_PRO/" "$M5_USER@$M5H:$MEM_M5_PATH/" 2>&1 | tail -3
  log "M5 → Pro (newer only)..."
  rsync -avz --update $EXC -e "ssh $M5_SSH_OPTS" "$M5_USER@$M5H:$MEM_M5_PATH/" "$MEM_PRO/" 2>&1 | tail -3

  local M5_COUNT
  M5_COUNT=$(ssh $M5_SSH_OPTS "$M5_USER@$M5H" "ls $MEM_M5_PATH/*.md 2>/dev/null | wc -l")
  log "M5 branch done: Pro=$(ls "$MEM_PRO"/*.md 2>/dev/null | wc -l | tr -d ' ') files, M5=$(echo $M5_COUNT | tr -d ' ') files"
}

sync_m5

log "=== Done (hub-and-spoke) ==="
