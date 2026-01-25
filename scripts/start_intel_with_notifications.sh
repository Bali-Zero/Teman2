#!/bin/bash
# Avvia Intel Scraper e invia notifiche per articoli completi pubblicati

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
MODE="${MODE:-full}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_APPROVAL_CHAT_ID:-1125336968}"

echo "🚀 Avvio Intel Scraper con Notifiche"
echo "====================================="
echo ""

# Verifica configurazione Telegram
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  TELEGRAM_BOT_TOKEN non configurato"
    echo "   Le notifiche saranno solo su console"
    echo ""
fi

# Avvia scraper in background e monitora output
cd "$INTEL_DIR"

echo "📊 Avvio scraper (mode: $MODE)..."
echo ""

# Esegui scraper e monitora output
python3 scripts/run_intel_feed.py --mode "$MODE" 2>&1 | while IFS= read -r line; do
    echo "$line"
    
    # Cerca pattern di articoli completi pubblicati
    if echo "$line" | grep -q "published\|article_url\|github\|mdx"; then
        echo ""
        echo "🔔 ARTICOLO PUBBLICATO TROVATO!"
        echo "   $line"
        echo ""
        
        # Invia notifica Telegram se configurato
        if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
            message="📰 *Articolo Pubblicato*

$line

🔗 Verifica pubblicazione completa"
            
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${TELEGRAM_CHAT_ID}" \
                -d "text=$(echo -e "$message" | sed 's/"/\\"/g')" \
                -d "parse_mode=Markdown" > /dev/null 2>&1 || true
        fi
    fi
done

echo ""
echo "✅ Scraper completato"
echo ""
echo "🔍 Verifica articoli completi:"
echo "   ./scripts/find_published_articles.py"
