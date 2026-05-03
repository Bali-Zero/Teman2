#!/bin/bash
# Deploy backend to Fly.io production
# Includes conversation persistence system

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Deploying Backend to Fly.io${NC}"
echo ""

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo -e "${RED}❌ flyctl not found. Please install: https://fly.io/docs/hands-on/install-flyctl/${NC}"
    exit 1
fi

# Check if logged in
if ! flyctl auth whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Fly.io. Run: flyctl auth login${NC}"
    exit 1
fi

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BACKEND_DIR"

echo -e "${YELLOW}📦 Building and deploying...${NC}"
echo ""

# Deploy to Fly.io
flyctl deploy --app nuzantara-rag --region sin

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""

# Post-deploy checks (includes DB pool stale connection auto-recovery)
PREFLIGHT="$(cd "$SCRIPT_DIR/../../.." && pwd)/scripts/preflight.sh"
if [ -f "$PREFLIGHT" ]; then
    echo -e "${YELLOW}🏥 Running post-deploy checks (preflight post)...${NC}"
    bash "$PREFLIGHT" post
else
    # Fallback: basic health check
    echo -e "${YELLOW}🏥 Running health check...${NC}"
    sleep 5
    HEALTH_URL="https://nuzantara-rag.fly.dev/api/health"
    if curl -f -s "$HEALTH_URL" > /dev/null; then
        echo -e "${GREEN}✅ Health check passed${NC}"
    else
        echo -e "${RED}❌ Health check failed${NC}"
        echo "Check logs: flyctl logs -a nuzantara-rag"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Backend deployed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "API URL: https://nuzantara-rag.fly.dev"
echo "Health: $HEALTH_URL"
echo ""
echo "Monitor logs: flyctl logs -a nuzantara-rag"
echo "SSH access: flyctl ssh console -a nuzantara-rag"
