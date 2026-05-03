#!/bin/bash
# Deployment script for Reranker Optimization (Zero-Downtime)
#
# Usage: ./deploy_reranker.sh [stage]
# Stages: feature-flags | cache-10 | cache-50 | cache-100 | full | rollback

set -e

STAGE=${1:-feature-flags}
ENV_FILE="${ENV_FILE:-.env}"

echo "🚀 Reranker Optimization Deployment - Stage: $STAGE"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to update env file
update_env() {
    local key=$1
    local value=$2
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        sed -i.bak "s/^${key}=.*/${key}=${value}/" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

# Function to wait for health check
wait_for_health() {
    local url=${1:-"http://localhost:8000/health"}
    local max_attempts=30
    local attempt=0

    echo "⏳ Waiting for service to be healthy..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Service is healthy${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "   Attempt $attempt/$max_attempts..."
        sleep 2
    done

    echo -e "${RED}❌ Service health check failed after $max_attempts attempts${NC}"
    return 1
}

# Function to check reranker stats
check_reranker_stats() {
    echo "📊 Checking reranker statistics..."
    curl -s "http://localhost:8000/health" | jq '.reranker // {}' || echo "Stats not available"
}

case $STAGE in
    feature-flags)
        echo -e "${YELLOW}Stage 1: Deploying with feature flags (disabled)${NC}"
        update_env "ENABLE_RERANKER" "true"
        update_env "RERANKER_CACHE_ENABLED" "false"
        update_env "RERANKER_BATCH_ENABLED" "false"
        update_env "RERANKER_AUDIT_ENABLED" "true"
        echo "✅ Feature flags deployed (cache/batch disabled, audit enabled)"
        ;;

    cache-10)
        echo -e "${YELLOW}Stage 2: Enabling cache for 10% traffic${NC}"
        update_env "RERANKER_CACHE_ENABLED" "true"
        update_env "RERANKER_CACHE_SIZE" "100"
        echo "✅ Cache enabled (small size: 100 entries)"
        echo "📊 Monitor cache hit rate over next 10 minutes"
        ;;

    cache-50)
        echo -e "${YELLOW}Stage 3: Scaling cache to 50% capacity${NC}"
        update_env "RERANKER_CACHE_SIZE" "500"
        echo "✅ Cache size increased to 500 entries"
        ;;

    cache-100)
        echo -e "${YELLOW}Stage 4: Full cache capacity${NC}"
        update_env "RERANKER_CACHE_SIZE" "1000"
        echo "✅ Cache at full capacity (1000 entries)"
        ;;

    full)
        echo -e "${YELLOW}Stage 5: Full rollout${NC}"
        update_env "RERANKER_CACHE_ENABLED" "true"
        update_env "RERANKER_BATCH_ENABLED" "true"
        update_env "RERANKER_AUDIT_ENABLED" "true"
        update_env "RERANKER_CACHE_SIZE" "1000"
        update_env "RERANKER_OVERFETCH_COUNT" "20"
        update_env "RERANKER_RETURN_COUNT" "5"
        echo "✅ All features enabled"
        ;;

    rollback)
        echo -e "${RED}Rollback: Disabling reranker optimizations${NC}"
        update_env "RERANKER_CACHE_ENABLED" "false"
        update_env "RERANKER_BATCH_ENABLED" "false"
        echo "✅ Reranker optimizations disabled (fallback to basic mode)"
        ;;

    *)
        echo -e "${RED}Unknown stage: $STAGE${NC}"
        echo "Available stages: feature-flags | cache-10 | cache-50 | cache-100 | full | rollback"
        exit 1
        ;;
esac

echo ""
echo "📋 Current configuration:"
grep "RERANKER" "$ENV_FILE" | grep -v "^#" || echo "No RERANKER config found"

echo ""
echo "🔄 Restarting service..."
# Note: Actual restart depends on deployment platform (Fly.io, Docker, etc.)
# For Fly.io: fly deploy
# For Docker: docker-compose restart backend
# For local: kill -HUP <pid> or restart service

wait_for_health

echo ""
check_reranker_stats

echo ""
echo -e "${GREEN}✅ Deployment stage '$STAGE' completed${NC}"
echo "📊 Monitor metrics: ./scripts/monitor_reranker.sh"
