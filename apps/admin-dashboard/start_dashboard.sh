#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Initializing Nuzantara Admin Dashboard...${NC}"

# 1. Kill any existing processes on relevant ports to prevent conflicts
echo -e "${BLUE}🧹 Cleaning up ports 3002, 15432, 6333...${NC}"
lsof -ti:3002 | xargs kill -9 2>/dev/null
lsof -ti:15432 | xargs kill -9 2>/dev/null
lsof -ti:6333 | xargs kill -9 2>/dev/null

# 2. Start Fly.io Proxies in background
echo -e "${GREEN}🔌 Establishing tunnel to PostgreSQL (nuzantara-postgres)...${NC}"
fly proxy 15432:5432 -a nuzantara-postgres > /dev/null 2>&1 &
PG_PID=$!

echo -e "${GREEN}🔌 Establishing tunnel to Qdrant (nuzantara-qdrant)...${NC}"
fly proxy 6333:6333 -a nuzantara-qdrant > /dev/null 2>&1 &
QDRANT_PID=$!

# Give proxies a moment to connect
sleep 3

# Verify connections (optional check, straightforward here)
echo -e "${GREEN}✅ Tunnels established.${NC}"

# 3. Start Next.js App
echo -e "${BLUE}💻 Starting Dashboard on http://localhost:3002...${NC}"
echo -e "${BLUE}ℹ️  Press Ctrl+C to stop everything.${NC}"

# Trap SIGINT (Ctrl+C) to kill proxies when user stops the app
trap "kill $PG_PID $QDRANT_PID; echo -e '${RED}🛑 Stopped.${NC}'; exit" SIGINT

# Run the app
export PORT=3002
export NODE_TLS_REJECT_UNAUTHORIZED='0' 
export NODE_OPTIONS='--dns-result-order=ipv4first'

# Check if build exists, if not build
if [ ! -d ".next" ]; then
    echo "Building application..."
    npm run build
fi

npm run start
