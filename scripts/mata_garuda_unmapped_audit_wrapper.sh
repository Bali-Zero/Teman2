#!/bin/bash
# Mata-Garuda C.2 — Daily unmapped gap audit.
# Reads knowledge.db `type='unmapped_gap'` rows from last 24h,
# aggregates by (gap_type, attribute), alerts Telegram if total > threshold.
#
# Reference:
#   research/symbiosis/2026-05-16-dispatch-alias-brainstorm.md §C.2
#   apps/mata-garuda/mata_garuda/workers/gap_legacy.py:_record_unmapped
#
# Scheduled: 09:00 WITA daily via com.matagaruda.unmapped-audit.daily.plist.

set -euo pipefail

REPO="$HOME/Desktop/nuzantara"
APP_DIR="$REPO/apps/mata-garuda"
DB="$APP_DIR/data/knowledge.db"
LOG_DIR="$HOME/logs"
LOG="$LOG_DIR/mata-garuda-unmapped-audit.log"

# Alert when unmapped count exceeds this in the last 24h.
THRESHOLD="${MATAGARUDA_UNMAPPED_ALERT_THRESHOLD:-50}"

# Source secrets (Telegram bot token + chat id) defensively.
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a; source "$HOME/.nuzantara-secrets.env"; set +a
fi

mkdir -p "$LOG_DIR"

now() { date '+%Y-%m-%d %H:%M:%S %Z'; }

echo "" >> "$LOG"
echo "=== Unmapped Gap Audit — $(now) ===" >> "$LOG"

if [ ! -f "$DB" ]; then
    echo "[unmapped-audit] FATAL: knowledge.db not found at $DB" >> "$LOG"
    exit 2
fi

# Aggregate last 24h unmapped count by (gap_type, attribute) tuple.
# Content is JSON like {"gap_type":"...","attribute":"...","count":N}.
SUMMARY=$(sqlite3 "$DB" <<SQL
SELECT
    json_extract(content, '\$.gap_type') AS gtype,
    json_extract(content, '\$.attribute') AS attr,
    SUM(CAST(json_extract(content, '\$.count') AS INTEGER)) AS total
FROM knowledge
WHERE type = 'unmapped_gap'
  AND created_at > datetime('now', '-24 hours')
GROUP BY gtype, attr
ORDER BY total DESC;
SQL
)

TOTAL_24H=$(sqlite3 "$DB" "
SELECT COALESCE(SUM(CAST(json_extract(content, '\$.count') AS INTEGER)), 0)
FROM knowledge
WHERE type = 'unmapped_gap'
  AND created_at > datetime('now', '-24 hours');
")

echo "[unmapped-audit] 24h total=$TOTAL_24H threshold=$THRESHOLD" >> "$LOG"
if [ -n "$SUMMARY" ]; then
    echo "[unmapped-audit] breakdown:" >> "$LOG"
    echo "$SUMMARY" >> "$LOG"
fi

if [ "${TOTAL_24H:-0}" -le "${THRESHOLD:-50}" ]; then
    echo "[unmapped-audit] OK — under threshold" >> "$LOG"
    exit 0
fi

# Alert path. hotfix-notify.sh is the canonical Telegram dispatcher.
NOTIFY="$HOME/.claude/scripts/hotfix-notify.sh"
MSG="📉 Mata-Garuda unmapped gaps last 24h: $TOTAL_24H (threshold $THRESHOLD)\n\nTop:\n$SUMMARY\n\nSee gap_legacy.py:_TRANSLATION — likely schema drift."

if [ -x "$NOTIFY" ]; then
    "$NOTIFY" "$MSG" >> "$LOG" 2>&1 || echo "[unmapped-audit] notify failed (non-fatal)" >> "$LOG"
else
    echo "[unmapped-audit] notify script missing at $NOTIFY — alert NOT sent" >> "$LOG"
fi

exit 0
