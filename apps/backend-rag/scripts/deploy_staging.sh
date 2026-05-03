#!/bin/bash
# Deploy Staging Script for Nuzantara Backend
# Includes: tests, build, deploy, health checks

set -e

echo "🚀 NUZANTARA STAGING DEPLOY"
echo "============================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
STAGING_APP="nuzantara-rag-staging"
MAIN_APP="nuzantara-rag"
REGION="sin"

# Step 1: Pre-deploy checks
echo -e "\n${YELLOW}Step 1: Pre-deploy checks${NC}"
python -c "from backend.services.rag.agentic.reasoning_utils import get_critical_domain_type; print('✅ reasoning_utils OK')"
python -c "from backend.core.embeddings import EmbeddingsGenerator; print('✅ embeddings OK')"
python -c "from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval; print('✅ kg_enhanced_retrieval OK')"

# Step 2: Run critical tests
echo -e "\n${YELLOW}Step 2: Running critical tests${NC}"
python -m pytest backend/tests/unit/services/rag/agentic/test_reasoning.py -v --tb=short -q
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Tests failed! Aborting deploy.${NC}"
    exit 1
fi

# Step 3: Build Docker image
echo -e "\n${YELLOW}Step 3: Building Docker image${NC}"
docker build -t nuzantara-rag:staging .

# Step 4: Deploy to Fly staging
echo -e "\n${YELLOW}Step 4: Deploying to Fly.io staging${NC}"
fly deploy --app $STAGING_APP --region $REGION --strategy rolling

# Step 5: Health check
echo -e "\n${YELLOW}Step 5: Health check${NC}"
sleep 10
curl -s https://$STAGING_APP.fly.dev/health | jq .

# Step 6: Performance smoke test
echo -e "\n${YELLOW}Step 6: Performance smoke test${NC}"
python scripts/smoke_test.py --staging

echo -e "\n${GREEN}✅ Staging deploy completed!${NC}"
echo "URL: https://$STAGING_APP.fly.dev"
