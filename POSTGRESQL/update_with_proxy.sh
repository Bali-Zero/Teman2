#!/bin/bash
#
# Script wrapper per aggiornamento automatico Excel
# Gestisce fly proxy in background e credenziali
#
# USO:
#   ./update_with_proxy.sh
#
# CRON (ogni giorno alle 6:00 AM):
#   crontab -e
#   0 6 * * * /Users/antonellosiano/Desktop/nuzantara/POSTGRESQL/update_with_proxy.sh >> /tmp/postgresql_export.log 2>&1
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROXY_PORT=15432
PG_APP="nuzantara-postgres"
RAG_APP="nuzantara-rag"

echo ""
echo "========================================"
echo "PostgreSQL Export - $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# Funzione cleanup
cleanup() {
    echo "Stopping fly proxy..."
    pkill -f "fly proxy $PROXY_PORT" 2>/dev/null || true
}

# Trap per cleanup on exit
trap cleanup EXIT

# Controlla se fly è installato
if ! command -v fly &> /dev/null; then
    echo "❌ fly CLI non trovato. Installa con: brew install flyctl"
    exit 1
fi

# Ottieni DATABASE_URL dal secret di nuzantara-rag
echo "Fetching DATABASE_URL from $RAG_APP..."
REMOTE_DB_URL=$(fly ssh console -a $RAG_APP -C "printenv DATABASE_URL" 2>/dev/null || echo "")

if [ -z "$REMOTE_DB_URL" ]; then
    echo "❌ Impossibile ottenere DATABASE_URL. Verifica che la macchina sia attiva."
    echo "   Prova: fly machine start -a $RAG_APP"
    exit 1
fi

# Sostituisci l'hostname interno con localhost:PROXY_PORT
# Da: postgres://user:pass@nuzantara-postgres.flycast:5432/db
# A:  postgres://user:pass@localhost:15432/db
export DATABASE_URL=$(echo "$REMOTE_DB_URL" | sed "s|@.*:5432|@localhost:$PROXY_PORT|")
echo "✅ DATABASE_URL configurato"

# Controlla se già c'è un proxy attivo sulla porta
if lsof -i :$PROXY_PORT &> /dev/null; then
    echo "⚠️  Porta $PROXY_PORT già in uso, uso proxy esistente"
else
    # Avvia fly proxy in background
    echo "Starting fly proxy on port $PROXY_PORT..."
    fly proxy $PROXY_PORT:5432 -a $PG_APP &
    PROXY_PID=$!

    # Aspetta che il proxy sia pronto
    echo "Waiting for proxy to be ready..."
    sleep 5

    # Verifica che il proxy sia attivo
    if ! kill -0 $PROXY_PID 2>/dev/null; then
        echo "❌ Fly proxy non si è avviato"
        exit 1
    fi
    echo "✅ Fly proxy attivo (PID: $PROXY_PID)"
fi

# Esegui lo script Python
echo ""
cd "$SCRIPT_DIR"
python3 update_excel.py

echo ""
echo "✅ Export completato: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
