#!/bin/bash
# Run Article Composer tests

set -e

echo "🧪 Running Article Composer Tests"
echo ""

cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    echo "Running: $1"
    if PYTHONPATH=. pytest "$1" -v --tb=short 2>&1; then
        echo -e "${GREEN}✅ Passed${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}❌ Failed${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    echo ""
}

echo "1️⃣ Unit Tests - Claude Client"
run_test "backend/tests/unit/services/article_composer/test_claude_client.py"

echo "2️⃣ Unit Tests - Error Handler"
run_test "backend/tests/unit/services/article_composer/test_error_handler.py"

echo "3️⃣ Unit Tests - Validators"
run_test "backend/tests/unit/services/article_composer/test_validators.py"

echo "4️⃣ Unit Tests - Cache Service"
run_test "backend/tests/unit/services/article_composer/test_cache.py"

echo "5️⃣ Integration Tests - Article Composer"
run_test "backend/tests/integration/article_composer/test_article_composer_integration.py"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results:"
echo "  ✅ Passed: $TESTS_PASSED"
echo "  ❌ Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
