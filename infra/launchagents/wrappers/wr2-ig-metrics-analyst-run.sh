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
# line keyed off the claude exit code. The agent stays Claude-only because it
# needs Read/Bash tools, but rotates across all configured OAuth seats.
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
POLL_SECS="${WR2_IG_METRICS_POLL_SECS:-5}"
KILL_GRACE_SECS="${WR2_IG_METRICS_KILL_GRACE_SECS:-10}"
if [ "$POLL_SECS" -lt 1 ]; then
  POLL_SECS=1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst starting" >> "$LOG"

# Source secrets for Gemini OAuth + any future env
if [ -f "${HOME}/.nuzantara-secrets.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${HOME}/.nuzantara-secrets.env"
  set +a
fi

# Pre-flight: do we have ≥10 published carousels with metrics?
PUBLISHED_COUNT=$(python3 -c "
import json
try:
    with open('${HOME}/nuzantara/apps/war-room/output/queue/human-review-queue.json') as f:
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

# Spawn Claude agent (Sonnet 5) per spec frontmatter. Each OAuth seat gets a
# bounded attempt; auth/quota/empty failures rotate to the next seat while the
# aggregate worst-case stays within the original two-hour budget.
cd "${HOME}/nuzantara"
CLAUDE_PROMPT="Use the wr2-ig-metrics-analyst agent to run the weekly IG metrics analysis. Follow the spec in ~/.claude/agents/wr2-ig-metrics-analyst.md exactly. Output the proposed amendment file path on the last line.${GEMINI_HINT}"

CLAUDE_BIN="${WR2_IG_CLAUDE_BIN:-$(command -v claude || true)}"
if [ -z "$CLAUDE_BIN" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] claude binary not found" >> "$ERR"
  exit 127
fi
MAX_CLAUDE_ATTEMPTS=7
DEFAULT_ACCOUNT_TIMEOUT_SECS=$((TIMEOUT_SECS / MAX_CLAUDE_ATTEMPTS))
if [ "$DEFAULT_ACCOUNT_TIMEOUT_SECS" -lt 1 ]; then
  DEFAULT_ACCOUNT_TIMEOUT_SECS=1
fi
ACCOUNT_TIMEOUT_SECS="${WR2_IG_METRICS_ACCOUNT_TIMEOUT_SECS:-$DEFAULT_ACCOUNT_TIMEOUT_SECS}"
if [ "$ACCOUNT_TIMEOUT_SECS" -lt 1 ]; then
  ACCOUNT_TIMEOUT_SECS=1
fi
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] cascade budget: total=${TIMEOUT_SECS}s max_attempts=${MAX_CLAUDE_ATTEMPTS} account_timeout=${ACCOUNT_TIMEOUT_SECS}s" >> "$LOG"
CASCADE_DEADLINE=$(( $(date +%s) + TIMEOUT_SECS ))
ACTIVE_CLAUDE_PID=""
ACTIVE_CLAUDE_PGID=""

terminate_claude_group() {
  local pgid="$1"
  if kill -TERM -- -"$pgid" 2>/dev/null; then
    sleep "$KILL_GRACE_SECS"
    # The group leader may already be gone while a descendant ignored TERM.
    kill -KILL -- -"$pgid" 2>/dev/null || true
  fi
}

cleanup_active_claude() {
  trap - EXIT INT TERM
  if [ -n "$ACTIVE_CLAUDE_PGID" ]; then
    terminate_claude_group "$ACTIVE_CLAUDE_PGID"
  fi
  if [ -n "$ACTIVE_CLAUDE_PID" ]; then
    wait "$ACTIVE_CLAUDE_PID" 2>/dev/null || true
  fi
}
trap cleanup_active_claude EXIT
trap 'cleanup_active_claude; exit 130' INT TERM

claude_stderr_retryable() {
  local stderr_file="$1"
  grep -qiE \
    'rate.?limit|too many requests|(^|[^0-9/])429([^0-9/]|$)|exhausted|quota|usage limit|weekly limit|hit your limit|authentication (failed|required|expired)|auth required|login required|please (log in|login)|not logged in|not authenticated|invalid[_ ](grant|token)|token[_ ]revoked|refresh_token|unauthori[sz]ed|(^|[^0-9/])401([^0-9/]|$)' \
    "$stderr_file"
}

claude_stdout_retryable() {
  local stdout_file="$1"
  python3 - "$stdout_file" <<'PY'
import json
import re
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
broad = re.compile(
    r"rate.?limit|too many requests|(?<![\d/])429(?![\d/])|exhausted|quota|"
    r"usage limit|weekly limit|hit your limit|authentication "
    r"(?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token|"
    r"unauthori[sz]ed|(?<![\d/])401(?![\d/])",
    re.I,
)
whole = re.compile(
    r"\s*(?:(?:error|fatal)(?:\s*[:\-]\s*|\s+))?"
    r"(?:rate.?limit(?:ed| exceeded)?|too many requests|"
    r"429(?:\s+too many requests)?|quota (?:exceeded|exhausted)|"
    r"usage limit(?: reached| exceeded)?|weekly limit(?: reached| exceeded)?|"
    r"hit your limit|authentication (?:failed|required|expired)|auth required|"
    r"login required|please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token(?:_reused)?|"
    r"unauthori[sz]ed|401(?: unauthori[sz]ed)?)"
    r"(?:[\s:.,;\-].{0,240})?\s*",
    re.I | re.S,
)
try:
    payload = json.loads(text)
except (json.JSONDecodeError, TypeError):
    payload = None
is_error = False
if isinstance(payload, dict):
    result = payload.get("result")
    result_kind = ""
    if isinstance(result, dict):
        result_kind = str(
            result.get("type") or result.get("status") or result.get("subtype") or ""
        ).lower()
    envelope_kind = str(payload.get("type") or payload.get("status") or "").lower()
    is_error = (
        payload.get("is_error") is True
        or envelope_kind in {"error", "failed", "failure"}
        or (
            envelope_kind == "result"
            and payload.get("subtype") not in (None, "success")
        )
        or result_kind in {"error", "failed", "failure"}
    )
retryable = (
    bool(is_error and broad.search(json.dumps(payload, ensure_ascii=False)))
    or bool(whole.fullmatch(text))
)
raise SystemExit(0 if retryable else 1)
PY
}

claude_retryable_files() {
  claude_stderr_retryable "$2" || claude_stdout_retryable "$1"
}

run_claude_account() {
  local label="$1"
  local token="$2"
  local attempt_out attempt_err elapsed last_heartbeat sleep_step timed_out claude_pid
  local remaining=$(( CASCADE_DEADLINE - $(date +%s) ))
  if [ "$remaining" -le 0 ]; then
    return 124
  fi
  local attempt_budget="$ACCOUNT_TIMEOUT_SECS"
  if [ "$remaining" -lt "$attempt_budget" ]; then
    attempt_budget="$remaining"
  fi
  attempt_out="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-claude-out.XXXXXX")"
  attempt_err="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-claude-err.XXXXXX")"

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] trying ${label}" >> "$LOG"
  local oauth_env=(env)
  local provider_var
  while IFS= read -r provider_var; do
    case "$provider_var" in
      CLAUDE_CODE_OAUTH_TOKEN*|CLAUDE_CODE_USE_*|ANTHROPIC_*|AWS_*|VERTEX_AI_*|\
      OPENAI_*|OPENROUTER_*|GEMINI_*|GOOGLE_API_KEY|\
      GOOGLE_APPLICATION_CREDENTIALS|CLOUD_ML_REGION|DEEPSEEK_*|\
      TOGETHER_*|FIREWORKS_*|MISTRAL_*|COHERE_*|GROQ_*|XAI_*|PERPLEXITY_*)
        oauth_env+=(-u "$provider_var")
        ;;
    esac
  done < <(compgen -e)
  set -m
  if [ -n "$token" ]; then
    "${oauth_env[@]}" CLAUDE_CODE_OAUTH_TOKEN="$token" \
      "$CLAUDE_BIN" -p \
      --model claude-sonnet-5 \
      --permission-mode bypassPermissions \
      --max-budget-usd "${WR2_IG_MAX_BUDGET_USD:-10}" \
      "$CLAUDE_PROMPT" > "$attempt_out" 2> "$attempt_err" &
  else
    "${oauth_env[@]}" -u CLAUDE_CODE_OAUTH_TOKEN \
      "$CLAUDE_BIN" -p \
      --model claude-sonnet-5 \
      --permission-mode bypassPermissions \
      --max-budget-usd "${WR2_IG_MAX_BUDGET_USD:-10}" \
      "$CLAUDE_PROMPT" > "$attempt_out" 2> "$attempt_err" &
  fi
  claude_pid=$!
  ACTIVE_CLAUDE_PID="$claude_pid"
  ACTIVE_CLAUDE_PGID="$claude_pid"
  set +m

  elapsed=0
  last_heartbeat=0
  timed_out=0
  while kill -0 "$claude_pid" 2>/dev/null; do
    if [ "$elapsed" -ge "$attempt_budget" ]; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} TIMEOUT after ${attempt_budget}s — sending SIGTERM to process group $claude_pid" >> "$LOG"
      terminate_claude_group "$claude_pid"
      timed_out=1
      break
    fi
    sleep_step="$POLL_SECS"
    if [ $((elapsed + sleep_step)) -gt "$attempt_budget" ]; then
      sleep_step=$((attempt_budget - elapsed))
    fi
    sleep "$sleep_step"
    elapsed=$((elapsed + sleep_step))
    if kill -0 "$claude_pid" 2>/dev/null && \
       [ $((elapsed - last_heartbeat)) -ge "$HEARTBEAT_SECS" ]; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} still running (${elapsed}s elapsed, pid $claude_pid)" >> "$LOG"
      last_heartbeat="$elapsed"
    fi
  done

  CLAUDE_EXIT=0
  wait "$claude_pid" 2>/dev/null && CLAUDE_EXIT=0 || CLAUDE_EXIT=$?
  # Reap any background descendant the CLI left in its dedicated group.
  terminate_claude_group "$claude_pid"
  ACTIVE_CLAUDE_PID=""
  ACTIVE_CLAUDE_PGID=""
  if [ "$timed_out" -eq 1 ]; then
    CLAUDE_EXIT=124
  fi

  if [ "$CLAUDE_EXIT" -eq 124 ] || \
     { [ "$CLAUDE_EXIT" -eq 0 ] && ! grep -q '[^[:space:]]' "$attempt_out"; } || \
     claude_retryable_files "$attempt_out" "$attempt_err"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} unavailable (exit=${CLAUDE_EXIT}) — trying next account" >> "$ERR"
    rm -f "$attempt_out" "$attempt_err"
    return 98
  fi
  if [ "$CLAUDE_EXIT" -eq 0 ]; then
    cat "$attempt_out" >> "$LOG"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] used: ${label} claude-sonnet-5 (exit=0)" >> "$LOG"
    rm -f "$attempt_out" "$attempt_err"
    return 0
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} failed (exit=${CLAUDE_EXIT})" >> "$ERR"
  rm -f "$attempt_out" "$attempt_err"
  return "$CLAUDE_EXIT"
}

