#!/usr/bin/env bash
# subhi-tutor-install-wsl.sh — Subhi WSL2 Ubuntu installer (Windows Acer, 2-day bridge before MacBook).
#
# Usage on Subhi's WSL2 Ubuntu shell:
#   bash <(curl -sL <gist-raw-url>)
#
# Differences vs subhi-tutor-install.sh (macOS variant):
#   - apt instead of brew
#   - no Xcode CLI tools, no .app cask
#   - Tailscale: NOT installed in WSL — uses Windows-host Tailscale via mirrored networking
#   - Path: /home/subhi/ instead of /Users/subhi/
#
# Reference: docs/superpowers/specs/2026-05-04-subhi-tutor-design-addendum-B.md
set -euo pipefail

# Cosmetic helpers
BAHASA() { echo -e "\033[36m▸\033[0m $*"; }
ERR()    { echo -e "\033[31m✗\033[0m $*" >&2; exit 1; }
OK()     { echo -e "\033[32m✓\033[0m $*"; }
INFO()   { echo -e "\033[33mℹ\033[0m $*"; }
PROMPT() { echo -e "\033[35m?\033[0m $*"; }

# Pre-flight
if ! grep -qi microsoft /proc/version 2>/dev/null; then
  ERR "Script ini untuk WSL2 Ubuntu. Kamu bukan di WSL — pakai variant macOS atau Linux native."
fi
OK "WSL2 Ubuntu terdeteksi: $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"

# Ensure interactive
if [[ ! -t 0 ]]; then
  ERR "Script harus dijalankan interactive di terminal Ubuntu. Jangan pipe."
fi

# Step 1: apt update + dependencies
BAHASA "Update apt + install build tools (akan minta sudo password)..."
sudo apt update -y
sudo apt install -y curl wget git build-essential ca-certificates gnupg python3 python3-pip python3-venv unzip jq
OK "Build tools installed"

# Step 2: Node.js 20 (NodeSource repo)
if ! command -v node &>/dev/null || [[ "$(node --version | grep -oE '[0-9]+' | head -1)" -lt 20 ]]; then
  BAHASA "Install Node.js 20 (via NodeSource)..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
fi
OK "node $(node --version), npm $(npm --version)"

# Step 3: GitHub CLI
if ! command -v gh &>/dev/null; then
  BAHASA "Install GitHub CLI..."
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  sudo chmod 0644 /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
  sudo apt update -y
  sudo apt install -y gh
fi
OK "gh $(gh --version | head -1)"

# Step 4: uv (Python tool installer)
if ! command -v uv &>/dev/null; then
  BAHASA "Install uv (Python tool installer)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin
  export PATH="$HOME/.local/bin:$PATH"
fi
OK "uv $(uv --version 2>/dev/null || echo 'installed')"

# Persist PATH for future sessions
SHELL_RC="$HOME/.bashrc"
grep -q '.local/bin' "$SHELL_RC" 2>/dev/null || \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"

# Step 5: Claude Code CLI
BAHASA "Install Claude Code CLI..."
NPM_GLOBAL="$HOME/.npm-global"
mkdir -p "$NPM_GLOBAL"
npm config set prefix "$NPM_GLOBAL"
grep -q '.npm-global/bin' "$SHELL_RC" 2>/dev/null || \
  echo "export PATH=\"$NPM_GLOBAL/bin:\$PATH\"" >> "$SHELL_RC"
export PATH="$NPM_GLOBAL/bin:$PATH"
npm install -g @anthropic-ai/claude-code
OK "Claude $(claude --version 2>/dev/null || echo 'installed')"

# Step 6: NLM CLI
BAHASA "Install NotebookLM CLI..."
uv tool install notebooklm-mcp-cli || INFO "Sudah terinstall"
OK "nlm CLI ready"

