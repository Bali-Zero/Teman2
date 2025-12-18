#!/bin/bash
# NUZANTARA PRIME - Backend Tests Validation Script
# Validates backend tests before pushing to prevent CI failures

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
MODE="fast"
COVERAGE=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            MODE="fast"
            shift
            ;;
        --full)
            MODE="full"
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fast       Run only unit tests (default, fast)"
            echo "  --full       Run all tests (unit + integration)"
            echo "  --coverage   Include coverage check"
            echo "  -v, --verbose  Verbose output"
            echo "  -h, --help    Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🧪 NUZANTARA PRIME - Backend Tests Validation${NC}"
echo "=========================================================="
echo ""

# Check if we're in the project root
if [ ! -d "apps/backend-rag" ]; then
    echo -e "${RED}❌ Error: apps/backend-rag directory not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

cd apps/backend-rag

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found${NC}"
    exit 1
fi

# Check if pytest is installed
if ! python3 -m pytest --version &> /dev/null; then
    echo -e "${YELLOW}⚠️  pytest not found, installing...${NC}"
    pip install pytest pytest-asyncio pytest-cov > /dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to install pytest${NC}"
        exit 1
    }
fi

# Set environment variables for testing
export DATABASE_URL="postgresql://test:test@localhost/test"
export JWT_SECRET_KEY="test-secret-key-for-validation-1234567890ab"
export API_KEYS="test-api-key-for-validation"
export WHATSAPP_VERIFY_TOKEN="test-verify-token"
export INSTAGRAM_VERIFY_TOKEN="test-verify-token"
export QDRANT_URL="http://localhost:6333"
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-key}"

echo -e "${YELLOW}📋 Mode: ${MODE}${NC}"
if [ "$COVERAGE" = true ]; then
    echo -e "${YELLOW}📊 Coverage: enabled${NC}"
fi
echo ""

# Build pytest command
PYTEST_CMD="python3 -m pytest"

if [ "$MODE" = "fast" ]; then
    PYTEST_CMD="$PYTEST_CMD tests/unit/"
elif [ "$MODE" = "full" ]; then
    PYTEST_CMD="$PYTEST_CMD tests/"
fi

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
else
    PYTEST_CMD="$PYTEST_CMD -q"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=backend --cov-config=.coveragerc --cov-report=term-missing"
fi

PYTEST_CMD="$PYTEST_CMD --tb=short"

echo -e "${BLUE}Running: ${PYTEST_CMD}${NC}"
echo ""

# Run tests
if eval "$PYTEST_CMD"; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo -e "${BLUE}📊 Coverage report generated${NC}"
    fi

    echo ""
    echo -e "${GREEN}✅ Validation successful - safe to push!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Tests failed!${NC}"
    echo ""
    echo -e "${YELLOW}💡 To fix:${NC}"
    echo "  1. Review the test failures above"
    echo "  2. Fix the failing tests"
    echo "  3. Run: cd apps/backend-rag && python -m pytest tests/unit/ -v"
    echo "  4. Then try pushing again"
    echo ""
    echo -e "${YELLOW}⚠️  To skip validation (emergency only):${NC}"
    echo "  git push --no-verify"
    echo ""
    exit 1
fi
