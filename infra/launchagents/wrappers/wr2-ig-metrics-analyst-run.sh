#!/bin/bash
# WR2 IG Metrics Analyst — weekly run wrapper
# Cron: Monday 06:00 WITA via com.balizero.wr2.ig-metrics-analyst.weekly.plist
# Reads engagement metrics from human-review-queue.json + wr2-episodic.db,
# correlates with carousel attributes, proposes amendments to
# ~/.claude/skills/bali-zero-brand/_proposed-amendments/<date>-ig-insights.md.
# Spec: ~/.claude/agents/wr2-ig-metrics-analyst.md (Sonnet 4.6 frontmatter).
# Phase B Phase D — created 2026-05-10 to close ciclo-vitale loop.
#
# Sonnet-5 runtime proof gap (PENDING-ARMS 2026-07-03/07-06): this wrapper called
# `claude` directly with no explicit "used: <tier>" log line, unlike
# regulatory-watcher-run.sh (via claude-cascade.sh) — structurally unprovable
# which model actually answered a given run. Fix: log an explicit provenance
# line keyed off the claude exit code, without changing the invocation itself
# (single-tier by design — this agent's Read/Bash tool needs stay Claude-only).
#
# B7 wall-clock timeout + loud logging (2026-07-14, WR2 deep audit §4/§10.7):
# a run hung 28h+ until externally SIGTERM'd, and BOTH log files were
# completely empty for the entire hang — nothing in this wrapper bounded the
# child's runtime, and `claude -p` in non-streaming mode writes nothing to
# stdout/stderr until the turn completes, so a hung child was structurally
# indistinguishable from "still working" (the wrapper itself never emitted a
# byte while waiting on `wait`/redirected `>>`). Fix: background the child,
# poll it with a heartbeat (log is never silent even if the child never
# writes anything) plus a hard wall-clock ceiling (SIGTERM, escalate to
# SIGKILL after a grace period, exit 124) — same convention as
# scripts/cron-wrapper.sh's bash-watchdog fallback for machines without
# gtimeout/timeout, and the same "background + sleep + kill" idiom this file
# already used for the agy health-check below. N=7200s (2h) — generous: the
# analyst legitimately reads a full carousel+metrics corpus. Override via
# WR2_IG_METRICS_TIMEOUT_SECS.

set -euo pipefail

LOGDIR="${HOME}/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/wr2-ig-metrics-analyst.log"
ERR="$LOGDIR/wr2-ig-metrics-analyst.err.log"

TIMEOUT_SECS="${WR2_IG_METRICS_TIMEOUT_SECS:-7200}"
HEARTBEAT_SECS=300
KILL_GRACE_SECS=10

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst starting" >> "$LOG"

# Source secrets for Gemini OAuth + any future env
set -a
source "${HOME}/.nuzantara-secrets.env" 2>/dev/null || true
set +a
# MAX-3 → expose the un-suffixed CLAUDE_CODE_OAUTH_TOKEN that the `claude` CLI reads
# (the _1/_2/_3 suffix is a python-client convention; the bare CLI ignores it).
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  export CLAUDE_CODE_OAUTH_TOKEN="${CLAUDE_CODE_OAUTH_TOKEN_1:-${CLAUDE_CODE_OAUTH_TOKEN_2:-${CLAUDE_CODE_OAUTH_TOKEN_3:-}}}"
fi


# Pre-flight: do we have ≥10 published carousels with metrics?
PUBLISHED_COUNT=$(python3 -c "
import json
try:
    with open('${HOME}/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json') as f:
        data = json.load(f)
    items = data.get('items', data) if isinstance(data, dict) else data
    n = sum(1 for i in items if i.get('state') in ('published', 'published_with_edits') and (i.get('engagement_metrics') or {}).get('likes') is not None)
    print(n)
except Exception as e:
    print(0)
")

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] published-with-metrics count: $PUBLISHED_COUNT" >> "$LOG"

