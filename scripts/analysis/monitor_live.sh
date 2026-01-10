#!/bin/bash
# Monitoraggio live dell'estrazione Vertex
# Esegui: bash scripts/analysis/monitor_live.sh

clear
echo "======================================================================"
echo "MONITORAGGIO LIVE - ESTRAZIONE VERTEX"
echo "======================================================================"
echo "Premi Ctrl+C per interrompere"
echo "======================================================================"
echo ""

while true; do
    clear
    echo "======================================================================"
    echo "MONITORAGGIO LIVE - ESTRAZIONE VERTEX"
    echo "======================================================================"
    echo "Ora: $(date '+%H:%M:%S')"
    echo "======================================================================"
    echo ""
    
    # Stato processo
    echo "=== PROCESSO ==="
    PROCESS=$(ps aux | grep "extract_lampiran_direct_vertex" | grep -v grep | grep python3)
    if [ -z "$PROCESS" ]; then
        echo "🔴 Processo NON TROVATO (completato o terminato)"
    else
        PID=$(echo "$PROCESS" | awk '{print $2}')
        CPU=$(echo "$PROCESS" | awk '{print $3}')
        MEM=$(echo "$PROCESS" | awk '{print $4}')
        CPU_TIME=$(echo "$PROCESS" | awk '{print $10}')
        echo "🟢 Processo ATTIVO (PID: $PID)"
        echo "   CPU: ${CPU}% | Mem: ${MEM}% | Tempo CPU: ${CPU_TIME}"
        
        # Interpreta CPU (senza bc, usa awk)
        CPU_FLOAT=$(echo "$CPU" | sed 's/%//' | awk '{print int($1)}')
        if [ "$CPU_FLOAT" -gt 5 ] 2>/dev/null; then
            echo "   ✅✅✅ CPU ALTA - Elaborazione ATTIVA!"
        elif [ "$CPU_FLOAT" -gt 1 ] 2>/dev/null; then
            echo "   ✅ CPU media - Elaborazione in corso"
        elif [ "$CPU_FLOAT" -gt 0 ] 2>/dev/null; then
            echo "   🟡 CPU bassa - In attesa di risposte API"
        else
            echo "   ⏳ CPU zero - In attesa (normale per API async)"
        fi
    fi
    echo ""
    
    # Stato estrazione
    echo "=== STATO ESTRAZIONE ==="
    python3 scripts/analysis/monitor_lampiran_extraction.py 2>/dev/null || echo "Errore esecuzione monitor"
    echo ""
    
    # Ultimi log
    echo "=== ULTIMI 15 LOG (tempo reale) ==="
    if [ -f "/tmp/vertex_analysis_full.log" ]; then
        tail -15 /tmp/vertex_analysis_full.log 2>/dev/null | grep -E "(Agent|Progress|Completato|Resoconto|PDF|Error|✅|❌|🔄)" | tail -10
    else
        echo "⚠️  Log file non trovato"
    fi
    echo ""
    
    # File più recenti
    echo "=== ULTIMI FILE CREATI ==="
    if [ -d "reports/lampiran_analysis" ]; then
        ls -lht reports/lampiran_analysis/*.json 2>/dev/null | head -3 | while read line; do
            echo "   $line"
        done
    fi
    echo ""
    
    echo "======================================================================"
    echo "Aggiornamento ogni 10 secondi... (Ctrl+C per interrompere)"
    echo "======================================================================"
    
    sleep 10
done
