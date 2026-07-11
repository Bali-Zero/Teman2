#!/bin/bash
# auth_sentinel_cron.sh — wrapper LaunchAgent per scripts/auth_sentinel.py.
#
# W84-safe: vive FUORI da ~/Desktop (il launchd perde il grant TCC su Desktop);
# il canon vive nel repo, la copia eseguita-live è ~/.nuzantara-cron/ (canon-pair
# come agent_worktree_cleanup_cron.sh / verify_connectome_run.sh). Il sentinel
# stesso è path-independent (import sys.path relativo), quindi lo invochiamo dal
# repo — sola lettura, nessun write nel main checkout.
#
# Blocking-loop NON necessario: è un cron puro → StartInterval, KeepAlive=false
# (scar #7 daemon-vs-cron). Un tick = un probe di tutte le credenziali + alert.
set -uo pipefail

REPO="$HOME/Desktop/nuzantara"
LOG_DIR="$HOME/.local/state/auth-sentinel"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# unset ANTHROPIC_API_KEY: il probe claude usa il CLI OAuth, mai la key a pagamento
unset ANTHROPIC_API_KEY 2>/dev/null || true

# PATH esteso: i CLI (agy/codex/nlm/fly) vivono in ~/.local/bin e homebrew — in
# env launchd il PATH è minimale, senza questo i probe darebbero SKIP/NOT_FOUND.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "[$(ts)] auth-sentinel tick start" >> "$LOG"
if [ ! -f "$REPO/scripts/auth_sentinel.py" ]; then
  echo "[$(ts)] FATAL: sentinel non trovato in $REPO/scripts/ (checkout spostato?)" >> "$LOG"
  exit 0   # mai far fallire launchd rumorosamente su un cron di monitoring
fi

# Il sentinel manda gli alert da sé (ramo ACTION → Telegram gateway). Qui logghiamo
# il verdetto completo per audit; exit 0 sempre (gli ACTION viaggiano via alert).
python3 "$REPO/scripts/auth_sentinel.py" >> "$LOG" 2>&1 || true
echo "[$(ts)] auth-sentinel tick end" >> "$LOG"
exit 0
