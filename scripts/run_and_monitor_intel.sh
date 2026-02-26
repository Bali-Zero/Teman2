#!/bin/bash
# Avvia Intel Scraper e monitora articoli completi pubblicati

set -e

INTEL_DIR="${INTEL_DIR:-apps/bali-intel-scraper}"
MODE="${MODE:-full}"  # full, quick, massive, enrich-only
LOG_DIR="${LOG_DIR:-logs}"
MONITOR_SCRIPT="scripts/monitor_intel_scraper.sh"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "🚀 Avvio Intel Scraper con Monitoraggio"
echo "========================================"
echo ""
echo "📁 Directory: $INTEL_DIR"
echo "🎯 Mode: $MODE"
echo ""

# Verifica che lo script esista
if [ ! -f "$INTEL_DIR/scripts/run_intel_feed.py" ]; then
    echo -e "${RED}❌ Script non trovato: $INTEL_DIR/scripts/run_intel_feed.py${NC}"
    exit 1
fi

# Crea directory logs
mkdir -p "$LOG_DIR"

# Funzione per cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Interruzione richiesta...${NC}"
    kill $SCRAPER_PID $MONITOR_PID 2>/dev/null || true
    wait
    echo -e "${GREEN}✅ Pulizia completata${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Avvia monitor in background
echo -e "${BLUE}🔍 Avvio monitoraggio articoli...${NC}"
"$MONITOR_SCRIPT" &
MONITOR_PID=$!
echo "   Monitor PID: $MONITOR_PID"
echo ""

# Avvia scraper
echo -e "${GREEN}🚀 Avvio Intel Scraper (mode: $MODE)...${NC}"
echo ""

cd "$INTEL_DIR"

# Esegui scraper
python3 scripts/run_intel_feed.py --mode "$MODE" 2>&1 | tee "$LOG_DIR/intel_scraper_$(date +%Y%m%d_%H%M%S).log" &
SCRAPER_PID=$!

echo "   Scraper PID: $SCRAPER_PID"
echo ""
echo -e "${GREEN}✅ Intel Scraper avviato${NC}"
echo ""
echo "📊 Monitoraggio attivo:"
echo "   - Articoli completi con cover image"
echo "   - Pubblicazioni GitHub"
echo "   - Notifiche Telegram"
echo ""
echo "📋 Logs:"
echo "   - Scraper: $LOG_DIR/intel_scraper_*.log"
echo "   - Monitor: $LOG_DIR/intel_monitor.log"
echo ""
echo "⏹️  Premi Ctrl+C per fermare"
echo ""

# Attendi che lo scraper finisca
wait $SCRAPER_PID
SCRAPER_EXIT=$?

# Ferma monitor
kill $MONITOR_PID 2>/dev/null || true
wait $MONITOR_PID 2>/dev/null || true

echo ""
if [ $SCRAPER_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ Intel Scraper completato con successo${NC}"
else
    echo -e "${RED}❌ Intel Scraper terminato con errore (exit code: $SCRAPER_EXIT)${NC}"
fi

echo ""
echo "📊 Riepilogo articoli completi:"
echo "   Controlla: $INTEL_DIR/data/pending_articles/"
echo "   Immagini: $INTEL_DIR/data/images/"
echo "   Preview: $INTEL_DIR/data/previews/"
