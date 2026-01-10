#!/bin/bash
# Script per configurare autenticazione Claude CLI
# Eseguire manualmente via SSH dopo il deploy: fly ssh console -a bali-intel-scraper

set -e

echo "🔐 Configurazione autenticazione Claude CLI..."
echo ""
echo "NOTA: Questo script richiede autenticazione interattiva."
echo "Se hai già autenticato localmente, puoi copiare ~/.claude su Fly.io"
echo ""

# Verifica se Claude CLI è installato
if ! command -v claude &> /dev/null; then
    echo "❌ Claude CLI non trovato. Installazione..."
    npm install -g @anthropic-ai/claude-code
fi

# Verifica se già autenticato
if claude -p "test" &> /dev/null; then
    echo "✅ Claude CLI già autenticato!"
    exit 0
fi

echo "🔑 Avvio processo di autenticazione..."
echo "Segui le istruzioni sullo schermo per completare l'autenticazione."
echo ""

# Avvia setup-token (richiede interazione)
claude setup-token

echo ""
echo "✅ Autenticazione completata!"
echo "La configurazione è salvata in ~/.claude"
