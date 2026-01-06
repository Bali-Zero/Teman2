#!/bin/bash
# EMERGENCY ROLLBACK SCRIPT
# Reverts to Fly.io in case of migration failure
# Usage: ./ROLLBACK.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}╔════════════════════════════════════════╗${NC}"
echo -e "${RED}║  EMERGENCY ROLLBACK                    ║${NC}"
echo -e "${RED}╚════════════════════════════════════════╝${NC}\n"

echo -e "${YELLOW}This will:${NC}"
echo -e "  ${RED}1. Revert DNS to Fly.io${NC}"
echo -e "  ${RED}2. Restart Fly.io machines${NC}"
echo -e "  ${RED}3. Pause Railway services${NC}"
echo -e "  ${RED}4. Send alert notification${NC}\n"

read -p "Continue with rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Aborted${NC}"
    exit 0
fi

ROLLBACK_LOG="rollback_$(date +%Y%m%d_%H%M%S).log"

echo -e "\n${RED}━━━ ROLLBACK IN PROGRESS ━━━${NC}\n" | tee "$ROLLBACK_LOG"

# Step 1: Restart Fly.io machines
echo -e "${YELLOW}[1/4] Restarting Fly.io machines...${NC}" | tee -a "$ROLLBACK_LOG"

FLY_APPS=("nuzantara-rag" "nuzantara-mouth" "bali-intel-scraper")

for app in "${FLY_APPS[@]}"; do
    echo -e "  ${YELLOW}Starting machines for: $app${NC}" | tee -a "$ROLLBACK_LOG"

    # Get all machine IDs
    MACHINE_IDS=$(fly machine list -a "$app" --json 2>/dev/null | jq -r '.[].id' || echo "")

    if [ -n "$MACHINE_IDS" ]; then
        while IFS= read -r machine_id; do
            echo -e "    ${BLUE}Starting: $machine_id${NC}" | tee -a "$ROLLBACK_LOG"
            fly machine start "$machine_id" -a "$app" 2>&1 | tee -a "$ROLLBACK_LOG" || true
        done <<< "$MACHINE_IDS"
    else
        echo -e "    ${YELLOW}No machines found for $app${NC}" | tee -a "$ROLLBACK_LOG"
    fi
done

echo -e "${GREEN}✓ Fly.io machines restarted${NC}\n" | tee -a "$ROLLBACK_LOG"

# Step 2: Verify Fly.io health
echo -e "${YELLOW}[2/4] Verifying Fly.io health...${NC}" | tee -a "$ROLLBACK_LOG"

sleep 15  # Wait for services to start

FLY_BACKEND_URL="https://nuzantara-rag.fly.dev"

if curl -f "${FLY_BACKEND_URL}/health" &>/dev/null; then
    echo -e "${GREEN}✓ Fly.io backend healthy${NC}\n" | tee -a "$ROLLBACK_LOG"
else
    echo -e "${RED}✗ Fly.io backend not responding${NC}" | tee -a "$ROLLBACK_LOG"
    echo -e "${YELLOW}⚠ Manual intervention required${NC}\n" | tee -a "$ROLLBACK_LOG"
fi

# Step 3: DNS Instructions
echo -e "${YELLOW}[3/4] DNS Rollback Instructions${NC}" | tee -a "$ROLLBACK_LOG"
echo -e "${RED}⚠ MANUAL ACTION REQUIRED${NC}\n" | tee -a "$ROLLBACK_LOG"

echo -e "Go to your DNS provider and revert these records:\n" | tee -a "$ROLLBACK_LOG"

echo -e "${BLUE}Backend:${NC}" | tee -a "$ROLLBACK_LOG"
echo -e "  CNAME: api.nuzantara.com → ${RED}nuzantara-rag.fly.dev${NC}" | tee -a "$ROLLBACK_LOG"

echo -e "\n${BLUE}Frontend:${NC}" | tee -a "$ROLLBACK_LOG"
echo -e "  CNAME: app.nuzantara.com → ${RED}nuzantara-mouth.fly.dev${NC}" | tee -a "$ROLLBACK_LOG"

echo -e "\n${YELLOW}Press Enter when DNS has been reverted...${NC}"
read

# Step 4: Pause Railway
echo -e "${YELLOW}[4/4] Pausing Railway services...${NC}" | tee -a "$ROLLBACK_LOG"

if command -v railway &> /dev/null; then
    echo -e "  ${YELLOW}Stopping Railway deployments...${NC}" | tee -a "$ROLLBACK_LOG"
    # Railway doesn't have a pause command, but we can remove the service
    echo -e "  ${BLUE}Go to Railway dashboard and remove services if needed${NC}" | tee -a "$ROLLBACK_LOG"
else
    echo -e "  ${YELLOW}Railway CLI not found, skip${NC}" | tee -a "$ROLLBACK_LOG"
fi

# Summary
echo -e "\n${RED}╔════════════════════════════════════════╗${NC}"
echo -e "${RED}║  ROLLBACK COMPLETE                     ║${NC}"
echo -e "${RED}╚════════════════════════════════════════╝${NC}\n"

echo -e "${GREEN}✓ Fly.io machines restarted${NC}"
echo -e "${GREEN}✓ Services should be accessible via Fly.io${NC}"
echo -e "${YELLOW}⚠ Verify DNS propagation (5-10 minutes)${NC}\n"

echo -e "${BLUE}Verification URLs:${NC}"
echo -e "  Backend:  $FLY_BACKEND_URL/health"
echo -e "  Frontend: https://nuzantara-mouth.fly.dev\n"

echo -e "${YELLOW}Rollback log saved to: $ROLLBACK_LOG${NC}\n"

# Send notification (optional)
echo -e "${YELLOW}Send notification? (yes/no):${NC}"
read -p "" NOTIFY

if [ "$NOTIFY" = "yes" ]; then
    # Add your notification logic here
    # e.g., Slack webhook, email, SMS
    echo -e "${BLUE}Add notification webhook in this script${NC}\n"
fi

echo -e "${GREEN}Rollback procedure complete.${NC}\n"
