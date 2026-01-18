#!/bin/bash
#
# Agent Test Automation with Ollama Qwen Local LLM
# Runs agentic RAG tests using real Ollama Qwen when available
#
# This script tests:
# - Reasoning module (test_reasoning.py)
# - Agentic tools (test_agentic_tools_comprehensive.py)
# - Orchestrator (test_orchestrator_*.py)
# - Router (test_agentic_rag_router.py)
# - LLM Gateway with Ollama Qwen (real LLM calls)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag"
LOG_FILE="$PROJECT_ROOT/logs/agent_test.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

echo -e "${BLUE}🤖 Running Agent Tests with Ollama Qwen...${NC}"
log "=== Agent Test Run Started ==="

# Check if Ollama is running
# During cron execution (3:30am): should be started by cron at 3:25am
# During manual execution: start it if not running (for development/testing)
echo -e "${BLUE}🔍 Checking Ollama status...${NC}"

# Check if this is a cron execution (3:30am) or manual
CURRENT_HOUR=$(date +%H)
CURRENT_MINUTE=$(date +%M)
IS_CRON_EXECUTION=false

if [ "$CURRENT_HOUR" -eq 3 ] && [ "$CURRENT_MINUTE" -ge 30 ] && [ "$CURRENT_MINUTE" -le 35 ]; then
    IS_CRON_EXECUTION=true
    echo -e "${BLUE}📅 Cron execution detected (3:30am)${NC}"
fi

if "$SCRIPT_DIR/ollama_cron_window.sh" status > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama is running${NC}"
    log "✅ Ollama running - using real LLM"
    export USE_OLLAMA_FOR_TESTS=true
    export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
    export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"
    OLLAMA_STARTED_BY_SCRIPT=false
else
    # Ollama not running - start it
    if [ "$IS_CRON_EXECUTION" = true ]; then
        echo -e "${YELLOW}⚠️  Ollama should be running (cron execution) - starting as fallback...${NC}"
    else
        echo -e "${BLUE}🚀 Starting Ollama for manual test execution...${NC}"
        echo -e "${YELLOW}   (Ollama will stay running for your development session)${NC}"
    fi
    
    if "$SCRIPT_DIR/ollama_cron_window.sh" start; then
        echo -e "${GREEN}✅ Ollama started${NC}"
        log "✅ Ollama started - using real LLM"
        export USE_OLLAMA_FOR_TESTS=true
        export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
        export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"
        OLLAMA_STARTED_BY_SCRIPT=true
        
        if [ "$IS_CRON_EXECUTION" = false ]; then
            echo -e "${BLUE}💡 Tip: Ollama will stay running. Stop it manually with:${NC}"
            echo -e "${BLUE}   ./scripts/ollama_cron_window.sh stop${NC}"
        fi
    else
        echo -e "${RED}❌ Failed to start Ollama - tests will use mocks${NC}"
        log "❌ Ollama not available - using mocks"
        export USE_OLLAMA_FOR_TESTS=false
        OLLAMA_STARTED_BY_SCRIPT=false
    fi
fi

cd "$BACKEND_DIR" || exit 1

# Set PYTHONPATH - must point to backend directory (parent of backend module)
export PYTHONPATH="$BACKEND_DIR/backend:${PYTHONPATH:-}"

# Verify we can import backend
if ! python3 -c "import sys; sys.path.insert(0, '$BACKEND_DIR/backend'); import backend" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Warning: Backend import check failed, but continuing...${NC}"
fi

# Test directories to run (more flexible than individual files)
TEST_DIRS=(
    "tests/unit/services/rag/agentic"
    "tests/unit/llm"
)

# Also try individual important test files
TEST_FILES=(
    "tests/unit/services/rag/agentic/test_reasoning.py"
    "tests/unit/services/rag/agentic/test_reasoning_comprehensive.py"
    "tests/unit/services/rag/agentic/test_agentic_tools_comprehensive.py"
    "tests/unit/services/rag/agentic/test_orchestrator_core.py"
    "tests/unit/app/routers/test_agentic_rag_router.py"
    "tests/unit/services/rag/agentic/test_llm_gateway_comprehensive.py"
    "tests/unit/llm/test_client.py"
    "tests/unit/llm/providers/test_gemini.py"
    "tests/unit/llm/providers/test_openrouter_comprehensive.py"
    "tests/unit/llm/providers/test_ollama.py"
    "tests/unit/llm/test_retry_handler.py"
    "tests/unit/llm/test_prompt_manager.py"
)

