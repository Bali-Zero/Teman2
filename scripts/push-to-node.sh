#!/bin/bash
# push-to-node.sh — Push gateway updates to a team node
# Usage: ./scripts/push-to-node.sh adit|damar [restart]

set -euo pipefail
NODE="${1:?Usage: push-to-node.sh <node-alias> [restart]}"
RESTART="${2:-no}"
SRC="$(dirname "$0")/zantara-gateway"
MCP_SRC="$(dirname "$0")/../apps/nuzantara-mcp/nuzantara_mcp"

echo "→ Pushing gateway files to ${NODE}..."
scp -q "$SRC"/{gateway.py,config.py,mcp_client.py,acp_client.py,claude_client.py,gemini_api_client.py} "${NODE}":~/.zantara-gateway/
echo "✓ Gateway files pushed"

echo "→ Pushing MCP server files to ${NODE}..."
ssh "$NODE" "mkdir -p ~/Desktop/nuzantara/apps/nuzantara-mcp/nuzantara_mcp"
scp -q -r "$MCP_SRC"/ "${NODE}":~/Desktop/nuzantara/apps/nuzantara-mcp/nuzantara_mcp/
echo "✓ MCP server pushed"

if [ "$RESTART" = "restart" ]; then
    echo "→ Restarting gateway on ${NODE}..."
    ssh "$NODE" "export PATH=/opt/homebrew/bin:~/bin:\$PATH && zantara-ctl restart-gw"
    echo "✓ Gateway restarted"
fi

echo "✅ ${NODE} updated"
