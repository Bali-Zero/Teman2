#!/bin/bash
# WR2 External Bench — monthly SOTA editorial IG carousel benchmark wrapper
# Cron: 1st Monday of month 07:00 WITA via com.balizero.wr2.external-bench.monthly.plist
# Spec: .claude/agents/wr2-external-bench.md (multi-LLM Gemini+DeepSeek+Opus)
# Output: ~/.claude/skills/bali-zero-brand/_external-bench-YYYY-MM.md
#
# Coordinated to run AFTER wr2-ig-metrics-analyst.weekly (Monday 06:07) so:
#  (a) any internal amendments from the analyst land first
#  (b) the bench has the same week's data to compare against
#
# Task F — created 2026-05-12 to automate the monthly external SOTA refresh
# seeded by hand for May 2026 (_external-bench-2026-05.md, commit 1095daa).

set -euo pipefail

LOGDIR="${HOME}/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/wr2-external-bench.log"
ERR="$LOGDIR/wr2-external-bench.err.log"

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run,
# not just "log line written" — the sidecar is what a fleet-wide dead-organ
# scan actually reads, per pro-healer.sh's established convention).
ORGAN_ID="wr2.external_bench_monthly"
SIDECAR_DIR="${HOME}/.organism/last_seen"
heartbeat() { # $1 status $2 note
  mkdir -p "$SIDECAR_DIR"
  printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G5_kill_switch — operator stop without uninstall (default enabled).
if [ "${WR2_EXTERNAL_BENCH_ENABLED:-true}" = "false" ]; then
  mkdir -p "$LOGDIR"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] kill switch WR2_EXTERNAL_BENCH_ENABLED=false — exiting" >> "$LOG"
  heartbeat "disabled" "kill switch"
  exit 0
fi

# G10_single_instance — this job is bounded by a 45min hard timeout below, but
# launchd can still overlap a slow prior run with a fresh StartCalendarInterval
# fire; a pidfile makes that overlap a clean skip instead of two Claude sessions
# racing on the same OUTPUT_FILE.
PIDFILE="/tmp/nuzantara-wr2-external-bench.pid"
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] previous run still alive (pid $(cat "$PIDFILE")) — skipping" >> "$LOG"
  heartbeat "ok" "skipped: previous run alive"
  exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

YEAR_MONTH=$(date +%Y-%m)
OUTPUT_FILE="${HOME}/.claude/skills/bali-zero-brand/_external-bench-${YEAR_MONTH}.md"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-external-bench starting (target: ${OUTPUT_FILE})" >> "$LOG"
heartbeat "running" "starting: target ${OUTPUT_FILE}"

# 1st-Monday-of-month enforcement (defense in depth — plist Day=1..7 alone is
# insufficient because Day=N is "day N of month", not "Nth occurrence of
# weekday"). Calculate: if day-of-month > 7 OR not Monday, skip.
DOM=$(date +%-d)  # 1-31
DOW=$(date +%u)   # 1=Mon..7=Sun
if [ "${WR2_BENCH_FORCE:-0}" != "1" ] && { [ "$DOW" -ne 1 ] || [ "$DOM" -gt 7 ]; }; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] skip: today is dow=$DOW dom=$DOM (need dow=1 AND dom<=7 for first Monday)" >> "$LOG"
  heartbeat "ok" "skip: not first Monday (dow=$DOW dom=$DOM)"
  exit 0
fi

# Idempotence: don't re-run if this month's file already exists and is non-empty
# (re-runs allowed via manual delete or --force flag — not implemented yet).
if [ -s "$OUTPUT_FILE" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] skip: ${OUTPUT_FILE} already exists ($(wc -l < "$OUTPUT_FILE") lines). Delete to re-run." >> "$LOG"
  heartbeat "ok" "skip: ${OUTPUT_FILE} already exists"
  exit 0
fi

# Source secrets for DeepSeek API + Gemini OAuth path discovery.
# The `[ -f ]` guard is load-bearing, not defensive noise: `source <missing>
# || true` under `set -e` does NOT degrade — bash treats a failed `source` as a
# special builtin and EXITS before the `||` ever runs. Verified on this fleet's
# /bin/bash (3.2.57): the line after such a source never executes, rc=1, and the
# job dies before writing a single word about why (W108).
[ -f "${HOME}/.nuzantara-secrets.env" ] && source "${HOME}/.nuzantara-secrets.env"

# Verify the seed file from May exists (carryover input per agent spec)
SEED_FILE="${HOME}/.claude/skills/bali-zero-brand/_external-bench-2026-05.md"
if [ ! -s "$SEED_FILE" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WARNING: seed file ${SEED_FILE} missing — first run without carryover" >> "$LOG"
fi

# Find previous month's bench file as primary carryover input
PREV_MONTH=$(date -v-1m +%Y-%m 2>/dev/null || date -d "1 month ago" +%Y-%m 2>/dev/null || echo "")
PREV_FILE=""
if [ -n "$PREV_MONTH" ]; then
  CANDIDATE="${HOME}/.claude/skills/bali-zero-brand/_external-bench-${PREV_MONTH}.md"
  [ -s "$CANDIDATE" ] && PREV_FILE="$CANDIDATE"
fi
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] carryover prior month: ${PREV_FILE:-<none>}" >> "$LOG"

