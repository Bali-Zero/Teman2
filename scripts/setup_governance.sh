#!/bin/bash
# NUZANTARA PRIME - Governance Activation Script
# Installs and activates pre-commit hooks and verifies setup

set -e

echo "🛡️  NUZANTARA PRIME - Activating Total Governance"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if we're in project root
if [ ! -f ".pre-commit-config.yaml" ]; then
    echo -e "${RED}❌ Error: .pre-commit-config.yaml not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check if .cursorrules exists
if [ ! -f ".cursorrules" ]; then
    echo -e "${RED}❌ Error: .cursorrules not found${NC}"
    exit 1
fi

echo -e "${YELLOW}🔧 Step 1: Resetting any incorrect git hooks configuration...${NC}"
git config --unset-all core.hooksPath 2>/dev/null || true
echo -e "${GREEN}✅ Git hooks path reset${NC}"
echo ""

echo -e "${YELLOW}📦 Step 2: Installing pre-commit...${NC}"
python3 -m pip install --upgrade pip > /dev/null 2>&1 || true
python3 -m pip install pre-commit > /dev/null 2>&1 || {
    echo -e "${RED}❌ Failed to install pre-commit${NC}"
    echo "Try: pip install pre-commit"
    exit 1
}

echo -e "${GREEN}✅ Pre-commit installed${NC}"
echo ""

echo -e "${YELLOW}🔧 Step 3: Installing git hooks...${NC}"
pre-commit install || {
    echo -e "${RED}❌ Failed to install hooks${NC}"
    exit 1
}

echo -e "${GREEN}✅ Git hooks installed${NC}"
echo ""

echo -e "${YELLOW}✅ Step 4: Verifying configuration files...${NC}"
if [ -f ".cursorrules" ]; then
    echo -e "${GREEN}✅ .cursorrules found${NC}"
else
    echo -e "${RED}❌ .cursorrules missing${NC}"
    exit 1
fi

if [ -f ".pre-commit-config.yaml" ]; then
    echo -e "${GREEN}✅ .pre-commit-config.yaml found${NC}"
else
    echo -e "${RED}❌ .pre-commit-config.yaml missing${NC}"
    exit 1
fi

echo ""
echo "================================================"
echo -e "${GREEN}🛡️  GOVERNANCE ACTIVATED${NC}"
echo ""
echo "Your codebase is now protected by:"
echo "  🧠 AI Rules (.cursorrules) - Active in Cursor"
echo "  📋 Ruff (Linter & Formatter) - Auto-fixes code"
echo "  🔒 Security Checks - Detects secrets & private keys"
echo "  🏥 Health Check - Validates env vars (on push)"
echo ""
echo "Hooks will run automatically on every commit!"
echo ""
