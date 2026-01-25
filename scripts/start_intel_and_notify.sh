#!/bin/bash
# Avvia Intel Scraper e invia notifiche per articoli completi pubblicati

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
MODE="${MODE:-full}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_APPROVAL_CHAT_ID:-1125336968}"
ADMIN_API_KEY="${ADMIN_API_KEY:-69ff6340462fd10b}"

echo "🚀 Avvio Intel Scraper con Monitoraggio e Notifiche"
echo "===================================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Verifica configurazione Telegram
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  TELEGRAM_BOT_TOKEN non configurato${NC}"
    echo "   Le notifiche saranno solo su console"
    echo ""
fi

# Funzione per inviare notifica Telegram
send_notification() {
    local message="$1"
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        return
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=$(echo -e "$message" | sed 's/"/\\"/g')" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
}

# Funzione per monitorare nuovi articoli pubblicati
monitor_published() {
    local last_check=$(date +%s)
    
    while true; do
        sleep 60  # Controlla ogni minuto
        
        # Trova articoli pubblicati di recente
        ./scripts/monitor_intel_published_articles.sh 2>&1 | grep "✅ Pubblicato" | while read line; do
            echo -e "${GREEN}🔔 $line${NC}"
            
            # Estrai informazioni
            title=$(echo "$line" | grep -oP '📰 Articolo: \K[^\n]+' || echo "")
            url=$(echo "$line" | grep -oP 'URL: \K[^\n]+' || echo "")
            
            if [ -n "$title" ] && [ -n "$url" ]; then
                message="📰 *Articolo Pubblicato!*

*Titolo:* $title
*URL:* $url

✅ Articolo completo con cover image pubblicato su balizero.com"
                
                send_notification "$message"
            fi
        done
    done
}

# Avvia monitor in background
echo -e "${BLUE}🔍 Avvio monitoraggio pubblicazioni...${NC}"
monitor_published &
MONITOR_PID=$!
echo "   Monitor PID: $MONITOR_PID"
echo ""

# Avvia scraper
echo -e "${GREEN}🚀 Avvio Intel Scraper (mode: $MODE)...${NC}"
echo ""

cd "$INTEL_DIR"

# Esegui scraper
python3 scripts/run_intel_feed.py --mode "$MODE" --max-enrich 5 2>&1 | tee "../logs/intel_scraper_$(date +%Y%m%d_%H%M%S).log" &
SCRAPER_PID=$!

echo "   Scraper PID: $SCRAPER_PID"
echo ""
echo -e "${GREEN}✅ Intel Scraper avviato${NC}"
echo ""
echo "📊 Monitoraggio attivo:"
echo "   - Nuovi articoli completi"
echo "   - Cover images generate"
echo "   - Pubblicazioni GitHub"
echo "   - Notifiche Telegram"
echo ""
echo "⏹️  Premi Ctrl+C per fermare"
echo ""

# Attendi che lo scraper finisca
wait $SCRAPER_PID
SCRAPER_EXIT=$?

# Ferma monitor
kill $MONITOR_PID 2>/dev/null || true

echo ""
if [ $SCRAPER_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ Intel Scraper completato${NC}"
else
    echo -e "${RED}❌ Intel Scraper terminato con errore${NC}"
fi

echo ""
echo "📊 Verifica articoli completi:"
echo "   ./scripts/monitor_intel_published_articles.sh"
