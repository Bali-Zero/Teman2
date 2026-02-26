#!/bin/bash
# Auto sync PostgreSQL: avvia fly proxy, fa sync, chiude proxy
# Da usare in OpenClaw cron

set -e

LOG_DIR="/tmp/nuzantara_dumps"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
AUTO_LOG="$LOG_DIR/auto_sync_$TIMESTAMP.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$AUTO_LOG"
}

log "🚀 Auto-sync PostgreSQL avviato"

# Check if fly proxy is already running
if nc -z localhost 15432 2>/dev/null; then
    log "✅ Fly proxy già attivo"
    PROXY_ALREADY_RUNNING=true
else
    log "🔌 Avvio fly proxy..."
    cd ~/Projects/nuzantara
    fly proxy 15432:5432 -a nuzantara-postgres > "$LOG_DIR/fly_proxy_$TIMESTAMP.log" 2>&1 &
    PROXY_PID=$!
    log "Proxy PID: $PROXY_PID"
    
    # Wait for proxy to be ready
    for i in {1..30}; do
        if nc -z localhost 15432 2>/dev/null; then
            log "✅ Fly proxy pronto"
            break
        fi
        sleep 1
    done
    
    if ! nc -z localhost 15432 2>/dev/null; then
        log "❌ Fly proxy non si è avviato entro 30 secondi"
        exit 1
    fi
fi

# Run sync
log "🔄 Esecuzione sync..."
~/Projects/nuzantara/scripts/sync_postgres_from_production.sh --tables-only 2>&1 | tee -a "$AUTO_LOG"

# Kill proxy if we started it
if [ -z "$PROXY_ALREADY_RUNNING" ] && [ -n "$PROXY_PID" ]; then
    log "🛑 Chiudo fly proxy (PID: $PROXY_PID)"
    kill $PROXY_PID 2>/dev/null || true
fi

log "🎉 Auto-sync completato"
log "📋 Log completo: $AUTO_LOG"

# Return summary for OpenClaw
echo "---"
echo "✅ PostgreSQL sync completato"
echo "📊 Locale ora allineato a production"
echo "📋 Log: $AUTO_LOG"
