#!/bin/zsh
# competitor-monitor cron wrapper. Monthly day 1 09:00 WITA.
# Spawns claude --print --agent competitor-monitor.
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

mkdir -p "$HOME/Desktop/nuzantara/research/competitive" "$HOME/.claude/projects/-Users-nuzantara/competitive-snapshots" "$HOME/logs"
LOG="$HOME/logs/competitor-monitor.log"
MONTH=$(TZ=Asia/Makassar date +%Y-%m)

echo "[$(date)] competitor-monitor run starting for $MONTH" >> "$LOG"

PROMPT="Run competitor-monitor agent for month $MONTH.
Read ~/.claude/agents/competitor-monitor.md for full spec.
- Web fetch 3 competitors: Lets Move Indonesia, Emerhub, Flado
- Compare vs last month's snapshot in ~/.claude/projects/-Users-nuzantara/competitive-snapshots/
- IG screenshot triage via Ollama qwen2.5vl:7b LOCAL pre-filter
- Sonnet analysis on filtered posts
- Output digest to ~/Desktop/nuzantara/research/competitive/${MONTH}-digest.md
- Save snapshot for next month
- Telegram digest if material changes detected
- Cold-start logic: if no prior snapshot, mark cold_start: true in digest
Do ALL the work inline in this session — never spawn a background task or background agent
for this; this is a one-shot print-mode run and backgrounded work is terminated at exit,
leaving no digest on disk (W89 class-audit, regulatory-watcher incident 2026-07-05)."

TMPOUT=$(mktemp)
TMPERR=$(mktemp)
# Multi-tier cascade: claude → claude-acct2 → claude-acct3 → gemini → codex → ollama
"$HOME/scripts/claude-cascade.sh" "$PROMPT" --model claude-sonnet-5 --agent competitor-monitor \
    >"$TMPOUT" 2>"$TMPERR"
EXIT=$?
cat "$TMPOUT" >> "$LOG"
cat "$TMPERR" >> "$LOG"

if [ $EXIT -ne 0 ]; then
    echo "[$(date)] competitor-monitor ALL TIERS FAILED ($EXIT)" >> "$LOG"
fi

# Explicit tier-provenance line (W89 class-audit, 2026-07-11): grep the cascade's own
# "[claude-cascade] used: <tier>" line so a run's actual answering tier is always on record
# in this wrapper's own log, not just buried in the cascade's stderr interleave.
# claude-cascade.sh prints this line to STDERR (>&2), so it must be grepped from TMPERR,
# never TMPOUT (stdout-only) — grepping TMPOUT can never match, on success or failure alike
# (PENDING-ARMS ledger, healer tick 2026-07-15).
USED_TIER=$(grep -o '\[claude-cascade\] used: [^"]*' "$TMPERR" | tail -1 || true)
if [ -n "$USED_TIER" ]; then
    echo "[$(date)] [competitor-monitor] ${USED_TIER}" >> "$LOG"
else
    echo "[$(date)] [competitor-monitor] used: none (all tiers failed or no tier line found)" >> "$LOG"
fi

rm -f "$TMPOUT" "$TMPERR"
echo "[$(date)] competitor-monitor run complete" >> "$LOG"
exit 0
