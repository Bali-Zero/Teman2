#!/bin/bash
# Script per deploy automatico delle modifiche Knowledge Base
# Fix: Rimosso fallback Google Drive, aggiunto logging

set -e

echo "🚀 Deploy Knowledge Base Fix - Nuzantara Mouth"
echo "================================================"
echo ""

# Verifica che siamo nella directory corretta
if [ ! -f "apps/mouth/fly.toml" ]; then
    echo "❌ Errore: Esegui questo script dalla root del progetto"
    exit 1
fi

# Verifica autenticazione Fly.io
echo "📋 Verifica autenticazione Fly.io..."
if ! flyctl auth whoami &>/dev/null; then
    echo "⚠️  Non autenticato. Esegui: flyctl auth login"
    exit 1
fi

echo "✅ Autenticato"
echo ""

# Verifica che le modifiche siano committate
echo "📋 Verifica modifiche..."
if git diff --quiet apps/mouth/src/app/\(workspace\)/knowledge/blueprints/page.tsx; then
    echo "✅ Modifiche già committate"
else
    echo "⚠️  Modifiche non committate. Committando..."
    git add apps/mouth/src/app/\(workspace\)/knowledge/blueprints/page.tsx
    git commit -m "fix(knowledge): remove Google Drive fallback, add download logging

- Remove window.open to Google Drive when PDF unavailable
- Add logger import and download action logging
- Add user-friendly alert instead of redirect
- Ensure all downloads work without Google Drive redirects"
    echo "✅ Modifiche committate"
fi
echo ""

# Deploy
echo "🚀 Avvio deploy..."
cd apps/mouth

if flyctl deploy --remote-only --app nuzantara-mouth; then
    echo ""
    echo "✅ Deploy completato con successo!"
    echo ""
    echo "📋 Verifica post-deploy:"
    echo "   1. Vai a https://nuzantara-mouth.fly.dev/knowledge/blueprints"
    echo "   2. Clicca su un bottone download"
    echo "   3. Verifica che NON ci sia redirect a Google Drive"
    echo ""
    echo "📊 Logs:"
    echo "   flyctl logs --app nuzantara-mouth | grep -i 'knowledge\\|blueprint\\|download'"
else
    echo ""
    echo "❌ Deploy fallito. Verifica logs sopra per dettagli."
    exit 1
fi

