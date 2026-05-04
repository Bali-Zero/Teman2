#!/usr/bin/env bash
# subhi-tutor-install.sh — Subhi MacBook one-shot installer.
# Usage on Subhi's Mac:
#   bash <(curl -sL <gist-raw-url>)
# Hosted as a GitHub gist for anonymous downloadability (see
# install.gist-readme.md in this directory).
#
# Reference: docs/superpowers/specs/2026-05-04-subhi-tutor-design-addendum-B.md
# Reference: docs/superpowers/plans/2026-05-04-subhi-tutor-implementation.md T6
set -euo pipefail

# === Cosmetic helpers (bahasa) ===
BAHASA() { echo -e "\033[36m▸\033[0m $*"; }
ERR()    { echo -e "\033[31m✗\033[0m $*" >&2; exit 1; }
OK()     { echo -e "\033[32m✓\033[0m $*"; }
INFO()   { echo -e "\033[33mℹ\033[0m $*"; }
PROMPT() { echo -e "\033[35m?\033[0m $*"; }

# === Pre-flight ===
[[ "$(uname)" == "Darwin" ]] || ERR "Script ini hanya untuk macOS. Kamu di $(uname)."
OK "macOS terdeteksi"

# Ensure interactive — script prompts for SSH key passphrase, GitHub
# auth, PAT paste, etc. Pipe-mode breaks read prompts.
if [[ ! -t 0 ]]; then
  ERR "Script harus dijalankan interactive di Terminal. Jangan pipe."
fi

# === Step 1: Xcode CLI tools ===
if ! xcode-select -p &>/dev/null; then
  BAHASA "Install Xcode CLI tools (akan minta password Mac)..."
  xcode-select --install || true
  INFO "Tunggu install GUI selesai (~5 menit), lalu re-run script ini."
  exit 0
fi
OK "Xcode CLI ready"

# === Step 2: Homebrew ===
if ! command -v brew &>/dev/null; then
  BAHASA "Install Homebrew (akan minta password Mac)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -d /opt/homebrew/bin ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -d /usr/local/Homebrew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi
OK "Homebrew $(brew --version | head -1)"

# === Step 3: CLI tools via brew ===
BAHASA "Install Node.js 20, GitHub CLI, uv (Python tool installer)..."
brew install node@20 gh uv
brew link --overwrite node@20 || true

SHELL_RC="$HOME/.zshrc"
grep -q "node@20/bin" "$SHELL_RC" 2>/dev/null || \
  echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> "$SHELL_RC"

# Pick up node@20 in current session so subsequent npm install works
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"

OK "node $(node --version 2>/dev/null || echo 'pending'), gh $(gh --version 2>/dev/null | head -1 || echo 'pending')"

# === Step 4: Tailscale + VSCode (cask) ===
if ! command -v tailscale &>/dev/null && [[ ! -d "/Applications/Tailscale.app" ]]; then
  BAHASA "Install Tailscale (cask)..."
  brew install --cask tailscale
fi
if [[ ! -d "/Applications/Visual Studio Code.app" ]] && ! command -v code &>/dev/null; then
  BAHASA "Install VSCode (cask)..."
  brew install --cask visual-studio-code || INFO "VSCode mungkin sudah terinstall"
fi
OK "GUI apps ready"

# === Step 5: Claude Code CLI ===
BAHASA "Install Claude Code CLI..."
NPM_GLOBAL="$HOME/.npm-global"
mkdir -p "$NPM_GLOBAL"
npm config set prefix "$NPM_GLOBAL"
grep -q ".npm-global/bin" "$SHELL_RC" 2>/dev/null || \
  echo "export PATH=\"$NPM_GLOBAL/bin:\$PATH\"" >> "$SHELL_RC"
export PATH="$NPM_GLOBAL/bin:$PATH"
npm install -g @anthropic-ai/claude-code
OK "Claude $(claude --version 2>/dev/null || echo 'installed')"

# === Step 6: NLM CLI ===
BAHASA "Install NotebookLM CLI..."
uv tool install notebooklm-mcp-cli || INFO "Sudah terinstall"
OK "nlm CLI ready"

# === Step 7: Tailscale up ===
if ! tailscale status &>/dev/null; then
  BAHASA "Login Tailscale (akan buka browser)..."
  INFO "Login pakai subhi@balizero.com"
  if [[ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]]; then
    /Applications/Tailscale.app/Contents/MacOS/Tailscale up || sudo tailscale up
  else
    sudo tailscale up
  fi
fi
TS_IP=$(tailscale ip -4 2>/dev/null | head -1 || echo "tidak ada")
OK "Tailscale: $TS_IP"

# === Step 8: SSH key ===
if [[ ! -f "$HOME/.ssh/id_ed25519" ]]; then
  BAHASA "Generate SSH key (buat git operations + Tailscale)..."
  ssh-keygen -t ed25519 -C "subhi@balizero.com" -f "$HOME/.ssh/id_ed25519" -N ""
fi
OK "SSH key ready"

# === Step 9: Tailscale SSH server enable (per option B Antonello-side push model) ===
BAHASA "Enable Tailscale SSH (untuk rsync push dari Pro)..."
INFO "Antonello akan push memory mirror ke Mac kamu via Tailscale SSH."
INFO "Tidak ada pull cron di Mac kamu — semua push dari sisi Antonello."
sudo tailscale set --ssh || INFO "Tailscale SSH already enabled or pending"
OK "Tailscale SSH enabled"

# === Step 10: GitHub login ===
BAHASA "Login GitHub CLI (akan buka browser)..."
INFO "Login pakai akun GitHub yang dikaitkan dengan subhi@balizero.com"
gh auth status 2>/dev/null || gh auth login --hostname github.com --git-protocol ssh --web
OK "GitHub authenticated"

