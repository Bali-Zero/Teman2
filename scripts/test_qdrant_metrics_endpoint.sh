#!/bin/bash
# Test script per verificare l'endpoint Qdrant metrics
# Usage: ./scripts/test_qdrant_metrics_endpoint.sh [BASE_URL]

BASE_URL="${1:-http://localhost:8000}"
ENDPOINT="${BASE_URL}/health/metrics/qdrant"

echo "🔍 Testing Qdrant Metrics Endpoint"
echo "=================================="
echo "URL: ${ENDPOINT}"
echo ""

# Test endpoint
response=$(curl -s -w "\n%{http_code}" "${ENDPOINT}")
http_code=$(echo "${response}" | tail -n1)
body=$(echo "${response}" | sed '$d')

echo "HTTP Status: ${http_code}"
echo ""

if [ "${http_code}" -eq 200 ]; then
    echo "✅ Endpoint risponde correttamente"
    echo ""
    echo "Response Body:"
    echo "${body}" | jq '.' 2>/dev/null || echo "${body}"
    echo ""

    # Verifica struttura response
    if echo "${body}" | jq -e '.status' > /dev/null 2>&1; then
        status=$(echo "${body}" | jq -r '.status')
        echo "Status: ${status}"

        if [ "${status}" = "ok" ]; then
            echo "✅ Metrics disponibili"

            # Mostra metrics chiave
            if echo "${body}" | jq -e '.metrics.search_calls' > /dev/null 2>&1; then
                search_calls=$(echo "${body}" | jq -r '.metrics.search_calls')
                echo "Search calls: ${search_calls}"
            fi

            if echo "${body}" | jq -e '.metrics.upsert_calls' > /dev/null 2>&1; then
                upsert_calls=$(echo "${body}" | jq -r '.metrics.upsert_calls')
                echo "Upsert calls: ${upsert_calls}"
            fi

            if echo "${body}" | jq -e '.metrics.errors' > /dev/null 2>&1; then
                errors=$(echo "${body}" | jq -r '.metrics.errors')
                echo "Errors: ${errors}"
            fi
        else
            echo "⚠️ Status non 'ok': ${status}"
        fi
    else
        echo "⚠️ Response non valida JSON o struttura errata"
    fi
else
    echo "❌ Endpoint non raggiungibile o errore HTTP ${http_code}"
    echo "Response: ${body}"
    exit 1
fi

echo ""
echo "✅ Test completato"


















