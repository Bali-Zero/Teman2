#!/bin/zsh
# run.sh — build then launch WR2 Control.
set -euo pipefail
ROOT="${0:A:h}"
"$ROOT/build.sh"
open "$ROOT/build/WR2 Control.app"
echo "▸ launched. (use Activity Monitor or 'pgrep WR2Control' to confirm)"