# Step 7: Verify Tailscale via Windows host (WSL mirrored networking)
BAHASA "Verify Tailscale dari Windows host..."
INFO "Tailscale tidak diinstall di WSL — pakai Windows-host Tailscale via mirrored networking."
INFO "Pastikan Tailscale sudah running di Windows (system tray)."

# Test reach to Pro tailnet IP (we know nuzantara is 100.64.165.11)
if ping -c 1 -W 3 100.64.165.11 &>/dev/null; then
  OK "Tailscale reachable: Pro nuzantara (100.64.165.11) ping OK"
else
  INFO "Pro nuzantara (100.64.165.11) tidak ter-ping dari WSL."
  INFO "Cek: di Windows tray, klik Tailscale → harus 'Connected' as subhi@balizero.com."
  INFO "Kalau WSL tidak share network Windows, mungkin perlu konfigurasi:"
  INFO "  /etc/wsl.conf:"
  INFO "    [network]"
  INFO "    networkingMode=mirrored"
  INFO "  Lalu di PowerShell admin: wsl --shutdown && wsl"
  PROMPT "Lanjut tanpa Tailscale verify? (y/n)"
  read -r -p "> " CONT
  [[ "$CONT" == "y" ]] || ERR "Aborted by user. Fix Tailscale di Windows lalu re-run."
fi

# Step 8: SSH key
if [[ ! -f "$HOME/.ssh/id_ed25519" ]]; then
  BAHASA "Generate SSH key (untuk git operations)..."
  ssh-keygen -t ed25519 -C "subhi@balizero.com" -f "$HOME/.ssh/id_ed25519" -N ""
fi
OK "SSH key ready"

# Step 9: GitHub login
BAHASA "Login GitHub CLI (akan kasih device code, paste di browser Windows)..."
INFO "Login pakai akun GitHub yang dikaitkan dengan subhi@balizero.com."
INFO "Browser akan terbuka via Windows host (WSL melemparnya ke Edge/Chrome)."
gh auth status 2>/dev/null || gh auth login --hostname github.com --git-protocol ssh --web
OK "GitHub authenticated"

# Step 10: Add SSH key to GitHub
PUB_KEY=$(cat "$HOME/.ssh/id_ed25519.pub")
PUB_KEY_BODY=$(echo "$PUB_KEY" | awk '{print $2}')
if ! gh ssh-key list 2>/dev/null | grep -qF "$PUB_KEY_BODY"; then
  BAHASA "Tambah SSH key ke GitHub..."
  gh ssh-key add "$HOME/.ssh/id_ed25519.pub" --title "WSL Subhi $(date +%Y-%m-%d)" 2>&1 || \
    INFO "SSH key sudah ada atau gagal — lanjut"
fi
OK "GitHub SSH key registered"

# Step 11: Clone main repo
mkdir -p "$HOME/Projects"
cd "$HOME/Projects"
if [[ ! -d nuzantara ]]; then
  BAHASA "Clone repo balizero/nuzantara (~5 min, repo besar)..."
  gh repo clone balizero/nuzantara
fi
OK "Repo nuzantara cloned di ~/Projects/nuzantara"

# Step 12: Set up zantara-onboarding workspace
BAHASA "Setup zantara-onboarding workspace..."
if [[ ! -d "$HOME/zantara-onboarding" ]]; then
  cp -R "$HOME/Projects/nuzantara/apps/zantara-onboarding" "$HOME/zantara-onboarding"
  chmod +x "$HOME/zantara-onboarding/.claude/hooks/"*.sh
fi
OK "Workspace at ~/zantara-onboarding/"

