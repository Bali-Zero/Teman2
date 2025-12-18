#!/bin/bash
# Setup Permanent CloudFlare Tunnel for Jaksel Ollama
# This creates a permanent subdomain: jaksel-ollama.nuzantara.com

set -e

TUNNEL_NAME="jaksel-ollama"
SUBDOMAIN="jaksel-ollama.nuzantara.com"

echo "🔧 Setting up permanent CloudFlare Tunnel for Jaksel AI"
echo "   Tunnel Name: $TUNNEL_NAME"
echo "   Subdomain: $SUBDOMAIN"
echo ""

# Check if already logged in
if ! cloudflared tunnel list &>/dev/null; then
    echo "📝 Please login to CloudFlare first..."
    cloudflared tunnel login
fi

# Check if tunnel exists
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "✅ Tunnel '$TUNNEL_NAME' already exists"
else
    echo "🔨 Creating tunnel '$TUNNEL_NAME'..."
    cloudflared tunnel create "$TUNNEL_NAME"
fi

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "   Tunnel ID: $TUNNEL_ID"

# Create config file
CONFIG_FILE="$HOME/.cloudflared/config-jaksel.yml"
echo "📝 Creating config file: $CONFIG_FILE"
cat > "$CONFIG_FILE" << EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $SUBDOMAIN
    service: http://localhost:11434
  - service: http_status:404
EOF

echo "✅ Config file created"

# Route DNS (requires domain to be on CloudFlare)
echo "🌐 Routing DNS..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$SUBDOMAIN" 2>/dev/null || echo "   DNS route may already exist"

echo ""
echo "🚀 To start the tunnel, run:"
echo "   cloudflared tunnel --config $CONFIG_FILE run"
echo ""
echo "Or use the service script:"
echo "   ./scripts/start-jaksel-tunnel-permanent.sh"
