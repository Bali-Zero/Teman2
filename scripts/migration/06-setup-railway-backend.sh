#!/bin/bash
# Script 6: Setup and deploy backend to Railway
# Usage: ./06-setup-railway-backend.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RAILWAY BACKEND SETUP                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

# Check Railway CLI
if ! command -v railway &> /dev/null; then
    echo -e "${RED}✗ Railway CLI not found${NC}"
    echo -e "${YELLOW}Install: npm i -g @railway/cli${NC}"
    exit 1
fi

# Login
echo -e "${YELLOW}→ Logging into Railway...${NC}"
railway login
echo -e "${GREEN}✓ Logged in${NC}\n"

# Create project
echo -e "${YELLOW}→ Creating Railway project...${NC}"
cd apps/backend-rag

railway init --name nuzantara-backend

echo -e "${GREEN}✓ Project created${NC}\n"

# Add PostgreSQL
echo -e "${YELLOW}→ Adding PostgreSQL database...${NC}"
railway add --plugin postgresql
echo -e "${GREEN}✓ PostgreSQL added${NC}\n"

# Wait for database
echo -e "${YELLOW}→ Waiting for database to be ready...${NC}"
sleep 10

# Set environment variables
echo -e "${BLUE}━━━ Setting Environment Variables ━━━${NC}\n"

# Read from backup
SECRETS_FILE="../../backups/secrets_backend_*.txt"
if [ -f "$SECRETS_FILE" ]; then
    echo -e "${YELLOW}Found secrets backup. Copying to Railway...${NC}"
fi

# Required variables
ENV_VARS=(
    "ENVIRONMENT=production"
    "PORT=8080"
    "LOG_LEVEL=INFO"
    "EMBEDDING_PROVIDER=openai"
    "PYTHONUNBUFFERED=1"
)

echo -e "${YELLOW}Setting base variables...${NC}"
for var in "${ENV_VARS[@]}"; do
    railway variables set "$var"
done

# Manual secrets
echo -e "\n${YELLOW}Please enter the following secrets:${NC}\n"

read -p "OPENAI_API_KEY: " OPENAI_KEY
railway variables set "OPENAI_API_KEY=$OPENAI_KEY"

read -p "GOOGLE_API_KEY: " GOOGLE_KEY
railway variables set "GOOGLE_API_KEY=$GOOGLE_KEY"

read -p "ANTHROPIC_API_KEY: " ANTHROPIC_KEY
railway variables set "ANTHROPIC_API_KEY=$ANTHROPIC_KEY"

read -p "QDRANT_URL (new Railway/Cloud URL): " QDRANT_URL
railway variables set "QDRANT_URL=$QDRANT_URL"

read -p "QDRANT_API_KEY (if any): " QDRANT_KEY
if [ -n "$QDRANT_KEY" ]; then
    railway variables set "QDRANT_API_KEY=$QDRANT_KEY"
fi

read -p "JWT_SECRET_KEY: " JWT_SECRET
railway variables set "JWT_SECRET_KEY=$JWT_SECRET"

# Optional secrets
echo -e "\n${YELLOW}Optional secrets (press Enter to skip):${NC}\n"

read -p "TELEGRAM_BOT_TOKEN: " TG_TOKEN
if [ -n "$TG_TOKEN" ]; then
    railway variables set "TELEGRAM_BOT_TOKEN=$TG_TOKEN"
fi

read -p "SENTRY_DSN: " SENTRY_DSN
if [ -n "$SENTRY_DSN" ]; then
    railway variables set "SENTRY_DSN=$SENTRY_DSN"
fi

echo -e "\n${GREEN}✓ Environment variables set${NC}\n"

# Deploy
echo -e "${YELLOW}→ Deploying to Railway...${NC}"
railway up

echo -e "\n${GREEN}✓ Deployment started${NC}"
echo -e "${YELLOW}Monitor: railway logs${NC}\n"

# Get URL
echo -e "${YELLOW}→ Getting service URL...${NC}"
SERVICE_URL=$(railway status | grep "URL" | awk '{print $2}')

echo -e "${GREEN}✓ Service deployed${NC}"
echo -e "${BLUE}URL: ${SERVICE_URL}${NC}\n"

# Test health
echo -e "${YELLOW}→ Testing health endpoint...${NC}"
sleep 30  # Wait for service to start

if curl -f "${SERVICE_URL}/health" &>/dev/null; then
    echo -e "${GREEN}✓ Health check passed${NC}\n"
else
    echo -e "${YELLOW}⚠ Health check failed. Check logs with: railway logs${NC}\n"
fi

echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Backend setup complete!${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"

echo -e "\n${BLUE}Service URL:${NC} ${SERVICE_URL}"
echo -e "${BLUE}Logs:${NC} railway logs"
echo -e "${BLUE}Dashboard:${NC} railway open\n"
