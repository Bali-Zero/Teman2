#!/usr/bin/env bash
# install.sh — Super OpenClaw Node Setup untuk Krisna
# Jalankan: bash install.sh
# Dieksekusi dari Pro via SSH setelah SSH aktif di Mac Krisna

set -euo pipefail

REPO_URL="git@github.com:Balizero1987/Teman2.git"
PROJECT_DIR="$HOME/Desktop/nuzantara"
OPENCLAW_DIR="$HOME/.openclaw-krisna"
KRISNA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjAxMzhjMC1jYWVkLTQ2NGItOGY0ZC0zZjJlMGM3ZTk3YjYiLCJlbWFpbCI6ImtyaXNuYUBiYWxpemVyby5jb20iLCJyb2xlIjoiRXhlY3V0aXZlIENvbnN1bHRhbnQiLCJleHAiOjE3ODIyNzk4Mzd9.mgXUhhc-JmU4UWpW1Un8bR7bdtwRPEMU86u_6B7ohJw"
GATEWAY_TOKEN=$(openssl rand -base64 48 | tr -d '\n')

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[node-krisna]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Super OpenClaw — Node Setup: Krisna             ║"
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
    # Try HTTPS first (no SSH key needed)
    git clone https://github.com/Balizero1987/Teman2.git "$PROJECT_DIR" || {
        warn "HTTPS failed, trying SSH..."
        git clone "$REPO_URL" "$PROJECT_DIR"
    }
fi
ok "Repo: $PROJECT_DIR"

# ─── 4. Node.js + Gemini CLI ─────────────────────────────────────────────────
log "Installing Node.js + Gemini CLI..."
brew install node 2>/dev/null || true
npm install -g @google/gemini-cli 2>/dev/null || warn "Gemini CLI install failed — try manually: npm i -g @google/gemini-cli"
GEMINI_VERSION=$(gemini --version 2>/dev/null | head -1 || echo "not found")
ok "Gemini CLI: $GEMINI_VERSION"

# ─── 5. Python venv per nuzantara-mcp ─────────────────────────────────────────
log "Setting up nuzantara-mcp venv..."
cd "$PROJECT_DIR/apps/nuzantara-mcp"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt 2>/dev/null || \
    .venv/bin/pip install -q fastmcp httpx pydantic 2>/dev/null || true
fi
ok "MCP venv ready"

# ─── 6. Gemini CLI settings ────────────────────────────────────────────────────
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
        "NUZANTARA_API_KEY": "$KRISNA_TOKEN",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
SETTINGS

cat > "$HOME/.gemini/trustedFolders.json" << TRUST
{"$PROJECT_DIR": "TRUST_PARENT"}
TRUST

# GEMINI.md globale
cp "$PROJECT_DIR/scripts/krisna-node/workspace/SOUL.md" /tmp/soul_tmp.md
cat > "$HOME/.gemini/GEMINI.md" << 'GEMINIMD'
# Gemini CLI — Nuzantara Node Krisna

Kamu adalah agen CRM internal tim Nuzantara/Bali Zero.
- Bicara Bahasa Indonesia dengan Krisna
- Gunakan MCP tools untuk data real (jangan tebak)
- Untuk bug/deploy → eskalasi ke Zero via shared/escalations.json
- Repo: ~/Desktop/nuzantara
- Backend: https://nuzantara-rag.fly.dev
- Docs lengkap: ~/Desktop/nuzantara/scripts/krisna-node/workspace/
GEMINIMD
ok "Gemini CLI configured"

# ─── 7. OpenClaw node config ───────────────────────────────────────────────────
log "Setting up OpenClaw node config..."
mkdir -p "$OPENCLAW_DIR/workspace/memory"
mkdir -p "$OPENCLAW_DIR/logs"

# Copy workspace files
cp "$PROJECT_DIR/scripts/krisna-node/workspace/AGENTS.md" "$OPENCLAW_DIR/workspace/"
cp "$PROJECT_DIR/scripts/krisna-node/workspace/SOUL.md" "$OPENCLAW_DIR/workspace/"
cp "$PROJECT_DIR/scripts/krisna-node/workspace/TASKS.md" "$OPENCLAW_DIR/workspace/"

# Write openclaw config with generated gateway token
sed "s/GENERATE_ON_INSTALL/$GATEWAY_TOKEN/g; s/KRISNA_JWT_PLACEHOLDER/$KRISNA_TOKEN/g" \
    "$PROJECT_DIR/scripts/krisna-node/openclaw-krisna.json" > "$OPENCLAW_DIR/openclaw.json"
ok "OpenClaw node config: $OPENCLAW_DIR"

# ─── 8. Git auto-sync (pull ogni ora) ─────────────────────────────────────────
log "Setting up git auto-sync cron..."
CRON_CMD="cd $PROJECT_DIR && git pull --ff-only --quiet 2>/dev/null"
(crontab -l 2>/dev/null | grep -v "nuzantara.*pull"; echo "0 * * * * $CRON_CMD") | crontab -
ok "Cron: git pull ogni ora"

# ─── 9. Report finale ─────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Setup completato!                            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Langkah selanjutnya:"
echo ""
echo "1. Login Gemini (buka browser):"
echo "   gemini auth login"
echo ""
echo "2. Test Gemini + MCP:"
echo "   cd ~/Desktop/nuzantara"
echo "   gemini"
echo "   > coba list 5 klien terakhir"
echo ""
echo "3. (Opsional) Install OpenClaw:"
echo "   brew install --cask openclaw"
echo "   cp ~/.openclaw-krisna/openclaw.json ~/.openclaw/openclaw.json"
echo ""
echo "Gateway token (simpan):"
echo "  $GATEWAY_TOKEN"
echo ""
warn "PENTING: Jalankan 'gemini auth login' setelah ini!"
