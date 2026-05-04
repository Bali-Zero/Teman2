#!/usr/bin/env bash
# subhi-mirror-publish.sh — verify staging dir is healthy, write .ready sentinel.
# Pro-side: runs after subhi-memory-mirror.sh, before Subhi-side pull cron.
# Subhi-side rsync pulls staging/ via Tailscale ts-ssh; this sentinel signals freshness.
set -euo pipefail

STAGING="/Users/nuzantara/Desktop/subhi_TUTOR_KIT/staging/.claude/memory-mirror"
LOG="$HOME/logs/subhi-mirror-publish.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Pre-flight checks
[[ -d "$STAGING" ]] || { log "FAIL: staging dir missing: $STAGING"; exit 1; }

FILE_COUNT=$(find "$STAGING" -type f -name "*.md" | wc -l | tr -d ' ')
[[ "$FILE_COUNT" -gt 100 ]] || { log "FAIL: too few files ($FILE_COUNT) — mirror likely broke"; exit 1; }

AUDIT="$STAGING/_AUDIT.txt"
[[ -f "$AUDIT" ]] || { log "FAIL: _AUDIT.txt missing"; exit 1; }

# Check audit age (must be <24h to avoid stale data going to Subhi)
AUDIT_AGE=$(( $(date +%s) - $(stat -f %m "$AUDIT") ))
[[ "$AUDIT_AGE" -lt 86400 ]] || { log "FAIL: _AUDIT.txt older than 24h ($AUDIT_AGE seconds)"; exit 1; }

# Write sentinel
SENTINEL="$STAGING/.ready"
{
  echo "ready_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "file_count=$FILE_COUNT"
  echo "audit_summary:"
  grep -E "^(Included|Excluded|Redacted):" "$AUDIT" | sed 's/^/  /'
} > "$SENTINEL"

log "OK: $FILE_COUNT files staged, sentinel written"
