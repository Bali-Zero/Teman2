#!/usr/bin/env zsh
# Wrapper che carica i segreti e lancia il bot

set -euo pipefail

SECRETS="${HOME}/.wa-audit-bot.env"
if [[ ! -f "$SECRETS" ]]; then
    echo "[wa-audit-bot] ERRORE: $SECRETS mancante. Crea il file con TELEGRAM_BOT_TOKEN e WA_AUDIT_MANAGEMENT_CHAT_ID." >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$SECRETS"

VENV="/Users/nuzantara/Desktop/nuzantara/scripts/wa-audit-bot/.venv"
if [[ ! -d "$VENV" ]]; then
    echo "[wa-audit-bot] Creo venv..." >&2
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$(dirname "$0")/requirements.txt"
fi

exec "$VENV/bin/python" "$(dirname "$0")/bot.py"
