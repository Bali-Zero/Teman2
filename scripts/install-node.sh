#!/usr/bin/env bash
# install-node.sh — Generic Nuzantara Team Node Setup
# Usage: ROLE=visa_specialist NAME=Damar TOKEN=xxx bash scripts/install-node.sh

set -euo pipefail

# ─── Required env vars ────────────────────────────────────────────────────────
: "${ROLE:?ERROR: ROLE is required (e.g. visa_specialist, executive_consultant)}"
: "${NAME:?ERROR: NAME is required (e.g. Damar, Krisna)}"
: "${TOKEN:?ERROR: TOKEN is required (API key from admin)}"

PROJECT_DIR="$HOME/Desktop/nuzantara"
GATEWAY_DIR="$HOME/.zantara-gateway"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[node-${NAME,,}]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Nuzantara Federation — Node Setup               ║"
printf "║  %-48s║\n" "Name: ${NAME} | Role: ${ROLE}"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── 1. Homebrew ──────────────────────────────────────────────────────────────
log "Mengecek Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Menginstall Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
ok "Homebrew siap"

# ─── 2. System tools ──────────────────────────────────────────────────────────
log "Menginstall system tools..."
brew install node python@3.11 ollama mkcert 2>/dev/null || true
ok "System tools siap"

# ─── 3. Gemini CLI ────────────────────────────────────────────────────────────
log "Menginstall Gemini CLI..."
npm install -g @google/gemini-cli 2>/dev/null || warn "Coba manual: npm i -g @google/gemini-cli"
ok "Gemini CLI: $(gemini --version 2>/dev/null | head -1 || echo 'installed')"

# ─── 4. Detect RAM and pull Gemma 4 model ─────────────────────────────────────
log "Mendeteksi RAM dan memilih model Ollama..."
RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
RAM_GB=$(( RAM_BYTES / 1073741824 ))
if [ "$RAM_GB" -ge 14 ]; then
    OLLAMA_MODEL="gemma4:e4b"
else
    OLLAMA_MODEL="gemma4:e2b"
fi
log "RAM: ${RAM_GB}GB → model: ${OLLAMA_MODEL}"
ollama pull "$OLLAMA_MODEL" 2>/dev/null || warn "Ollama pull ${OLLAMA_MODEL} gagal — coba manual: ollama pull ${OLLAMA_MODEL}"
ok "Ollama model: ${OLLAMA_MODEL}"

# ─── 5. Clone/update repo ─────────────────────────────────────────────────────
log "Menyiapkan repo Nuzantara..."
if [ -d "$PROJECT_DIR/.git" ]; then
    ok "Repo sudah ada — update"
    cd "$PROJECT_DIR" && git pull --ff-only
else
    git clone https://github.com/Balizero1987/Teman2.git "$PROJECT_DIR"
fi
ok "Repo: $PROJECT_DIR"

# ─── 6. Python venv untuk nuzantara-mcp ───────────────────────────────────────
log "Menyiapkan Python environment untuk nuzantara-mcp..."
cd "$PROJECT_DIR/apps/nuzantara-mcp"
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
    .venv/bin/pip install -q fastmcp httpx pydantic 2>/dev/null || true
fi
ok "Python venv siap: $PROJECT_DIR/apps/nuzantara-mcp/.venv"

# ─── 7. Generate mkcert TLS certs ─────────────────────────────────────────────
log "Membuat TLS certificates dengan mkcert..."
mkdir -p "$GATEWAY_DIR"
mkcert -install 2>/dev/null || true
mkcert -cert-file "$GATEWAY_DIR/cert.pem" -key-file "$GATEWAY_DIR/key.pem" localhost 127.0.0.1 2>/dev/null || \
    warn "mkcert gagal — gateway akan berjalan tanpa TLS"
ok "TLS certs: $GATEWAY_DIR/cert.pem"

