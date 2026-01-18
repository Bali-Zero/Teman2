#!/bin/bash
#
# Check Ollama Status
#

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Checking Ollama status...${NC}"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama is not installed${NC}"
    exit 1
fi

# Check if Ollama is running
if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama is running${NC}"
    
    # Get models
    MODELS=$(curl -s "${OLLAMA_URL}/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "")
    
    if [ -n "$MODELS" ]; then
        echo ""
        echo "📦 Available models:"
        echo "$MODELS" | while read -r model; do
            echo "   - $model"
        done
        
        # Check for Qwen
        if echo "$MODELS" | grep -q "qwen"; then
            echo ""
            echo -e "${GREEN}✅ Qwen model is available${NC}"
        else
            echo ""
            echo -e "${YELLOW}⚠️  Qwen model not found${NC}"
            echo "   Run: ollama pull qwen2.5:latest"
        fi
    fi
    
    # Check service status
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if launchctl list | grep -q "com.ollama.test"; then
            echo ""
            echo -e "${GREEN}✅ Ollama service is configured (launchd)${NC}"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if systemctl is-active --quiet ollama-test.service 2>/dev/null; then
            echo ""
            echo -e "${GREEN}✅ Ollama service is running (systemd)${NC}"
        fi
    fi
    
    # Check daemon
    if [ -f "/tmp/ollama_daemon.pid" ]; then
        PID=$(cat /tmp/ollama_daemon.pid)
        if ps -p $PID > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✅ Ollama daemon is running (PID: $PID)${NC}"
        fi
    fi
    
    exit 0
else
    echo -e "${RED}❌ Ollama is not running${NC}"
    echo ""
    echo "To start:"
    echo "  - Service: ./scripts/setup_ollama_service.sh"
    echo "  - Daemon:  ./scripts/start_ollama_daemon.sh"
    echo "  - Manual:  ollama serve"
    exit 1
fi
