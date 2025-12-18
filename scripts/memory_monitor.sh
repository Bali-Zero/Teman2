#!/bin/bash

# Memory Monitor & Auto-Clean Script
# Previne crash di RAM su macOS

THRESHOLD_LOAD=50
THRESHOLD_MEM=85

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

while true; do
    # Check load average
    LOAD=$(uptime | awk '{print $NF}' | sed 's/,//')
    LOAD_INT=$(echo "$LOAD" | cut -d. -f1)

    # Check memory usage
    MEM_USED=$(top -l 1 | grep "PhysMem" | awk '{print $2}' | sed 's/[^0-9]//g')
    MEM_TOTAL=16384  # 16GB in MB
    MEM_PERCENT=$((MEM_USED * 100 / MEM_TOTAL))

    echo "$(date): Load: $LOAD | Memory: $MEM_PERCENT%"

    if [ "$LOAD_INT" -gt "$THRESHOLD_LOAD" ] || [ "$MEM_PERCENT" -gt "$THRESHOLD_MEM" ]; then
        echo -e "${RED}🚨 CRITICAL: Load: $LOAD, Memory: $MEM_PERCENT%${NC}"

        # Auto-cleanup actions
        echo -e "${YELLOW}🔧 Executing automatic cleanup...${NC}"

        # Kill high-memory IDE processes
        pkill -f "Antigravity.*Helper.*Plugin"
        pkill -f "Claude.*Opus"
        pkill -f "gemini.*node"

        # Clear caches
        sudo purge 2>/dev/null

        # Compress inactive memory
        sudo sysctl -w vm.compressor_mode=4 2>/dev/null

        echo -e "${GREEN}✅ Cleanup completed${NC}"

        # Send notification
        osascript -e "display notification \"System memory cleanup completed\" with title \"Auto-Clean Script\""
    fi

    sleep 30
done