# Step 13: Configure settings.json placeholders
SETTINGS="$HOME/zantara-onboarding/.claude/settings.json"
if [[ -f "$SETTINGS" ]]; then
  BAHASA "Configure settings.json placeholders..."

  CURRENT_USER=$(whoami)
  sed -i.bak "s|__SUBHI_USERNAME_PLACEHOLDER__|$CURRENT_USER|g" "$SETTINGS"

  # WSL paths use /home/subhi/ — different from /Users/subhi/. The settings.json
  # has /Users/__SUBHI_USERNAME_PLACEHOLDER__/Projects/nuzantara-subhi as the
  # filesystem MCP path. We need to fix this to /home/<user>/zantara-onboarding.
  sed -i.bak2 "s|/Users/$CURRENT_USER/Projects/nuzantara-subhi|/home/$CURRENT_USER/zantara-onboarding|g" "$SETTINGS"

  # Prompt for GitHub PAT
  PROMPT "Antonello akan kasih kamu GitHub Personal Access Token (PAT) via WhatsApp."
  PROMPT "Format: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx (40 chars) atau github_pat_*"
  PROMPT "Tekan ENTER kalau kamu mau skip sekarang (bisa edit manual nanti):"
  read -r -s -p "Paste PAT (akan tersembunyi, atau ENTER untuk skip): " PAT
  echo ""

  if [[ -n "$PAT" ]]; then
    if [[ "$PAT" =~ ^ghp_[A-Za-z0-9]{36}$ ]] || [[ "$PAT" =~ ^github_pat_ ]]; then
      sed -i.bak3 "s|__SUBHI_GITHUB_PAT_PLACEHOLDER__|$PAT|g" "$SETTINGS"
      rm -f "$SETTINGS.bak" "$SETTINGS.bak2" "$SETTINGS.bak3"
      chmod 0600 "$SETTINGS"
      OK "PAT configured (settings.json mode 0600)"
    else
      INFO "Format PAT tidak terlihat valid — tinggalkan placeholder. Edit manual: $SETTINGS"
      rm -f "$SETTINGS.bak3" 2>/dev/null
    fi
  else
    INFO "PAT skipped — edit manual: $SETTINGS"
  fi
fi

# Step 14: Claude OAuth login
BAHASA "Login Claude Code (akan kasih URL, buka di browser Windows)..."
INFO "Login pakai subhi@balizero.com — claim slot MAX plan dari Antonello"
INFO "WSL akan melempar URL ke browser Windows otomatis."
INFO ""
INFO "Setelah install ini selesai, manual run:"
INFO "  cd ~/zantara-onboarding && claude"
INFO ""

# Step 15: NLM login
BAHASA "Login NotebookLM (akan kasih URL, buka di browser Windows)..."
INFO "Login pakai subhi@balizero.com — accept invite NB-1, NB-2, NB-9, NB-OPS"
nlm login --clear || INFO "NLM login interactive — ikuti petunjuk di browser"

# Final
echo ""
echo "════════════════════════════════════════════════════════"
OK "Setup WSL selesai!"
echo ""
INFO "Catatan: ini setup sementara untuk WSL. Hari Kamis (saat MacBook"
INFO "datang), kamu akan setup ulang di macOS — lebih simpel."
echo ""
echo "Langkah berikutnya:"
echo ""
echo "  1. Re-source shell config (atau restart terminal):"
echo "     source ~/.bashrc"
echo ""
echo "  2. Buka VSCode di workspace onboarding (via WSL):"
echo "     code ~/zantara-onboarding"
echo ""
echo "     (VSCode Windows otomatis pakai Remote-WSL extension)"
echo ""
echo "  3. Buka integrated terminal (Ctrl+\`)"
echo ""
echo "  4. Run claude:"
echo "     cd ~/zantara-onboarding"
echo "     claude"
echo ""
echo "  5. Test tutor pertama kali:"
echo "     /agent zantara-onboarding halo, perkenalkan diri kamu"
echo ""
echo "  6. Tutor harus jawab dalam Bahasa Indonesia."
echo "     Screenshot reply, kirim ke Antonello via WhatsApp."
echo ""
echo "  7. Lanjut: baca docs/onboarding/00_SELAMAT_DATANG.md"
echo "     dan exercises/day1_setup_check.md"
echo "════════════════════════════════════════════════════════"
