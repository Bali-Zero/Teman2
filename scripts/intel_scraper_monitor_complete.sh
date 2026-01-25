#!/bin/bash
# Monitor completo Intel Scraper - Trova e notifica articoli pubblicati

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_APPROVAL_CHAT_ID:-1125336968}"
GITHUB_OWNER="${GITHUB_OWNER:-Balizero1987}"
GITHUB_REPO="${GITHUB_REPO:-Teman2}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔍 Monitor Completo Intel Scraper"
echo "=================================="
echo ""

# Funzione per inviare notifica Telegram
send_notification() {
    local message="$1"
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        echo -e "${YELLOW}⚠️  Telegram non configurato - notifica solo su console${NC}"
        echo ""
        echo "$message"
        return
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=$(echo -e "$message" | sed 's/"/\\"/g')" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
}

# Trova articoli completi con cover image
echo "📋 Scansione articoli completi..."
echo ""

PENDING_DIR="$INTEL_DIR/data/pending_articles"
IMAGES_DIR="$INTEL_DIR/data/images"
PREVIEWS_DIR="$INTEL_DIR/data/previews"

if [ ! -d "$PENDING_DIR" ]; then
    echo -e "${RED}❌ Directory non trovata: $PENDING_DIR${NC}"
    exit 1
fi

# Lista articoli trovati (usa file temporaneo per compatibilità)
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

for article_file in "$PENDING_DIR"/*.json; do
    [ -f "$article_file" ] || continue
    
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
    
    cover_image=$(python3 -c "
import json
try:
    with open('$article_file') as f:
        data = json.load(f)
        cover = data.get('cover_image') or data.get('image_url') or ''
        print(cover if cover and cover != 'None' else '')
except:
    print('')
" 2>/dev/null)
    
    # Verifica se ha cover image
    if [ -n "$cover_image" ] && [ "$cover_image" != "None" ]; then
        # Verifica cover image esiste
        image_path="$INTEL_DIR/$cover_image"
        has_image=false
        if [ -f "$image_path" ] || [ -f "$cover_image" ]; then
            has_image=true
        fi
        
        # Verifica preview
        preview_file="$PREVIEWS_DIR/${article_id}.html"
        has_preview=false
        if [ -f "$preview_file" ]; then
            has_preview=true
        fi
        
        # Genera slug e URL
        slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | cut -c1-50)
        
        case "$category" in
            "immigration") folder="immigration" ;;
            "business") folder="business" ;;
            "tax"|"tax-legal"|"legal") folder="tax-legal" ;;
            "property") folder="property" ;;
            "lifestyle") folder="lifestyle" ;;
            "tech") folder="tech" ;;
            *) folder="$category" ;;
        esac
        
        article_url="https://balizero.com/${folder}/${slug}"
        mdx_path="apps/mouth/src/content/articles/${folder}/${slug}.mdx"
        
        # Salva info articolo
        echo "$article_id|$title|$category|$cover_image|$has_image|$has_preview|$article_url|$mdx_path|$preview_file" >> "$TEMP_FILE"
    fi
done

# Mostra risultati
complete_count=$(wc -l < "$TEMP_FILE" 2>/dev/null || echo "0")
echo -e "${GREEN}✅ Trovati $complete_count articoli completi con cover image${NC}"
echo ""

while IFS='|' read -r article_id title category cover_image has_image has_preview article_url mdx_path preview_file; do
    
    echo -e "${BLUE}📰 $title${NC}"
    echo "   ID: $article_id"
    echo "   Categoria: $category"
    
    if [ "$has_image" = "true" ]; then
        echo -e "${GREEN}   📷 Cover Image: ✅${NC}"
        echo "      Path: $cover_image"
    else
        echo -e "${YELLOW}   📷 Cover Image: ⚠️  (path: $cover_image)${NC}"
    fi
    
    if [ "$has_preview" = "true" ]; then
        echo -e "${GREEN}   📄 Preview HTML: ✅${NC}"
        echo "      Path: $preview_file"
    else
        echo -e "${YELLOW}   📄 Preview HTML: ❌${NC}"
    fi
    
    echo "   🔗 URL Previsto: $article_url"
    echo "   📁 MDX Path: $mdx_path"
    echo ""
done < "$TEMP_FILE"

# Riepilogo
echo "=========================================="
echo -e "${GREEN}📊 Riepilogo:${NC}"
echo "   Articoli completi: $complete_count"
echo "   Con cover image file: $(echo "${articles_found[@]}" | tr '|' '\n' | grep -c "true" || echo "0")"
echo "   Con preview HTML: $(echo "${articles_found[@]}" | tr '|' '\n' | grep -c "true" || echo "0")"
echo ""
echo "📍 Posizioni:"
echo "   📄 Pending: $PENDING_DIR"
echo "   🖼️  Immagini: $IMAGES_DIR"
echo "   📋 Preview: $PREVIEWS_DIR"
echo "   🚀 Pubblicati: GitHub → $mdx_path"
echo "   🌐 URL Pubblici: https://balizero.com/{category}/{slug}"
echo ""

# Invia notifica se configurato
if [ "$complete_count" -gt 0 ]; then
    message="📰 *Articoli Completi Intel Scraper*

Trovati *$complete_count* articoli completi con cover image:

"
    
    count=1
    while IFS='|' read -r article_id title category cover_image has_image has_preview article_url mdx_path preview_file; do
        
        message+="$count. *$title*
   Categoria: \`$category\`
   ID: \`$article_id\`
   URL: $article_url
"
        count=$((count + 1))
        
        if [ $count -gt 5 ]; then
            message+="   ... e altri $((complete_count - 5)) articoli"
            break
        fi
    done < "$TEMP_FILE"
    
    message+="
📍 Posizioni:
   • Pending: \`data/pending_articles/\`
   • Preview: \`data/previews/\`
   • Pubblicati: GitHub → \`apps/mouth/src/content/articles/\`
   • URL: https://balizero.com/{category}/{slug}"
    
    send_notification "$message"
fi

echo "🔔 Notifica inviata (se Telegram configurato)"
echo ""
echo "📋 Per pubblicare manualmente:"
echo "   API: $API_URL/api/articles/publish"
echo "   Usa: ADMIN_API_KEY=69ff6340462fd10b"
