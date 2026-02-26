#!/bin/bash
# Monitor Intel Scraper e notifica articoli completi pubblicati

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
MONITOR_INTERVAL="${MONITOR_INTERVAL:-30}"  # secondi
LOG_FILE="${LOG_FILE:-logs/intel_monitor.log}"
NOTIFICATION_CHAT_ID="${TELEGRAM_APPROVAL_CHAT_ID:-1125336968}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🔍 Monitor Intel Scraper - Articoli Completi"
echo "=============================================="
echo ""
echo "📁 Directory: $INTEL_DIR"
echo "⏱️  Intervallo monitoraggio: ${MONITOR_INTERVAL}s"
echo ""

# Crea directory logs se non esiste
mkdir -p logs

# Funzione per inviare notifica Telegram
send_notification() {
    local message="$1"
    local bot_token="${TELEGRAM_BOT_TOKEN:-}"
    
    if [ -z "$bot_token" ]; then
        echo -e "${YELLOW}⚠️  TELEGRAM_BOT_TOKEN non configurato - notifica saltata${NC}"
        return
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -d "chat_id=${NOTIFICATION_CHAT_ID}" \
        -d "text=$(echo -e "$message" | sed 's/"/\\"/g')" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
}

# Funzione per monitorare nuovi articoli
monitor_articles() {
    local pending_dir="$INTEL_DIR/data/pending_articles"
    local images_dir="$INTEL_DIR/data/images"
    local previews_dir="$INTEL_DIR/data/previews"
    
    # Trova articoli con cover image
    find "$pending_dir" -name "*.json" -type f -newer "$LOG_FILE" 2>/dev/null | while read article_file; do
        article_id=$(basename "$article_file" .json)
        
        # Verifica se ha cover image
        cover_image=$(python3 -c "
import json
try:
    with open('$article_file') as f:
        data = json.load(f)
        cover = data.get('cover_image') or data.get('image_url') or ''
        title = data.get('title', 'Unknown')
        headline = data.get('headline', title)
        category = data.get('category', 'unknown')
        print(f\"{cover}|{title}|{headline}|{category}\")
except:
    pass
" 2>/dev/null)
        
        if [ -n "$cover_image" ]; then
            IFS='|' read -r cover_path title headline category <<< "$cover_image"
            
            if [ -n "$cover_path" ] && [ "$cover_path" != "None" ]; then
                # Verifica che l'immagine esista
                if [ -f "$INTEL_DIR/$cover_path" ] || [ -f "$cover_path" ]; then
                    echo -e "${GREEN}✅ Articolo completo trovato:${NC}"
                    echo "   ID: $article_id"
                    echo "   Titolo: $title"
                    echo "   Categoria: $category"
                    echo "   Cover Image: $cover_path"
                    
                    # Cerca preview HTML
                    preview_file="$previews_dir/${article_id}.html"
                    if [ -f "$preview_file" ]; then
                        echo "   Preview: $preview_file"
                    fi
                    
                    # Invia notifica
                    message="📰 *Nuovo Articolo Completo*

*Titolo:* $title
*Categoria:* $category
*ID:* \`$article_id\`

📷 Cover Image: ✅
📄 Preview: $([ -f "$preview_file" ] && echo "✅" || echo "❌")

📁 File: \`$article_file\`"
                    
                    send_notification "$message"
                    echo ""
                fi
            fi
        fi
    done
}

# Funzione per monitorare pubblicazioni GitHub
monitor_github_publishments() {
    # Cerca nei log o chiama API per verificare pubblicazioni
    local api_url="${API_URL:-https://nuzantara-rag.fly.dev}"
    
    # Verifica ultime pubblicazioni tramite API (se disponibile)
    # Questo è un esempio - adatta alla tua API
    echo -e "${BLUE}🔍 Verificando pubblicazioni...${NC}"
}

# Funzione principale di monitoraggio
main_monitor() {
    echo "🚀 Avvio monitoraggio..."
    echo "   Premi Ctrl+C per fermare"
    echo ""
    
    # Crea file di log se non esiste
    touch "$LOG_FILE"
    
    while true; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Scanning..."
        
        # Monitora nuovi articoli
        monitor_articles
        
        # Monitora pubblicazioni
        monitor_github_publishments
        
        # Aggiorna timestamp log
        touch "$LOG_FILE"
        
        sleep "$MONITOR_INTERVAL"
    done
}

# Avvia monitoraggio
main_monitor
