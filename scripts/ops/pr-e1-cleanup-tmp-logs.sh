#!/usr/bin/env bash
# PR-E1 — Move /tmp/cron-*.log + 2 outliers (/tmp/legal_radar.log,
# /tmp/openclaw-bridge.log) to ~/logs/cron-tmp/<name>.log on Pro crontab.
#
# RUN ON PRO ONLY. Idempotent: re-run after success is a no-op.
#
# Reason: /tmp/ is volatile across reboots (and macOS aggressive cleanup).
# Logs there are routinely lost — Sentinel and audit trails depend on log
# persistence. Other cron-agent-python jobs already log to ~/logs/cron-agent-python/
# (canonical), so we mirror that pattern under ~/logs/cron-tmp/ to avoid
# colliding with Python jobs while still being persistent.
#
# Strategy:
#   1. Snapshot current crontab to ~/.crontab.backups/<utc-ts>.cron
#   2. Awk pipeline rewrites every "/tmp/cron-NAME.log" reference to
#      "/Users/nuzantara/logs/cron-tmp/NAME.log" (preserves the rest of
#      the cron line).
#   3. Same for the 2 non-cron-prefixed outliers (legal_radar, openclaw-bridge).
#   4. mkdir -p ~/logs/cron-tmp/ before installing the new crontab so the
#      first cron firing doesn't fail with "no such directory".
#   5. Validate: line count must be unchanged (we never delete/add lines,
#      only rewrite paths in place).
#   6. Install + verify by re-reading the live crontab.
#
# Reference: PR-E1 in plan
#   ~/.claude/plans/RESUME-renaissance-2026-04-29.md
#   research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv

set -euo pipefail

if [[ "$(whoami)" != "nuzantara" ]]; then
  echo "[pr-e1] ERROR: must run on Pro (whoami=nuzantara). got: $(whoami)" >&2
  exit 1
fi

BACKUP_DIR="$HOME/.crontab.backups"
LOG_DIR="$HOME/logs/ops"
LOG_FILE="$LOG_DIR/pr-e1-cleanup-tmp-logs.log"
TARGET_LOG_DIR="$HOME/logs/cron-tmp"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR" "$LOG_DIR" "$TARGET_LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG_FILE"
}

TMP_BEFORE="$(mktemp -t pr-e1-before.XXXXXX)"
TMP_AFTER="$(mktemp -t pr-e1-after.XXXXXX)"
trap 'rm -f "$TMP_BEFORE" "$TMP_AFTER"' EXIT

crontab -l > "$TMP_BEFORE"
cp "$TMP_BEFORE" "$BACKUP_DIR/$TS_UTC.cron"
log "snapshot saved: $BACKUP_DIR/$TS_UTC.cron ($(wc -l < "$TMP_BEFORE" | tr -d ' ') lines)"

# Awk: rewrite /tmp/cron-*.log + 2 outliers, in-place.
awk '
  {
    # Pass 1: /tmp/cron-NAME.log → ~/logs/cron-tmp/NAME.log
    while (match($0, /\/tmp\/cron-[A-Za-z0-9_-]+\.log/)) {
      matched = substr($0, RSTART, RLENGTH)
      name = substr(matched, length("/tmp/cron-") + 1, length(matched) - length("/tmp/cron-") - 4)
      replacement = "/Users/nuzantara/logs/cron-tmp/" name ".log"
      $0 = substr($0, 1, RSTART - 1) replacement substr($0, RSTART + RLENGTH)
    }
    # Pass 2: /tmp/{legal_radar,openclaw-bridge}.log → ~/logs/cron-tmp/<NAME>.log
    while (match($0, /\/tmp\/(legal_radar|openclaw-bridge)\.log/)) {
      matched = substr($0, RSTART, RLENGTH)
      name = substr(matched, length("/tmp/") + 1, length(matched) - length("/tmp/") - 4)
      replacement = "/Users/nuzantara/logs/cron-tmp/" name ".log"
      $0 = substr($0, 1, RSTART - 1) replacement substr($0, RSTART + RLENGTH)
    }
    print
  }
' "$TMP_BEFORE" > "$TMP_AFTER"

# Diff summary for audit log.
DIFF_OUT="$(diff -u "$TMP_BEFORE" "$TMP_AFTER" || true)"
if [[ -z "$DIFF_OUT" ]]; then
  log "no-op: crontab already matches PR-E1 target state"
  exit 0
fi
log "diff (rewrites only):"
printf '%s\n' "$DIFF_OUT" | tee -a "$LOG_FILE"

# Sanity: line count must be unchanged (rewrite-only, no add/delete).
LINES_BEFORE=$(wc -l < "$TMP_BEFORE" | tr -d ' ')
LINES_AFTER=$(wc -l < "$TMP_AFTER" | tr -d ' ')
if (( LINES_BEFORE != LINES_AFTER )); then
  log "ERROR: line count changed ($LINES_BEFORE → $LINES_AFTER). aborting (rewrite-only contract violated)."
  exit 2
fi
log "line count unchanged: $LINES_BEFORE"

# Sanity: no /tmp/cron- or /tmp/legal_radar.log or /tmp/openclaw-bridge.log left.
RESIDUALS=$(grep -cE "/tmp/cron-|/tmp/legal_radar\.log|/tmp/openclaw-bridge\.log" "$TMP_AFTER" || true)
if (( RESIDUALS > 0 )); then
  log "ERROR: $RESIDUALS residual /tmp/ paths after rewrite. aborting."
  exit 3
fi
log "no /tmp/ residual paths after rewrite."

# Install + verify.
crontab "$TMP_AFTER"
log "crontab installed."

crontab -l > "$TMP_BEFORE"
if ! diff -q "$TMP_BEFORE" "$TMP_AFTER" >/dev/null; then
  log "WARNING: post-install crontab differs from intended. Investigate manually."
  exit 4
fi
log "post-install verified."

log "PR-E1 applied. Backup: $BACKUP_DIR/$TS_UTC.cron"
log "Rollback: crontab '$BACKUP_DIR/$TS_UTC.cron'"
log "New log dir: $TARGET_LOG_DIR (created)."
