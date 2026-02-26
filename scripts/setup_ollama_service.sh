#!/bin/bash
#
# Setup Ollama as a System Service (macOS/Linux)
# Ensures Ollama always starts automatically and stays running
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔧 Setting up Ollama as persistent service...${NC}"
echo -e "${YELLOW}   This will ensure Ollama is ALWAYS running${NC}"
echo ""

# Check OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - Use launchd
    echo -e "${YELLOW}📱 Detected macOS - setting up launchd service${NC}"
    
    PLIST_FILE="$HOME/Library/LaunchAgents/com.ollama.test.plist"
    
    cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.test</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which ollama)</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ollama_service.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ollama_service.error.log</string>
</dict>
</plist>
EOF
    
    # Load the service
    launchctl load "$PLIST_FILE" 2>/dev/null || launchctl unload "$PLIST_FILE" 2>/dev/null && launchctl load "$PLIST_FILE"
    
    echo -e "${GREEN}✅ Ollama service installed for macOS${NC}"
    echo "   Service file: $PLIST_FILE"
    echo "   To stop: launchctl unload $PLIST_FILE"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - Use systemd
    echo -e "${YELLOW}🐧 Detected Linux - setting up systemd service${NC}"
    
    SERVICE_FILE="/etc/systemd/system/ollama-test.service"
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Need sudo to create systemd service${NC}"
        echo "Run: sudo $0"
        exit 1
    fi
    
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Ollama Test Service
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$(which ollama) serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ollama-test.service
    systemctl start ollama-test.service
    
    echo -e "${GREEN}✅ Ollama service installed for Linux${NC}"
    echo "   Service: ollama-test.service"
    echo "   To stop: sudo systemctl stop ollama-test.service"
    
else
    echo -e "${YELLOW}⚠️  Unsupported OS: $OSTYPE${NC}"
    echo "   Ollama will need to be started manually"
    exit 1
fi

# Ensure Qwen model is available
echo -e "${BLUE}📥 Ensuring Qwen model is available...${NC}"
sleep 3  # Wait for Ollama to be ready
if ollama pull qwen2.5:latest; then
    echo -e "${GREEN}✅ Qwen model ready${NC}"
else
    echo -e "${YELLOW}⚠️  Model pull may have failed, but service is running${NC}"
    echo "   You can pull manually later: ollama pull qwen2.5:latest"
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📋 Status:"
echo "   ✅ Ollama will start automatically on boot"
echo "   ✅ Ollama will restart if it crashes"
echo "   ✅ Model: qwen2.5:latest"
echo ""
echo "🔧 Management commands:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   Start:   launchctl load $PLIST_FILE"
    echo "   Stop:    launchctl unload $PLIST_FILE"
    echo "   Status:  launchctl list | grep ollama"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "   Start:   sudo systemctl start ollama-test.service"
    echo "   Stop:    sudo systemctl stop ollama-test.service"
    echo "   Status:  sudo systemctl status ollama-test.service"
fi
echo ""
echo -e "${GREEN}🎉 Ollama is now ALWAYS available!${NC}"
echo "   No need to run scripts manually - Ollama stays running"
