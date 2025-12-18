#!/bin/bash

# Script per generare report settimanale di monitoring
# Usage: ./scripts/weekly-monitoring-report.sh

set -e

echo "📊 Weekly Monitoring Report Generator"
echo "======================================"
echo ""

APP_URL="${PLAYWRIGHT_BASE_URL:-https://nuzantara-mouth.fly.dev}"
REPORT_DIR="./monitoring-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/weekly-report-$TIMESTAMP.json"

# Crea directory se non esiste
mkdir -p "$REPORT_DIR"

echo "📡 App URL: $APP_URL"
echo "📁 Report directory: $REPORT_DIR"
echo ""

# Verifica che l'app sia raggiungibile
echo "⏳ Verificando che l'app sia raggiungibile..."
if ! curl -f -s "$APP_URL" > /dev/null 2>&1; then
  echo "❌ L'app non è raggiungibile. Verifica che sia deployata."
  exit 1
fi
echo "✅ App raggiungibile!"
echo ""

echo "📝 Istruzioni per generare il report:"
echo "======================================"
echo ""
echo "1. Apri il browser e vai a: $APP_URL"
echo ""
echo "2. Apri DevTools (F12)"
echo ""
echo "3. Vai alla tab Console"
echo ""
echo "4. Esegui questi comandi nella console:"
echo ""
echo "   // Mostra summary"
echo "   monitoringHelpers.summary()"
echo ""
echo "   // Mostra alert attivi"
echo "   monitoringHelpers.alerts()"
echo ""
echo "   // Esporta metriche"
echo "   monitoringHelpers.export()"
echo ""
echo "5. Copia l'output JSON e salvalo in: $REPORT_FILE"
echo ""
echo "6. Analizza il report per:"
echo "   - Conversazioni lunghe (>15 turni)"
echo "   - Errori frequenti"
echo "   - Timeout patterns"
echo "   - Rate limit issues"
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
echo "💡 Tip: Puoi anche eseguire questo script settimanalmente per tracciare trend"
echo ""

# Crea template di report
cat > "$REPORT_DIR/.report-template.json" << 'EOF'
{
  "reportDate": "YYYY-MM-DD",
  "summary": {
    "activeSessions": 0,
    "totalTurns": 0,
    "totalErrors": 0,
    "totalTimeouts": 0,
    "totalRateLimitHits": 0
  },
  "sessions": [],
  "alerts": [],
  "recommendations": []
}
EOF

echo "✅ Template di report creato in: $REPORT_DIR/.report-template.json"
echo ""
echo "📋 Prossimi passi:"
echo "   1. Esegui i comandi nella console del browser"
echo "   2. Salva l'output JSON nel file di report"
echo "   3. Analizza i dati per identificare pattern e problemi"
echo "   4. Condividi il report con il team"

