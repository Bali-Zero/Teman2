#!/bin/zsh
# install-mini.sh — deploy WR2 Control to the Mini-Pro2 office-TV postazione.
#
# Step 0 fact (verified on disk 2026-06-22): the Mini has the nuzantara repo but NO
# war-room/output (no queue, 0 carousels). That data lives on the Pro. The Mini reaches
# the Pro (ssh pro ok). So this script ALSO syncs the data Pro→Mini into a local copy the
# app reads via WR2_WARROOM_ROOT (set in the LaunchAgent).
#
# Boundaries respected: copies a local .app + a plist + a one-shot data sync. No git push,
# no deploy, no Instagram. The war-room data contains client-adjacent references → it stays
# on Zero's fleet machines only (Pro→Mini, both Zero's). Run this MANUALLY (operator gate).
set -euo pipefail

ROOT="${0:A:h:h}"            # repo root (deploy/ is one level down)
cd "$ROOT"
APP="build/WR2 Control.app"
MINI="mini"                  # ssh alias

[[ -d "$APP" ]] || { echo "✗ build first: ./build.sh"; exit 1; }

echo "▸ 1/5 ensuring Mini dirs (Applications, LaunchAgents, Logs, sync target)…"
ssh "$MINI" 'mkdir -p ~/Applications ~/Library/LaunchAgents ~/Library/Logs ~/.wr2-warroom-sync'

echo "▸ 2/5 copying the .app to Mini ~/Applications (NOT ~/Desktop — scar W84)…"
rsync -a --delete "$APP" "$MINI":'~/Applications/'

echo "▸ 3/5 syncing war-room DATA Pro→Mini (queue + carousel covers) into ~/.wr2-warroom-sync/output…"
# Pull from the Pro (authoritative) to the Mini's local sync dir. Fail closed if the
# sync does not produce the queue + carousel root the app needs.
ssh "$MINI" 'set -e
mkdir -p "$HOME/.wr2-warroom-sync/output"
rsync -a --delete pro:/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/ "$HOME/.wr2-warroom-sync/output/"
test -f "$HOME/.wr2-warroom-sync/output/queue/human-review-queue.json"
test -d "$HOME/.wr2-warroom-sync/output/carousel"
count=$(find "$HOME/.wr2-warroom-sync/output/carousel" -maxdepth 1 -type d | wc -l | tr -d " ")
echo "  synced war-room output ($count carousel dirs incl. root)"'

echo "▸ 4/5 installing + (re)loading the LaunchAgent…"
scp deploy/com.balizero.wr2control.plist "$MINI":'~/Library/LaunchAgents/'
ssh "$MINI" 'launchctl bootout gui/$(id -u)/com.balizero.wr2control 2>/dev/null || true;
             launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2control.plist'

echo "▸ 5/5 verifying REAL liveness (not just exit 0 — scar #2)…"
sleep 4
ssh "$MINI" 'if pgrep -f "WR2Control" >/dev/null; then
    echo "  ✅ WR2 Control running on Mini (pid $(pgrep -f WR2Control | head -1))";
  else
    echo "  ✗ NOT running — tail of error log:"; tail -5 ~/Library/Logs/wr2control.err 2>/dev/null; exit 1;
  fi'

echo ""
echo "✅ deployed. The office TV should now show the ambient editorial wall."
echo "   Data sync is one-shot here; schedule a periodic Pro→Mini rsync separately if wanted."
