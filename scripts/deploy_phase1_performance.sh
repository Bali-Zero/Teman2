#!/bin/bash
#
# Deploy Phase 1 Performance Optimizations
# Commits, pushes, and monitors deployment
#

set -e

echo "🚀 Deploying Phase 1 Performance Optimizations"
echo "================================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not a git repository${NC}"
    exit 1
fi

# Check for uncommitted changes
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  No changes to commit${NC}"
else
    echo -e "${GREEN}📝 Staging changes...${NC}"
    git add apps/backend-rag/backend/services/golden_answer_service.py
    git add apps/backend-rag/backend/services/search_service.py
    git add apps/backend-rag/backend/app/metrics.py
    git add scripts/benchmark_performance.py
    git add docs/debug/performance/
    git add scripts/performance_profiler.py
    
    echo -e "${GREEN}💾 Committing changes...${NC}"
    git commit -m "perf: Phase 1 performance optimizations - Database & RAG Pipeline

- Increase GoldenAnswerService connection pool (min=5, max=20)
- Add early exit for reranking when score > 0.9
- Add Prometheus metrics for RAG pipeline performance tracking
- Implement performance monitoring for embedding, search, reranking
- Add benchmark script for before/after comparison
- Add comprehensive performance debugging documentation

Expected improvements:
- RAG Pipeline: -20% total time
- Database Query: -30% query time  
- Early Exit Rate: >30% of queries
- Connection Pool: no wait time

See docs/debug/performance/ for details"
    
    echo -e "${GREEN}✅ Commit created${NC}"
fi

# Show current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo -e "${GREEN}📍 Current branch: ${BRANCH}${NC}"

# Ask for confirmation before push
read -p "Push to remote? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}📤 Pushing to remote...${NC}"
    git push origin "$BRANCH"
    echo -e "${GREEN}✅ Pushed successfully${NC}"
else
    echo -e "${YELLOW}⏭️  Skipping push${NC}"
    exit 0
fi

# Check if Fly.io is configured
if command -v fly &> /dev/null; then
    echo -e "${GREEN}🪂 Checking Fly.io deployment...${NC}"
    
    # Check if fly.toml exists
    if [ -f "apps/backend-rag/fly.toml" ] || [ -f "fly.toml" ]; then
        echo -e "${GREEN}📋 Fly.io configuration found${NC}"
        read -p "Deploy to Fly.io? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}🚀 Deploying to Fly.io...${NC}"
            cd apps/backend-rag 2>/dev/null || cd .
            fly deploy --app nuzantara-rag || fly deploy
            echo -e "${GREEN}✅ Deployment initiated${NC}"
            
            echo -e "${GREEN}📊 Monitoring deployment...${NC}"
            echo "Check status with: fly status --app nuzantara-rag"
            echo "View logs with: fly logs --app nuzantara-rag"
        fi
    else
        echo -e "${YELLOW}⚠️  No fly.toml found, skipping Fly.io deploy${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Fly.io CLI not found, skipping Fly.io deploy${NC}"
fi

# Check for deployment configuration
if [ -f "fly.toml" ] || [ -d "apps/backend-rag" ]; then
    echo -e "${GREEN}🔄 Deployment pipeline detected${NC}"
fi

echo ""
echo -e "${GREEN}✅ Deployment process completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Monitor deployment status"
echo "2. Check Prometheus metrics: http://your-backend-url/metrics"
echo "3. Run benchmark comparison: python scripts/benchmark_performance.py --compare"
echo "4. Verify improvements in production"

