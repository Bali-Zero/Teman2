#!/bin/bash
# Monitoring script for Fly.io deployment
#
# Usage: ./monitor_fly.sh [interval_seconds]

INTERVAL=${1:-30}
APP_NAME="${FLY_APP_NAME:-nuzantara-rag}"
HEALTH_URL="https://${APP_NAME}.fly.dev/health"

echo "📊 Reranker Optimization Monitoring - Fly.io"
echo "App: $APP_NAME"
echo "Health URL: $HEALTH_URL"
echo "Interval: ${INTERVAL}s"
echo "Press Ctrl+C to stop"
echo ""

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Fetch health endpoint
    HEALTH_RESPONSE=$(curl -s "$HEALTH_URL" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$HEALTH_RESPONSE" ]; then
        # Extract reranker stats (requires jq)
        if command -v jq &> /dev/null; then
            RERANKER_STATS=$(echo "$HEALTH_RESPONSE" | jq '.reranker.stats // {}')

            if [ "$RERANKER_STATS" != "{}" ] && [ "$RERANKER_STATS" != "null" ]; then
                TOTAL_RERANKS=$(echo "$RERANKER_STATS" | jq -r '.total_reranks // 0')
                AVG_LATENCY=$(echo "$RERANKER_STATS" | jq -r '.avg_latency_ms // 0')
                P95_LATENCY=$(echo "$RERANKER_STATS" | jq -r '.p95_latency_ms // 0')
                CACHE_HIT_RATE=$(echo "$RERANKER_STATS" | jq -r '.cache_hit_rate_percent // 0')
                TARGET_MET_RATE=$(echo "$RERANKER_STATS" | jq -r '.target_latency_met_rate_percent // 0')

                # Color coding
                LATENCY_COLOR=$GREEN
                if (( $(echo "$AVG_LATENCY > 50" | bc -l 2>/dev/null || echo "0") )); then
                    LATENCY_COLOR=$RED
                elif (( $(echo "$AVG_LATENCY > 40" | bc -l 2>/dev/null || echo "0") )); then
                    LATENCY_COLOR=$YELLOW
                fi

                CACHE_COLOR=$GREEN
                if (( $(echo "$CACHE_HIT_RATE < 20" | bc -l 2>/dev/null || echo "0") )); then
                    CACHE_COLOR=$YELLOW
                fi

                # Display
                echo -e "${BLUE}[$TIMESTAMP]${NC}"
                echo -e "  Total Reranks: $TOTAL_RERANKS"
                echo -e "  Avg Latency: ${LATENCY_COLOR}${AVG_LATENCY}ms${NC} (target: <50ms)"
                echo -e "  P95 Latency: ${LATENCY_COLOR}${P95_LATENCY}ms${NC}"
                echo -e "  Cache Hit Rate: ${CACHE_COLOR}${CACHE_HIT_RATE}%${NC} (target: >30%)"
                echo -e "  Target Met Rate: ${TARGET_MET_RATE}%"
                echo ""
            else
                echo -e "${YELLOW}[$TIMESTAMP] Reranker stats not available yet${NC}"
            fi
        else
            # Basic check without jq
            if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
                echo -e "${GREEN}[$TIMESTAMP] Service healthy${NC}"
            else
                echo -e "${RED}[$TIMESTAMP] Service unhealthy${NC}"
            fi
        fi
    else
        echo -e "${RED}[$TIMESTAMP] Health check FAILED${NC}"
    fi

    sleep $INTERVAL
done
