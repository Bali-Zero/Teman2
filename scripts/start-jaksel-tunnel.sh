#!/bin/bash
# Start CloudFlare Tunnel for Jaksel Ollama API
# This exposes local Ollama (port 11434) to the internet via CloudFlare

echo "🚀 Starting Jaksel Ollama Tunnel..."

# Check if Ollama is running
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama is not running. Starting it..."
    ollama serve &
    sleep 3
fi

# Verify zantara-jaksel model is available
if ! ollama list | grep -q "zantara-jaksel"; then
    echo "❌ Model zantara-jaksel not found!"
    exit 1
fi

echo "✅ Ollama is running with zantara-jaksel model"

# Start CloudFlare Quick Tunnel (no configuration needed)
# This creates a temporary public URL
echo "🌐 Starting CloudFlare Quick Tunnel..."
echo "   The URL will be displayed below - use it in simple_jaksel_caller.py"
echo ""

cloudflared tunnel --url http://localhost:11434

# Note: For a permanent URL, you need to:
# 1. cloudflared tunnel login
# 2. cloudflared tunnel create jaksel-ollama
# 3. cloudflared tunnel route dns jaksel-ollama jaksel-ollama.nuzantara.com
# 4. cloudflared tunnel run jaksel-ollama
