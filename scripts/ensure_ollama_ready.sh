#!/bin/bash
#
# Ensure Ollama is Ready for Tests
# Starts Ollama if not running, ensures Qwen model is available
#

set -e

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:latest}"
OLLAMA_TIMEOUT=30

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Ensuring Ollama is ready for tests...${NC}"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama is not installed!${NC}"
    echo ""
    echo "Install Ollama:"
    echo "  macOS: brew install ollama"
    echo "  Linux: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

# Function to check if Ollama is running
check_ollama_running() {
    if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to start Ollama
start_ollama() {
    echo -e "${YELLOW}🚀 Starting Ollama server...${NC}"
    
    # Start Ollama in background
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    # Wait for Ollama to be ready
    echo -e "${YELLOW}⏳ Waiting for Ollama to start...${NC}"
    for i in $(seq 1 $OLLAMA_TIMEOUT); do
        if check_ollama_running; then
            echo -e "${GREEN}✅ Ollama started (PID: $OLLAMA_PID)${NC}"
            echo $OLLAMA_PID > /tmp/ollama_test.pid
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    echo -e "${RED}❌ Ollama failed to start within ${OLLAMA_TIMEOUT}s${NC}"
    kill $OLLAMA_PID 2>/dev/null || true
    return 1
}

# Function to check if model exists
check_model_exists() {
    local model=$1
    if curl -s "${OLLAMA_URL}/api/tags" | grep -q "\"name\":\"${model}\""; then
        return 0
    else
        return 1
    fi
}

# Function to pull model
pull_model() {
    local model=$1
    echo -e "${YELLOW}📥 Pulling model: ${model}...${NC}"
    if ollama pull "$model"; then
        echo -e "${GREEN}✅ Model ${model} ready${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to pull model ${model}${NC}"
        return 1
    fi
}

# Main logic
if ! check_ollama_running; then
    echo -e "${YELLOW}⚠️  Ollama is not running${NC}"
    start_ollama || exit 1
else
    echo -e "${GREEN}✅ Ollama is already running${NC}"
fi

# Check if model exists
if ! check_model_exists "$OLLAMA_MODEL"; then
    echo -e "${YELLOW}⚠️  Model ${OLLAMA_MODEL} not found${NC}"
    pull_model "$OLLAMA_MODEL" || exit 1
else
    echo -e "${GREEN}✅ Model ${OLLAMA_MODEL} is available${NC}"
fi

# Verify everything works
echo -e "${BLUE}🧪 Testing Ollama connection...${NC}"
if curl -s --max-time 5 "${OLLAMA_URL}/api/tags" > /dev/null; then
    echo -e "${GREEN}✅ Ollama is ready for tests!${NC}"
    echo ""
    echo "Configuration:"
    echo "  URL: ${OLLAMA_URL}"
    echo "  Model: ${OLLAMA_MODEL}"
    exit 0
else
    echo -e "${RED}❌ Ollama connection test failed${NC}"
    exit 1
fi
