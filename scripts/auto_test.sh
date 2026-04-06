#!/bin/bash
#
# Unified Test Automation (merged from auto_test_force.sh + auto_agent_test.sh)
# Runs: 1) Agent pytest suite  2) Test Force Orchestrator (if available)
# Requires Ollama for real LLM tests
#

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag"
LOG_FILE="$PROJECT_ROOT/logs/auto_test.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

log "=== Unified Test Run Started ==="

# --- Ensure Ollama is running ---
if "$SCRIPT_DIR/ollama_cron_window.sh" status > /dev/null 2>&1; then
    log "✅ Ollama running"
    export USE_OLLAMA_FOR_TESTS=true
else
    log "Starting Ollama..."
    if "$SCRIPT_DIR/ollama_cron_window.sh" start; then
        log "✅ Ollama started"
        export USE_OLLAMA_FOR_TESTS=true
        sleep 5
    else
        log "⚠️ Ollama unavailable — tests will use mocks"
        export USE_OLLAMA_FOR_TESTS=false
    fi
fi

export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"

# --- Phase 1: Agent pytest suite ---
log "--- Phase 1: Agent pytest suite ---"
cd "$BACKEND_DIR" || exit 1
# Activate virtualenv for pytest — use full path as fallback for cron
# Prefer venv (Python 3.11, has pytest) over .venv (Python 3.13, no pytest)
if [ -d "$BACKEND_DIR/venv" ] && "$BACKEND_DIR/venv/bin/python" -c "import pytest" 2>/dev/null; then
    source "$BACKEND_DIR/venv/bin/activate" 2>/dev/null || true
    PYTEST_CMD=("$BACKEND_DIR/venv/bin/python" "-m" "pytest")
elif [ -d "$BACKEND_DIR/.venv" ] && "$BACKEND_DIR/.venv/bin/python3.13" -c "import pytest" 2>/dev/null; then
    PYTEST_CMD=("$BACKEND_DIR/.venv/bin/python3.13" "-m" "pytest")
else
    PYTEST_CMD=("python3" "-m" "pytest")
fi
export PYTHONPATH="$BACKEND_DIR:${PYTHONPATH:-}"

PASSED=0
FAILED=0
FAILED_TESTS=()

TEST_DIRS=(
    "backend/tests/unit/services/rag/agentic"
    "backend/tests/unit/llm"
)

for test_dir in "${TEST_DIRS[@]}"; do
    [ ! -d "$test_dir" ] && continue
    dir_name=$(basename "$test_dir")
    log "Running: $dir_name"
    if "${PYTEST_CMD[@]}" "$test_dir" -v --tb=short -q -p no:xonsh >> "$LOG_FILE" 2>&1; then
        log "✅ $dir_name PASSED"
        ((PASSED++))
    else
        log "❌ $dir_name FAILED"
        FAILED_TESTS+=("$dir_name")
        ((FAILED++))
    fi
done

# --- Phase 2: Test Force Orchestrator (if available) ---
if [ -f "$SCRIPT_DIR/run_test_force.py" ]; then
    log "--- Phase 2: Test Force Orchestrator ---"
    if python3 "$SCRIPT_DIR/run_test_force.py" \
        --mode=scan \
        --provider=local \
        --coverage-target=99.0 \
        >> "$LOG_FILE" 2>&1; then
        log "✅ Test Force completed"
    else
        log "⚠️ Test Force failed (non-blocking)"
    fi
else
    log "--- Phase 2: Test Force skipped (run_test_force.py not found) ---"
fi

# --- Summary ---
log "=== Unified Test Run Completed ==="
log "Agent tests — Passed: $PASSED | Failed: $FAILED"

# Load secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID)
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
TELEGRAM_CHAT_ID="${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-1125336968}}"

if [ $FAILED -eq 0 ]; then
    log "✅ All tests passed (Passed: $PASSED)"
    exit 0
else
    log "❌ Test failures: ${FAILED_TESTS[*]}"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=⚠️ *Air Auto-Test FAILED* — $FAILED suite(s): ${FAILED_TESTS[*]}%0ACheck: ~/Projects/nuzantara/logs/auto_test.log" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
    exit 1
fi
