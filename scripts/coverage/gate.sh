#!/bin/bash
#
# Coverage Gate Orchestrator
#
# Runs diff coverage checks for both backend and frontend.
# Exits with non-zero code if any check fails.
#
# Usage:
#     bash scripts/coverage/gate.sh [--backend-threshold=80] [--frontend-threshold=80] [--base=main]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
# Thresholds: 80% is industry standard for diff coverage (new code)
# This is stricter than global coverage because it only checks changed lines
# Global coverage targets: Backend ≥95% (long-term), Frontend ≥70% (floor)
BACKEND_THRESHOLD=80.0
FRONTEND_THRESHOLD=80.0
BASE_BRANCH="main"
GENERATE_COVERAGE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --backend-threshold=*)
            BACKEND_THRESHOLD="${arg#*=}"
            ;;
        --frontend-threshold=*)
            FRONTEND_THRESHOLD="${arg#*=}"
            ;;
        --base=*)
            BASE_BRANCH="${arg#*=}"
            ;;
        --generate-coverage)
            GENERATE_COVERAGE=true
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Usage: $0 [--backend-threshold=80] [--frontend-threshold=80] [--base=main] [--generate-coverage]"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 COVERAGE GATE - DIFF COVERAGE CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Backend threshold:  ${BACKEND_THRESHOLD}%"
echo "Frontend threshold: ${FRONTEND_THRESHOLD}%"
echo "Base branch:        ${BASE_BRANCH}"
echo ""

BACKEND_PASSED=false
FRONTEND_PASSED=false
BACKEND_EXIT=0
FRONTEND_EXIT=0

# Run backend diff coverage
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 BACKEND DIFF COVERAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BACKEND_ARGS=(
    "--threshold=${BACKEND_THRESHOLD}"
    "--base=${BASE_BRANCH}"
)

if [ "$GENERATE_COVERAGE" = true ]; then
    BACKEND_ARGS+=("--generate-coverage")
fi

if python3 "$SCRIPT_DIR/diff_coverage_py.py" "${BACKEND_ARGS[@]}"; then
    BACKEND_PASSED=true
    echo -e "${GREEN}✅ Backend diff coverage PASSED${NC}"
else
    BACKEND_EXIT=$?
    echo -e "${RED}❌ Backend diff coverage FAILED${NC}"
fi

echo ""

# Run frontend diff coverage
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 FRONTEND DIFF COVERAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FRONTEND_ARGS=(
    "--threshold=${FRONTEND_THRESHOLD}"
    "--base=${BASE_BRANCH}"
)

if [ "$GENERATE_COVERAGE" = true ]; then
    FRONTEND_ARGS+=("--generate-coverage")
fi

if node "$SCRIPT_DIR/diff_coverage_lcov.mjs" "${FRONTEND_ARGS[@]}"; then
    FRONTEND_PASSED=true
    echo -e "${GREEN}✅ Frontend diff coverage PASSED${NC}"
else
    FRONTEND_EXIT=$?
    echo -e "${RED}❌ Frontend diff coverage FAILED${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$BACKEND_PASSED" = true ] && [ "$FRONTEND_PASSED" = true ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo ""
    echo "Backend:  ✅ PASSED"
    echo "Frontend: ✅ PASSED"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME CHECKS FAILED${NC}"
    echo ""
    if [ "$BACKEND_PASSED" = true ]; then
        echo -e "Backend:  ${GREEN}✅ PASSED${NC}"
    else
        echo -e "Backend:  ${RED}❌ FAILED${NC}"
    fi
    if [ "$FRONTEND_PASSED" = true ]; then
        echo -e "Frontend: ${GREEN}✅ PASSED${NC}"
    else
        echo -e "Frontend: ${RED}❌ FAILED${NC}"
    fi
    echo ""
    exit 1
fi

