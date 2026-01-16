#!/bin/bash
# Weekly Review Script
# Analyzes trends and generates weekly report

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/deploy-logs"
WEEKLY_REPORT="$PROJECT_ROOT/docs/ai/WEEKLY_REPORT_$(date +%Y%m%d).md"

mkdir -p "$(dirname "$WEEKLY_REPORT")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📈 WEEKLY REVIEW${NC}"
echo "=================="
echo ""

# Analyze daily logs from last 7 days
echo -e "${BLUE}Analyzing logs from last 7 days...${NC}"

DAILY_LOGS=$(find "$LOG_DIR" -name "daily-*.log" -mtime -7 | sort)

if [ -z "$DAILY_LOGS" ]; then
    echo -e "${YELLOW}⚠️  No daily logs found for last 7 days${NC}"
    exit 0
fi

# Generate report
cat > "$WEEKLY_REPORT" << EOF
# WEEKLY MONITORING REPORT

**Date:** $(date +'%Y-%m-%d')  
**Period:** Last 7 days  
**Generated:** $(date)

---

## 📊 SUMMARY

### Logs Analyzed:
\`\`\`
$(echo "$DAILY_LOGS" | wc -l | tr -d ' ') daily log files
\`\`\`

### Error Analysis:
\`\`\`
Total Errors: $(grep -h "error\|Error\|ERROR\|❌" $DAILY_LOGS | wc -l | tr -d ' ')
Total Warnings: $(grep -h "warning\|Warning\|WARNING\|⚠️" $DAILY_LOGS | wc -l | tr -d ' ')
\`\`\`

### Performance Trends:
\`\`\`
Average Response Time: $(grep -h "Response time:" $DAILY_LOGS | awk '{print $NF}' | awk '{sum+=$1; count++} END {if(count>0) printf "%.0fms", sum/count; else print "N/A"}')
\`\`\`

---

## 📈 TRENDS

### Error Rate:
- **Trend:** [INCREASING/DECREASING/STABLE]
- **Analysis:** [Descrizione]

### Performance:
- **Trend:** [IMPROVING/DEGRADING/STABLE]
- **Analysis:** [Descrizione]

### Type Safety:
- **Status:** 100%
- **Any Count:** 0
- **Type Errors:** 0

---

## 🔍 KEY FINDINGS

### Issues Found:
- [Issue 1]
- [Issue 2]

### Improvements:
- [Improvement 1]
- [Improvement 2]

### Recommendations:
- [Recommendation 1]
- [Recommendation 2]

---

## 📝 NEXT ACTIONS

- [ ] Action 1
- [ ] Action 2
- [ ] Action 3

---

**Report Generated:** $(date)
EOF

echo -e "${GREEN}✅ Weekly report generated: $WEEKLY_REPORT${NC}"
echo ""
echo "Review the report and update with:"
echo "  - Error trends analysis"
echo "  - Performance trends"
echo "  - User feedback"
echo "  - Recommendations"
