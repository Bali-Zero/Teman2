#!/bin/bash
# Fly.io Deployment Script for Reranker Optimization
#
# Usage: ./deploy_fly.sh [stage]
# Stages: feature-flags | cache-10 | cache-50 | cache-100 | full | rollback

set -e

STAGE=${1:-feature-flags}
APP_NAME="${FLY_APP_NAME:-nuzantara-rag}"

echo "🚀 Fly.io Deployment - Reranker Optimization"
echo "App: $APP_NAME"
echo "Stage: $STAGE"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Function to set Fly.io secrets
set_fly_secret() {
    local key=$1
    local value=$2
    echo "Setting secret: $key"
    fly secrets set "$key=$value" -a "$APP_NAME" || echo "⚠️ Failed to set $key"
}

case $STAGE in
    feature-flags)
        echo -e "${YELLOW}Stage 1: Deploying with feature flags (disabled)${NC}"
        set_fly_secret "ENABLE_RERANKER" "true"
        set_fly_secret "RERANKER_CACHE_ENABLED" "false"
        set_fly_secret "RERANKER_BATCH_ENABLED" "false"
        set_fly_secret "RERANKER_AUDIT_ENABLED" "true"
        echo "✅ Feature flags configured"
        echo "📦 Deploying to Fly.io..."
        fly deploy -a "$APP_NAME"
        ;;

    cache-10)
        echo -e "${YELLOW}Stage 2: Enabling cache for 10% traffic${NC}"
        set_fly_secret "RERANKER_CACHE_ENABLED" "true"
        set_fly_secret "RERANKER_CACHE_SIZE" "100"
        echo "✅ Cache enabled (small size: 100 entries)"
        fly deploy -a "$APP_NAME"
        ;;

    cache-50)
        echo -e "${YELLOW}Stage 3: Scaling cache to 50% capacity${NC}"
        set_fly_secret "RERANKER_CACHE_SIZE" "500"
        fly deploy -a "$APP_NAME"
        ;;

    cache-100)
        echo -e "${YELLOW}Stage 4: Full cache capacity${NC}"
        set_fly_secret "RERANKER_CACHE_SIZE" "1000"
        fly deploy -a "$APP_NAME"
        ;;

    full)
        echo -e "${YELLOW}Stage 5: Full rollout${NC}"
        set_fly_secret "RERANKER_CACHE_ENABLED" "true"
        set_fly_secret "RERANKER_BATCH_ENABLED" "true"
        set_fly_secret "RERANKER_AUDIT_ENABLED" "true"
        set_fly_secret "RERANKER_CACHE_SIZE" "1000"
        set_fly_secret "RERANKER_OVERFETCH_COUNT" "20"
        set_fly_secret "RERANKER_RETURN_COUNT" "5"
        echo "✅ All features enabled"
        fly deploy -a "$APP_NAME"
        ;;

    rollback)
        echo -e "${RED}Rollback: Disabling reranker optimizations${NC}"
        set_fly_secret "RERANKER_CACHE_ENABLED" "false"
        set_fly_secret "RERANKER_BATCH_ENABLED" "false"
        fly deploy -a "$APP_NAME"
        ;;

    *)
        echo -e "${RED}Unknown stage: $STAGE${NC}"
        echo "Available stages: feature-flags | cache-10 | cache-50 | cache-100 | full | rollback"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Deployment stage '$STAGE' completed${NC}"
echo "📊 Check health: fly ssh console -a $APP_NAME -C 'curl http://localhost:8000/health'"
echo "📊 Monitor logs: fly logs -a $APP_NAME"
