#!/bin/bash
#
# Ollama Cron Window Manager
# Manages Ollama lifecycle during test window (1am-6am)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"
PID_FILE="/tmp/ollama_cron.pid"
LOG_FILE="/tmp/ollama_cron.log"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

ACTION="${1:-start}"

case "$ACTION" in
    start)
        echo -e "${BLUE}🚀 Starting Ollama for agent tests...${NC}"
        
        # Check if already running
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Ollama already running (PID: $PID)${NC}"
                exit 0
            else
                rm "$PID_FILE"
            fi
        fi
        
        # Check if Ollama is installed
        if ! command -v ollama &> /dev/null; then
            echo -e "${RED}❌ Ollama is not installed!${NC}"
            exit 1
        fi
        
        # Start Ollama
        nohup ollama serve > "$LOG_FILE" 2>&1 &
        OLLAMA_PID=$!
        echo $OLLAMA_PID > "$PID_FILE"
        
        # Wait for Ollama to be ready
        echo -e "${YELLOW}⏳ Waiting for Ollama to start...${NC}"
        for i in {1..30}; do
            if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Ollama started (PID: $OLLAMA_PID)${NC}"
                
                # Ensure Qwen model is available
                echo -e "${BLUE}📥 Checking Qwen model...${NC}"
                if curl -s "${OLLAMA_URL}/api/tags" | grep -q "qwen"; then
                    echo -e "${GREEN}✅ Qwen model available${NC}"
                else
                    echo -e "${YELLOW}⚠️  Pulling Qwen model...${NC}"
                    ollama pull "$OLLAMA_MODEL" || echo -e "${YELLOW}⚠️  Model pull may take time${NC}"
                fi
                
                exit 0
            fi
            sleep 1
            echo -n "."
        done
        
        echo -e "${RED}❌ Ollama failed to start${NC}"
        kill $OLLAMA_PID 2>/dev/null || true
        rm "$PID_FILE"
        exit 1
        ;;
        
    stop)
        echo -e "${BLUE}🛑 Stopping Ollama after test window...${NC}"
        
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo "   Stopping process $PID..."
                kill $PID
                rm "$PID_FILE"
                echo -e "${GREEN}✅ Ollama stopped${NC}"
            else
                rm "$PID_FILE"
                echo -e "${YELLOW}ℹ️  Ollama was not running${NC}"
            fi
        else
            echo -e "${YELLOW}ℹ️  No Ollama cron instance found${NC}"
        fi
        ;;
        
    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Ollama is running (PID: $PID)${NC}"
                if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
                    echo -e "${GREEN}✅ Ollama API is responding${NC}"
                else
                    echo -e "${RED}❌ Ollama API not responding${NC}"
                fi
            else
                echo -e "${RED}❌ Ollama PID file exists but process not running${NC}"
                rm "$PID_FILE"
            fi
        else
            echo -e "${YELLOW}ℹ️  Ollama is not running (no PID file)${NC}"
        fi
        ;;
        
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
