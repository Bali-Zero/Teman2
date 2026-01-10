#!/bin/bash
# Script per eseguire test completo usando env vars da Fly.io
# Recupera temporaneamente le chiavi e le usa per il test

set -e

echo "🔐 Recupero environment variables da Fly.io..."

# Crea un file temporaneo con le env vars
TMP_ENV=$(mktemp)
fly ssh console -a nuzantara-rag -C "env | grep -E 'QDRANT|OPENAI' > /tmp/fly_env.txt && cat /tmp/fly_env.txt" > "$TMP_ENV" 2>/dev/null || {
    echo "⚠️ Impossibile recuperare env vars direttamente da Fly.io"
    echo "   Eseguendo test con variabili d'ambiente locali..."
    rm -f "$TMP_ENV"
    python3 "$(dirname "$0")/run_complete_test.py"
    exit $?
}

# Carica le variabili
if [ -s "$TMP_ENV" ]; then
    export $(cat "$TMP_ENV" | xargs)
    echo "✅ Variabili caricate"
    rm -f "$TMP_ENV"
else
    echo "⚠️ Nessuna variabile trovata, usando .env locale"
    rm -f "$TMP_ENV"
fi

# Esegui il test
cd "$(dirname "$0")"
python3 run_complete_test.py
