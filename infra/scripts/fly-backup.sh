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

# 2026-07-27 (W101 shape): `set -e` above plus a BARE pipeline decapitated the very
# capture written to tolerate a failure. On a PG failure bash aborted on the pipeline
# itself — PG_EXIT was never assigned, Phase 2 never ran, and the "PARTIAL" report below
# was dead code on the one path it exists for. `${PIPESTATUS[0]}` was already correct
# about the pipe (W97); it simply never got to run.
# Measured, not reasoned: the qdrant nightly is MISSING for 2026-07-26 — the night the
# PG backup failed — and present on 20-25 and 27. One failing phase silently took the
# other down with it.
# Each phase now runs with errexit disarmed and is judged by its CAPTURED code, never by
# having survived.
log "--- Phase 1: PostgreSQL ---"
set +e
bash "$HOME/scripts/fly-pg-backup.sh" 2>&1 | tee -a "$LOG"
PG_EXIT=${PIPESTATUS[0]}
set -e

log "--- Phase 2: Qdrant ---"
set +e
bash "$HOME/scripts/fly-qdrant-backup.sh" 2>&1 | tee -a "$LOG"
QD_EXIT=${PIPESTATUS[0]}
set -e

if [[ $PG_EXIT -eq 0 && $QD_EXIT -eq 0 ]]; then
    log "=== Backup complete: PG ✅ Qdrant ✅ ==="
else
    log "=== Backup PARTIAL: PG=$PG_EXIT Qdrant=$QD_EXIT ==="
    exit 1
fi
