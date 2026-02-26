#!/bin/bash
#
# Start Ollama Daemon (keeps it running)
# Use this if you don't want system service but want Ollama always running
#

set -e

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
PID_FILE="/tmp/ollama_daemon.pid"
LOG_FILE="/tmp/ollama_daemon.log"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama daemon already running (PID: $PID)${NC}"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama is not installed!${NC}"
    echo "Install: brew install ollama (macOS) or curl -fsSL https://ollama.com/install.sh | sh (Linux)"
    exit 1
fi

echo -e "${BLUE}🚀 Starting Ollama daemon...${NC}"

# Start Ollama in background
nohup ollama serve > "$LOG_FILE" 2>&1 &
OLLAMA_PID=$!

# Save PID
echo $OLLAMA_PID > "$PID_FILE"

# Wait for Ollama to be ready
echo -e "${YELLOW}⏳ Waiting for Ollama to start...${NC}"
for i in {1..30}; do
    if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama daemon started (PID: $OLLAMA_PID)${NC}"
        echo "   Logs: $LOG_FILE"
        echo "   PID file: $PID_FILE"
        echo ""
        echo "To stop: kill $OLLAMA_PID or ./scripts/stop_ollama_daemon.sh"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo -e "${RED}❌ Ollama failed to start within 30s${NC}"
kill $OLLAMA_PID 2>/dev/null || true
rm "$PID_FILE"
exit 1
