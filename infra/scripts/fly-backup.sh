#!/usr/bin/env bash
# Fly.io Unified Backup — PostgreSQL + Qdrant
# Runs daily at 03:00 WITA. pg first, qdrant second (30min gap built-in).
set -euo pipefail

# Wave 3 ops-hardening fix 2026-05-19 (4-LLM panel 2/2 quorum):
# fly-pg-backup.sh + fly-qdrant-backup.sh require AWS_ACCESS_KEY_ID +
# AWS_SECRET_ACCESS_KEY (Tigris S3-compatible credentials). The cron
# scheduler (crontab `0 3 * * * fly-backup.sh`) inherits ONLY the
# cron-launched env, NOT the interactive shell env. Without explicit
# secrets sourcing here, child fly-pg-backup.sh hits its
# `${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID not set}` parameter expansion
# and bails immediately. Daily PG backup silently failed for days
# (visible in fly-backup-YYYYMMDD.log: "AWS_ACCESS_KEY_ID not set").
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"
    set +a
else
    echo "[$(date '+%H:%M:%S')] WARN: secrets file not found at $SECRETS_FILE — backup will likely fail" >&2
fi

LOG="$HOME/logs/fly-backup-$(date +%Y%m%d).log"
mkdir -p "$HOME/logs"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Fly Backup start ==="

log "--- Phase 1: PostgreSQL ---"
bash "$HOME/scripts/fly-pg-backup.sh" 2>&1 | tee -a "$LOG"
PG_EXIT=${PIPESTATUS[0]}

log "--- Phase 2: Qdrant ---"
bash "$HOME/scripts/fly-qdrant-backup.sh" 2>&1 | tee -a "$LOG"
QD_EXIT=${PIPESTATUS[0]}

if [[ $PG_EXIT -eq 0 && $QD_EXIT -eq 0 ]]; then
    log "=== Backup complete: PG ✅ Qdrant ✅ ==="
else
    log "=== Backup PARTIAL: PG=$PG_EXIT Qdrant=$QD_EXIT ==="
    exit 1
fi