# === Step 11: Add SSH key to GitHub ===
PUB_KEY=$(cat "$HOME/.ssh/id_ed25519.pub")
# Extract the base64 portion (second whitespace-separated field) for grep match
PUB_KEY_BODY=$(awk '{print $2}' "$HOME/.ssh/id_ed25519.pub")
if ! gh ssh-key list 2>/dev/null | grep -qF "$PUB_KEY_BODY"; then
  BAHASA "Tambah SSH key ke GitHub..."
  gh ssh-key add "$HOME/.ssh/id_ed25519.pub" --title "MacBook Subhi $(date +%Y-%m-%d)" 2>&1 || \
    INFO "SSH key sudah ada atau gagal — lanjut"
fi
OK "GitHub SSH key registered"

# === Step 12: Clone main repo ===
mkdir -p "$HOME/Projects"
cd "$HOME/Projects"
if [[ ! -d nuzantara ]]; then
  BAHASA "Clone repo balizero/nuzantara (~5 min, repo besar)..."
  gh repo clone balizero/nuzantara
fi
OK "Repo nuzantara cloned di ~/Projects/nuzantara"

# === Step 13: Set up zantara-onboarding workspace ===
BAHASA "Setup zantara-onboarding workspace..."

# Initial copy: clone main repo's apps/zantara-onboarding/ to ~/zantara-onboarding/
# Per addendum B §9: scaffold lives in main repo, gets distributed to Subhi
# via initial cp here + ongoing rsync from Pro for the memory mirror.
if [[ ! -d "$HOME/zantara-onboarding" ]]; then
  cp -R "$HOME/Projects/nuzantara/apps/zantara-onboarding" "$HOME/zantara-onboarding"

  # Ensure hook scripts are executable (cp -R may not preserve mode under
  # all macOS filesystems, e.g. external drives).
  if [[ -d "$HOME/zantara-onboarding/.claude/hooks" ]]; then
    chmod +x "$HOME/zantara-onboarding/.claude/hooks/"*.sh 2>/dev/null || true
  fi
fi
OK "Workspace at ~/zantara-onboarding/"

# === Step 14: Configure settings.json placeholders ===
SETTINGS="$HOME/zantara-onboarding/.claude/settings.json"
if [[ -f "$SETTINGS" ]]; then
  BAHASA "Configure settings.json placeholders..."

  # Replace username placeholder (used for filesystem MCP root path)
  CURRENT_USER=$(whoami)
  sed -i.bak "s|__SUBHI_USERNAME_PLACEHOLDER__|$CURRENT_USER|g" "$SETTINGS"

  # Prompt for GitHub PAT (Antonello sends via WhatsApp separately)
  PROMPT "Antonello akan kasih kamu GitHub Personal Access Token (PAT) via WhatsApp."
  PROMPT "Format: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx (40 chars) atau github_pat_*"
  PROMPT "Tekan ENTER kalau kamu mau skip sekarang (bisa edit manual nanti)."
  read -r -s -p "Paste PAT (akan tersembunyi, atau ENTER untuk skip): " PAT
  echo ""

  if [[ -n "$PAT" ]]; then
    if [[ "$PAT" =~ ^ghp_[A-Za-z0-9]{36}$ ]] || [[ "$PAT" =~ ^github_pat_ ]]; then
      sed -i.bak2 "s|__SUBHI_GITHUB_PAT_PLACEHOLDER__|$PAT|g" "$SETTINGS"
      rm -f "$SETTINGS.bak" "$SETTINGS.bak2"
      chmod 0600 "$SETTINGS"
      OK "PAT configured (settings.json mode 0600)"
    else
      INFO "Format PAT tidak terlihat valid — tinggalkan placeholder."
      INFO "Edit manual nanti: $SETTINGS"
      rm -f "$SETTINGS.bak2" 2>/dev/null
    fi
  else
    INFO "PAT skipped — edit manual: $SETTINGS"
    rm -f "$SETTINGS.bak" 2>/dev/null
  fi
fi

# === Step 15: Claude OAuth login ===
BAHASA "Login Claude Code (akan buka browser)..."
INFO "Login pakai subhi@balizero.com — claim slot MAX plan dari Antonello"
INFO ""
INFO "Setelah browser login selesai, claude akan ready."
INFO "Kalau browser tidak otomatis terbuka, manual: claude (di terminal lain)"
INFO ""
# Don't actually launch claude here — it waits on stdin for an interactive
# session and confuses install scripts. User does this manually after install.

# === Step 16: NLM login ===
BAHASA "Login NotebookLM (akan buka browser)..."
INFO "Login pakai subhi@balizero.com — accept invite NB-1, NB-2, NB-9, NB-OPS"
nlm login --clear || INFO "NLM login interactive — ikuti petunjuk di browser"

# === Final ===
echo ""
echo "════════════════════════════════════════════════════════"
OK "Setup selesai! Langkah berikutnya:"
echo ""
echo "  1. Buka VSCode di workspace onboarding:"
echo "     code ~/zantara-onboarding"
echo ""
echo "  2. Buka integrated terminal (Ctrl+\`)"
echo ""
echo "  3. Run claude:"
echo "     claude"
echo ""
echo "  4. Test tutor pertama kali:"
echo "     /agent zantara-onboarding halo, perkenalkan diri kamu"
echo ""
echo "  5. Tutor harus jawab dalam Bahasa Indonesia."
echo "     Screenshot reply, kirim ke Antonello via WhatsApp."
echo ""
echo "  6. Lanjut: baca docs/onboarding/00_SELAMAT_DATANG.md"
echo "     dan exercises/day1_setup_check.md"
echo "════════════════════════════════════════════════════════"
