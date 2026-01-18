#!/bin/bash
#
# Unified Test Force - Complete System Testing
# Tests ENTIRE system: Backend + Frontend + Integration
# Calculates unified coverage and differential
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/unified_test_force.log"
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

echo -e "${BLUE}🌐 Running Unified Test Force (Complete System)...${NC}"
log "=== Unified Test Force Run Started ==="

# Check Ollama
echo -e "${BLUE}🔍 Checking Ollama status...${NC}"
if ! "$SCRIPT_DIR/ollama_cron_window.sh" status > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Ollama not running - starting...${NC}"
    "$SCRIPT_DIR/ollama_cron_window.sh" start
    sleep 5
fi

# Set environment
export PYTHONPATH="$PROJECT_ROOT/apps/backend-rag/backend:${PYTHONPATH:-}"
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"

echo -e "${BLUE}🤖 Running Unified Test Force Orchestrator...${NC}"
log "Starting Unified Test Force with provider=local"

# Run Unified Orchestrator
cd "$PROJECT_ROOT/apps/backend-rag" || exit 1

if python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root="$PROJECT_ROOT" \
    --provider=local \
    --generate-tests \
    --max-tests=5 \
    --output="$PROJECT_ROOT/logs/unified_coverage_report.json" \
    >> "$LOG_FILE" 2>&1; then
    echo -e "${GREEN}✅ Unified Test Force completed successfully${NC}"
    log "✅ Unified Test Force completed successfully"
    
    # Show summary
    echo ""
    echo -e "${CYAN}📊 Unified Test Force Summary:${NC}"
    tail -50 "$LOG_FILE" | grep -E "Overall|Components|coverage|delta|generated" | tail -15 || true
    
else
    echo -e "${RED}❌ Unified Test Force failed - check $LOG_FILE${NC}"
    log "❌ Unified Test Force failed"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Unified Test Force automation completed${NC}"
echo -e "${BLUE}📝 Full log: $LOG_FILE${NC}"
echo -e "${BLUE}📄 Report: logs/unified_coverage_report.json${NC}"
log "=== Unified Test Force Run Completed ==="
