#!/bin/bash
# Continuous Deployment Monitoring Script
# Monitors Vercel deployment status, errors, and performance

set -e

FRONTEND_URL="https://kita.balizero.com"
BACKEND_URL="https://nuzantara-rag.fly.dev"
VERCEL_PROJECT="nuzantara-2026/mouth"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="deploy-logs/monitoring-$(date +%Y%m%d-%H%M%S).log"
mkdir -p deploy-logs

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

echo -e "${BLUE}🔍 DEPLOYMENT MONITORING${NC}"
echo "================================"
echo ""

# 1. Check Vercel Deployment Status
log "Checking Vercel deployment status..."
echo -e "${BLUE}📊 VERCEL DEPLOYMENT STATUS${NC}"
echo "--------------------------------"

LATEST_DEPLOYMENT=$(cd apps/mouth && npx vercel ls --json 2>&1 | jq -r '.[0].url' 2>/dev/null)
if [ -n "$LATEST_DEPLOYMENT" ]; then
    echo -e "${GREEN}✅ Latest Deployment: $LATEST_DEPLOYMENT${NC}"
    log "Latest deployment: $LATEST_DEPLOYMENT"
else
    echo -e "${YELLOW}⚠️  Could not fetch latest deployment${NC}"
fi

# 2. Check Frontend Health
log "Checking frontend health..."
echo ""
echo -e "${BLUE}🌐 FRONTEND HEALTH CHECK${NC}"
echo "----------------------------"

FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL")
if [ "$FRONTEND_STATUS" -eq 200 ] || [ "$FRONTEND_STATUS" -eq 307 ]; then
    echo -e "${GREEN}✅ Frontend responding (Status: $FRONTEND_STATUS)${NC}"
    log "Frontend status: $FRONTEND_STATUS"
else
    echo -e "${RED}❌ Frontend error (Status: $FRONTEND_STATUS)${NC}"
    log "ERROR: Frontend status: $FRONTEND_STATUS"
fi

# 3. Check Backend Health
log "Checking backend health..."
echo ""
echo -e "${BLUE}🔧 BACKEND HEALTH CHECK${NC}"
echo "---------------------------"

BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/health")
if [ "$BACKEND_STATUS" -eq 200 ]; then
    echo -e "${GREEN}✅ Backend responding (Status: $BACKEND_STATUS)${NC}"
    log "Backend status: $BACKEND_STATUS"
else
    echo -e "${RED}❌ Backend error (Status: $BACKEND_STATUS)${NC}"
    log "ERROR: Backend status: $BACKEND_STATUS"
fi

# 4. Check for JavaScript Errors (basic check)
log "Checking for JavaScript errors..."
echo ""
echo -e "${BLUE}🔍 ERROR CHECK${NC}"
echo "----------------"

if curl -s "$FRONTEND_URL" | grep -qi "error\|Error\|ERROR\|exception\|Exception"; then
    echo -e "${YELLOW}⚠️  Possible errors found in HTML${NC}"
    log "WARNING: Possible errors in HTML"
else
    echo -e "${GREEN}✅ No obvious errors in HTML${NC}"
    log "No obvious errors in HTML"
fi

# 5. Performance Check
log "Checking performance..."
echo ""
echo -e "${BLUE}⚡ PERFORMANCE CHECK${NC}"
echo "------------------------"

START_TIME=$(date +%s%N)
curl -s -o /dev/null "$FRONTEND_URL"
END_TIME=$(date +%s%N)
DURATION=$(( (END_TIME - START_TIME) / 1000000 ))

if [ "$DURATION" -lt 2000 ]; then
    echo -e "${GREEN}✅ Response time: ${DURATION}ms (Good)${NC}"
    log "Response time: ${DURATION}ms"
elif [ "$DURATION" -lt 5000 ]; then
    echo -e "${YELLOW}⚠️  Response time: ${DURATION}ms (Acceptable)${NC}"
    log "Response time: ${DURATION}ms (acceptable)"
else
    echo -e "${RED}❌ Response time: ${DURATION}ms (Slow)${NC}"
    log "WARNING: Slow response time: ${DURATION}ms"
fi

# 6. Summary
echo ""
echo -e "${BLUE}📊 SUMMARY${NC}"
echo "-------------"
echo "Frontend URL: $FRONTEND_URL"
echo "Backend URL: $BACKEND_URL"
echo "Log File: $LOG_FILE"
echo ""
echo "For detailed monitoring:"
echo "  - Vercel Dashboard: https://vercel.com/dashboard"
echo "  - Vercel Logs: cd apps/mouth && vercel logs <deployment-url>"
echo "  - Sentry: Check error tracking dashboard"
echo "  - Browser Console: Check for JavaScript errors"
echo ""

log "Monitoring completed"
