#!/usr/bin/env bash
# Compatibility entrypoint for com.balizero.wa-mirror-launcher.
#
# The LaunchAgent calls this repo path, while the single-account launcher
# operational scripts live under ~/scripts/wa-mirror-launcher. Keep this thin
# so launchd has a stable, versioned entrypoint without duplicating launcher
# logic.

set -euo pipefail

export HOME="${HOME:-/Users/nuzantara}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LAUNCHER="${WA_MIRROR_LAUNCHER_START_ALL:-${HOME}/scripts/wa-mirror-launcher/start-all.sh}"

if [[ ! -f "$LAUNCHER" ]]; then
  echo "wa-mirror launcher missing: $LAUNCHER" >&2
  exit 127
fi

exec /bin/bash "$LAUNCHER" "$@"
