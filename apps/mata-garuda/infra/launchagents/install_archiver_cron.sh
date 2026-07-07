#!/usr/bin/env bash
# Install the mata_garuda archiver as an hourly LaunchAgent on the Pro.
#
# Council pattern (cold-store / Lambda-arch slow path): the Redis streams are a
# bounded HOT buffer (MAXLEN-capped). The archiver is the DURABLE record — it
# consumes garuda:enriched and appends every item to data/archive.db (stdlib
# SQLite, WAL). This gives full-corpus auditability WITHOUT growing Redis RAM:
# the cap can trim freely because the archive holds the history.
#
# Design (same discipline as the pipeline-health cron):
#  - Runs the venv python DIRECTLY (adhoc-signed, fast, no nlm-headless → no -9
#    hang) — NO ~/scripts wrapper (avoids cicatrix #1 HOME-fork).
#  - Targets the CANONICAL Pro Redis (127.0.0.1) — NOT Mini. (cicatrix #10
#    split-brain: a stale GARUDA_REDIS_HOST=<mini> override made the feeder read
#    the wrong empty Redis for days. The canonical is Pro; opt out of -h via the
#    local sentinel.)
#  - StartInterval 3600 (hourly) + RunAtLoad. plist chmod 600 (carries the Redis
#    password — cicatrix #4).
#  - Logs to ~/logs/matagaruda-archiver.log
set -euo pipefail

REPO="$HOME/Desktop/nuzantara"
VENV="$REPO/apps/mata-garuda/.venv/bin/python"
LABEL="com.matagaruda.archiver.hourly"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/logs/matagaruda-archiver.log"
SECRETS="$HOME/.nuzantara-secrets.env"

mkdir -p "$HOME/logs" "$REPO/apps/mata-garuda/data"

# pull the Redis password (no echo — never print values)
[ -f "$SECRETS" ] && set -a && . "$SECRETS" && set +a || true
RPW="${GARUDA_REDIS_PASSWORD:-}"

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
    <string>mata_garuda.workers.archiver</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO/apps/mata-garuda</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$REPO/apps/mata-garuda</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin</string>
    <key>GARUDA_CANONICAL_REDIS_HOST</key><string>127.0.0.1</string>
    <key>GARUDA_REDIS_PASSWORD</key><string>$RPW</string>
    <key>GARUDA_ARCHIVE_MAX_ITEMS</key><string>1000</string>
  </dict>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF

chmod 600 "$PLIST"   # carries the Redis password — never world-readable (cicatrix #4)

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart "gui/$(id -u)/$LABEL"

echo "installed + kicked: $LABEL"
echo "plist: $PLIST (perms $(stat -f %Lp "$PLIST"))"
echo "log:   $LOG"
sleep 8
echo "--- first run output ---"
tail -10 "$LOG" 2>/dev/null
