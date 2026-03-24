#!/usr/bin/env bash
# Pre/Post Deploy Validation — Run before and after fly deploy
#
# Usage:
#   scripts/preflight.sh pre    # Before deploy: import chain + core tests + ruff
#   scripts/preflight.sh post   # After deploy: health + search + agent health
#   scripts/preflight.sh full   # Both pre and post

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_DIR="$(cd "$(dirname "$0")/../apps/backend-rag" && pwd)"
BACKEND_URL="https://nuzantara-rag.fly.dev"
PASS=0
FAIL=0

check() {
    local name="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC} $name"
        ((PASS++))
    else
        echo -e "  ${RED}❌${NC} $name"
        ((FAIL++))
    fi
}

# --- PRE-DEPLOY ---
pre_deploy() {
    echo -e "${YELLOW}=== PRE-DEPLOY CHECKS ===${NC}"

    # Use SSH to Pro for pre-deploy checks (Pro has the correct venv)
    echo "Import chain (Pro):"
    check "dependencies.py imports" \
        ssh -o ConnectTimeout=5 -o BatchMode=yes pro \
        "cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null; PYTHONPATH=. python -c 'from backend.app.dependencies import get_current_user; print(\"OK\")'"

    # 2. Core tests on Pro
    echo "Core tests (Pro):"
    check "confidence tests" \
        ssh -o ConnectTimeout=5 -o BatchMode=yes pro \
        "cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null; PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no -x 2>/dev/null"

    # 3. Ruff check
    echo "Lint:"
    check "ruff check (backend/app)" \
        ssh -o ConnectTimeout=5 -o BatchMode=yes pro \
        "cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null; ruff check backend/app/ --select E,F --quiet 2>/dev/null"

    # 4. Check for rogue changes
    echo "Rogue change detection:"
    check "no uncommitted changes in backend" \
        bash -c "cd $BACKEND_DIR/.. && [ $(git diff --name-only HEAD -- apps/backend-rag/backend/ | wc -l) -eq 0 ]"
}

# --- POST-DEPLOY ---
post_deploy() {
    echo -e "${YELLOW}=== POST-DEPLOY CHECKS ===${NC}"

    # Wait for backend to be ready (cold start ~35s)
    echo "Waiting for backend..."
    for i in $(seq 1 5); do
        if curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
            break
        fi
        echo "  Attempt $i/5 - waiting 10s..."
        sleep 10
    done

    # 1. Health endpoint
    echo "Health:"
    check "/health returns healthy" \
        bash -c "curl -sf '$BACKEND_URL/health' | grep -q '\"healthy\"'"

    # 2. Embedding model
    check "embedding model = text-embedding-3-small" \
        bash -c "curl -sf '$BACKEND_URL/health' | grep -q 'text-embedding-3-small'"

    # 3. Agent health
    echo "Agent:"
    check "/api/agent/health returns ok" \
        bash -c "curl -sf '$BACKEND_URL/api/agent/health' | grep -q 'healthy\|operational'"

    # 4. Collections count
    check "10+ Qdrant collections" \
        bash -c "curl -sf '$BACKEND_URL/health' | python3 -c 'import json,sys; d=json.load(sys.stdin); exit(0 if d.get(\"database\",{}).get(\"collections\",0)>=10 else 1)'"

    # 5. Public endpoint responds (not 5xx)
    echo "Public endpoints:"
    check "KBLI notebook reachable (not 5xx)" \
        bash -c "HTTP_CODE=\$(curl -so /dev/null -w '%{http_code}' '$BACKEND_URL/api/v1/kbli-notebook/search?q=test&limit=1'); [ \"\$HTTP_CODE\" -lt 500 ]"
}

# --- MAIN ---
MODE="${1:-full}"

case "$MODE" in
    pre)
        pre_deploy
        ;;
    post)
        post_deploy
        ;;
    full)
        pre_deploy
        echo ""
        post_deploy
        ;;
    *)
        echo "Usage: $0 {pre|post|full}"
        exit 1
        ;;
esac

echo ""
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}All $TOTAL checks passed ✅${NC}"
else
    echo -e "${RED}$FAIL/$TOTAL checks failed ❌${NC}"
    exit 1
fi
