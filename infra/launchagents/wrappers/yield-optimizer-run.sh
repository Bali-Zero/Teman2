#!/bin/zsh
# yield-optimizer cron wrapper. Sun 04:00 WITA.
# Spawns claude --print --agent yield-optimizer (Sonnet 4.6 OAuth, Ollama qwen3.5:9b LOCAL for CRM PII).
# Cost: 0$ (OAuth + local Ollama).
#
# W89 class-audit fix (2026-07-11, PENDING-ARMS ledger ~68): sonnet-5 in --print mode can
# silently spawn its work as a background task; the CLI kills it at the print-mode ceiling
# and exits 0 with no output — "success" with nothing produced (incident: regulatory-watcher
# 2026-07-05). Fix here is the same shape: claude-cascade.sh (this wrapper's Claude-tier
# entry point) raises CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS, and the prompt below tells the
# model inline never to background this run.

set -uo pipefail
unset ANTHROPIC_API_KEY

[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

mkdir -p "$HOME/Desktop/nuzantara/research/commercial" "$HOME/logs"
LOG="$HOME/logs/yield-optimizer.log"
DATE=$(TZ=Asia/Makassar date +%Y-%m-%d)
WEEK=$(TZ=Asia/Makassar date +%Y-W%V)

echo "[$(date)] yield-optimizer run starting for $WEEK" >> "$LOG"

PROMPT="Run yield-optimizer agent for week $WEEK ($DATE).
Read ~/.claude/agents/yield-optimizer.md for full spec.
- Pull CRM via Postgres (apply 6 opportunity rules R1-R6, cap 20)
- Generate WhatsApp pitches via Ollama qwen3.5:9b LOCAL (NEVER cloud LLM for CRM PII)
- Output to ~/Desktop/nuzantara/research/commercial/${WEEK}-yield-opportunities.md
- Telegram digest to TELEGRAM_OWNER_CHAT_ID
- Emit eventbus learning.updated event
NO autonomous outreach. Drafts ONLY for ops team.
Do ALL the work inline in this session — never spawn a background task or background agent
for this; this is a one-shot print-mode run and backgrounded work is terminated at exit,
leaving no opportunities file on disk (W89 class-audit, regulatory-watcher incident 2026-07-05)."

TMPOUT=$(mktemp)
TMPERR=$(mktemp)
# Multi-tier cascade: claude → claude-acct2 → claude-acct3 → gemini → codex → ollama
"$HOME/scripts/claude-cascade.sh" "$PROMPT" --model claude-sonnet-5 --agent yield-optimizer \
    >"$TMPOUT" 2>"$TMPERR"
EXIT=$?
cat "$TMPOUT" >> "$LOG"
cat "$TMPERR" >> "$LOG"

if [ $EXIT -ne 0 ]; then
    echo "[$(date)] yield-optimizer ALL TIERS FAILED ($EXIT)" >> "$LOG"
fi

# Explicit tier-provenance line (W89 class-audit, 2026-07-11): grep the cascade's own
# "[claude-cascade] used: <tier>" line so a run's actual answering tier is always on record
# in this wrapper's own log, not just buried in the cascade's stderr interleave.
# claude-cascade.sh prints this line to STDERR (>&2), so it must be grepped from TMPERR,
# never TMPOUT (stdout-only) — grepping TMPOUT can never match, on success or failure alike
# (PENDING-ARMS ledger, healer tick 2026-07-15).
USED_TIER=$(grep -o '\[claude-cascade\] used: [^"]*' "$TMPERR" | tail -1 || true)
if [ -n "$USED_TIER" ]; then
    echo "[$(date)] [yield-optimizer] ${USED_TIER}" >> "$LOG"
else
    echo "[$(date)] [yield-optimizer] used: none (all tiers failed or no tier line found)" >> "$LOG"
fi

rm -f "$TMPOUT" "$TMPERR"
echo "[$(date)] yield-optimizer run complete" >> "$LOG"
exit 0