# ─── 8. Copy gateway files ────────────────────────────────────────────────────
log "Menyalin file gateway..."
cp "$PROJECT_DIR/scripts/zantara-gateway/gateway.py" "$GATEWAY_DIR/gateway.py"
cp "$PROJECT_DIR/scripts/zantara-gateway/config.py"  "$GATEWAY_DIR/config.py"
cp "$PROJECT_DIR/scripts/zantara-gateway/mcp_client.py" "$GATEWAY_DIR/mcp_client.py"
ok "Gateway files disalin ke $GATEWAY_DIR"

# ─── 9. Install gateway Python deps ──────────────────────────────────────────
log "Menginstall Python dependencies untuk gateway..."
python3.11 -m venv "$GATEWAY_DIR/.venv" 2>/dev/null || python3 -m venv "$GATEWAY_DIR/.venv"
"$GATEWAY_DIR/.venv/bin/pip" install -q aiohttp mcp httpx 2>/dev/null || \
    warn "pip install gagal — coba manual: $GATEWAY_DIR/.venv/bin/pip install aiohttp mcp httpx"
ok "Gateway venv siap"

# ─── 10. Generate gateway token and write config.json ────────────────────────
log "Membuat gateway token dan config.json..."
GATEWAY_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat > "$GATEWAY_DIR/config.json" << CONFIG
{
  "role": "${ROLE}",
  "agent_name": "${NAME}",
  "gateway_token": "${GATEWAY_TOKEN}",
  "port": 8090,
  "gemini_cli": {
    "timeout_seconds": 60,
    "allowed_mcp_servers": ["nuzantara"]
  },
  "ollama": {
    "url": "http://localhost:11434",
    "model": "${OLLAMA_MODEL}",
    "max_tool_iterations": 3,
    "tool_fail_threshold": 2
  },
  "cors": {
    "allowed_origins": ["https://kita.balizero.com"]
  },
  "tls": {
    "cert": "${GATEWAY_DIR}/cert.pem",
    "key": "${GATEWAY_DIR}/key.pem"
  }
}
CONFIG
ok "config.json scritto"

# ─── 11. Write ~/.gemini/settings.json ────────────────────────────────────────
log "Mengkonfigurasi Gemini CLI settings..."
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
        "NUZANTARA_API_KEY": "$TOKEN",
        "AGENT_ROLE": "$ROLE",
        "AGENT_NAME": "$NAME",
        "PYTHONPATH": "$PROJECT_DIR/apps/nuzantara-mcp"
      }
    }
  }
}
SETTINGS

cat > "$HOME/.gemini/trustedFolders.json" << TRUST
{"$PROJECT_DIR": "TRUST_PARENT"}
TRUST
ok "Gemini CLI settings dikonfigurasi"

# ─── 12. Write ~/.gemini/GEMINI.md (generic persona) ─────────────────────────
log "Menulis agent persona GEMINI.md..."
cat > "$HOME/.gemini/GEMINI.md" << GEMINIMD
# Zantara — Asisten AI Pribadi ${NAME} (${ROLE})

Kamu adalah **Zantara**, asisten AI pribadi untuk **${NAME}**, ${ROLE} di Bali Zero.
Bali Zero adalah perusahaan jasa bisnis di Bali — visa, pendirian perusahaan, pajak, properti.

