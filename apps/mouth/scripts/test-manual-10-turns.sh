#!/bin/bash

# Script per test manuali di conversazioni lunghe (10+ turni)
# Usage: ./scripts/test-manual-10-turns.sh

set -e

echo "🧪 Manual Test: 10+ Turn Conversation"
echo "======================================"
echo ""
echo "Questo script ti guiderà attraverso un test manuale di una conversazione lunga."
echo "Apri l'app in un browser e segui le istruzioni."
echo ""

APP_URL="${PLAYWRIGHT_BASE_URL:-https://nuzantara-mouth.fly.dev}"
echo "📡 App URL: $APP_URL"
echo ""

# Verifica che l'app sia raggiungibile
echo "⏳ Verificando che l'app sia raggiungibile..."
if ! curl -f -s "$APP_URL" > /dev/null 2>&1; then
  echo "❌ L'app non è raggiungibile. Verifica che sia deployata."
  exit 1
fi
echo "✅ App raggiungibile!"
echo ""

# Lista di messaggi di test
MESSAGES=(
  "Ciao, sono Paolo, un imprenditore italiano"
  "Voglio aprire un bar a Bali"
  "Il mio budget è 200 milioni IDR"
  "Ho già un socio indonesiano"
  "Lui ha esperienza nel settore"
  "Preferisco una location a Seminyak"
  "Quanto tempo ci vuole per aprire?"
  "E per i permessi del personale?"
  "Riassumi tutto quello che abbiamo discusso"
  "Grazie per le informazioni"
)

echo "📋 Messaggi di test (10 turni):"
echo "================================"
for i in "${!MESSAGES[@]}"; do
  echo "$((i+1)). ${MESSAGES[$i]}"
done
echo ""

echo "🔍 Checklist per il test:"
echo "=========================="
echo ""
echo "Per ogni messaggio, verifica:"
echo "  ✅ L'input è abilitato prima di inviare"
echo "  ✅ Il messaggio viene inviato correttamente"
echo "  ✅ La risposta dell'AI arriva"
echo "  ✅ L'input viene riabilitato dopo la risposta"
echo "  ✅ Non ci sono errori nella console del browser"
echo ""
echo "⚠️  Problemi da segnalare:"
echo "  ❌ Input disabilitato permanentemente"
echo "  ❌ Messaggio non inviato"
echo "  ❌ Risposta non ricevuta"
echo "  ❌ Errori nella console"
echo "  ❌ Timeout dopo 8+ turni"
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
echo "⏳ Attendi che la pagina si carichi completamente..."
sleep 3

echo ""
echo "📝 Istruzioni:"
echo "=============="
echo "1. Fai login nell'app"
echo "2. Invia i messaggi uno alla volta nell'ordine indicato"
echo "3. Dopo ogni messaggio, verifica che:"
echo "   - La risposta arriva"
echo "   - L'input è riabilitato"
echo "   - Non ci sono errori"
echo ""
echo "4. Dopo il 10° messaggio, verifica che:"
echo "   - Tutti i messaggi sono visibili"
echo "   - L'input è ancora abilitato"
echo "   - La conversazione è coerente"
echo ""

echo "🔍 Per monitorare gli errori:"
echo "=============================="
echo "1. Apri DevTools (F12)"
echo "2. Vai alla tab Console"
echo "3. Cerca errori o warning"
echo "4. Vai alla tab Network per vedere le richieste"
echo ""

echo "📊 Dopo il test, verifica:"
echo "==========================="
echo "- Controlla la console per eventuali errori"
echo "- Verifica che tutti i 10 messaggi siano visibili"
echo "- Verifica che l'input sia sempre abilitato"
echo "- Verifica che non ci siano timeout o rate limit errors"
echo ""

echo "✅ Test completato!"
echo ""
echo "Se hai trovato problemi, segnalali con:"
echo "- Screenshot degli errori"
echo "- Log della console"
echo "- Numero del turno in cui si è verificato il problema"

