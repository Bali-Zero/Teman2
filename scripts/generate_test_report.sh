#!/bin/bash
#
# Generate Test Report
# Creates HTML report with test results and coverage
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag/backend"
REPORT_DIR="$PROJECT_ROOT/reports"
TIMESTAMP=$(date '+%Y%m%d-%H%M%S')

mkdir -p "$REPORT_DIR"

echo "📊 Generating test report..."

cd "$BACKEND_DIR"
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"

# Run tests with coverage and HTML report
pytest \
    tests/unit/services/rag/agentic/ \
    tests/unit/llm/ \
    --cov=backend.services.rag.agentic \
    --cov=backend.llm \
    --cov-report=html:"$REPORT_DIR/coverage-$TIMESTAMP" \
    --cov-report=term \
    --html="$REPORT_DIR/test-report-$TIMESTAMP.html" \
    --self-contained-html \
    -v

echo ""
echo "✅ Report generated!"
echo ""
echo "📊 Reports:"
echo "   Test Report: $REPORT_DIR/test-report-$TIMESTAMP.html"
echo "   Coverage: $REPORT_DIR/coverage-$TIMESTAMP/index.html"
echo ""
echo "🌐 Open in browser:"
echo "   open $REPORT_DIR/test-report-$TIMESTAMP.html"
