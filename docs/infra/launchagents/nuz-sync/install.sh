#!/bin/bash
#
# install.sh — install or reinstall nuz-sync on the current machine
#
# Idempotent: safe to re-run after a git pull or to fix a broken install.
# Detects host (Pro/Air) automatically and configures paths accordingly.
#
# Usage:
#   bash docs/infra/launchagents/nuz-sync/install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
case "$HOST" in
    Nuzantara|nuzantara)
        TARGET_USER_HOME="/Users/nuzantara"
        ;;
    Nuzantara-9|nuzantara-9)
        TARGET_USER_HOME="/Users/antonellosiano"
        ;;
    *)
        echo "FATAL: unknown host '$HOST' — nuz-sync only supports Nuzantara and Nuzantara-9"
        exit 1
        ;;
esac

INSTALL_DIR="$TARGET_USER_HOME/scripts/nuz-sync"
LOG_DIR="$TARGET_USER_HOME/logs/nuz-sync"
LAUNCHAGENTS_DIR="$TARGET_USER_HOME/Library/LaunchAgents"

DAEMON_LABEL="com.nuzantara.nuz-sync"
WATCHDOG_LABEL="com.nuzantara.nuz-sync-watchdog"
DAEMON_PLIST="$LAUNCHAGENTS_DIR/${DAEMON_LABEL}.plist"
WATCHDOG_PLIST="$LAUNCHAGENTS_DIR/${WATCHDOG_LABEL}.plist"

echo "==> Installing nuz-sync on $HOST (home=$TARGET_USER_HOME)"

# Step 1: directories
echo "==> Creating directories"
mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$LAUNCHAGENTS_DIR"

# Step 2: scripts
echo "==> Copying scripts"
for f in nuz-sync.sh nuz-sync-check.sh nuz-sync-watchdog.sh README.md; do
    cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
done
chmod +x "$INSTALL_DIR/nuz-sync.sh" "$INSTALL_DIR/nuz-sync-check.sh" "$INSTALL_DIR/nuz-sync-watchdog.sh"

# Step 3: plists — rewrite paths for the target user
echo "==> Installing launchd plists with paths for $TARGET_USER_HOME"

generate_plist() {
    local label="$1"
    local script_name="$2"
    local interval="$3"
    local out="$4"

    cat > "$out" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTD/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${INSTALL_DIR}/${script_name}</string>
    </array>
    <key>StartInterval</key>
    <integer>${interval}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/${label##*.}-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/${label##*.}-stderr.log</string>
    <key>ThrottleInterval</key>
    <integer>60</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>${TARGET_USER_HOME}</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${TARGET_USER_HOME}</string>
</dict>
</plist>
PLIST
}

generate_plist "$DAEMON_LABEL"    "nuz-sync.sh"          120 "$DAEMON_PLIST"
generate_plist "$WATCHDOG_LABEL"  "nuz-sync-watchdog.sh" 600 "$WATCHDOG_PLIST"

# Step 4: reload launchd
echo "==> Reloading launchd"
launchctl unload "$DAEMON_PLIST"   2>/dev/null || true
launchctl unload "$WATCHDOG_PLIST" 2>/dev/null || true
launchctl load "$DAEMON_PLIST"
launchctl load "$WATCHDOG_PLIST"

# Step 5: smoke test
echo "==> Running daemon once to bootstrap heartbeat"
/bin/bash "$INSTALL_DIR/nuz-sync.sh"

echo "==> Running watchdog once"
/bin/bash "$INSTALL_DIR/nuz-sync-watchdog.sh"

# Step 6: status
echo
echo "==> Status:"
launchctl list "$DAEMON_LABEL"   2>/dev/null | grep -E 'PID|LastExitStatus' || echo "  $DAEMON_LABEL: NOT LOADED"
launchctl list "$WATCHDOG_LABEL" 2>/dev/null | grep -E 'PID|LastExitStatus' || echo "  $WATCHDOG_LABEL: NOT LOADED"

if [[ -f "$LOG_DIR/last-run" ]]; then
    last=$(cat "$LOG_DIR/last-run")
    echo "  heartbeat: $(date -r "$last" '+%Y-%m-%d %H:%M:%S')"
fi

echo
echo "==> Install complete on $HOST"
echo "    Logs: $LOG_DIR/sync.log"
echo "    Docs: $INSTALL_DIR/README.md"