PASSED=0
FAILED=0
FAILED_TESTS=()

# First, try running test directories (more reliable)
for test_dir in "${TEST_DIRS[@]}"; do
    if [ ! -d "$test_dir" ]; then
        log "⚠️  Test directory not found: $test_dir (skipping)"
        continue
    fi
    
    dir_name=$(basename "$test_dir")
    log "Running tests in: $dir_name"
    
    if pytest "$test_dir" -v --tb=short -q -p no:xonsh >> "$LOG_FILE" 2>&1; then
        echo -e "${GREEN}✓ $dir_name tests PASSED${NC}"
        log "✅ $dir_name tests PASSED"
        # Count passed tests from pytest output
        TEST_COUNT=$(grep -E "passed|failed" "$LOG_FILE" | tail -1 | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
        PASSED=$((PASSED + TEST_COUNT))
    else
        echo -e "${RED}✗ $dir_name tests FAILED${NC}"
        log "❌ $dir_name tests FAILED"
        FAILED_TESTS+=("$dir_name")
        # Count failed tests
        TEST_COUNT=$(grep -E "passed|failed" "$LOG_FILE" | tail -1 | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
        FAILED=$((FAILED + TEST_COUNT))
    fi
done

# Then try individual test files (if directories didn't work)
if [ $PASSED -eq 0 ] && [ $FAILED -eq 0 ]; then
    log "No tests found in directories, trying individual files..."
    for test_file in "${TEST_FILES[@]}"; do
        if [ ! -f "$test_file" ]; then
            continue  # Skip silently if file doesn't exist
        fi
        
        test_name=$(basename "$test_file" .py)
        log "Running: $test_name"
        
        if pytest "$test_file" -v --tb=short -q -p no:xonsh >> "$LOG_FILE" 2>&1; then
            echo -e "${GREEN}✓ $test_name PASSED${NC}"
            log "✅ $test_name PASSED"
            ((PASSED++))
        else
            echo -e "${RED}✗ $test_name FAILED${NC}"
            log "❌ $test_name FAILED"
            FAILED_TESTS+=("$test_name")
            ((FAILED++))
        fi
    done
fi

# Summary
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Agent Test Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"

log "=== Agent Test Run Completed ==="
log "Passed: $PASSED | Failed: $FAILED"

# Cleanup: Only stop Ollama if we started it AND it's a cron execution
# For manual executions, keep Ollama running for development
CURRENT_HOUR=$(date +%H)
CURRENT_MINUTE=$(date +%M)
IS_CRON_EXECUTION=false

if [ "$CURRENT_HOUR" -eq 3 ] && [ "$CURRENT_MINUTE" -ge 30 ] && [ "$CURRENT_MINUTE" -le 35 ]; then
    IS_CRON_EXECUTION=true
fi

if [ "$OLLAMA_STARTED_BY_SCRIPT" = true ] && [ "$IS_CRON_EXECUTION" = true ]; then
    # Cron execution - cron will stop it at 3:35am anyway, but clean up if we started it
    echo -e "${BLUE}🧹 Cron execution - Ollama will be stopped by cron at 3:35am${NC}"
elif [ "$OLLAMA_STARTED_BY_SCRIPT" = true ] && [ "$IS_CRON_EXECUTION" = false ]; then
    # Manual execution - keep Ollama running for development
    echo -e "${BLUE}💡 Manual execution - Ollama will stay running for your development${NC}"
    echo -e "${BLUE}   Stop it manually when done: ./scripts/ollama_cron_window.sh stop${NC}"
fi

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All agent tests passed!${NC}"
    log "✅ All agent tests passed"
    echo ""
    echo -e "${BLUE}📊 View results:${NC}"
    echo "   Log: $LOG_FILE"
    echo "   Viewer: ./scripts/view_test_results.sh"
    exit 0
else
    echo -e "${RED}❌ Some agent tests failed:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}- $test${NC}"
    done
    log "❌ Failed tests: ${FAILED_TESTS[*]}"
    echo ""
    echo -e "${BLUE}📊 View results:${NC}"
    echo "   Log: $LOG_FILE"
    echo "   Viewer: ./scripts/view_test_results.sh"
    exit 1
fi