CLAUDE_EXIT=98
CLAUDE_LABELS=()
CLAUDE_TOKENS=()
for token_var in CLAUDE_CODE_OAUTH_TOKEN_1 CLAUDE_CODE_OAUTH_TOKEN_2 CLAUDE_CODE_OAUTH_TOKEN_3 CLAUDE_CODE_OAUTH_TOKEN_4 CLAUDE_CODE_OAUTH_TOKEN_5 CLAUDE_CODE_OAUTH_TOKEN; do
  token_value="${!token_var:-}"
  [ -z "$token_value" ] && continue
  duplicate=0
  for seen_token in "${CLAUDE_TOKENS[@]:-}"; do
    [ "$seen_token" = "$token_value" ] && duplicate=1
  done
  if [ "$duplicate" -eq 0 ]; then
    CLAUDE_LABELS+=("$token_var")
    CLAUDE_TOKENS+=("$token_value")
  fi
done

for token_index in "${!CLAUDE_LABELS[@]}"; do
  if run_claude_account "${CLAUDE_LABELS[$token_index]}" "${CLAUDE_TOKENS[$token_index]}"; then
    CLAUDE_EXIT=0
    break
  else
    attempt_rc=$?
    if [ "$attempt_rc" -ne 98 ]; then
      CLAUDE_EXIT="$attempt_rc"
      break
    fi
  fi
done

if [ "$CLAUDE_EXIT" -ne 0 ] && [ "$CLAUDE_EXIT" -eq 98 ]; then
  if run_claude_account "keychain" ""; then
    CLAUDE_EXIT=0
  else
    CLAUDE_EXIT=$?
  fi
fi

if [ "$CLAUDE_EXIT" -eq 98 ]; then
  CLAUDE_EXIT=1
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] all Claude OAuth accounts unavailable" >> "$ERR"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst done" >> "$LOG"

exit "$CLAUDE_EXIT"
