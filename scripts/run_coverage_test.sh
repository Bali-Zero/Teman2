#!/bin/bash
#
# Run Coverage Test Suite
# Executes all tests and generates coverage report
#

# Don't exit on error - we want to continue and see coverage even if some tests fail
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag"
LOG_FILE="$PROJECT_ROOT/logs/coverage_test.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$LOG_FILE")"

echo "🧪 Running Coverage Test Suite..."
echo "[$TIMESTAMP] Starting coverage tests..." >> "$LOG_FILE"

cd "$BACKEND_DIR" || exit 1

# Set PYTHONPATH - must point to backend directory (parent of backend module)
export PYTHONPATH="$BACKEND_DIR/backend:${PYTHONPATH:-}"

# Run tests with coverage - execute on subdirectories separately to avoid name conflicts
# First, run adapters tests
if pytest \
    backend/tests/unit/llm/adapters/ \
    --cov=backend.llm \
    --cov-append \
    --cov-report=term-missing \
    -v \
    >> "$LOG_FILE" 2>&1; then
    echo "✅ LLM adapters tests passed!"
else
    echo "❌ LLM adapters tests failed - check $LOG_FILE"
    echo "[$TIMESTAMP] ❌ LLM adapters tests failed" >> "$LOG_FILE"
    exit 1
fi

# Then, run providers tests
if pytest \
    backend/tests/unit/llm/providers/ \
    --cov=backend.llm \
    --cov-append \
    --cov-report=term-missing \
    -v \
    >> "$LOG_FILE" 2>&1; then
    echo "✅ LLM providers tests passed!"
else
    echo "⚠️  LLM providers tests had failures - check $LOG_FILE (continuing...)"
    echo "[$TIMESTAMP] ⚠️  LLM providers tests had failures (continuing)" >> "$LOG_FILE"
fi

# Finally, run other LLM tests
if pytest \
    backend/tests/unit/llm/ \
    --ignore=backend/tests/unit/llm/adapters \
    --ignore=backend/tests/unit/llm/providers \
    --cov=backend.llm \
    --cov-append \
    --cov-report=term-missing \
    --cov-report=html:backend/htmlcov/llm \
    -v \
    >> "$LOG_FILE" 2>&1; then
    echo "✅ LLM tests passed!"
    echo "[$TIMESTAMP] ✅ LLM tests passed" >> "$LOG_FILE"
else
    echo "⚠️  LLM tests had failures - check $LOG_FILE (continuing...)"
    echo "[$TIMESTAMP] ⚠️  LLM tests had failures (continuing)" >> "$LOG_FILE"
fi

# Run agentic tests
if pytest \
    backend/tests/unit/services/rag/agentic/ \
    --cov=backend.services.rag.agentic \
    --cov-report=term-missing \
    --cov-report=html:backend/htmlcov/agentic \
    -v \
    >> "$LOG_FILE" 2>&1; then
    echo "✅ Agentic tests passed!"
    echo "[$TIMESTAMP] ✅ Agentic tests passed" >> "$LOG_FILE"
else
    echo "⚠️  Agentic tests had failures - check $LOG_FILE (continuing...)"
    echo "[$TIMESTAMP] ⚠️  Agentic tests had failures (continuing)" >> "$LOG_FILE"
fi

echo ""
echo "📊 Coverage reports generated in backend/htmlcov/"
echo "📝 Full log: $LOG_FILE"
