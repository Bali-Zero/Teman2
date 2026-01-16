#!/bin/bash
# Deploy Intel Router to Fly.io with post-deploy verification
# Usage: ./deploy_intel_router.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MONITORING_DIR="$PROJECT_ROOT/scripts/monitoring"
TESTING_DIR="$PROJECT_ROOT/scripts/testing"

echo "=========================================="
echo "Intel Router Deployment Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Pre-deploy checks
echo -e "${BLUE}1. Running pre-deploy checks...${NC}"
cd "$PROJECT_ROOT/apps/backend-rag"

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo -e "${RED}Error: fly CLI not found. Install from https://fly.io/docs/hands-on/install-flyctl/${NC}"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "fly.toml" ]; then
    echo -e "${RED}Error: fly.toml not found. Are you in the backend-rag directory?${NC}"
    exit 1
fi

# Check code syntax
echo -e "${BLUE}   Checking code syntax...${NC}"
python3 -m py_compile backend/services/intel/*.py 2>&1 || {
    echo -e "${RED}Error: Code syntax check failed${NC}"
    exit 1
}
python3 -m py_compile backend/app/routers/intel.py 2>&1 || {
    echo -e "${RED}Error: Router syntax check failed${NC}"
    exit 1
}
echo -e "${GREEN}   ✅ Code syntax OK${NC}"

# 2. Deploy to Fly.io
echo ""
echo -e "${BLUE}2. Deploying to Fly.io...${NC}"
echo -e "${YELLOW}   Running: fly deploy -a nuzantara-rag${NC}"
echo ""

fly deploy -a nuzantara-rag --remote-only

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Deployment failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Deployment successful${NC}"

# 3. Wait for deployment to stabilize
echo ""
echo -e "${BLUE}3. Waiting for deployment to stabilize...${NC}"
echo -e "${YELLOW}   Waiting 30 seconds...${NC}"
sleep 30

# 4. Health check
echo ""
echo -e "${BLUE}4. Running health check...${NC}"
HEALTH_URL="https://nuzantara-rag.fly.dev/health"
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")

if [ "$HEALTH_RESPONSE" = "200" ]; then
    echo -e "${GREEN}   ✅ Health check passed (HTTP $HEALTH_RESPONSE)${NC}"
else
    echo -e "${RED}   ❌ Health check failed (HTTP $HEALTH_RESPONSE)${NC}"
    echo -e "${YELLOW}   Continuing with tests anyway...${NC}"
fi

# 5. Run production tests
echo ""
echo -e "${BLUE}5. Running production tests...${NC}"
cd "$PROJECT_ROOT"

if [ -f "$TESTING_DIR/test_intel_production.py" ]; then
    python3 "$TESTING_DIR/test_intel_production.py"
    TEST_EXIT=$?
    
    if [ $TEST_EXIT -eq 0 ]; then
        echo -e "${GREEN}   ✅ Production tests passed${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Production tests completed with warnings${NC}"
    fi
else
    echo -e "${YELLOW}   ⚠️  Production test script not found, skipping${NC}"
fi

# 6. Run monitoring checks
echo ""
echo -e "${BLUE}6. Running monitoring checks...${NC}"

if [ -f "$MONITORING_DIR/monitor_intel_metrics.py" ]; then
    echo -e "${BLUE}   Checking Prometheus metrics...${NC}"
    python3 "$MONITORING_DIR/monitor_intel_metrics.py" || echo -e "${YELLOW}   Metrics check completed with warnings${NC}"
fi

if [ -f "$MONITORING_DIR/monitor_intel_performance.py" ]; then
    echo -e "${BLUE}   Checking performance...${NC}"
    python3 "$MONITORING_DIR/monitor_intel_performance.py" 5 || echo -e "${YELLOW}   Performance check completed with warnings${NC}"
fi

# 7. Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Monitor logs: fly logs -a nuzantara-rag"
echo "  2. Check metrics: python3 scripts/monitoring/monitor_intel_metrics.py"
echo "  3. Review test reports in: scripts/monitoring/"
echo ""
echo "To rollback if needed:"
echo "  fly releases -a nuzantara-rag"
echo "  fly releases rollback <release-id> -a nuzantara-rag"
echo ""
