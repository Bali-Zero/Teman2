#!/bin/bash

# Script per verificare il monitoraggio in produzione
# Apre il browser con DevTools e mostra come controllare gli alert

set -e

APP_URL="${PLAYWRIGHT_BASE_URL:-https://nuzantara-mouth.fly.dev}"

echo "📊 Monitoring Check Script"
echo "=========================="
echo ""
echo "Questo script ti aiuta a verificare il monitoraggio in produzione."
echo ""

# Verifica che l'app sia raggiungibile
echo "⏳ Verificando che l'app sia raggiungibile..."
if ! curl -f -s "$APP_URL" > /dev/null 2>&1; then
  echo "❌ L'app non è raggiungibile. Verifica che sia deployata."
  exit 1
fi
echo "✅ App raggiungibile!"
echo ""

echo "🔍 Come verificare il monitoraggio:"
echo "===================================="
echo ""
echo "1. Apri il browser e vai a: $APP_URL"
echo ""
echo "2. Apri DevTools (F12 o Cmd+Option+I su Mac)"
echo ""
echo "3. Vai alla tab Console"
echo ""
echo "4. Avvia una conversazione lunga (10+ messaggi)"
echo ""
echo "5. Cerca questi alert nella console:"
echo "   - [MONITORING ALERT] LONG_CONVERSATION (dopo 15 turni)"
echo "   - [MONITORING ALERT] MULTIPLE_ERRORS (dopo 3 errori)"
echo "   - [MONITORING ALERT] MULTIPLE_TIMEOUTS (dopo 2 timeout)"
echo "   - [MONITORING ALERT] RATE_LIMIT_ISSUES (dopo 2 rate limit)"
echo ""
echo "6. Per vedere le metriche, esegui nella console:"
echo ""
echo "   // Ottieni tutte le sessioni attive"
echo "   window.conversationMonitor?.getActiveSessions()"
echo ""
echo "   // Ottieni statistiche aggregate"
echo "   window.conversationMonitor?.getSummary()"
echo ""
echo "   // Ottieni metriche per una sessione specifica"
echo "   window.conversationMonitor?.getMetrics('session-id')"
echo ""

# Apri il browser se possibile
if command -v open &> /dev/null; then
  echo "🌐 Aprendo il browser..."
  open "$APP_URL"
elif command -v xdg-open &> /dev/null; then
  echo "🌐 Aprendo il browser..."
  xdg-open "$APP_URL"
else
  echo "📝 Apri manualmente: $APP_URL"
fi

echo ""
echo "📝 Test rapido:"
echo "==============="
echo "1. Invia 10+ messaggi nella chat"
echo "2. Controlla la console per eventuali alert"
echo "3. Verifica che non ci siano errori"
echo "4. Controlla che l'input rimanga sempre abilitato"
echo ""

echo "✅ Script completato!"
echo ""
echo "💡 Tip: Gli alert appaiono solo in produzione (NODE_ENV=production)"
echo "   In sviluppo vedrai [DEV MONITORING] invece di [MONITORING ALERT]"

