#!/bin/bash
# Test Semantic Deduplication usando secrets da Fly.io
# Questo script recupera le chiavi da Fly.io e le usa per il test

set -e

echo "🔐 Recupero secrets da Fly.io..."

# Recupera le chiavi (senza mostrarle)
export QDRANT_URL=$(fly secrets list -a nuzantara-rag --json 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print([s['Name'] for s in data if s['Name'] == 'QDRANT_URL'][0] if any(s['Name'] == 'QDRANT_URL' for s in data) else 'https://nuzantara-qdrant.fly.dev')")
export QDRANT_API_KEY=$(fly secrets list -a nuzantara-rag --json 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print([s['Digest'] for s in data if s['Name'] == 'QDRANT_API_KEY'][0] if any(s['Name'] == 'QDRANT_API_KEY' for s in data) else '')")
export OPENAI_API_KEY=$(fly secrets list -a nuzantara-rag --json 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print([s['Digest'] for s in data if s['Name'] == 'OPENAI_API_KEY'][0] if any(s['Name'] == 'OPENAI_API_KEY' for s in data) else '')")

# Nota: I digest non sono le chiavi reali, solo hash
# Per un test reale, dobbiamo eseguire su Fly.io o aggiungere le chiavi al .env

echo "⚠️  I secrets su Fly.io sono criptati."
echo "   Per testare localmente, aggiungi le chiavi al .env:"
echo "   - QDRANT_API_KEY=..."
echo "   - OPENAI_API_KEY=..."
echo ""
echo "   Oppure esegui il test direttamente su Fly.io:"
echo "   fly ssh console -a nuzantara-rag"
echo "   cd /app && python apps/bali-intel-scraper/scripts/test_complete_setup.py"
