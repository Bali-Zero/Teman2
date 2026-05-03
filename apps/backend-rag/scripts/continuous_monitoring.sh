#!/bin/bash
# Script per monitoraggio continuo ogni 24h per 48h

set -e

DURATION_HOURS=${1:-48}
INTERVAL_HOURS=${2:-24}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor_reranking.sh"

echo "🔄 AVVIO MONITORAGGIO CONTINUO"
echo "Durata: ${DURATION_HOURS}h | Intervallo: ${INTERVAL_HOURS}h"
echo "=========================================="
echo ""

ITERATIONS=$((DURATION_HOURS / INTERVAL_HOURS))
CURRENT_ITERATION=1

while [ $CURRENT_ITERATION -le $ITERATIONS ]; do
    echo ""
    echo "📊 ITERAZIONE $CURRENT_ITERATION/$ITERATIONS - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "----------------------------------------"
    
    # Esegui monitoraggio
    bash "$MONITOR_SCRIPT"
    
    # Calcola prossima esecuzione
    if [ $CURRENT_ITERATION -lt $ITERATIONS ]; then
        echo ""
        echo "⏳ Prossima esecuzione tra ${INTERVAL_HOURS}h..."
        echo "   (Premere Ctrl+C per interrompere)"
        
        # Attendi INTERVAL_HOURS (in secondi)
        sleep $((INTERVAL_HOURS * 3600))
    fi
    
    CURRENT_ITERATION=$((CURRENT_ITERATION + 1))
done

echo ""
echo "✅ Monitoraggio completato dopo ${DURATION_HOURS}h!"
echo "📁 Controlla i file in monitoring/reranking/"
