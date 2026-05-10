#!/bin/bash
# scripts/mini-migration/log-prune.sh
#
# Daily log retention for Mini-Pro2. Cron: 03:00 WITA.
#
# What it deletes (mtime > 30d):
# - ~/logs/*.log         (job-emitted logs)
# - ~/.cache/*/launchd.{stdout,stderr}.log
# - /tmp/balizero-*.log
# - /tmp/<job-name>-*.log
#
# What it preserves:
# - active log files (mtime < 30d)
# - lockfiles (no extension)
# - state files in ~/.agent/decisions/state/
#
# Read-only on the rest of the disk. Logs its own work to
# ~/logs/log-prune.log (exempt from deletion).

set -u

LOG_FILE="$HOME/logs/log-prune.log"
mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "=== log-prune run ==="

DELETED=0

# ~/logs/*.log
if [ -d "$HOME/logs" ]; then
  count=$(find "$HOME/logs" -maxdepth 2 -name "*.log" -mtime +30 -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -gt 0 ]; then
    find "$HOME/logs" -maxdepth 2 -name "*.log" -mtime +30 -type f -delete 2>/dev/null || true
    log "deleted $count old logs from ~/logs/"
    DELETED=$((DELETED + count))
  fi
fi

# ~/.cache/*/launchd.{stdout,stderr}.log
if [ -d "$HOME/.cache" ]; then
  count=$(find "$HOME/.cache" -maxdepth 3 -name "launchd.std*.log" -mtime +30 -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -gt 0 ]; then
    find "$HOME/.cache" -maxdepth 3 -name "launchd.std*.log" -mtime +30 -type f -delete 2>/dev/null || true
    log "deleted $count old launchd logs from ~/.cache/"
    DELETED=$((DELETED + count))
  fi
fi

# /tmp ephemeral logs (mtime > 7d on /tmp; macOS may evict but we explicit anyway)
count=$(find /tmp -maxdepth 1 -name "balizero-*.log" -mtime +7 -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then
  find /tmp -maxdepth 1 -name "balizero-*.log" -mtime +7 -type f -delete 2>/dev/null || true
  log "deleted $count old /tmp/balizero-*.log files"
  DELETED=$((DELETED + count))
fi

count=$(find /tmp -maxdepth 1 \( -name "*.log" -or -name "*.stderr" -or -name "*.stdout" \) -mtime +7 -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then
  find /tmp -maxdepth 1 \( -name "*.log" -or -name "*.stderr" -or -name "*.stdout" \) -mtime +7 -type f -delete 2>/dev/null || true
  log "deleted $count old /tmp/*.log files"
  DELETED=$((DELETED + count))
fi

# Self-rotate: if log-prune.log itself > 1 MB, keep last 1000 lines.
if [ -f "$LOG_FILE" ]; then
  size=$(stat -f %z "$LOG_FILE" 2>/dev/null || echo 0)
  if [ "$size" -gt 1048576 ]; then
    tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    log "rotated self-log (was ${size} bytes)"
  fi
fi

log "=== done — deleted $DELETED files ==="
exit 0
