#!/bin/bash
# NUZANTARA PRIME - Setup Pre-commit Hooks
# Installs and activates pre-commit hooks for code quality automation

set -e

echo "🤖 NUZANTARA PRIME - Setting up Automation & Governance"
echo "=========================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the project root
if [ ! -f ".pre-commit-config.yaml" ]; then
    echo -e "${RED}❌ Error: .pre-commit-config.yaml not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found${NC}"
    echo "Please install Python 3.11 or later"
    exit 1
fi

echo -e "${YELLOW}📦 Step 1: Installing pre-commit...${NC}"
cd apps/backend-rag
python3 -m pip install --upgrade pip > /dev/null 2>&1 || true
python3 -m pip install pre-commit ruff > /dev/null 2>&1 || {
    echo -e "${RED}❌ Failed to install pre-commit or ruff${NC}"
    echo "Try: pip install pre-commit ruff"
    exit 1
}
cd ../..

echo -e "${GREEN}✅ Pre-commit installed${NC}"
echo ""

echo -e "${YELLOW}🔧 Step 2: Installing pre-commit hooks...${NC}"
pre-commit install --install-hooks || {
    echo -e "${RED}❌ Failed to install hooks${NC}"
    exit 1
}

echo -e "${GREEN}✅ Hooks installed${NC}"
echo ""

echo -e "${YELLOW}🧪 Step 3: Testing hooks (dry-run)...${NC}"
pre-commit run --all-files --hook-stage manual || {
    echo -e "${YELLOW}⚠️  Some hooks failed (this is normal on first run)${NC}"
    echo "The hooks will run automatically on your next commit"
}

echo ""
echo "=========================================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "🤖 Your 'robot guardians' are now active:"
echo ""
echo "  📋 Janitor (Ruff):"
echo "     - Auto-fixes linting errors"
echo "     - Formats Python code"
echo "     - Checks for os.getenv() usage"
echo "     - Checks for print() statements"
echo ""
echo "  🔒 Gatekeeper (Security):"
echo "     - Detects secrets in code"
echo "     - Checks for large files"
echo "     - Validates YAML/JSON/TOML"
echo "     - Runs health checks (on push)"
echo ""
echo "📝 Next steps:"
echo ""
echo "  1. Make a commit - hooks will run automatically"
echo "  2. To run hooks manually: pre-commit run --all-files"
echo "  3. To skip hooks (emergency): git commit --no-verify"
echo ""
echo "⚠️  Note: Skipping hooks should be rare exceptions!"
echo ""
