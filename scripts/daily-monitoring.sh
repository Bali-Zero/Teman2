#!/bin/bash
# Daily Monitoring Script
# Run this script daily to monitor deployment health

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/deploy-logs"
DAILY_LOG="$LOG_DIR/daily-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$DAILY_LOG"
}

echo -e "${BLUE}📊 DAILY MONITORING${NC}"
echo "===================="
echo "Date: $(date)"
echo "Log File: $DAILY_LOG"
echo ""

log "=== DAILY MONITORING STARTED ==="

# 1. Run deployment monitoring
log "Running deployment monitoring..."
"$SCRIPT_DIR/monitor-deployment.sh" >> "$DAILY_LOG" 2>&1

# 2. Check for errors in logs
log "Checking for errors..."
ERROR_COUNT=$(grep -i "error\|fail\|❌" "$DAILY_LOG" | wc -l | tr -d ' ')
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Found $ERROR_COUNT potential issues${NC}"
    log "WARNING: Found $ERROR_COUNT potential issues"
else
    echo -e "${GREEN}✅ No errors found${NC}"
    log "No errors found"
fi

# 3. Performance summary
log "Generating performance summary..."
RESPONSE_TIME=$(grep "Response time:" "$DAILY_LOG" | tail -1 | awk '{print $NF}' | tr -d 'ms')
if [ -n "$RESPONSE_TIME" ]; then
    if [ "$RESPONSE_TIME" -lt 500 ]; then
        echo -e "${GREEN}✅ Performance: ${RESPONSE_TIME}ms (Good)${NC}"
        log "Performance: ${RESPONSE_TIME}ms (Good)"
    elif [ "$RESPONSE_TIME" -lt 2000 ]; then
        echo -e "${YELLOW}⚠️  Performance: ${RESPONSE_TIME}ms (Acceptable)${NC}"
        log "Performance: ${RESPONSE_TIME}ms (Acceptable)"
    else
        echo -e "${RED}❌ Performance: ${RESPONSE_TIME}ms (Slow)${NC}"
        log "WARNING: Slow performance: ${RESPONSE_TIME}ms"
    fi
fi

# 4. Summary
echo ""
echo -e "${BLUE}📊 SUMMARY${NC}"
echo "----------"
echo "Date: $(date)"
echo "Log File: $DAILY_LOG"
echo "Errors Found: $ERROR_COUNT"
echo ""
echo "Next Steps:"
echo "  1. Review log file: $DAILY_LOG"
echo "  2. Check Vercel dashboard for detailed logs"
echo "  3. Test critical features manually"
echo "  4. Document any issues found"
echo ""

log "=== DAILY MONITORING COMPLETED ==="
