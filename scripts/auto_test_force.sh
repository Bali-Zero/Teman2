#!/bin/bash
#
# Test Force Automation
# Runs Test Force Orchestrator with Qwen for intelligent test management
#
# This script:
# - Ensures Ollama is running (required for Qwen)
# - Runs Test Force Orchestrator (Guardian, Creator, Maintainer, Cleaner)
# - Generates, modifies, and maintains tests intelligently
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag/backend"
LOG_FILE="$PROJECT_ROOT/logs/test_force.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

echo -e "${BLUE}🎭 Running Test Force Orchestrator with Qwen...${NC}"
log "=== Test Force Run Started ==="

# Check if Ollama is running (required for Qwen)
echo -e "${BLUE}🔍 Checking Ollama status...${NC}"
if ! "$SCRIPT_DIR/ollama_cron_window.sh" status > /dev/null 2>&1; then
    echo -e "${RED}❌ Ollama is not running!${NC}"
    echo -e "${YELLOW}   Test Force requires Ollama (Qwen) to work${NC}"
    echo -e "${BLUE}   Starting Ollama...${NC}"
    
    if "$SCRIPT_DIR/ollama_cron_window.sh" start; then
        echo -e "${GREEN}✅ Ollama started${NC}"
        log "✅ Ollama started for Test Force"
        sleep 5  # Wait for Ollama to be ready
    else
        echo -e "${RED}❌ Failed to start Ollama${NC}"
        log "❌ Failed to start Ollama - Test Force cannot run"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Ollama is running${NC}"
    log "✅ Ollama running - Test Force can proceed"
fi

# Set PYTHONPATH - MUST point to backend-rag directory (parent of backend module)
export PYTHONPATH="$PROJECT_ROOT/apps/backend-rag/backend:${PYTHONPATH:-}"
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"

echo -e "${BLUE}🤖 Running Test Force Orchestrator...${NC}"
log "Starting Test Force Orchestrator with provider=local"
log "PYTHONPATH=$PYTHONPATH"
log "Working directory: $PROJECT_ROOT/apps/backend-rag"

# Run Test Force Orchestrator using Python wrapper
# Mode: scan (full scan)
# Provider: local (Ollama Qwen)
if python3 "$SCRIPT_DIR/run_test_force.py" \
    --mode=scan \
    --provider=local \
    --coverage-target=99.0 \
    >> "$LOG_FILE" 2>&1; then
    echo -e "${GREEN}✅ Test Force completed successfully${NC}"
    log "✅ Test Force completed successfully"
    
    # Extract summary from log
    echo ""
    echo -e "${CYAN}📊 Test Force Summary:${NC}"
    tail -30 "$LOG_FILE" | grep -E "Duration|completed|generated|updated|deleted" | tail -10 || true
    
else
    echo -e "${RED}❌ Test Force failed - check $LOG_FILE${NC}"
    log "❌ Test Force failed"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Test Force automation completed${NC}"
echo -e "${BLUE}📝 Full log: $LOG_FILE${NC}"
log "=== Test Force Run Completed ==="
