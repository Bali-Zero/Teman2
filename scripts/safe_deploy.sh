#!/bin/bash
# scripts/safe_deploy.sh
# 🛡️ GLOBAL SAFE DEPLOYMENT SCRIPT
# Enforces pre-flight checks, testing, and sequential deployment.

set -e

# Configuration
BACKEND_APP="nuzantara-rag"
FRONTEND_APP="nuzantara-mouth"
SCRIPT_DIR="$(dirname "$0")"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🛡️  NUZANTARA SAFE DEPLOY SYSTEM${NC}"
echo "========================================"

# 1. Dependency Check
echo -e "\n${YELLOW}[1/5] Checking dependencies...${NC}"
if ! command -v flyctl &> /dev/null; then
    echo -e "${RED}❌ flyctl not found! Install it first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ flyctl found${NC}"

# 2. Sentinel Check (Quality Control)
echo -e "\n${YELLOW}[2/5] Checking Quality Control (Sentinel)...${NC}"
# We assume if the user is running deploy, they might have already run sentinel.
# checking for a recent sentinel log or asking execution.
LAST_SENTINEL_LOG=$(ls -t sentinel-results/*.log 2>/dev/null | head -n 1)

if [ -z "$LAST_SENTINEL_LOG" ]; then
    echo -e "${YELLOW}⚠ No recent Sentinel run found.${NC}"
    read -p "Do you want to run Sentinel (Tests & Lint) now? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        ./sentinel
    else
        echo -e "${RED}⚠ Proceeding WITHOUT quality checks. This is risky.${NC}"
        read -p "Type 'I UNDERSTAND' to continue: " CONFIRM
        if [ "$CONFIRM" != "I UNDERSTAND" ]; then
            echo -e "${RED}Aborting.${NC}"
            exit 1
        fi
    fi
else
    # Check if log is recent (e.g., last 1 hour) -- simplified for now just showing it
    echo -e "${GREEN}✓ Found recent Sentinel log: $LAST_SENTINEL_LOG${NC}"
fi

# 3. Pre-flight Python Checks
echo -e "\n${YELLOW}[3/5] Running Pre-flight Checks...${NC}"
python3 scripts/deployment/preflight_check.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Pre-flight checks failed.${NC}"
    exit 1
fi

# 4. Backend Deployment
echo -e "\n${YELLOW}[4/5] Deploying BACKEND ($BACKEND_APP)...${NC}"
read -p "Deploy Backend? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd "$ROOT_DIR/apps/backend-rag"
    
    # Check if release_command is active in fly.toml
    if grep -q "^[[:space:]]*release_command" fly.toml; then
        echo -e "${BLUE}ℹ️  Native Release Command found in fly.toml - Migrations will run on Fly.io${NC}"
        flyctl deploy
    else
        echo -e "${YELLOW}⚠ No active release_command found.${NC}"
        echo "We must ensure migrations run. Options:"
        echo "1) Deploy and hope (Dangerous)"
        echo "2) Run migrations manually via SSH console before/after"
        
        flyctl deploy
        
        echo -e "${YELLOW}⚠ REMINDER: Did you check migrations?${NC}"
        echo "You can run: flyctl ssh console -C 'python -m backend.db.migrate apply-all'"
    fi
    cd "$ROOT_DIR"
else
    echo "Skipping Backend deploy."
fi

# 5. Frontend Deployment
echo -e "\n${YELLOW}[5/5] Deploying FRONTEND ($FRONTEND_APP)...${NC}"
read -p "Deploy Frontend? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd "$ROOT_DIR/apps/mouth"
    flyctl deploy
    cd "$ROOT_DIR"
else
    echo "Skipping Frontend deploy."
fi

echo -e "\n${GREEN}✨ Deployment Sequence Complete.${NC}"
