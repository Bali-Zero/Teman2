#!/usr/bin/env bash
# mac-bootstrap.sh — Setup a team member's Mac as a Nuzantara OpenClaw node
#
# Usage:
#   ./mac-bootstrap.sh --role visa_specialist --name damar
#
# Prerequisites: Homebrew installed, Google Workspace account

set -euo pipefail

# Parse arguments
ROLE=""
NAME=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --role) ROLE="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$ROLE" || -z "$NAME" ]]; then
  echo "Usage: $0 --role <role> --name <name>"
  echo "Roles: visa_specialist, tax_consultant, company_setup, admin"
  exit 1
fi

echo "🦞 Nuzantara Team Agent Setup"
echo "   Name: $NAME"
echo "   Role: $ROLE"
echo ""

# 1. Check Homebrew
command -v brew >/dev/null || { echo "❌ Install Homebrew first: https://brew.sh"; exit 1; }
echo "✅ Homebrew found"

# 2. Install Node.js (for Baileys bridge)
if ! command -v node >/dev/null; then
  echo "📦 Installing Node.js..."
  brew install node
else
  echo "✅ Node.js $(node -v) found"
fi

# 3. Install OpenClaw
if ! command -v openclaw >/dev/null; then
  echo "📦 Installing OpenClaw..."
  npm install -g openclaw
else
  echo "✅ OpenClaw $(openclaw --version 2>/dev/null | head -1) found"
fi

# 4. Install Gemini CLI
if ! command -v gemini >/dev/null; then
  echo "📦 Installing Gemini CLI..."
  npm install -g @google/gemini-cli
  echo "🔑 Login to Gemini CLI with your @balizero.com account..."
  echo "   Run: gemini"
  echo "   Follow the OAuth login flow"
else
  echo "✅ Gemini CLI found"
fi

# 5. Setup bridge directory
BRIDGE_DIR="$HOME/.nuzantara/bridge"
WRAPPER_DIR="$HOME/.nuzantara/mcp-wrapper"
LOGS_DIR="$HOME/.nuzantara/logs"
mkdir -p "$BRIDGE_DIR" "$WRAPPER_DIR" "$LOGS_DIR"

echo "📂 Created directories:"
echo "   Bridge:  $BRIDGE_DIR"
echo "   Wrapper: $WRAPPER_DIR"
echo "   Logs:    $LOGS_DIR"

# 6. Copy bridge files (assumes script is run from monorepo root or files are alongside)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONOREPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ -d "$MONOREPO_ROOT/apps/team-agent/bridge" ]]; then
  echo "📋 Copying bridge from monorepo..."
  cp -r "$MONOREPO_ROOT/apps/team-agent/bridge/"* "$BRIDGE_DIR/"
  cd "$BRIDGE_DIR" && npm install --production
  echo "✅ Bridge installed"
else
  echo "⚠️  Bridge files not found at $MONOREPO_ROOT/apps/team-agent/bridge"
  echo "   Copy them manually to $BRIDGE_DIR"
fi

# 7. Copy MCP wrapper
if [[ -d "$MONOREPO_ROOT/apps/team-agent/mcp-wrapper" ]]; then
  echo "📋 Copying MCP wrapper from monorepo..."
  cp -r "$MONOREPO_ROOT/apps/team-agent/mcp-wrapper/"* "$WRAPPER_DIR/"
  echo "✅ MCP wrapper installed"
else
  echo "⚠️  MCP wrapper not found"
fi

# 8. Create .env for bridge
PHONE_NUMBER=""
echo ""
read -p "📱 Enter your WhatsApp number (no +, e.g. 6281234567890): " PHONE_NUMBER

cat > "$BRIDGE_DIR/.env" << EOF
WHITELIST_NUMBER=$PHONE_NUMBER
OPENCLAW_URL=http://localhost:18789
SESSION_DIR=./sessions
HEALTH_PORT=3100
AGENT_NAME=${NAME}-${ROLE}
EOF
echo "✅ Bridge .env created"

# 9. Create wrapper env
cat > "$WRAPPER_DIR/.env" << EOF
AGENT_ROLE=$ROLE
REAL_MCP_CMD=$HOME/.local/bin/nuzantara-mcp-server
EOF
echo "✅ Wrapper .env created"

# 10. Create LaunchAgent for auto-start
PLIST_PATH="$HOME/Library/LaunchAgents/com.nuzantara.agent.plist"
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which node)</string>
        <string>${BRIDGE_DIR}/dist/index.js</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${BRIDGE_DIR}</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOGS_DIR}/agent.log</string>
    <key>StandardErrorPath</key>
    <string>${LOGS_DIR}/agent-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF
echo "✅ LaunchAgent created at $PLIST_PATH"

echo ""
echo "========================================="
echo "🎉 Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Login to Gemini CLI:  gemini"
echo "  2. Start the bridge:     cd $BRIDGE_DIR && npm run dev"
echo "  3. Scan QR code from your phone when it appears"
echo "  4. Test: send a WhatsApp message to yourself"
echo ""
echo "To enable auto-start on login:"
echo "  launchctl load $PLIST_PATH"
echo ""
