#!/bin/bash
# Coverage Test Script for Nuzantara Backend
# Runs pytest with coverage and generates reports
#
# Usage:
#   ./scripts/run_coverage_test.sh              # Run all tests with coverage
#   ./scripts/run_coverage_test.sh unit         # Run only unit tests
#   ./scripts/run_coverage_test.sh api          # Run only API tests
#   ./scripts/run_coverage_test.sh integration  # Run only integration tests
#   ./scripts/run_coverage_test.sh unit -k "test_feedback"  # Run specific tests
#
# See docs/TEST_COVERAGE.md for detailed documentation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

# Parse test type argument
TEST_TYPE="${1:-all}"

echo "🧪 Running Coverage Tests..."
echo "📁 Project root: $PROJECT_ROOT"
echo "🎯 Test type: $TEST_TYPE"
echo ""

# Determine test path based on argument
case "$TEST_TYPE" in
    unit)
        TEST_PATH="tests/unit"
        ;;
    api)
        TEST_PATH="tests/api"
        ;;
    integration)
        TEST_PATH="tests/integration"
        ;;
    all|*)
        TEST_PATH="tests/"
        ;;
esac

# Run pytest with coverage
pytest "$TEST_PATH" \
    --cov=backend \
    --cov-config=.coveragerc \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml \
    --cov-fail-under=75 \
    -v \
    "${@:2}"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Coverage test completed successfully!"
    echo "📊 HTML report: htmlcov/index.html"
    echo "📄 XML report: coverage.xml"
    echo ""
    echo "💡 To view HTML report: open htmlcov/index.html"
else
    echo "❌ Coverage test failed (exit code: $EXIT_CODE)"
    echo "📊 Check reports for details: htmlcov/index.html"
fi

exit $EXIT_CODE

