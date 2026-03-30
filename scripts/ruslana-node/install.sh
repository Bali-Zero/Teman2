#!/usr/bin/env bash
# install.sh — Super OpenClaw Node Setup per Ruslana
# Esegui: bash install.sh
# Da eseguire sul Mac di Ruslana con il repo già clonato

set -euo pipefail

REPO_URL="git@github.com:Balizero1987/Teman2.git"
PROJECT_DIR="$HOME/Desktop/nuzantara"
OPENCLAW_DIR="$HOME/.openclaw-ruslana"
RUSLANA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNmRlMDI1ZC0xYjM4LTRhMmUtODI5Mi00ZTIwZGM2YmJjNGMiLCJlbWFpbCI6InJ1c2xhbmFAYmFsaXplcm8uY29tIiwicm9sZSI6IkJvYXJkIE1lbWJlciIsImV4cCI6MTgwNjM5MDg2N30.a2uo32DXTfIu7Cs-wCUKkUlMo7jekVmQGIJa9UggX4s"
GATEWAY_TOKEN=$(openssl rand -base64 48 | tr -d '\n')

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[node-ruslana]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Super OpenClaw — Node Setup: Ruslana            ║"
echo "║  Nuzantara Federation v1.0                       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── 1. Homebrew ──────────────────────────────────────────────────────────────
log "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
ok "Homebrew ready"

# ─── 2. Git ───────────────────────────────────────────────────────────────────
log "Checking Git..."
brew install git 2>/dev/null || true
ok "Git: $(git --version)"

# ─── 3. Clone repo ────────────────────────────────────────────────────────────
log "Cloning Nuzantara repo..."
if [ -d "$PROJECT_DIR/.git" ]; then
    ok "Repo già esiste — pull"
    cd "$PROJECT_DIR" && git pull --ff-only
else
    git clone https://github.com/Balizero1987/Teman2.git "$PROJECT_DIR" || {
        warn "HTTPS failed, trying SSH..."
        git clone "$REPO_URL" "$PROJECT_DIR"
    }
fi
ok "Repo: $PROJECT_DIR"

# ─── 4. Node.js + Gemini CLI ──────────────────────────────────────────────────
log "Installing Node.js + Gemini CLI..."
brew install node 2>/dev/null || true
npm install -g @google/gemini-cli 2>/dev/null || warn "Gemini CLI install failed — try manually: npm i -g @google/gemini-cli"
GEMINI_VERSION=$(gemini --version 2>/dev/null | head -1 || echo "not found")
ok "Gemini CLI: $GEMINI_VERSION"

# ─── 5. Claude CLI (in aggiunta a Gemini) ────────────────────────────────────
log "Installing Claude CLI..."
npm install -g @anthropic-ai/claude-code 2>/dev/null || warn "Claude CLI install failed — try manually: npm i -g @anthropic-ai/claude-code"
CLAUDE_VERSION=$(claude --version 2>/dev/null | head -1 || echo "not found")
ok "Claude CLI: $CLAUDE_VERSION"

# ─── 6. Python venv per nuzantara-mcp ─────────────────────────────────────────
log "Setting up nuzantara-mcp venv..."
cd "$PROJECT_DIR/apps/nuzantara-mcp"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt 2>/dev/null || \
    .venv/bin/pip install -q fastmcp httpx pydantic 2>/dev/null || true
fi
ok "MCP venv ready"

