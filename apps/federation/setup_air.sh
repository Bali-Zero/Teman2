#!/bin/bash
# Federation Air Machine Setup — Deploy agents to air.local
#
# Deploys: notebooklm (port 8087), air-batch (port 8091)
# Run from Pro: bash apps/federation/setup_air.sh
#
# Prerequisites:
#   - Air reachable via `ssh air`
#   - Git repo synced on Air at ~/Projects/nuzantara
#   - Python + a2a-sdk installed on Air

set -euo pipefail

AIR_HOST="air"
AIR_REPO="~/Projects/nuzantara"

echo "═══════════════════════════════════════════"
echo "  Federation Air Machine Setup"
echo "═══════════════════════════════════════════"

# 1. Check Air connectivity
echo ""
echo "[1/4] Checking Air connectivity..."
ssh -o ConnectTimeout=5 "$AIR_HOST" 'echo "✅ Connected: $(whoami)@$(hostname)"' || {
    echo "❌ Air unreachable. Check SSH config."
    exit 1
}

# 2. Sync repo
echo ""
echo "[2/4] Syncing git repo on Air..."
ssh "$AIR_HOST" "cd $AIR_REPO && git pull --ff-only" || {
    echo "⚠️  Git pull failed. Manual sync may be needed."
}

# 3. Check dependencies
echo ""
echo "[3/4] Checking dependencies on Air..."
ssh "$AIR_HOST" "cd $AIR_REPO && python3 -c 'from a2a.server.apps.jsonrpc import A2AFastAPIApplication; print(\"✅ a2a-sdk OK\")'" || {
    echo "❌ a2a-sdk not installed on Air. Run: pip3 install a2a-sdk"
    exit 1
}

# 4. Create launcher script on Air
echo ""
echo "[4/4] Creating Air agent launcher..."
ssh "$AIR_HOST" "cat > $AIR_REPO/start_air_agents.sh << 'LAUNCHER'
#!/bin/bash
# Auto-generated Air federation agent launcher
cd ~/Projects/nuzantara

echo \"Starting Air federation agents...\"

# Start notebooklm on port 8087
echo \"  Starting notebooklm (port 8087)...\"
python3 -m apps.federation.a2a_service --agent notebooklm --port 8087 --host 0.0.0.0 &
NLM_PID=\$!

# Start air-batch on port 8091
echo \"  Starting air-batch (port 8091)...\"
python3 -m apps.federation.a2a_service --agent air-batch --port 8091 --host 0.0.0.0 &
BATCH_PID=\$!

echo \"\"
echo \"Air agents started:\"
echo \"  notebooklm: PID=\$NLM_PID, port=8087\"
echo \"  air-batch:  PID=\$BATCH_PID, port=8091\"
echo \"\"
echo \"Press Ctrl+C to stop.\"

trap \"kill \$NLM_PID \$BATCH_PID 2>/dev/null; echo 'Stopped.'; exit 0\" SIGINT SIGTERM
wait
LAUNCHER
chmod +x $AIR_REPO/start_air_agents.sh"

echo ""
echo "═══════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  To start agents on Air:"
echo "    ssh air 'cd ~/Projects/nuzantara && ./start_air_agents.sh'"
echo ""
echo "  Or use nohup for background:"
echo "    ssh air 'cd ~/Projects/nuzantara && nohup ./start_air_agents.sh > /tmp/air-agents.log 2>&1 &'"
echo ""
echo "  To verify from Pro:"
echo "    curl http://air.local:8087/.well-known/agent-card.json"
echo "    curl http://air.local:8091/.well-known/agent-card.json"
echo "═══════════════════════════════════════════"
