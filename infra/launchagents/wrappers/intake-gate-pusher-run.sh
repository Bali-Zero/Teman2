#!/bin/bash
# intake-gate-count-pusher wrapper: source the 0600 env-file with BRIDGE_API_KEY
# (shared with wa-media-pull), then exec the pusher. Durable across reboot —
# avoids relying on a launchd-cached env or the fragile dedicated keychain.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
ENVF="$HOME/.cell-bridge-state/wa-media.env"
if [[ -f "$ENVF" ]]; then
  set -a; source "$ENVF"; set +a
fi
PYBIN="$HOME/nuzantara/apps/backend-rag/.venv/bin/python"
exec "$PYBIN" -u "$HOME/nuzantara/scripts/intake_gate_count_pusher.py"
