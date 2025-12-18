#!/bin/bash
# Check Fly.io deployment status
#
# Usage: ./check_fly_deployment.sh

APP_NAME="${FLY_APP_NAME:-nuzantara-rag}"
HEALTH_URL="https://${APP_NAME}.fly.dev/health"

echo "🔍 Reranker Optimization - Fly.io Deployment Check"
echo "App: $APP_NAME"
echo "Health URL: $HEALTH_URL"
echo ""

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check 1: Fly.io app status
echo "1. Checking Fly.io app status..."
if fly status -a "$APP_NAME" > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ App exists${NC}"
    fly status -a "$APP_NAME" | head -10
else
    echo -e "   ${RED}❌ App not found or fly CLI not configured${NC}"
    exit 1
fi

echo ""
echo "2. Checking health endpoint..."
HEALTH_RESPONSE=$(curl -s "$HEALTH_URL" 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$HEALTH_RESPONSE" ]; then
    echo -e "   ${GREEN}✅ Health endpoint responding${NC}"

    if command -v jq &> /dev/null; then
        echo ""
        echo "3. Reranker Status:"
        RERANKER_ENABLED=$(echo "$HEALTH_RESPONSE" | jq -r '.reranker.enabled // false')
        RERANKER_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.reranker.status // "unknown"')

        STATUS_COLOR=$GREEN
        if [ "$RERANKER_STATUS" != "ready" ] && [ "$RERANKER_STATUS" != "healthy" ]; then
            STATUS_COLOR=$YELLOW
        fi

        echo -e "   Enabled: $RERANKER_ENABLED"
        echo -e "   Status: ${STATUS_COLOR}$RERANKER_STATUS${NC}"

        RERANKER_STATS=$(echo "$HEALTH_RESPONSE" | jq '.reranker.stats // {}')
        if [ "$RERANKER_STATS" != "{}" ] && [ "$RERANKER_STATS" != "null" ]; then
            echo ""
            echo "   📊 Statistics:"
            echo "$HEALTH_RESPONSE" | jq '.reranker.stats | {
                total_reranks,
                avg_latency_ms,
                p95_latency_ms,
                cache_hit_rate_percent,
                target_latency_met_rate_percent,
                cache_enabled,
                cache_size
            }'
        fi
    else
        echo "   ℹ️ Install jq for detailed stats: brew install jq"
    fi
else
    echo -e "   ${RED}❌ Health endpoint not responding${NC}"
    exit 1
fi

echo ""
echo "4. Checking Fly.io secrets..."
SECRETS=$(fly secrets list -a "$APP_NAME" 2>/dev/null | grep -i reranker || echo "")
if [ -n "$SECRETS" ]; then
    echo -e "   ${GREEN}✅ Reranker secrets configured:${NC}"
    echo "$SECRETS"
else
    echo -e "   ${YELLOW}⚠️ No reranker secrets found (using defaults)${NC}"
fi

echo ""
echo -e "${GREEN}✅ Deployment check completed${NC}"
