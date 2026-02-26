#!/bin/bash
# Visualizza articoli pending per approvazione

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
PENDING_DIR="$INTEL_DIR/data/pending_articles"
PREVIEWS_DIR="$INTEL_DIR/data/previews"
PREVIEW_BASE_URL="${PREVIEW_BASE_URL:-https://bali-intel-scraper.fly.dev/preview}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "📋 Articoli Pending - Visione per Approvazione"
echo "=============================================="
echo ""

if [ ! -d "$PENDING_DIR" ]; then
    echo "❌ Directory non trovata: $PENDING_DIR"
    exit 1
fi

# Trova articoli pending
article_files=($(ls -t "$PENDING_DIR"/*.json 2>/dev/null | head -20))

if [ ${#article_files[@]} -eq 0 ]; then
    echo "❌ Nessun articolo pending trovato"
    exit 1
fi

echo -e "${GREEN}✅ Trovati ${#article_files[@]} articoli pending${NC}"
echo ""

# Mostra lista articoli con opzioni
for i in "${!article_files[@]}"; do
    article_file="${article_files[$i]}"
    article_id=$(basename "$article_file" .json)
    
    # Leggi dati articolo
    title=$(python3 -c "
import json
try:
    with open('$article_file') as f:
        data = json.load(f)
        print(data.get('title', data.get('headline', 'Unknown')))
except:
    print('Unknown')
" 2>/dev/null)
    
    category=$(python3 -c "
import json
try:
    with open('$article_file') as f:
        data = json.load(f)
        print(data.get('category', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)
    
    preview_file="$PREVIEWS_DIR/${article_id}.html"
    has_preview=false
    if [ -f "$preview_file" ]; then
        has_preview=true
    fi
    
    preview_url="$PREVIEW_BASE_URL/$article_id"
    
    echo -e "${CYAN}$((i+1)). ${title}${NC}"
    echo "   ID: $article_id"
    echo "   Categoria: $category"
    
    if [ "$has_preview" = "true" ]; then
        echo -e "   ${GREEN}📄 Preview HTML: ✅${NC}"
        echo "      Locale: $preview_file"
        echo "      Online: $preview_url"
    else
        echo -e "   ${YELLOW}📄 Preview HTML: ❌${NC}"
    fi
    
    echo ""
done

echo "=============================================="
echo ""
echo "🔍 OPZIONI PER VISIONARE:"
echo ""
echo "1. Preview HTML Locale:"
echo "   open $PREVIEWS_DIR/{article_id}.html"
echo ""
echo "2. Preview Online (se deployato):"
echo "   $PREVIEW_BASE_URL/{article_id}"
echo ""
echo "3. Telegram Approval (se configurato):"
echo "   Gli articoli vengono inviati a Telegram per approvazione"
echo ""
echo "4. News Room UI (se disponibile):"
echo "   https://zantara.balizero.com/intelligence"
echo ""
echo "📋 COMANDI RAPIDI:"
echo ""
echo "# Apri preview del primo articolo"
echo "open $PREVIEWS_DIR/$(basename ${article_files[0]} .json).html"
echo ""
echo "# Lista tutti i preview disponibili"
echo "ls -lh $PREVIEWS_DIR/*.html"
echo ""
echo "# Apri tutti i preview nel browser"
echo "for f in $PREVIEWS_DIR/*.html; do open \"\$f\"; done"
