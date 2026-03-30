#!/usr/bin/env bash
# install.sh — Nuzantara Node Setup per Damar
# Jalankan: bash install.sh

set -euo pipefail

PROJECT_DIR="$HOME/Desktop/nuzantara"
DAMAR_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwZjAyYWQ3YS0wZWVlLTRjZWQtOGRkMi0zNmVlNWE1NzcyODAiLCJlbWFpbCI6ImRhbWFyQGJhbGl6ZXJvLmNvbSIsInJvbGUiOiJKdW5pb3IgQ29uc3VsdGFudCIsImV4cCI6MTgwNjM5MDkyOH0.vFIoKhJRuAa3hTZunNR4DGLj0Zh0OK_rVvw_mLWZiDw"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[node-damar]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Nuzantara Federation — Node Setup: Damar        ║"
echo "║  Visa Specialist Assistant                       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── 1. Homebrew ──────────────────────────────────────────────────────────────
log "Mengecek Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Menginstall Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
ok "Homebrew siap"

# ─── 2. Node.js + Gemini CLI ──────────────────────────────────────────────────
log "Menginstall Node.js + Gemini CLI..."
brew install node 2>/dev/null || true
npm install -g @google/gemini-cli 2>/dev/null || warn "Coba manual: npm i -g @google/gemini-cli"
ok "Gemini CLI: $(gemini --version 2>/dev/null | head -1 || echo 'installed')"

# ─── 3. Clone/update repo ─────────────────────────────────────────────────────
log "Menyiapkan repo Nuzantara..."
if [ -d "$PROJECT_DIR/.git" ]; then
    ok "Repo sudah ada — update"
    cd "$PROJECT_DIR" && git pull --ff-only
else
    git clone https://github.com/Balizero1987/Teman2.git "$PROJECT_DIR"
fi
ok "Repo: $PROJECT_DIR"

# ─── 4. Python venv untuk nuzantara-mcp ───────────────────────────────────────
log "Menyiapkan Python environment..."
cd "$PROJECT_DIR/apps/nuzantara-mcp"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q fastmcp httpx pydantic 2>/dev/null || true
fi
ok "Python environment siap"

# ─── 5. Gemini CLI settings ───────────────────────────────────────────────────
log "Mengkonfigurasi Gemini CLI..."
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
    "enableAutoUpdate": true
  },
  "mcpServers": {
    "nuzantara": {
      "command": "$PROJECT_DIR/apps/nuzantara-mcp/.venv/bin/python",
      "args": ["$PROJECT_DIR/apps/nuzantara-mcp/nuzantara_mcp/server.py"],
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_API_KEY": "$DAMAR_TOKEN",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
SETTINGS

cat > "$HOME/.gemini/GEMINI.md" << 'GEMINIMD'
# Gemini CLI — Nuzantara Visa Specialist Assistant (Damar)

Kamu adalah AI assistant untuk Damar, Visa Specialist di Bali Zero.
- Gunakan **Bahasa Indonesia** (default)
- Gunakan tools MCP untuk data nyata — jangan mengarang
- Untuk bug/masalah teknis → laporkan ke Zero
- Fokus: visa, perizinan, klien, pratik

## Tools Utama
- `get_client` — cek data klien
- `list_practices` — daftar pratik aktif
- `get_practice` — detail satu pratik
- `get_expiry_alerts` — visa yang akan habis
- `get_compliance_alerts` — alert kepatuhan
- `list_visa_types` — jenis visa tersedia
- `check_health` — cek status sistem
GEMINIMD

cat > "$HOME/.gemini/trustedFolders.json" << TRUST
{"$PROJECT_DIR": "TRUST_PARENT"}
TRUST

ok "Gemini CLI dikonfigurasi"

# ─── 6. Git auto-sync ─────────────────────────────────────────────────────────
log "Mengaktifkan auto-sync repo..."
CRON_CMD="cd $PROJECT_DIR && git pull --ff-only --quiet 2>/dev/null"
(crontab -l 2>/dev/null | grep -v "nuzantara.*pull"; echo "0 * * * * $CRON_CMD") | crontab -
ok "Auto-sync aktif (setiap jam)"

# ─── Selesai ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Setup selesai!                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Langkah selanjutnya:"
echo ""
echo "1. Login Gemini:"
echo "   gemini auth login"
echo "   → pilih damar@balizero.com"
echo ""
echo "2. Test:"
echo "   cd ~/Desktop/nuzantara"
echo "   gemini"
echo "   > tampilkan daftar pratik aktif"
echo ""
warn "PENTING: Login dengan damar@balizero.com saat diminta!"
