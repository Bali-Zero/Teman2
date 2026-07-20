#!/usr/bin/env bash
# Install the mata_garuda NLM daily-rollup (#5 summarize-then-store) as a daily
# LaunchAgent on the Pro.
#
# Council daily-rollup / log-compaction: NLM is a HARD-capped sink (~500 sources).
# This rolls up the archived enriched corpus into ONE digest source per (day,
# domain) — a day of intel = 1 source, so the cap holds ~500 DAYS not ~500 items.
# Reads FROM the archive (the durable store), posts title-preserving digests.
#
# Cadence: DAILY (not hourly) at 23:30 WITA — runs after the day's harvest/score so
# the digest is complete. Idempotent (rollup_ledger), so an extra run is harmless.
# venv python direct (no HOME-fork), canonical Pro Redis is irrelevant here (reads
# SQLite), but NLM auth needs the `nlm` CLI profile. plist chmod 600 (no Redis pw
# needed, but keep restrictive).
set -euo pipefail

REPO="$HOME/nuzantara"
VENV="$REPO/apps/mata-garuda/.venv/bin/python"
LABEL="com.matagaruda.nlm-rollup.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/logs/matagaruda-nlm-rollup.log"

mkdir -p "$HOME/logs"

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
    <string>mata_garuda.workers.nlm_rollup</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO/apps/mata-garuda</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$REPO/apps/mata-garuda</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin</string>
    <key>GARUDA_ROLLUP_DAYS_BACK</key><string>3</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>23</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF

chmod 600 "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "installed: $LABEL (daily 23:30 WITA)"
echo "plist: $PLIST (perms $(stat -f %Lp "$PLIST"))"
echo "log:   $LOG"
echo "manual test: launchctl kickstart gui/\$(id -u)/$LABEL"
