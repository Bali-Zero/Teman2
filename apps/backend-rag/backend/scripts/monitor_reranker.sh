#!/bin/bash
# Monitoring script for Reranker Optimization
#
# Usage: ./monitor_reranker.sh [interval_seconds]

INTERVAL=${1:-10}
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"
LOG_FILE="${LOG_FILE:-reranker_monitoring.log}"

echo "📊 Reranker Optimization Monitoring"
echo "Health endpoint: $HEALTH_URL"
echo "Interval: ${INTERVAL}s"
echo "Log file: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create log file
echo "Timestamp,TotalReranks,AvgLatencyMs,P95LatencyMs,CacheHitRate,TargetMetRate,Errors" > "$LOG_FILE"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Fetch health endpoint
    HEALTH_RESPONSE=$(curl -s "$HEALTH_URL" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$HEALTH_RESPONSE" ]; then
        # Extract reranker stats (requires jq)
        if command -v jq &> /dev/null; then
            RERANKER_STATS=$(echo "$HEALTH_RESPONSE" | jq '.reranker // {}')

            TOTAL_RERANKS=$(echo "$RERANKER_STATS" | jq -r '.total_reranks // 0')
            AVG_LATENCY=$(echo "$RERANKER_STATS" | jq -r '.avg_latency_ms // 0')
            P95_LATENCY=$(echo "$RERANKER_STATS" | jq -r '.p95_latency_ms // 0')
            CACHE_HIT_RATE=$(echo "$RERANKER_STATS" | jq -r '.cache_hit_rate_percent // 0')
            TARGET_MET_RATE=$(echo "$RERANKER_STATS" | jq -r '.target_latency_met_rate_percent // 0')

            # Color coding
            LATENCY_COLOR=$GREEN
            if (( $(echo "$AVG_LATENCY > 50" | bc -l) )); then
                LATENCY_COLOR=$RED
            elif (( $(echo "$AVG_LATENCY > 40" | bc -l) )); then
                LATENCY_COLOR=$YELLOW
            fi

            CACHE_COLOR=$GREEN
            if (( $(echo "$CACHE_HIT_RATE < 20" | bc -l) )); then
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

            # Log to file
            echo "$TIMESTAMP,$TOTAL_RERANKS,$AVG_LATENCY,$P95_LATENCY,$CACHE_HIT_RATE,$TARGET_MET_RATE,0" >> "$LOG_FILE"
        else
            echo "[$TIMESTAMP] Health check OK (jq not installed, limited stats)"
            echo "$TIMESTAMP,?,?,?,?,?,0" >> "$LOG_FILE"
        fi
    else
        echo -e "${RED}[$TIMESTAMP] Health check FAILED${NC}"
        echo "$TIMESTAMP,0,0,0,0,0,1" >> "$LOG_FILE"
    fi

    sleep $INTERVAL
done
