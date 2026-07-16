#!/bin/bash
# WA-corpus daily reconcile wrapper.
# Runs the per-member reconciler over all configured team members, then sends a
# digest to the owner via Telegram. Intended to be launched by
# com.nuzantara.wa-corpus.daily (see infra/launchagents/).
#
# Env (set in the plist EnvironmentVariables, NEVER hardcode secrets here):
#   TELEGRAM_BOT_TOKEN       — owner alert bot
#   TELEGRAM_OWNER_CHAT_ID   — Zero's chat id
#   WA_CORPUS_MEMBERS_CONFIG — optional, default ~/.config/nuzantara/wa_corpus_members.json
#   WA_CORPUS_LIMIT          — optional, cap counterparts per member (smoke runs)
#   WA_CORPUS_DRY_RUN        — optional, "1" to decide-only (no Drive/NLM/CRM writes)
set -euo pipefail

REPO_ROOT="${WA_CORPUS_REPO_ROOT:-$HOME/nuzantara}"
VENV_PY="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
LOG="$HOME/logs/wa-corpus-daily.log"
mkdir -p "$HOME/logs"

# Telegram secrets live in ~/.wa-mirror.env (0600), same as the other wa-mirror
# crons — NOT in the plist. Do NOT `source` it: that file has values with spaces
# (WA_MIRROR_SESSION_LABEL=Bali Zero …) that break shell sourcing. Extract just
# the two keys we need, safely. plist env still wins if already set.
_env_val() { grep -m1 -E "^$1=" "$HOME/.wa-mirror.env" 2>/dev/null | cut -d= -f2-; }
if [[ -f "$HOME/.wa-mirror.env" ]]; then
  : "${TELEGRAM_BOT_TOKEN:=$(_env_val TELEGRAM_BOT_TOKEN)}"
  : "${TELEGRAM_OWNER_CHAT_ID:=$(_env_val TELEGRAM_OWNER_CHAT_ID)}"
  export TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID
fi

ts() { date "+%Y-%m-%d %H:%M:%S %Z"; }
echo "[$(ts)] wa-corpus daily start" >>"$LOG"

ARGS=()
[[ -n "${WA_CORPUS_MEMBERS_CONFIG:-}" ]] && ARGS+=(--config "$WA_CORPUS_MEMBERS_CONFIG")
[[ -n "${WA_CORPUS_LIMIT:-}" ]] && ARGS+=(--limit "$WA_CORPUS_LIMIT")
[[ "${WA_CORPUS_DRY_RUN:-}" == "1" ]] && ARGS+=(--dry-run)

cd "$REPO_ROOT"
set +e
OUT="$(PYTHONPATH=. "$VENV_PY" -m scripts.wa_corpus.run_all_members "${ARGS[@]}" 2>&1)"
RC=$?
set -e

echo "$OUT" >>"$LOG"
echo "[$(ts)] wa-corpus daily exit=$RC" >>"$LOG"

# Telegram digest (only the TOTAL line + member lines; never leak chat content).
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]]; then
  SUMMARY="$(printf '%s\n' "$OUT" | grep -E '^WA-CORPUS|^TOTAL|^  ' | head -40)"
  MSG="🗂️ WA-corpus daily (rc=$RC)
$SUMMARY"
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
    --data-urlencode "text=${MSG}" >/dev/null || \
    echo "[$(ts)] telegram send failed" >>"$LOG"
fi

exit "$RC"