if [ "$PUBLISHED_COUNT" -lt 10 ]; then
  STUB="${HOME}/.claude/skills/bali-zero-brand/_proposed-amendments/$(date +%Y-%m-%d)-ig-insights-insufficient-data.md"
  cat > "$STUB" <<EOF
# IG Insights — Insufficient Data — $(date +%Y-%m-%d)

**Run**: weekly cron Monday 06:00 WITA
**Published+metrics count**: $PUBLISHED_COUNT (threshold: ≥10)
**Action**: STOP. No analysis run. Re-evaluate next week.

Once Damar marks ≥10 carousels as 'published' with IG URLs and the daily ig-scraper
fills engagement_metrics, the analyst will produce real amendments.

## Bootstrap path (2026-05-10)
First-prod publish: kep71-spt-extension-test6-FIRSTPROD (DAHJRpG2QIs).
N=1 — need 9 more publishes to unlock analysis.
EOF
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] insufficient data — stub written: $STUB" >> "$LOG"
  exit 0
fi

# --- GEMINI HEALTH-CHECK (2026-06-23, fixes the agy-hang bug) -----------------
# The agent's Step-2 calls `agy -p` for 1M-context analysis. When agy is NOT logged in,
# it opens an OAuth flow and BLOCKS (CPU 0%, up to 5m timeout per call) instead of failing
# cleanly — the agent then hangs and never reaches its local-stats fallback. We probe agy
# here with a hard 25s ceiling; if it does not return a clean answer, we tell the agent
# explicitly to SKIP Gemini and go straight to the local Python/jq fallback path.
#
# 2026-07-14 zombie fix: the previous watchdog only `kill $AGY_PID` — the exact
# PID named after backgrounding the `echo | agy` pipeline. If agy forks a
# detached grandchild that keeps the pipe's write-end open, agy itself dies on
# the kill but the command-substitution's read() blocks forever waiting for
# EOF from that orphaned descendant (live incident: a 32h zombie found+killed
# on 2026-07-14). Fix: no pipe at all (prompt goes in via a temp file, so
# capture never depends on every fd holder closing), agy runs as the sole/
# first process of its own job so `set -m` gives it its own process group
# (PGID == its own PID), and the watchdog kills the WHOLE group
# (`kill -- -$PGID`, TERM then KILL) — no descendant can outlive the timeout.
GEMINI_HINT=""
AGY=/Users/nuzantara/.local/bin/agy
if [ -x "$AGY" ]; then
  AGY_PROMPT="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-agy-prompt.XXXXXX")"
  AGY_TMP="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-agy-health.XXXXXX")"
  echo "reply with exactly: AGYUP" > "$AGY_PROMPT"
  (
    set -m
    "$AGY" -p --print-timeout 20s < "$AGY_PROMPT" > "$AGY_TMP" 2>&1 &
    AGY_PID=$!
    (
      sleep 25
      kill -TERM -- -"$AGY_PID" 2>/dev/null
      sleep 2
      kill -KILL -- -"$AGY_PID" 2>/dev/null
    ) &
    WATCHDOG_PID=$!
    wait "$AGY_PID" 2>/dev/null
    kill "$WATCHDOG_PID" 2>/dev/null
    wait "$WATCHDOG_PID" 2>/dev/null
  ) 2>/dev/null
  AGY_OUT="$(cat "$AGY_TMP" 2>/dev/null || true)"
  rm -f "$AGY_PROMPT" "$AGY_TMP"
  if printf '%s' "$AGY_OUT" | grep -qi 'AGYUP'; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] gemini health-check: UP" >> "$LOG"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] gemini health-check: DOWN (agy not logged in / unreachable) — instructing local fallback" >> "$LOG"
    GEMINI_HINT=" IMPORTANT: agy/Gemini is NOT available right now (auth required or unreachable). DO NOT call agy at Step 2 — skip it and use the LOCAL statistical fallback (Python/jq on the corpus) directly, and mark partial:true. Do not block waiting for Gemini."
  fi
