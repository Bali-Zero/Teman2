#!/bin/zsh
# make-desk-icon.sh — place WR2 Control launchers on this Mac and, when reachable, Pro.
set -euo pipefail

ROOT="${0:A:h:h}"
APP="$ROOT/build/WR2 Control.app"
[[ -d "$APP" ]] || { echo "✗ build first: ./build.sh"; exit 1; }

DESK="$HOME/Desktop/WR2 Control.app"
rm -rf "$DESK"
ln -s "$APP" "$DESK"
echo "✅ Desk icon placed on $(hostname): $HOME/Desktop/WR2 Control.app"

if ssh -o ConnectTimeout=3 pro 'true' >/dev/null 2>&1; then
  echo "▸ copying .app + Desk icon to Pro…"
  ssh pro 'mkdir -p ~/Applications'
  rsync -a --delete "$APP" pro:'~/Applications/'
  ssh pro 'rm -rf "$HOME/Desktop/WR2 Control.app"; ln -s "$HOME/Applications/WR2 Control.app" "$HOME/Desktop/WR2 Control.app"'
  echo "✅ Pro Desk icon placed: ~/Desktop/WR2 Control.app"
else
  echo "⚠︎ Pro unreachable; local Desk icon done, Pro icon skipped."
fi
