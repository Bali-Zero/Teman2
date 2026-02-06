#!/bin/bash
# Script per eseguire la migration via flyctl proxy

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_FILE="$SCRIPT_DIR/001_add_performance_indexes.sql"
FLY_PG_APP="nuzantara-postgres"
LOCAL_PORT="54333"

echo "🚀 Migration Database via Fly.io Proxy"
echo "======================================="
echo ""

# Verifica file migration
if [ ! -f "$MIGRATION_FILE" ]; then
    echo "❌ File migration non trovato: $MIGRATION_FILE"
    exit 1
fi

echo "📁 File migration: $MIGRATION_FILE"
echo "🗄️  Database: $FLY_PG_APP"
echo "🔌 Porta locale: $LOCAL_PORT"
echo ""

# Verifica flyctl
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl non trovato. Installa: https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Pulizia..."
    if [ -n "$PROXY_PID" ]; then
        kill $PROXY_PID 2>/dev/null || true
        wait $PROXY_PID 2>/dev/null || true
    fi
    echo "✅ Proxy chiuso"
}
trap cleanup EXIT

echo "🔌 Avvio proxy flyctl..."
echo "   flyctl proxy ${LOCAL_PORT}:5432 -a $FLY_PG_APP"
echo ""

# Avvia proxy in background
flyctl proxy ${LOCAL_PORT}:5432 -a "$FLY_PG_APP" &
PROXY_PID=$!

# Attendi che il proxy sia pronto
echo "⏳ Attesa connessione proxy (5s)..."
sleep 5

# Verifica che il proxy sia attivo
if ! kill -0 $PROXY_PID 2>/dev/null; then
    echo "❌ Proxy fallito ad avviarsi"
    exit 1
fi

echo "✅ Proxy attivo su localhost:$LOCAL_PORT"
echo ""

# Ottieni le credenziali dal DATABASE_URL
# postgres://backend_rag_v2:2zEjit43IF6gNUV@nuzantara-postgres.flycast:5432/nuzantara_rag
DB_USER="backend_rag_v2"
DB_PASS="2zEjit43IF6gNUV"
DB_NAME="nuzantara_rag"

echo "🚀 Esecuzione migration..."
echo ""

# Esegui migration
PGPASSWORD="$DB_PASS" psql \
    -h localhost \
    -p "$LOCAL_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -f "$MIGRATION_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Migration completata con successo!"
    echo ""
    echo "📊 Verifica indici creati:"
    PGPASSWORD="$DB_PASS" psql \
        -h localhost \
        -p "$LOCAL_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "SELECT indexname, tablename FROM pg_indexes WHERE indexname LIKE 'idx_%' ORDER BY tablename, indexname;"
else
    echo ""
    echo "❌ Migration fallita con codice: $EXIT_CODE"
    exit $EXIT_CODE
fi