else
  GEMINI_HINT=" IMPORTANT: agy binary not found — use the LOCAL statistical fallback at Step 2, mark partial:true."
fi

# Spawn Claude agent (Sonnet 5) per spec frontmatter — backgrounded under a
# wall-clock watchdog (see B7 note at top of file).
cd "${HOME}/Desktop/nuzantara"
CLAUDE_PROMPT="Use the wr2-ig-metrics-analyst agent to run the weekly IG metrics analysis. Follow the spec in ~/.claude/agents/wr2-ig-metrics-analyst.md exactly. Output the proposed amendment file path on the last line.${GEMINI_HINT}"

# Best-effort line-buffering for the child's stdout/stderr (macOS ships a
# native `stdbuf`, syntax `-o L`/`-e L` — not the GNU `-oL` short form).
# Defense-in-depth only: the primary "log is never silent" guarantee below
# is the wrapper's own heartbeat, which does not depend on child buffering
# behavior at all.
if command -v stdbuf &>/dev/null; then
  stdbuf -o L -e L /Users/nuzantara/.local/bin/claude -p \
    --model claude-sonnet-5 \
    --permission-mode bypassPermissions \
    "$CLAUDE_PROMPT" \
    >> "$LOG" 2>> "$ERR" &
else
  /Users/nuzantara/.local/bin/claude -p \
    --model claude-sonnet-5 \
    --permission-mode bypassPermissions \
    "$CLAUDE_PROMPT" \
    >> "$LOG" 2>> "$ERR" &
fi
CLAUDE_PID=$!

ELAPSED=0
TIMED_OUT=0
while kill -0 "$CLAUDE_PID" 2>/dev/null; do
  if [ "$ELAPSED" -ge "$TIMEOUT_SECS" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] TIMEOUT after ${TIMEOUT_SECS}s — sending SIGTERM to pid $CLAUDE_PID" >> "$LOG"
    kill -TERM "$CLAUDE_PID" 2>/dev/null || true
    sleep "$KILL_GRACE_SECS"
    if kill -0 "$CLAUDE_PID" 2>/dev/null; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] pid $CLAUDE_PID survived SIGTERM — sending SIGKILL" >> "$LOG"
      kill -KILL "$CLAUDE_PID" 2>/dev/null || true
    fi
    TIMED_OUT=1
    break
  fi
  sleep "$HEARTBEAT_SECS"
  ELAPSED=$((ELAPSED + HEARTBEAT_SECS))
  if kill -0 "$CLAUDE_PID" 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] still running (${ELAPSED}s elapsed, timeout ${TIMEOUT_SECS}s, pid $CLAUDE_PID)" >> "$LOG"
  fi
done

CLAUDE_EXIT=0
wait "$CLAUDE_PID" 2>/dev/null && CLAUDE_EXIT=0 || CLAUDE_EXIT=$?
if [ "$TIMED_OUT" -eq 1 ]; then
  CLAUDE_EXIT=124
fi

# Explicit tier-provenance line (PENDING-ARMS sonnet-5 runtime proof, 2026-07-06 fix):
# single-tier by design (no claude-cascade.sh fallback — this agent needs Claude's
# Read/Bash tools, which agy/codex/ollama tiers cannot serve), so "tier" here means
# "did the one tier we have actually answer", not "which of several answered".
if [ "$CLAUDE_EXIT" -eq 0 ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] used: tier1-claude-sonnet-5 (exit=0)" >> "$LOG"
elif [ "$CLAUDE_EXIT" -eq 124 ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] used: tier1-claude-sonnet-5 ABORTED (timeout after ${TIMEOUT_SECS}s, pid $CLAUDE_PID)" >> "$ERR"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] agent run failed (exit $CLAUDE_EXIT) model=claude-sonnet-5" >> "$ERR"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst done" >> "$LOG"

exit "$CLAUDE_EXIT"
