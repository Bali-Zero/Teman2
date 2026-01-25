#!/bin/bash
# Apri tutti i preview HTML degli articoli pending nel browser

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
PREVIEWS_DIR="$INTEL_DIR/data/previews"

echo "🌐 Apertura Preview HTML per Approvazione"
echo "=========================================="
echo ""

if [ ! -d "$PREVIEWS_DIR" ]; then
    echo "❌ Directory non trovata: $PREVIEWS_DIR"
    exit 1
fi

preview_files=($(ls -t "$PREVIEWS_DIR"/*.html 2>/dev/null))

if [ ${#preview_files[@]} -eq 0 ]; then
    echo "❌ Nessun preview HTML trovato"
    exit 1
fi

echo "📋 Trovati ${#preview_files[@]} preview HTML"
echo ""
echo "🌐 Apertura nel browser..."
echo ""

# Apri ogni preview nel browser
for preview_file in "${preview_files[@]}"; do
    article_id=$(basename "$preview_file" .html)
    echo "   Aprendo: $article_id"
    
    # Usa 'open' su macOS, 'xdg-open' su Linux
    if command -v open > /dev/null; then
        open "$preview_file"
    elif command -v xdg-open > /dev/null; then
        xdg-open "$preview_file"
    else
        echo "   ⚠️  Comando 'open' non disponibile - apri manualmente: $preview_file"
    fi
    
    # Delay tra aperture per evitare sovraccarico
    sleep 1
done

echo ""
echo "✅ Tutti i preview aperti nel browser"
echo ""
echo "💡 Suggerimento:"
echo "   - Controlla ogni articolo nel browser"
echo "   - Approva quelli che vuoi pubblicare"
echo "   - Usa: python3 scripts/publish_pending_articles.py per pubblicare"
