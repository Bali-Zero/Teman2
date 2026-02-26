#!/bin/bash
# Monitor Intel Scraper e trova articoli completi pubblicati con cover image

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
ADMIN_API_KEY="${ADMIN_API_KEY:-69ff6340462fd10b}"
GITHUB_OWNER="${GITHUB_OWNER:-Balizero1987}"
GITHUB_REPO="${GITHUB_REPO:-Teman2}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔍 Monitor Articoli Completi Intel Scraper"
echo "=========================================="
echo ""

# Funzione per verificare pubblicazione GitHub
check_github_published() {
    local article_id="$1"
    local title="$2"
    local category="$3"
    
    # Genera slug approssimativo dal titolo
    slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | cut -c1-50)
    
    # Mappa categoria a folder
    case "$category" in
        "immigration") folder="immigration" ;;
        "business") folder="business" ;;
        "tax"|"tax-legal"|"legal") folder="tax-legal" ;;
        "property") folder="property" ;;
        "lifestyle") folder="lifestyle" ;;
        "tech") folder="tech" ;;
        *) folder="$category" ;;
    esac
    
    # Verifica se file MDX esiste su GitHub
    mdx_path="apps/mouth/src/content/articles/${folder}/${slug}.mdx"
    
    # Prova a verificare via GitHub API (se token disponibile)
    if [ -n "$GITHUB_TOKEN" ]; then
        response=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
            "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${mdx_path}" 2>/dev/null || echo "")
        
        if echo "$response" | grep -q '"sha"'; then
            echo -e "${GREEN}   ✅ Pubblicato su GitHub${NC}"
            echo "      MDX: $mdx_path"
            echo "      URL: https://balizero.com/${folder}/${slug}"
            return 0
        fi
    fi
    
    # Fallback: verifica URL pubblico
    article_url="https://balizero.com/${folder}/${slug}"
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$article_url" 2>/dev/null || echo "000")
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}   ✅ Pubblicato e Live${NC}"
        echo "      URL: $article_url"
        return 0
    fi
    
    echo -e "${YELLOW}   ⏳ In attesa di pubblicazione${NC}"
    return 1
}

# Trova articoli completi
echo "📋 Scansione articoli completi..."
echo ""

PENDING_DIR="$INTEL_DIR/data/pending_articles"
IMAGES_DIR="$INTEL_DIR/data/images"
PREVIEWS_DIR="$INTEL_DIR/data/previews"

if [ ! -d "$PENDING_DIR" ]; then
    echo -e "${RED}❌ Directory non trovata: $PENDING_DIR${NC}"
    exit 1
fi

complete_count=0
published_count=0

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
        complete_count=$((complete_count + 1))
        
        echo -e "${BLUE}📰 Articolo: $title${NC}"
        echo "   ID: $article_id"
        echo "   Categoria: $category"
        
        # Verifica cover image
        image_path="$INTEL_DIR/$cover_image"
        if [ -f "$image_path" ] || [ -f "$cover_image" ]; then
            echo -e "${GREEN}   📷 Cover Image: ✅${NC}"
            echo "      Path: $cover_image"
        else
            echo -e "${YELLOW}   📷 Cover Image: ⚠️  (file non trovato)${NC}"
        fi
        
        # Verifica preview
        preview_file="$PREVIEWS_DIR/${article_id}.html"
        if [ -f "$preview_file" ]; then
            echo -e "${GREEN}   📄 Preview HTML: ✅${NC}"
            echo "      Path: $preview_file"
        else
            echo -e "${YELLOW}   📄 Preview HTML: ❌${NC}"
        fi
        
        # Verifica pubblicazione
        if check_github_published "$article_id" "$title" "$category"; then
            published_count=$((published_count + 1))
        fi
        
        echo ""
    fi
done

# Riepilogo
echo "=========================================="
echo -e "${GREEN}📊 Riepilogo:${NC}"
echo "   Articoli completi: $complete_count"
echo "   Pubblicati: $published_count"
echo "   In attesa: $((complete_count - published_count))"
echo ""
echo "📍 Posizioni:"
echo "   Pending: $PENDING_DIR"
echo "   Immagini: $IMAGES_DIR"
echo "   Preview: $PREVIEWS_DIR"
echo "   Pubblicati: GitHub → apps/mouth/src/content/articles/{category}/{slug}.mdx"
echo "   URL Pubblici: https://balizero.com/{category}/{slug}"
echo ""
echo "🔗 Per pubblicare manualmente:"
echo "   API: $API_URL/api/articles/publish"
echo "   Usa: ADMIN_API_KEY=$ADMIN_API_KEY"
