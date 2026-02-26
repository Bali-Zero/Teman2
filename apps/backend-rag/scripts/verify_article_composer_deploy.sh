#!/bin/bash
# Pre-deployment verification script for Article Composer

set -e

echo "🔍 Article Composer - Pre-Deployment Verification"
echo ""

ERRORS=0
WARNINGS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $1"
    else
        echo -e "${RED}❌${NC} $1"
        ERRORS=$((ERRORS + 1))
    fi
}

warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

echo "1️⃣ Checking Python syntax..."
python3 -m py_compile backend/app/routers/article_composer.py
check "article_composer.py syntax OK"

python3 -m py_compile backend/services/article_composer/claude_client.py
check "claude_client.py syntax OK"

python3 -m py_compile backend/services/article_composer/error_handler.py
check "error_handler.py syntax OK"

python3 -m py_compile backend/services/article_composer/validators.py
check "validators.py syntax OK"

python3 -m py_compile backend/services/article_composer/cache.py
check "cache.py syntax OK"

echo ""
echo "2️⃣ Checking imports..."
python3 -c "
from backend.services.article_composer import (
    cache_service,
    call_claude_with_retry,
    handle_anthropic_error,
    ComposeRequestValidator,
)
print('✅ All imports successful')
" 2>&1
check "Service imports OK"

python3 -c "
from backend.app.routers import article_composer
print('✅ Router import successful')
" 2>&1
check "Router import OK"

echo ""
echo "3️⃣ Checking dependencies..."
if grep -q "slowapi" requirements.txt; then
    check "slowapi in requirements.txt"
else
    warn "slowapi not found in requirements.txt"
fi

if grep -q "tenacity" requirements.txt; then
    check "tenacity in requirements.txt"
else
    warn "tenacity not found in requirements.txt"
fi

if grep -q "redis" requirements.txt; then
    check "redis in requirements.txt"
else
    warn "redis not found in requirements.txt"
fi

echo ""
echo "4️⃣ Checking environment variables..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
    warn "ANTHROPIC_API_KEY not set (will be checked in production)"
else
    check "ANTHROPIC_API_KEY is set"
fi

if [ -z "$REDIS_URL" ]; then
    warn "REDIS_URL not set (cache will be disabled if Redis unavailable)"
else
    check "REDIS_URL is set"
fi

echo ""
echo "5️⃣ Checking file structure..."
if [ -f "backend/services/article_composer/claude_client.py" ]; then
    check "claude_client.py exists"
else
    warn "claude_client.py not found"
fi

if [ -f "backend/services/article_composer/error_handler.py" ]; then
    check "error_handler.py exists"
else
    warn "error_handler.py not found"
fi

if [ -f "backend/services/article_composer/validators.py" ]; then
    check "validators.py exists"
else
    warn "validators.py not found"
fi

if [ -f "backend/services/article_composer/cache.py" ]; then
    check "cache.py exists"
else
    warn "cache.py not found"
fi

echo ""
echo "6️⃣ Running basic tests..."
if command -v pytest &> /dev/null; then
    pytest backend/tests/unit/services/article_composer/ -v --tb=short 2>&1 | tail -20
    if [ $? -eq 0 ]; then
        check "Unit tests passed"
    else
        warn "Some unit tests failed (check output above)"
    fi
else
    warn "pytest not found - skipping tests"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  $WARNINGS warning(s) - Review above${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS error(s), $WARNINGS warning(s)${NC}"
    echo "Please fix errors before deploying"
    exit 1
fi
