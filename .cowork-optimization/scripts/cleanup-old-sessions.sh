#!/bin/bash
# Cleanup Old Cowork Sessions - Performance Optimization
# Rimuove sessioni più vecchie di N giorni per mantenere performance

SESSIONS_DIR="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
LOG_FILE="$HOME/Desktop/nuzantara/.cowork-optimization/logs/session-cleanup.log"
DAYS_TO_KEEP=7

mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date)] Starting session cleanup (keeping last $DAYS_TO_KEEP days)..." >> "$LOG_FILE"

# Conta sessioni prima del cleanup
SESSIONS_BEFORE=$(find "$SESSIONS_DIR" -type f -name "*.json" | wc -l)

# Rimuovi file JSON più vecchi di N giorni
DELETED=0
find "$SESSIONS_DIR" -type f -name "*.json" -mtime +$DAYS_TO_KEEP | while read file; do
    SESSION_NAME=$(basename "$file")
    rm "$file" && echo "[$(date)] Deleted old session: $SESSION_NAME" >> "$LOG_FILE"
    DELETED=$((DELETED + 1))
done

# Rimuovi directory vuote
find "$SESSIONS_DIR" -type d -empty -delete 2>/dev/null

SESSIONS_AFTER=$(find "$SESSIONS_DIR" -type f -name "*.json" | wc -l)

echo "[$(date)] Cleanup completed: $SESSIONS_BEFORE → $SESSIONS_AFTER sessions" >> "$LOG_FILE"
