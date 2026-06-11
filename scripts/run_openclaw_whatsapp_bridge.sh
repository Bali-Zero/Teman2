#!/usr/bin/env bash
set -euo pipefail

SECRET_FILE="${OPENCLAW_WHATSAPP_BRIDGE_SECRET_FILE:-$HOME/.openclaw/secrets/whatsapp-openclaw-bridge-secret}"
PORT="${OPENCLAW_WHATSAPP_BRIDGE_PORT:-8789}"
UVICORN_BIN="${OPENCLAW_WHATSAPP_UVICORN_BIN:-/opt/homebrew/bin/uvicorn}"

if [[ ! -r "$SECRET_FILE" ]]; then
  echo "Missing bridge secret file: $SECRET_FILE" >&2
  exit 78
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export WHATSAPP_OPENCLAW_BRIDGE_SECRET
WHATSAPP_OPENCLAW_BRIDGE_SECRET="$(tr -d '\n\r' < "$SECRET_FILE")"

# Army-command sender allowlist (digits-only, comma-separated). Only these
# WhatsApp numbers may trigger /lancia & friends, which run an autonomous
# `claude --dangerously-skip-permissions` on the Pro. UNSET in the bridge env
# = deny-all (feature disabled). Default to the owner number; override by
# exporting WA_ARMY_OWNERS before launch.
export WA_ARMY_OWNERS="${WA_ARMY_OWNERS:-6282264599868}"

exec "$UVICORN_BIN" \
  --app-dir "$HOME/.openclaw/bin" \
  openclaw_whatsapp_bridge:app \
  --host 127.0.0.1 \
  --port "$PORT"
