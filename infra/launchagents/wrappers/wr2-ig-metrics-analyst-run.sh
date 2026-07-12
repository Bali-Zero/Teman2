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

set -euo pipefail

LOGDIR="${HOME}/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/wr2-ig-metrics-analyst.log"
ERR="$LOGDIR/wr2-ig-metrics-analyst.err.log"

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
GEMINI_HINT=""
AGY=/Users/nuzantara/.local/bin/agy
if [ -x "$AGY" ]; then
  AGY_OUT=$( (echo "reply with exactly: AGYUP" | "$AGY" -p --print-timeout 20s 2>&1 &
             AGY_PID=$!; ( sleep 25; kill $AGY_PID 2>/dev/null ) & wait $AGY_PID 2>/dev/null) || true )
  if printf '%s' "$AGY_OUT" | grep -qi 'AGYUP'; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] gemini health-check: UP" >> "$LOG"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] gemini health-check: DOWN (agy not logged in / unreachable) — instructing local fallback" >> "$LOG"
    GEMINI_HINT=" IMPORTANT: agy/Gemini is NOT available right now (auth required or unreachable). DO NOT call agy at Step 2 — skip it and use the LOCAL statistical fallback (Python/jq on the corpus) directly, and mark partial:true. Do not block waiting for Gemini."
  fi
else
  GEMINI_HINT=" IMPORTANT: agy binary not found — use the LOCAL statistical fallback at Step 2, mark partial:true."
fi

# Spawn Claude agent (Sonnet 5) per spec frontmatter
cd "${HOME}/Desktop/nuzantara"
CLAUDE_EXIT=0
/Users/nuzantara/.local/bin/claude -p \
  --model claude-sonnet-5 \
  --permission-mode bypassPermissions \
  "Use the wr2-ig-metrics-analyst agent to run the weekly IG metrics analysis. Follow the spec in ~/.claude/agents/wr2-ig-metrics-analyst.md exactly. Output the proposed amendment file path on the last line.${GEMINI_HINT}" \
  >> "$LOG" 2>> "$ERR" || CLAUDE_EXIT=$?

# Explicit tier-provenance line (PENDING-ARMS sonnet-5 runtime proof, 2026-07-06 fix):
# single-tier by design (no claude-cascade.sh fallback — this agent needs Claude's
# Read/Bash tools, which agy/codex/ollama tiers cannot serve), so "tier" here means
# "did the one tier we have actually answer", not "which of several answered".
if [ "$CLAUDE_EXIT" -eq 0 ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] used: tier1-claude-sonnet-5 (exit=0)" >> "$LOG"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] agent run failed (exit $CLAUDE_EXIT) model=claude-sonnet-5" >> "$ERR"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst done" >> "$LOG"