# Spawn Claude Opus 4.7 with the wr2-external-bench agent spec
# Per CLAUDE.md global rule: OAuth-only, never ANTHROPIC_API_KEY.
# wr2-external-bench frontmatter declares model: opus (synthesis-grade).
#
# G6_spawn_hardened — TCC is PER-BINARY (W84): launchd granting bash access to
# a path says nothing about the node binary behind `claude`. Probe repo access
# BEFORE spawning so a TCC-denied context fails loud (exit 78) instead of the
# claude child hanging invisibly on a consent dialog nothing can answer.
if [ -z "${SSH_CONNECTION:-}" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] no SSH_CONNECTION — running in direct launchd/local context" >> "$LOG"
fi
if ! /bin/ls "${HOME}/nuzantara/CLAUDE.md" >/dev/null 2>&1; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FATAL: TCC denies repo access in this context" >> "$ERR"
  heartbeat "error" "TCC denied"
  exit 78
fi
cd "${HOME}/nuzantara"

PROMPT="Execute wr2-external-bench monthly run for ${YEAR_MONTH}.

Per your agent spec (.claude/agents/wr2-external-bench.md):
- Step 1: ingest 12 editorial brands + 3 competitor + 2 trend reports via Gemini 3.1 Pro
- Step 2: DeepSeek Reasoner extracts 20-30 patterns cross-brand
- Step 3: synthesis vs Bali Zero baseline (_empirical-metrics-2026-05-12.md +
  any newer _empirical-metrics-*.md files)
- Step 4: write ${OUTPUT_FILE}

Carryover prior month: ${PREV_FILE:-<none — first auto run, use seed _external-bench-2026-05.md as baseline>}.

Anti-stagnation: add ≥2 patterns NOT in carryover.

CRITICAL EXECUTION RULE: run EVERY step synchronously in the foreground and
finish ALL steps (including writing ${OUTPUT_FILE}) before ending your turn.
NEVER use run_in_background, background monitors, or 'I will wait for X' —
this print-mode session terminates the moment your turn ends, killing any
background work (2026-06-11 post-mortem: DeepSeek launched async, agent
exited success with zero output).
Budget: ~30 min wall-clock, ≤\$0.10 cost (DeepSeek 2 calls).

When done, log to ${LOG} a one-line summary: 'wr2-external-bench ${YEAR_MONTH} DONE: <N patterns extracted, X ADOPT / Y PARTIAL / Z OBSERVE / W REJECT>'.

Telegram notify Antonello after write (per agent spec Step 5) with the executive summary."

CLAUDE_BIN="${HOME}/.local/bin/claude"
[ -x "$CLAUDE_BIN" ] || CLAUDE_BIN="/opt/homebrew/bin/claude"

# Run with timeout cap (45 min hard limit — agent budget is 30 min nominal)
BENCH_TIMEOUT="${WR2_BENCH_TIMEOUT:-2700}"
if [ "${WR2_BENCH_DEBUG:-0}" = "1" ]; then
  # stream the agent turns to a dedicated debug log so a hang shows WHERE
  timeout "$BENCH_TIMEOUT" "$CLAUDE_BIN" -p \
    --model claude-opus-4-8 \
    --permission-mode bypassPermissions \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --max-budget-usd "${WR2_BENCH_MAX_BUDGET_USD:-10}" \
    --verbose --output-format stream-json \
    --append-system-prompt "You are wr2-external-bench. Read your spec at .claude/agents/wr2-external-bench.md. Follow it exactly." \
    "$PROMPT" \
    < /dev/null >> "${LOG%.log}.debug.jsonl" 2>> "$ERR" || EXIT_CODE=$?
else
  timeout "$BENCH_TIMEOUT" "$CLAUDE_BIN" -p \
    --model claude-opus-4-8 \
    --permission-mode bypassPermissions \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    --max-budget-usd "${WR2_BENCH_MAX_BUDGET_USD:-10}" \
    --append-system-prompt "You are wr2-external-bench. Read your spec at .claude/agents/wr2-external-bench.md. Follow it exactly." \
    "$PROMPT" \
    < /dev/null >> "$LOG" 2>> "$ERR" || EXIT_CODE=$?
fi

EXIT_CODE=${EXIT_CODE:-0}
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-external-bench done (exit=${EXIT_CODE}, output_lines=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo 0))" >> "$LOG"
if [ "$EXIT_CODE" -eq 0 ]; then
  heartbeat "ok" "done: ${YEAR_MONTH}"
else
  heartbeat "error" "exit=${EXIT_CODE}"
fi

# Telegram alert on failure (success notify is agent's job per Step 5).
#
# Routed through the ONE gateway (tg_notify.py owns token resolution, tiering and
# dedup) rather than a direct sendMessage. Two defects died with the old block:
#   - it was gated on `[ -f ~/.nuzantara-secrets.env ]` AND on both variables
#     being non-empty, so in a token-poor cron environment it did nothing and
#     left no trace of having done nothing — the exact W108 signature;
#   - `> /dev/null || true` threw away the outcome, so "the alarm fired" and
#     "the alarm was swallowed" were indistinguishable afterwards.
# The rc is now captured with errexit disarmed (W101: judge by the CAPTURED code,
# never by having survived the line) and written to the log either way.
if [ "$EXIT_CODE" -ne 0 ]; then
  GATEWAY="$(dirname "$0")/tg_notify.py"
  [ -f "$GATEWAY" ] || GATEWAY="${HOME}/nuzantara/scripts/tg_notify.py"
  set +e
  python3 "$GATEWAY" --tier p0 --source wr2-external-bench \
    --dedup-key "wr2-external-bench:${YEAR_MONTH}:$(hostname -s)" \
    -- "⚠️ wr2-external-bench ${YEAR_MONTH} FAILED (exit=${EXIT_CODE}). Check ${ERR}" \
    >> "$LOG" 2>&1
  NOTIFY_RC=$?
  set -e
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] telegram notify rc=${NOTIFY_RC} (gateway=${GATEWAY})" >> "$LOG"
fi

exit "$EXIT_CODE"
