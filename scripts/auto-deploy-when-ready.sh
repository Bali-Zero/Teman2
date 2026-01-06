#!/bin/bash
# Script che riprova automaticamente il deploy quando la connettività è ripristinata

set -e

APP_NAME="nuzantara-mouth"
MAX_ATTEMPTS=10
RETRY_DELAY=30

echo "🔄 Auto-Deploy Script - Riprova automaticamente quando Fly.io è raggiungibile"
echo "======================================================================"
echo ""

cd "$(dirname "$0")/.."

for attempt in $(seq 1 $MAX_ATTEMPTS); do
    echo "📡 Tentativo $attempt/$MAX_ATTEMPTS..."
    
    # Verifica connettività
    if curl -s --max-time 5 https://api.fly.io/graphql > /dev/null 2>&1; then
        echo "✅ Connettività ripristinata!"
        echo ""
        
        # Verifica autenticazione
        if flyctl auth whoami &>/dev/null; then
            echo "✅ Autenticato"
        else
            echo "⚠️  Richiesto login. Esegui: flyctl auth login"
            exit 1
        fi
        
        echo ""
        echo "🚀 Avvio deploy..."
        cd apps/mouth
        
        if flyctl deploy --remote-only --app $APP_NAME; then
            echo ""
            echo "✅✅✅ DEPLOY COMPLETATO CON SUCCESSO! ✅✅✅"
            echo ""
            echo "📋 Verifica:"
            echo "   https://nuzantara-mouth.fly.dev/knowledge/blueprints"
            exit 0
        else
            echo "❌ Deploy fallito. Verifica logs."
            exit 1
        fi
    else
        echo "⏳ Connettività non disponibile. Attendo ${RETRY_DELAY}s..."
        sleep $RETRY_DELAY
    fi
done

echo ""
echo "❌ Timeout: Connettività non ripristinata dopo $MAX_ATTEMPTS tentativi"
echo "   Esegui manualmente: ./scripts/deploy-mouth-knowledge-fix.sh"
exit 1

