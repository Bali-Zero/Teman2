#!/bin/bash
#
# Run Coverage Test Suite
# Executes all tests and generates coverage report
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag/backend"
LOG_FILE="$PROJECT_ROOT/logs/coverage_test.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$LOG_FILE")"

echo "🧪 Running Coverage Test Suite..."
echo "[$TIMESTAMP] Starting coverage tests..." >> "$LOG_FILE"

cd "$BACKEND_DIR"

export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"

# Run tests with coverage
if pytest \
    tests/unit/llm/ \
    --cov=backend.llm \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/llm \
    -v \
    >> "$LOG_FILE" 2>&1; then
    echo "✅ LLM tests passed!"
    echo "[$TIMESTAMP] ✅ LLM tests passed" >> "$LOG_FILE"
else
    echo "❌ LLM tests failed - check $LOG_FILE"
    echo "[$TIMESTAMP] ❌ LLM tests failed" >> "$LOG_FILE"
    exit 1
fi

# Run agentic tests
if pytest \
    tests/unit/services/rag/agentic/ \
    --cov=backend.services.rag.agentic \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/agentic \
    -v \
    >> "$LOG_FILE" 2>&1; then
    echo "✅ Agentic tests passed!"
    echo "[$TIMESTAMP] ✅ Agentic tests passed" >> "$LOG_FILE"
else
    echo "❌ Agentic tests failed - check $LOG_FILE"
    echo "[$TIMESTAMP] ❌ Agentic tests failed" >> "$LOG_FILE"
    exit 1
fi

echo ""
echo "📊 Coverage reports generated in htmlcov/"
echo "📝 Full log: $LOG_FILE"
