#!/bin/bash

# Script per analizzare il feedback degli utenti
# Usage: ./scripts/analyze-feedback.sh

set -e

echo "📊 Feedback Analysis Script"
echo "==========================="
echo ""

FEEDBACK_FILE="./feedback-analysis-$(date +%Y%m%d).json"

echo "📝 Questo script analizza il feedback raccolto dagli utenti."
echo ""
echo "Il feedback viene salvato in localStorage del browser."
echo "Per esportarlo:"
echo ""
echo "1. Apri il browser e vai all'app"
echo "2. Apri DevTools (F12)"
echo "3. Vai alla tab Console"
echo "4. Esegui:"
echo ""
echo "   JSON.parse(localStorage.getItem('conversationFeedback') || '[]')"
echo ""
echo "5. Copia l'output e salvalo in: $FEEDBACK_FILE"
echo ""

# Crea template di analisi
cat > "$FEEDBACK_FILE.template" << 'EOF'
{
  "analysisDate": "YYYY-MM-DD",
  "totalFeedback": 0,
  "byType": {
    "positive": 0,
    "negative": 0,
    "issue": 0
  },
  "commonIssues": [],
  "averageTurnCount": 0,
  "recommendations": []
}
EOF

echo "✅ Template creato: $FEEDBACK_FILE.template"
echo ""
echo "📋 Analisi da fare:"
echo "   1. Conta feedback positivi vs negativi"
echo "   2. Identifica problemi comuni"
echo "   3. Analizza turni medi delle conversazioni con problemi"
echo "   4. Genera raccomandazioni per miglioramenti"
echo ""
echo "💡 Tip: Usa questo script settimanalmente per tracciare trend"

