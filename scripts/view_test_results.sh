#!/bin/bash
#
# View Test Results
# Shows test results, logs, and coverage reports
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
COVERAGE_DIR="$PROJECT_ROOT/htmlcov"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}📊 Test Results Viewer${NC}"
echo "================================"
echo ""

# Check log files
echo -e "${CYAN}📝 Log Files:${NC}"
echo ""

if [ -f "$LOG_DIR/agent_test.log" ]; then
    echo -e "${GREEN}✅ Agent Test Log:${NC}"
    echo "   Location: $LOG_DIR/agent_test.log"
    echo "   Last modified: $(stat -f "%Sm" "$LOG_DIR/agent_test.log" 2>/dev/null || stat -c "%y" "$LOG_DIR/agent_test.log" 2>/dev/null || echo "unknown")"
    echo ""
    echo "   Last 20 lines:"
    echo "   ──────────────────────────────────────"
    tail -20 "$LOG_DIR/agent_test.log" | sed 's/^/   /'
    echo "   ──────────────────────────────────────"
    echo ""
else
    echo -e "${YELLOW}⚠️  Agent test log not found${NC}"
    echo ""
fi

if [ -f "$LOG_DIR/ollama_cron.log" ]; then
    echo -e "${GREEN}✅ Ollama Cron Log:${NC}"
    echo "   Location: $LOG_DIR/ollama_cron.log"
    echo "   Last modified: $(stat -f "%Sm" "$LOG_DIR/ollama_cron.log" 2>/dev/null || stat -c "%y" "$LOG_DIR/ollama_cron.log" 2>/dev/null || echo "unknown")"
    echo ""
    echo "   Last 10 lines:"
    echo "   ──────────────────────────────────────"
    tail -10 "$LOG_DIR/ollama_cron.log" | sed 's/^/   /'
    echo "   ──────────────────────────────────────"
    echo ""
fi

# Check coverage reports
echo -e "${CYAN}📈 Coverage Reports:${NC}"
echo ""

if [ -d "$COVERAGE_DIR" ]; then
    echo -e "${GREEN}✅ Coverage reports available:${NC}"
    echo "   Location: $COVERAGE_DIR"
    echo ""
    echo "   Open in browser:"
    echo "   ${CYAN}open $COVERAGE_DIR/index.html${NC} (macOS)"
    echo "   ${CYAN}xdg-open $COVERAGE_DIR/index.html${NC} (Linux)"
    echo ""
    
    # List coverage files
    if [ -f "$COVERAGE_DIR/index.html" ]; then
        echo "   Files:"
        find "$COVERAGE_DIR" -name "*.html" -type f | head -5 | sed 's|^|     - |'
        echo ""
    fi
else
    echo -e "${YELLOW}⚠️  Coverage reports not found${NC}"
    echo "   Run: ./scripts/run_coverage_test.sh"
    echo ""
fi

# Test summary
echo -e "${CYAN}📋 Quick Summary:${NC}"
echo ""

if [ -f "$LOG_DIR/agent_test.log" ]; then
    # Extract summary from log - look for pytest summary lines
    echo "   Last run results:"
    
    # Find pytest summary (e.g., "19 passed in 0.44s")
    PYTEST_SUMMARY=$(grep -E "passed|failed|error" "$LOG_DIR/agent_test.log" | grep -E "in [0-9]+\.[0-9]+s" | tail -1)
    if [ -n "$PYTEST_SUMMARY" ]; then
        echo "     $PYTEST_SUMMARY" | sed 's/^/     /'
    fi
    
    # Find our custom summary
    CUSTOM_SUMMARY=$(grep -E "Passed: [0-9]+ \| Failed: [0-9]+" "$LOG_DIR/agent_test.log" | tail -1)
    if [ -n "$CUSTOM_SUMMARY" ]; then
        echo "     $CUSTOM_SUMMARY" | sed 's/^/     /'
    fi
    
    # Check if all passed
    if grep -q "✅ All agent tests passed" "$LOG_DIR/agent_test.log" | tail -1; then
        echo -e "     ${GREEN}✅ All tests passed!${NC}"
    elif grep -q "❌.*failed" "$LOG_DIR/agent_test.log" | tail -1; then
        echo -e "     ${RED}❌ Some tests failed${NC}"
    fi
    echo ""
fi

# Recent test runs
echo -e "${CYAN}🕐 Recent Test Runs:${NC}"
echo ""

if [ -f "$LOG_DIR/agent_test.log" ]; then
    echo "   Timestamps:"
    grep -E "^\[.*\]" "$LOG_DIR/agent_test.log" | tail -5 | sed 's/^/     /' || echo "     No timestamps found"
    echo ""
fi

# Commands
echo -e "${CYAN}🔧 Useful Commands:${NC}"
echo ""
echo "   View full log:"
echo -e "   ${CYAN}tail -f $LOG_DIR/agent_test.log${NC}"
echo ""
echo "   Run tests now:"
echo -e "   ${CYAN}./scripts/auto_agent_test.sh${NC}"
echo ""
echo "   Generate coverage:"
echo -e "   ${CYAN}./scripts/run_coverage_test.sh${NC}"
echo ""
echo "   Check Ollama status:"
echo -e "   ${CYAN}./scripts/ollama_cron_window.sh status${NC}"
echo ""
echo -e "${GREEN}💡 Tip:${NC} Run tests to see results: ./scripts/auto_agent_test.sh"
echo ""
