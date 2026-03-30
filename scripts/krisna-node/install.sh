#!/usr/bin/env bash
# install.sh — Nuzantara Node Setup per Krisna
# Jalankan: bash install.sh

set -euo pipefail

PROJECT_DIR="$HOME/Desktop/nuzantara"
KRISNA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjAxMzhjMC1jYWVkLTQ2NGItOGY0ZC0zZjJlMGM3ZTk3YjYiLCJlbWFpbCI6ImtyaXNuYUBiYWxpemVyby5jb20iLCJyb2xlIjoiRXhlY3V0aXZlIENvbnN1bHRhbnQiLCJleHAiOjE4MDYzOTA4Njd9.fZRo1yhqxgd3dqvYv0m6p36xr5xP3u8fghVc4ycdP5g"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[node-krisna]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Nuzantara Federation — Node Setup: Krisna       ║"
echo "║  Executive Consultant Assistant                  ║"
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
        "NUZANTARA_API_KEY": "$KRISNA_TOKEN",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
SETTINGS

cat > "$HOME/.gemini/GEMINI.md" << 'GEMINIMD'
# Gemini CLI — Nuzantara Executive Consultant Assistant (Krisna)

Kamu adalah AI assistant untuk Krisna, Executive Consultant di Bali Zero.
- Gunakan **Bahasa Indonesia** (default)
- Gunakan tools MCP untuk data nyata — jangan mengarang
- Untuk bug/masalah teknis → laporkan ke Zero
- Fokus: setup perusahaan, klien, onboarding, pratik

## Tools Utama
- `get_client` — cek data klien
- `create_client` — buat klien baru
- `list_practices` — daftar pratik aktif
- `get_practice` — detail satu pratik
- `update_practice_status` — update status pratik
- `get_client_timeline` — riwayat klien
- `create_journey` — buat journey baru
- `get_journey_next_steps` — langkah selanjutnya
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
echo "   → pilih krisna@balizero.com"
echo ""
echo "2. Test:"
echo "   cd ~/Desktop/nuzantara"
echo "   gemini"
echo "   > tampilkan daftar klien terbaru"
echo ""
warn "PENTING: Login dengan krisna@balizero.com saat diminta!"
