#!/bin/bash
# Script rapido per verificare reranking dopo una query

BASE_URL="https://nuzantara-rag.fly.dev"

echo "🔍 VERIFICA RAPIDA RERANKING"
echo "=============================="
echo ""

echo "📊 METRICHE ATTUALE:"
echo "-------------------"
METRICS=$(curl -s "$BASE_URL/metrics")

RERANK_COUNT=$(echo "$METRICS" | grep "rag_reranking_duration_seconds_count" | awk '{print $2}' || echo "0")
EARLY_EXIT=$(echo "$METRICS" | grep "^zantara_rag_early_exit_total " | awk '{print $2}' || echo "0")

echo "   Reranking calls: $RERANK_COUNT"
echo "   Early exits: $EARLY_EXIT"
echo ""

if [ "$RERANK_COUNT" != "0.0" ] && [ "$RERANK_COUNT" != "0" ]; then
    echo "✅ RERANKING ATTIVO! Sono state eseguite $RERANK_COUNT chiamate."
else
    echo "⏳ Nessuna chiamata reranking ancora (normale se non ci sono state query complesse)"
fi

echo ""
echo "📋 LOG RECENTI:"
echo "--------------"
echo "Esegui per vedere log dettagliati:"
echo "   flyctl logs -a nuzantara-rag --limit 100 | grep -E 'Re-ranking|reranked|Ze-Rank'"
echo ""

echo "🌐 URL DA TESTARE:"
echo "   Chat: https://kita.balizero.com/chat"
echo "   Omnichannel: https://kita.balizero.com/omnichannel"
echo ""
