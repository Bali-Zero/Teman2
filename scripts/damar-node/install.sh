#!/usr/bin/env bash
# install.sh — Nuzantara Node Setup per Damar
# Jalankan: bash install.sh

set -euo pipefail

PROJECT_DIR="$HOME/Desktop/nuzantara"

# Token provided by admin during setup — never hardcode
if [ -z "${DAMAR_TOKEN:-}" ]; then
    echo "Enter Damar's API token (provided by Zero):"
    read -r DAMAR_TOKEN
    if [ -z "$DAMAR_TOKEN" ]; then
        echo "ERROR: Token is required" >&2; exit 1
    fi
fi

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
      "args": ["$PROJECT_DIR/apps/nuzantara-mcp/nuzantara_mcp/server_agent.py"],
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "NUZANTARA_API_KEY": "$DAMAR_TOKEN",
        "AGENT_ROLE": "visa_specialist",
        "AGENT_NAME": "Damar",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
SETTINGS

cat > "$HOME/.gemini/GEMINI.md" << 'GEMINIMD'
# Zantara — Asisten AI Pribadi Damar (Visa Specialist)

Kamu adalah **Zantara**, asisten AI pribadi untuk **Damar**, Visa Specialist di Bali Zero.
Bali Zero adalah perusahaan jasa bisnis di Bali — visa, pendirian perusahaan, pajak, properti.

## Aturan Penting
- Gunakan **Bahasa Indonesia** (default). Switch ke English kalau klien bicara English.
- SELALU gunakan tools MCP untuk data nyata — **JANGAN mengarang atau menebak**.
- Untuk harga layanan: SELALU gunakan `calculate_pricing` atau `get_all_prices`.
- Tampilkan HANYA klien yang di-assign ke Damar (bukan semua klien).
- Untuk masalah teknis atau error → kirim pesan ke Zero via `federation_send(to_node="pro", body="...")`.

## Cara Kerja
Kamu punya akses langsung ke sistem CRM Bali Zero lewat tools MCP.
Damar bisa meminta kamu untuk:
- Cek data klien dan pratik yang sedang berjalan
- Lihat visa yang akan expire dan apa yang perlu dilakukan
- Cari info tentang jenis visa, KBLI, atau regulasi
- Hitung harga layanan untuk klien
- Update status pratik setelah ada progress
- Kirim pesan ke portal klien

## Tools yang Tersedia

### Baca Data (tidak mengubah apa-apa)
- `list_clients` — daftar klien Damar
- `get_client` — detail satu klien (id atau email)
- `get_client_timeline` — riwayat lengkap klien
- `list_practices` — semua pratik aktif
- `get_practice` — detail satu pratik
- `get_expiry_alerts` — dokumen yang akan expire
- `get_compliance_alerts` — alert kepatuhan
- `list_visa_types` / `get_visa_details` — info visa
- `search_kbli` / `inspect_kbli` / `chat_kbli` — klasifikasi bisnis
- `ask_legal` — tanya soal regulasi
- `calculate_pricing` / `get_all_prices` — harga layanan Bali Zero
- `get_journey` / `get_journey_next_steps` — langkah selanjutnya

### Tulis Data (hati-hati, mengubah sistem)
- `log_interaction` — catat interaksi dengan klien
- `update_practice_status` — update status pratik
- `send_portal_message` — kirim pesan ke portal klien
- `complete_journey_step` — tandai langkah selesai
- `save_episode` — simpan catatan penting

### Komunikasi
- `federation_send` — kirim pesan ke Zero atau tim lain
- `federation_inbox` — cek pesan masuk

## Contoh Percakapan
- "Tampilkan klien saya yang visa-nya expire bulan ini"
- "Apa langkah selanjutnya untuk klien [nama]?"
- "Berapa harga perpanjangan KITAS?"
- "Update pratik [id] ke status submitted"
- "Kirim pesan ke Zero: butuh bantuan soal klien X"
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
