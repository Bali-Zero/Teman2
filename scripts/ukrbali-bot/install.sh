#!/bin/bash
# Turnkey installer for @UkrBaliVisaAssistant_bot on Pro (macOS / launchd).
# Run ON the Pro machine:  bash scripts/ukrbali-bot/install.sh [BOT_TOKEN]
# Idempotent: re-running re-deploys with the latest code.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.balizero.ukrbali-bot"
ENV_FILE="$HOME/.ukrbali-bot.env"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/logs"

echo "==> ukrbali-bot installer"
echo "    repo script dir: $SCRIPT_DIR"

# --- 1. token / env file (token NEVER goes into the plist or repo) ---
if [ -f "$ENV_FILE" ] && grep -q '^export UKRBALI_BOT_TOKEN=' "$ENV_FILE"; then
  echo "==> using existing $ENV_FILE"
else
  TOKEN="${1:-}"
  if [ -z "$TOKEN" ]; then
    read -r -p "Enter the BotFather token for @UkrBaliVisaAssistant_bot: " TOKEN
  fi
  [ -z "$TOKEN" ] && { echo "FATAL: no token provided" >&2; exit 78; }
  cat > "$ENV_FILE" <<EOF
export UKRBALI_BOT_TOKEN=$TOKEN
export UKRBALI_USE_RAG=0
export UKRBALI_CLAUDE_MODEL=claude-fable-5
EOF
  chmod 600 "$ENV_FILE"
  echo "==> wrote $ENV_FILE (chmod 600)"
fi

# --- 2. logs dir + executable wrapper ---
mkdir -p "$LOG_DIR"
chmod +x "$SCRIPT_DIR/run.sh"

# --- 3. generate the plist with REAL absolute paths (no hardcoded user) ---
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/run.sh</string>
    </array>
    <key>KeepAlive</key><true/>
    <key>RunAtLoad</key><true/>
    <key>ThrottleInterval</key><integer>15</integer>
    <key>StandardOutPath</key><string>$LOG_DIR/ukrbali-bot.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/ukrbali-bot.err</string>
    <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
</dict>
</plist>
EOF
echo "==> wrote $PLIST_DST"

# --- 4. (re)load the LaunchAgent ---
GUI="gui/$(id -u)"
launchctl bootout "$GUI/$LABEL" 2>/dev/null || true
launchctl bootstrap "$GUI" "$PLIST_DST"
launchctl kickstart -k "$GUI/$LABEL"

# --- 5. verify ---
sleep 4
echo "==> status:"
launchctl print "$GUI/$LABEL" 2>/dev/null | grep -E 'state =|last exit code' || true
echo "==> last log lines:"
tail -n 5 "$LOG_DIR/ukrbali-bot.log" 2>/dev/null || echo "(no log yet — check $LOG_DIR/ukrbali-bot.err)"
echo
echo "==> done. Manage with:"
echo "    tail -f $LOG_DIR/ukrbali-bot.log"
echo "    launchctl kickstart -k $GUI/$LABEL     # restart"
echo "    launchctl bootout $GUI/$LABEL          # stop"