## Aturan Penting
- Gunakan **Bahasa Indonesia** (default). Switch ke English kalau klien bicara English.
- SELALU gunakan tools MCP untuk data nyata — **JANGAN mengarang atau menebak**.
- Untuk harga layanan: SELALU gunakan \`calculate_pricing\` atau \`get_all_prices\`.
- Tampilkan HANYA klien yang di-assign ke ${NAME} (bukan semua klien).
- Untuk masalah teknis atau error → kirim pesan ke Zero via \`federation_send(to_node="pro", body="...")\`.

## Cara Kerja
Kamu punya akses langsung ke sistem CRM Bali Zero lewat tools MCP.
${NAME} bisa meminta kamu untuk:
- Cek data klien dan pratik yang sedang berjalan
- Lihat visa yang akan expire dan apa yang perlu dilakukan
- Cari info tentang jenis visa, KBLI, atau regulasi
- Hitung harga layanan untuk klien
- Update status pratik setelah ada progress
- Kirim pesan ke portal klien

## Tools yang Tersedia

### Baca Data (tidak mengubah apa-apa)
- \`list_clients\` — daftar klien ${NAME}
- \`get_client\` — detail satu klien (id atau email)
- \`get_client_timeline\` — riwayat lengkap klien
- \`list_practices\` — semua pratik aktif
- \`get_practice\` — detail satu pratik
- \`get_expiry_alerts\` — dokumen yang akan expire
- \`get_compliance_alerts\` — alert kepatuhan
- \`list_visa_types\` / \`get_visa_details\` — info visa
- \`search_kbli\` / \`inspect_kbli\` / \`chat_kbli\` — klasifikasi bisnis
- \`ask_legal\` — tanya soal regulasi
- \`calculate_pricing\` / \`get_all_prices\` — harga layanan Bali Zero
- \`get_journey\` / \`get_journey_next_steps\` — langkah selanjutnya

### Tulis Data (hati-hati, mengubah sistem)
- \`log_interaction\` — catat interaksi dengan klien
- \`update_practice_status\` — update status pratik
- \`send_portal_message\` — kirim pesan ke portal klien
- \`complete_journey_step\` — tandai langkah selesai
- \`save_episode\` — simpan catatan penting

### Komunikasi
- \`federation_send\` — kirim pesan ke Zero atau tim lain
- \`federation_inbox\` — cek pesan masuk

## Contoh Percakapan
- "Tampilkan klien saya yang visa-nya expire bulan ini"
- "Apa langkah selanjutnya untuk klien [nama]?"
- "Berapa harga perpanjangan KITAS?"
- "Update pratik [id] ke status submitted"
- "Kirim pesan ke Zero: butuh bantuan soal klien X"
GEMINIMD
ok "GEMINI.md ditulis"

# ─── 13. Create launchd plist for auto-start ─────────────────────────────────
log "Membuat launchd plist untuk auto-start gateway..."
PLIST_PATH="$HOME/Library/LaunchAgents/com.balizero.zantara-gateway.plist"
BREW_PREFIX=$(brew --prefix 2>/dev/null || echo "/opt/homebrew")

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.balizero.zantara-gateway</string>

    <key>ProgramArguments</key>
    <array>
        <string>${GATEWAY_DIR}/.venv/bin/python</string>
        <string>${GATEWAY_DIR}/gateway.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${GATEWAY_DIR}</string>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${GATEWAY_DIR}/gateway.log</string>
    <key>StandardErrorPath</key>
    <string>${GATEWAY_DIR}/gateway.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>${HOME}</string>
        <key>PATH</key>
        <string>${BREW_PREFIX}/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST

# Load the plist (unload first in case it was already loaded)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
ok "LaunchAgent dimuat: com.balizero.zantara-gateway"

# ─── 14. Hourly git auto-sync via crontab ────────────────────────────────────
log "Mengaktifkan auto-sync repo (cron setiap jam)..."
CRON_CMD="cd $PROJECT_DIR && git pull --ff-only --quiet 2>/dev/null"
(crontab -l 2>/dev/null | grep -v "nuzantara.*pull"; echo "0 * * * * $CRON_CMD") | crontab -
ok "Auto-sync aktif (setiap jam)"

# ─── Selesai ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Setup selesai!                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Node: ${NAME} | Role: ${ROLE}"
echo ""
echo "Langkah selanjutnya:"
echo ""
echo "1. Login Gemini:"
echo "   gemini auth login"
echo ""
echo "2. Test gateway:"
echo "   curl -s http://localhost:8090/health | python3 -m json.tool"
echo ""
echo "3. Test Gemini CLI + MCP:"
echo "   gemini"
echo "   > tampilkan daftar pratik aktif"
echo ""
echo "4. Konfigurasi widget (berikan ke admin):"
echo "   Gateway URL  : https://localhost:8090"
echo "   Gateway Token: ${GATEWAY_TOKEN}"
echo ""
warn "SIMPAN gateway token di atas — admin perlu ini untuk konfigurasi widget!"
warn "Login Gemini dengan email balizero.com milik ${NAME} saat diminta!"
