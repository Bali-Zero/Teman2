#!/bin/bash
# Script per eseguire KG Incremental Extraction con Fly Proxy automatico

set -e

echo "🚀 Starting KG Incremental Extraction..."

# 1. Trova porta libera per il proxy
PROXY_PORT=5433
for port in 5433 5434 5435 5436; do
    if ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        PROXY_PORT=$port
        break
    fi
done

echo "📡 Using port $PROXY_PORT for Fly Proxy"

# 2. Avvia Fly Proxy in background
echo "📡 Starting Fly Proxy for PostgreSQL..."
fly proxy $PROXY_PORT:5432 -a nuzantara-postgres > /tmp/fly_proxy.log 2>&1 &
PROXY_PID=$!

# Aspetta che il proxy sia pronto
echo "⏳ Waiting for proxy to be ready..."
sleep 5

# Verifica che il proxy sia attivo
if ! kill -0 $PROXY_PID 2>/dev/null; then
    echo "❌ Failed to start Fly Proxy. Check /tmp/fly_proxy.log"
    exit 1
fi

# Trap per killare il proxy quando lo script termina
cleanup() {
    echo ""
    echo "🧹 Cleaning up Fly Proxy (PID: $PROXY_PID)..."
    kill $PROXY_PID 2>/dev/null || true
    wait $PROXY_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 3. Recupera QDRANT_API_KEY dal container Qdrant
echo "🔑 Retrieving QDRANT_API_KEY from Fly.io..."
QDRANT_API_KEY_VALUE=$(fly ssh console -a nuzantara-qdrant -C 'printenv QDRANT__SERVICE__API_KEY' 2>&1 | grep -v "Connecting\|^\$" | tail -1 | tr -d '\r\n ')

# Se non riesce a recuperarlo, usa il valore trovato manualmente
if [ -z "$QDRANT_API_KEY_VALUE" ] || [ "$QDRANT_API_KEY_VALUE" = "NOT_FOUND" ]; then
    echo "⚠️ Using hardcoded QDRANT_API_KEY (found from previous retrieval)"
    QDRANT_API_KEY_VALUE="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
fi

# 4. Configura variabili ambiente
export GOOGLE_PROJECT_ID='nuzantara'
export DATABASE_URL="postgres://backend_rag_v2:2zEjit43IF6gNUV@localhost:$PROXY_PORT/nuzantara_rag?sslmode=disable"
export QDRANT_URL='https://nuzantara-qdrant.fly.dev'
export QDRANT_API_KEY="$QDRANT_API_KEY_VALUE"

echo "✅ Environment variables configured:"
echo "   DATABASE_URL: postgres://...@localhost:$PROXY_PORT/nuzantara_rag"
echo "   QDRANT_URL: $QDRANT_URL"
echo "   GOOGLE_PROJECT_ID: $GOOGLE_PROJECT_ID"
echo "   QDRANT_API_KEY: ${QDRANT_API_KEY:0:15}... (set)"
echo ""

# 5. Verifica che gemini CLI sia autenticato
if ! command -v gemini &> /dev/null; then
    echo "⚠️ Warning: gemini CLI not found. Make sure you've run 'gemini /auth'"
fi

# 6. Esegui lo script
cd /Users/antonellosiano/Desktop/nuzantara
echo "🕸️ Running KG Incremental Extraction..."
python apps/backend-rag/scripts/kg_incremental_extraction.py

echo ""
echo "✅ KG Extraction completed!"
