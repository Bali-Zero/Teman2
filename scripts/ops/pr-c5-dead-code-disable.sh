#!/usr/bin/env bash
# PR-C5 — Dead code uninstall on Pro crontab.
# Reproducible script that disables / reduces cron jobs that audit
# 2026-04-29 (research/ops/2026-04-29-pro-automations-audit/) flagged
# as dead code, dormant, or duplicated.
#
# RUN ON PRO ONLY. Idempotent: re-running after success is a no-op.
#
# Targets (all crontab Pro):
#   1. core-guardian          DELETE   — 56 runs/week, 0 fixable candidates ever
#   2. weekly-review          DELETE   — never produced a log file (cron schedule
#                                        misfire or upstream nlm CLI broken)
#   3. intel-feed-processor   REDUCE   — */30 → 0 */2 (every 2h) — starved 95%,
#                                        keep on schedule for occasional batches
#   4. vision-doc-extractor   REDUCE   — '5 * * * *' → '5 */6 * * *' (every 6h) —
#                                        always inbox_empty, no upstream drops files
#   5. fly-restart-loop-detector (cron) DELETE — duplicates LaunchAgent that
#                                        already runs every ~auto-respawn cycle
#   6. system-doctor (cron-wrapper '0 0 * * *') DELETE — TCC PermissionError;
#                                        cron-agent-python version '0 */4 * * *'
#                                        already covers it
#
# Backups: previous crontab saved to ~/.crontab.backups/<utc-ts>.cron before edit.
# Audit log: appended to ~/logs/ops/pr-c5-dead-code-disable.log
#
# Reference: PR-C5 in plan
#   ~/.claude/plans/RESUME-renaissance-2026-04-29.md
#   research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv

set -euo pipefail

if [[ "$(whoami)" != "nuzantara" ]]; then
  echo "[pr-c5] ERROR: must run on Pro (whoami=nuzantara). got: $(whoami)" >&2
  exit 1
fi

BACKUP_DIR="$HOME/.crontab.backups"
LOG_DIR="$HOME/logs/ops"
LOG_FILE="$LOG_DIR/pr-c5-dead-code-disable.log"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG_FILE"
}

# 1. Snapshot current crontab.
TMP_BEFORE="$(mktemp -t pr-c5-before.XXXXXX)"
TMP_AFTER="$(mktemp -t pr-c5-after.XXXXXX)"
trap 'rm -f "$TMP_BEFORE" "$TMP_AFTER"' EXIT

crontab -l > "$TMP_BEFORE"
cp "$TMP_BEFORE" "$BACKUP_DIR/$TS_UTC.cron"
log "snapshot saved: $BACKUP_DIR/$TS_UTC.cron ($(wc -l < "$TMP_BEFORE" | tr -d ' ') lines)"

# 2. Apply transforms via awk pipeline.
#    Each transform is idempotent: it tolerates the line being absent.

# 2a. Core-guardian DELETE: drop the line and its preceding "# core-guardian" comment.
# 2b. Weekly-review DELETE: drop the line.
# 2c. fly-restart-loop-detector cron DELETE: drop the line.
# 2d. system-doctor cron-wrapper '0 0 * * *' DELETE: drop the line and its preceding "# C2.3 system-doctor" comment.
# 2e. intel-feed-processor REDUCE: rewrite '*/30 * * * *' to '0 */2 * * *'.
# 2f. vision-doc-extractor REDUCE: rewrite '5 * * * *' to '5 */6 * * *'.

awk '
  # Delete blocks: drop the comment line that precedes the cron line, and the cron line itself.
  /^# core-guardian: every 3h$/             { skip_next=1; next }
  /^# C2.3 system-doctor \(daily 08:00 WITA/ { skip_next=1; next }
  # intel-feed-processor comment is informational; keep it (renaissance update will rewrite).
  # Single-line deletes:
  /^0 \*\/3 \* \* \* \/bin\/bash ~\/scripts\/cron-agent\.sh exec core-guardian/ { next }
  /^0 9 \* \* 5 bash \/Users\/nuzantara\/scripts\/cron-agent-python\/run\.sh weekly-review/ { next }
  /^\*\/15 \* \* \* \* \/Users\/nuzantara\/scripts\/fly-restart-loop-detector\.sh/ { next }
  /^0 0 \* \* \* \/Users\/nuzantara\/Desktop\/nuzantara\/scripts\/cron-wrapper\.sh system-doctor/ { next }
  # Cadence reductions (idempotent: only rewrite if old cadence still present).
  /^\*\/30 \* \* \* \* bash \/Users\/nuzantara\/scripts\/cron-agent-python\/run\.sh intel-feed-processor/ {
    sub(/^\*\/30 \* \* \* \*/, "0 */2 * * *"); print; next
  }
  /^5 \* \* \* \* bash \/Users\/nuzantara\/scripts\/cron-agent-python\/run\.sh vision-doc-extractor/ {
    sub(/^5 \* \* \* \*/, "5 */6 * * *"); print; next
  }
  # Skip the cron line right after a flagged comment.
  skip_next == 1 { skip_next=0; next }
  { print }
' "$TMP_BEFORE" > "$TMP_AFTER"

# 3. Diff summary for audit.
DIFF_OUT="$(diff -u "$TMP_BEFORE" "$TMP_AFTER" || true)"
if [[ -z "$DIFF_OUT" ]]; then
  log "no-op: crontab already matches PR-C5 target state"
  exit 0
fi

log "diff:"
printf '%s\n' "$DIFF_OUT" | tee -a "$LOG_FILE"

# 4. Validate: refuse install if line count drop is unexpectedly large (safety net).
LINES_BEFORE=$(wc -l < "$TMP_BEFORE" | tr -d ' ')
LINES_AFTER=$(wc -l < "$TMP_AFTER" | tr -d ' ')
DELTA=$((LINES_BEFORE - LINES_AFTER))
if (( DELTA < 0 || DELTA > 10 )); then
  log "ERROR: unexpected line delta=$DELTA (expected 0..10). aborting."
  exit 2
fi
log "line delta: $LINES_BEFORE -> $LINES_AFTER (-$DELTA)"

# 5. Install the new crontab.
crontab "$TMP_AFTER"
log "crontab installed."

# 6. Verify by re-reading.
crontab -l > "$TMP_BEFORE"
if ! diff -q "$TMP_BEFORE" "$TMP_AFTER" >/dev/null; then
  log "WARNING: post-install crontab differs from intended. Investigate manually."
  exit 3
fi
log "post-install verified: crontab matches intended state."

# 7. Final summary.
log "PR-C5 applied. Backup: $BACKUP_DIR/$TS_UTC.cron"
log "Rollback: crontab '$BACKUP_DIR/$TS_UTC.cron'"
