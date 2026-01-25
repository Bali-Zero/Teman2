#!/bin/bash
# Script interattivo per visionare e approvare articoli prima della pubblicazione

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
PENDING_DIR="$INTEL_DIR/data/pending_articles"
PREVIEWS_DIR="$INTEL_DIR/data/previews"
ADMIN_API_KEY="${ADMIN_API_KEY:-69ff6340462fd10b}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo "📋 Approvazione e Pubblicazione Articoli"
echo "========================================"
echo ""

if [ ! -d "$PENDING_DIR" ]; then
    echo -e "${RED}❌ Directory non trovata: $PENDING_DIR${NC}"
    exit 1
fi

# Trova articoli pending
article_files=($(ls -t "$PENDING_DIR"/*.json 2>/dev/null))

if [ ${#article_files[@]} -eq 0 ]; then
    echo -e "${RED}❌ Nessun articolo pending trovato${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Trovati ${#article_files[@]} articoli pending${NC}"
echo ""

# Mostra lista articoli
declare -a selected_articles

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
    
    echo -e "${CYAN}$((i+1)). ${title}${NC}"
    echo "   ID: $article_id | Categoria: $category"
    
    if [ "$has_preview" = "true" ]; then
        echo -e "   ${GREEN}📄 Preview disponibile${NC}"
    else
        echo -e "   ${YELLOW}📄 Preview non disponibile${NC}"
    fi
    
    echo ""
done

echo "========================================"
echo ""
echo "🔍 OPZIONI:"
echo ""
echo "1. Visiona preview di un articolo specifico"
echo "2. Visiona tutti i preview"
echo "3. Seleziona articoli da pubblicare"
echo "4. Pubblica tutti gli articoli"
echo "5. Esci"
echo ""

read -p "Scegli opzione (1-5): " choice

case $choice in
    1)
        read -p "Inserisci numero articolo da visionare (1-${#article_files[@]}): " num
        if [ "$num" -ge 1 ] && [ "$num" -le "${#article_files[@]}" ]; then
            idx=$((num-1))
            article_file="${article_files[$idx]}"
            article_id=$(basename "$article_file" .json)
            preview_file="$PREVIEWS_DIR/${article_id}.html"
            
            if [ -f "$preview_file" ]; then
                echo ""
                echo "🌐 Apertura preview nel browser..."
                open "$preview_file"
                echo -e "${GREEN}✅ Preview aperto${NC}"
            else
                echo -e "${RED}❌ Preview non trovato${NC}"
            fi
        else
            echo -e "${RED}❌ Numero non valido${NC}"
        fi
        ;;
    2)
        echo ""
        echo "🌐 Apertura tutti i preview..."
        ./scripts/open_all_previews.sh
        ;;
    3)
        echo ""
        echo "📝 Seleziona articoli da pubblicare (separati da virgola, es: 1,3,5):"
        read -p "Numeri articoli: " selection
        
        IFS=',' read -ra nums <<< "$selection"
        for num in "${nums[@]}"; do
            num=$(echo "$num" | tr -d ' ')
            if [ "$num" -ge 1 ] && [ "$num" -le "${#article_files[@]}" ]; then
                idx=$((num-1))
                selected_articles+=("${article_files[$idx]}")
            fi
        done
        
        if [ ${#selected_articles[@]} -gt 0 ]; then
            echo ""
            echo -e "${GREEN}✅ Selezionati ${#selected_articles[@]} articoli:${NC}"
            for article_file in "${selected_articles[@]}"; do
                article_id=$(basename "$article_file" .json)
                title=$(python3 -c "
import json
with open('$article_file') as f:
    data = json.load(f)
    print(data.get('title', 'Unknown'))
" 2>/dev/null)
                echo "   - $title"
            done
            
            echo ""
            read -p "Pubblicare questi articoli? (s/n): " confirm
            if [ "$confirm" = "s" ]; then
                echo ""
                echo "🚀 Pubblicazione articoli selezionati..."
                export ADMIN_API_KEY="$ADMIN_API_KEY"
                
                # Pubblica solo gli articoli selezionati
                for article_file in "${selected_articles[@]}"; do
                    python3 scripts/publish_pending_articles.py --article "$article_file"
                done
            fi
        else
            echo -e "${RED}❌ Nessun articolo valido selezionato${NC}"
        fi
        ;;
    4)
        echo ""
        read -p "⚠️  Pubblicare TUTTI gli articoli? (s/n): " confirm
        if [ "$confirm" = "s" ]; then
            echo ""
            echo "🚀 Pubblicazione tutti gli articoli..."
            export ADMIN_API_KEY="$ADMIN_API_KEY"
            python3 scripts/publish_pending_articles.py
        else
            echo "❌ Operazione annullata"
        fi
        ;;
    5)
        echo "👋 Arrivederci!"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Opzione non valida${NC}"
        exit 1
        ;;
esac
