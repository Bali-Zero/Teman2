#!/bin/bash
# Sync Knowledge Base to Qdrant - Smart Sync
# Sincronizza KB con Qdrant solo se ci sono modifiche

KB_DIR="$HOME/Desktop/KB"
KBLI_DIR="$HOME/Desktop/kbli"
SYNC_LOG="$HOME/Desktop/nuzantara/.cowork-optimization/logs/kb-sync.log"
LAST_SYNC_FILE="$HOME/Desktop/nuzantara/.cowork-optimization/.last-kb-sync"
BACKEND_DIR="$HOME/Desktop/nuzantara/apps/backend-rag"

mkdir -p "$(dirname "$SYNC_LOG")"

echo "[$(date)] Checking for KB changes..." >> "$SYNC_LOG"

# Controlla se ci sono modifiche dalla last sync
if [ -f "$LAST_SYNC_FILE" ]; then
    LAST_SYNC=$(cat "$LAST_SYNC_FILE")
    KB_CHANGES=$(find "$KB_DIR" "$KBLI_DIR" -type f -newer "$LAST_SYNC_FILE" 2>/dev/null | wc -l)

    if [ "$KB_CHANGES" -eq 0 ]; then
        echo "[$(date)] No changes detected, skipping sync" >> "$SYNC_LOG"
        exit 0
    fi
    echo "[$(date)] Found $KB_CHANGES changed files" >> "$SYNC_LOG"
fi

# Esegui sync se backend disponibile
if [ -d "$BACKEND_DIR" ]; then
    echo "[$(date)] Starting KB → Qdrant sync..." >> "$SYNC_LOG"

    cd "$BACKEND_DIR" || exit 1

    # Attiva virtual environment se esiste
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    # Esegui script di ingestion (adatta al tuo setup)
    if python -m scripts.ingestion.ingest_kbli_platinum_2026 2>&1 | tee -a "$SYNC_LOG"; then
        touch "$LAST_SYNC_FILE"
        echo "[$(date)] Sync completed successfully" >> "$SYNC_LOG"
    else
        echo "[$(date)] ERROR: Sync failed" >> "$SYNC_LOG"
        exit 1
    fi
else
    echo "[$(date)] WARNING: Backend directory not found" >> "$SYNC_LOG"
fi
