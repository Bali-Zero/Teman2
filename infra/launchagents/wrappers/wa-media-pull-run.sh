#!/bin/bash
# wa-media-pull wrapper: source the 0600 env-file with WHATSAPP_ACCESS_TOKEN +
# BRIDGE_API_KEY, then exec the worker. Mirrors how ~/.wa-mirror.env delivers
# WA_MIRROR_DATABASE_URL. No secret in this file or the plist (2026-04-29 scar).
# Replaces the prior dedicated-keychain approach, which macOS Keychain Services
# quarantined to .bak-conflict under concurrent launchd access.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
ENVF="$HOME/.cell-bridge-state/wa-media.env"
if [[ -f "$ENVF" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENVF"
  set +a
fi
PYBIN="$HOME/nuzantara/apps/backend-rag/.venv/bin/python"
WORKER="$HOME/nuzantara/scripts/wa_media_pull_worker.py"
exec "$PYBIN" -u "$WORKER"
