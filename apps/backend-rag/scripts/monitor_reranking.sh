#!/bin/bash
# Script per monitorare reranking ogni 24h per 48h
# Esegue snapshot delle metriche e analisi costi

set -e

BASE_URL="https://nuzantara-rag.fly.dev"
OUTPUT_DIR="monitoring/reranking"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DURATION_HOURS=${1:-48}  # Default 48h
INTERVAL_HOURS=${2:-24}  # Default ogni 24h

mkdir -p "$OUTPUT_DIR"

echo "📊 MONITORAGGIO RERANKING - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Durata: ${DURATION_HOURS}h | Intervallo: ${INTERVAL_HOURS}h"
echo "=========================================="
echo ""

# Funzione per catturare snapshot metriche
capture_snapshot() {
    local snapshot_file="$OUTPUT_DIR/snapshot_${TIMESTAMP}.txt"
    local metrics_file="$OUTPUT_DIR/metrics_${TIMESTAMP}.txt"
    
    echo "📸 Catturando snapshot metriche..."
    
    # Cattura tutte le metriche reranking
    curl -s "$BASE_URL/metrics" > "$metrics_file"
    
    # Estrai metriche chiave
    {
        echo "=== RERANKING METRICS SNAPSHOT ==="
        echo "Timestamp: $(date -Iseconds)"
        echo ""
        echo "--- Reranking Duration ---"
        grep "rag_reranking_duration_seconds" "$metrics_file" | head -10
        echo ""
        echo "--- Early Exit ---"
        grep "^zantara_rag_early_exit_total " "$metrics_file"
        echo ""
        echo "--- Context Length ---"
        grep "rag_context_length_tokens" "$metrics_file" | tail -5
        echo ""
        echo "--- Pipeline Duration ---"
        grep "rag_pipeline_duration_seconds" "$metrics_file" | head -5
    } > "$snapshot_file"
    
    echo "✅ Snapshot salvato: $snapshot_file"
    cat "$snapshot_file"
}

# Funzione per analisi costi
analyze_costs() {
    local analysis_file="$OUTPUT_DIR/cost_analysis_${TIMESTAMP}.md"
    
    echo ""
    echo "💰 ANALISI COSTI..."
    
    METRICS=$(curl -s "$BASE_URL/metrics")
    
    RERANK_COUNT=$(echo "$METRICS" | grep "rag_reranking_duration_seconds_count" | awk '{print $2}' || echo "0")
    EARLY_EXIT=$(echo "$METRICS" | grep "^zantara_rag_early_exit_total " | awk '{print $2}' || echo "0")
    
    # Stima costi (da aggiornare con valori reali)
    ZERANK_COST_PER_CALL=0.0001  # Esempio, da verificare
    GEMINI_SAVINGS_PER_QUERY=0.00028  # Media stimata
    
    TOTAL_RERANK_CALLS=$RERANK_COUNT
    TOTAL_EARLY_EXITS=$EARLY_EXIT
    TOTAL_QUERIES=$((TOTAL_RERANK_CALLS + TOTAL_EARLY_EXITS))
    
    ZERANK_COST=$(echo "$TOTAL_RERANK_CALLS * $ZERANK_COST_PER_CALL" | bc)
    GEMINI_SAVINGS=$(echo "$TOTAL_RERANK_CALLS * $GEMINI_SAVINGS_PER_QUERY" | bc)
    NET_SAVINGS=$(echo "$GEMINI_SAVINGS - $ZERANK_COST" | bc)
    
    {
        echo "# 💰 ANALISI COSTI RERANKING"
        echo ""
        echo "**Data**: $(date -Iseconds)"
        echo ""
        echo "## 📊 Statistiche"
        echo ""
        echo "- **Query totali**: $TOTAL_QUERIES"
        echo "- **Reranking calls**: $TOTAL_RERANK_CALLS"
        echo "- **Early exits**: $TOTAL_EARLY_EXITS"
        echo "- **Early exit rate**: $(echo "scale=2; $TOTAL_EARLY_EXITS * 100 / ($TOTAL_QUERIES + 1)" | bc)%"
        echo ""
        echo "## 💵 Costi"
        echo ""
        echo "- **Costo ZeRank**: \$$(echo "scale=6; $ZERANK_COST" | bc)"
        echo "- **Risparmio Gemini**: \$$(echo "scale=6; $GEMINI_SAVINGS" | bc)"
        echo "- **Risparmio netto**: \$$(echo "scale=6; $NET_SAVINGS" | bc)"
        echo ""
        echo "## 📈 ROI"
        echo ""
        if (( $(echo "$NET_SAVINGS > 0" | bc -l) )); then
            echo "✅ **ROI POSITIVO**: Reranking genera risparmio netto"
        else
            echo "⚠️ **ROI NEGATIVO**: Costi ZeRank superano risparmio Gemini"
        fi
        echo ""
        echo "## 📝 Note"
        echo ""
        echo "- Costi ZeRank per chiamata: \$$ZERANK_COST_PER_CALL (da verificare su dashboard)"
        echo "- Risparmio Gemini per query: \$$GEMINI_SAVINGS_PER_QUERY (stimato)"
        echo "- Verificare valori reali su dashboard ZeroEntropy"
    } > "$analysis_file"
    
    echo "✅ Analisi salvata: $analysis_file"
    cat "$analysis_file"
}

# Funzione per valutazione precisione
evaluate_precision() {
    local precision_file="$OUTPUT_DIR/precision_${TIMESTAMP}.md"
    
    echo ""
    echo "🎯 VALUTAZIONE PRECISIONE..."
    
    METRICS=$(curl -s "$BASE_URL/metrics")
    
    # Estrai evidence score (se disponibile)
    EVIDENCE_SCORE=$(echo "$METRICS" | grep "rag_evidence_score" | tail -1 | awk '{print $2}' || echo "N/A")
    
    {
        echo "# 🎯 VALUTAZIONE PRECISIONE RERANKING"
        echo ""
        echo "**Data**: $(date -Iseconds)"
        echo ""
        echo "## 📊 Metriche Qualità"
        echo ""
        echo "- **Evidence Score**: $EVIDENCE_SCORE"
        echo ""
        echo "## 📝 Note"
        echo ""
        echo "Per valutazione completa precisione:"
        echo "1. Confrontare risultati con/senza reranking"
        echo "2. Misurare precision@5 (top 5 risultati rilevanti)"
        echo "3. Raccogliere feedback utenti"
        echo "4. Analizzare ranking quality"
    } > "$precision_file"
    
    echo "✅ Valutazione salvata: $precision_file"
    cat "$precision_file"
}

# Esegui monitoraggio
capture_snapshot
analyze_costs
evaluate_precision

echo ""
echo "✅ Monitoraggio completato!"
echo "📁 File salvati in: $OUTPUT_DIR/"
