#!/usr/bin/env bash
# Install the mata_garuda pipeline-health monitor as an hourly LaunchAgent on the Pro.
#
# Council + cicatrix #2: the monitor reads the OUTPUT (lag/freshness/RAM) every hour,
# writes a heartbeat sidecar, and TG-alerts Zero on RED. This is the automation that
# proves CONCRETE operativity — not exit-0 theater.
#
# Design notes (lessons from this session):
#  - Runs the venv python DIRECTLY (adhoc-signed, fast, no nlm-headless → no -9 hang,
#    unlike the harvester which we just decoupled from nlm).
#  - StartInterval 3600 (hourly) + RunAtLoad so it fires immediately on install.
#  - Injects GARUDA_REDIS_HOST/PASSWORD + TELEGRAM_* from the secrets env so the
#    monitor can auth Redis and alert. (Read from ~/.nuzantara-secrets.env at install
#    time; the plist carries them as EnvironmentVariables — chmod 600.)
#  - Logs to ~/logs/matagaruda-pipeline-health.log
set -euo pipefail

REPO="$HOME/Desktop/nuzantara"
VENV="$REPO/apps/mata-garuda/.venv/bin/python"
LABEL="com.matagaruda.pipeline-health.hourly"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/logs/matagaruda-pipeline-health.log"
SECRETS="$HOME/.nuzantara-secrets.env"

mkdir -p "$HOME/logs" "$HOME/.organism/last_seen"

# pull the needed secrets (no echo — never print values)
[ -f "$SECRETS" ] && set -a && . "$SECRETS" && set +a || true
RH="${GARUDA_REDIS_HOST:-localhost}"
RPW="${GARUDA_REDIS_PASSWORD:-}"
TGT="${TELEGRAM_BOT_TOKEN:-}"
TGC="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV</string>
    <string>-u</string>
    <string>-m</string>
    <string>mata_garuda.workers.pipeline_health</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO/apps/mata-garuda</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$REPO/apps/mata-garuda</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin</string>
    <key>GARUDA_REDIS_HOST</key><string>$RH</string>
    <key>GARUDA_REDIS_PASSWORD</key><string>$RPW</string>
    <key>TELEGRAM_BOT_TOKEN</key><string>$TGT</string>
    <key>TELEGRAM_OWNER_CHAT_ID</key><string>$TGC</string>
  </dict>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF

chmod 600 "$PLIST"   # carries secrets — never world-readable (cicatrix #4)

# (re)load
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart "gui/$(id -u)/$LABEL"

echo "installed + kicked: $LABEL"
echo "plist: $PLIST (perms $(stat -f %Lp "$PLIST"))"
echo "log:   $LOG"
sleep 8
echo "--- first run output ---"
tail -25 "$LOG" 2>/dev/null | head -30