# ─── 7. Gemini CLI settings ────────────────────────────────────────────────────
log "Writing Gemini CLI config..."
mkdir -p "$HOME/.gemini"
cat > "$HOME/.gemini/settings.json" << SETTINGS
{
  "security": {
    "auth": {"selectedType": "oauth-personal"},
    "enablePermanentToolApproval": true,
    "folderTrust": {"enabled": true}
  },
  "general": {
    "previewFeatures": true,
    "enableAutoUpdate": true,
    "defaultApprovalMode": "default"
  },
  "mcpServers": {
    "nuzantara": {
      "command": "$PROJECT_DIR/apps/nuzantara-mcp/.venv/bin/python",
      "args": ["$PROJECT_DIR/apps/nuzantara-mcp/nuzantara_mcp/server.py"],
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_API_KEY": "$RUSLANA_TOKEN",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
SETTINGS

cat > "$HOME/.gemini/trustedFolders.json" << TRUST
{"$PROJECT_DIR": "TRUST_PARENT"}
TRUST

cat > "$HOME/.gemini/GEMINI.md" << 'GEMINIMD'
# Gemini CLI — Nuzantara Board Assistant (Ruslana)

Sei un AI assistant tecnico per il board di Nuzantara/Bali Zero.
- Parla **italiano** o **inglese** con Ruslana
- Usa i tool MCP per dati reali — non inventare
- Per bug/deploy → segnala a Zero
- Repo: ~/Desktop/nuzantara
- Backend: https://nuzantara-rag.fly.dev

## Ruolo Ruslana
Board Member — accesso completo a analytics, revenue, compliance, clienti.

## MCP Tools Chiave
- `get_revenue_analytics` — analytics ricavi
- `get_client_stats` — statistiche CRM
- `get_compliance_alerts` — alert compliance
- `list_clients` — lista clienti
- `get_team_productivity` — produttività team
- `check_health` — stato sistema
GEMINIMD
ok "Gemini CLI configured"

# ─── 8. Claude CLI settings (MCP) ────────────────────────────────────────────
log "Writing Claude CLI config..."
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/settings.json" << CLAUDE_SETTINGS
{
  "defaultMode": "acceptEdits",
  "mcpServers": {
    "nuzantara": {
      "command": "$PROJECT_DIR/apps/nuzantara-mcp/.venv/bin/python",
      "args": ["$PROJECT_DIR/apps/nuzantara-mcp/nuzantara_mcp/server.py"],
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_API_KEY": "$RUSLANA_TOKEN",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
CLAUDE_SETTINGS
ok "Claude CLI configured with MCP"

# ─── 9. OpenClaw node config ──────────────────────────────────────────────────
log "Setting up OpenClaw node config..."
mkdir -p "$OPENCLAW_DIR/workspace/memory"
mkdir -p "$OPENCLAW_DIR/logs"

cp "$PROJECT_DIR/scripts/ruslana-node/workspace/AGENTS.md" "$OPENCLAW_DIR/workspace/"
cp "$PROJECT_DIR/scripts/ruslana-node/workspace/SOUL.md" "$OPENCLAW_DIR/workspace/"
cp "$PROJECT_DIR/scripts/ruslana-node/workspace/TASKS.md" "$OPENCLAW_DIR/workspace/"

sed "s/GENERATE_ON_INSTALL/$GATEWAY_TOKEN/g; s/RUSLANA_JWT_PLACEHOLDER/$RUSLANA_TOKEN/g" \
    "$PROJECT_DIR/scripts/ruslana-node/openclaw-ruslana.json" > "$OPENCLAW_DIR/openclaw.json"
ok "OpenClaw node config: $OPENCLAW_DIR"

# ─── 10. Git auto-sync (pull ogni ora) ────────────────────────────────────────
log "Setting up git auto-sync cron..."
CRON_CMD="cd $PROJECT_DIR && git pull --ff-only --quiet 2>/dev/null"
(crontab -l 2>/dev/null | grep -v "nuzantara.*pull"; echo "0 * * * * $CRON_CMD") | crontab -
ok "Cron: git pull ogni ora"

# ─── Report finale ────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Setup completato!                            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Prossimi passi:"
echo ""
echo "1. Login Gemini:"
echo "   gemini auth login"
echo "   → seleziona ruslana@balizero.com"
echo ""
echo "2. Test Gemini + MCP:"
echo "   cd ~/Desktop/nuzantara"
echo "   gemini"
echo "   > mostrami le ultime analytics revenue"
echo ""
echo "3. Test Claude + MCP:"
echo "   cd ~/Desktop/nuzantara"
echo "   claude"
echo "   > mostrami le ultime analytics revenue"
echo ""
echo "4. (Opzionale) Installa OpenClaw:"
echo "   brew install --cask openclaw"
echo "   cp ~/.openclaw-ruslana/openclaw.json ~/.openclaw/openclaw.json"
echo ""
warn "IMPORTANTE: Fai 'gemini auth login' con ruslana@balizero.com!"
