#!/bin/bash
# Backup Cowork Sessions - Automated Backup
# Backup incrementale delle sessioni Cowork

SESSIONS_DIR="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
BACKUP_DIR="$HOME/Desktop/nuzantara/.cowork-optimization/backups/sessions"
LOG_FILE="$HOME/Desktop/nuzantara/.cowork-optimization/logs/session-backup.log"
MAX_BACKUPS=10

# Crea directory
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date)] Starting Cowork sessions backup..." >> "$LOG_FILE"

# Crea backup con timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/cowork-sessions-$TIMESTAMP.tar.gz"

# Comprimi sessioni
if tar -czf "$BACKUP_FILE" -C "$SESSIONS_DIR" . 2>/dev/null; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup created: $(basename $BACKUP_FILE) ($BACKUP_SIZE)" >> "$LOG_FILE"

    # Mantieni solo ultimi N backup
    ls -t "$BACKUP_DIR"/cowork-sessions-*.tar.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm
    echo "[$(date)] Old backups cleaned (keeping last $MAX_BACKUPS)" >> "$LOG_FILE"
else
    echo "[$(date)] ERROR: Backup failed" >> "$LOG_FILE"
    exit 1
fi

echo "[$(date)] Backup completed successfully" >> "$LOG_FILE"
