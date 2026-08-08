#!/usr/bin/env zsh
# Wrapper: bootstraps a local venv (pattern per scripts/wa-audit-bot/run-bot.sh)
# and runs the mirror. Telegram credentials are resolved by tg_notify.py
# itself (env or ~/.nuzantara-secrets.env) — nothing to source here.
#
# NOT wired into cron/launchd by this change. Manual/dry-run invocation only
# until the operator decides to arm a schedule (Zero mandate, 2026-08-08).

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/.venv"

if [[ ! -d "$VENV" ]]; then
    echo "[imigrasi-mirror] creating venv..." >&2
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$HERE/requirements.txt"
fi

exec "$VENV/bin/python" "$HERE/run.py" "$@"
