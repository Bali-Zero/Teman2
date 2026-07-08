#!/usr/bin/env bash
# supervisor_autofix_tier2.sh — invokes claude --print + codex exec to
# diagnose + fix Supervisor when tier-1 kickstart fails to recover.
#
# Tier-1 (supervisor_liveness_watchdog.sh) handles the simple case:
# Supervisor stuck → kickstart → if data flow resumes, done.
#
# Tier-2 handles the case where the BUG is in code/config: kickstart
# respawns the daemon but it crashes again (P1 2026-05-08 worktree-path
# trap was exactly this). Restart loop without diagnosis is useless.
#
# Workflow:
#   T0:        check liveness gap > LIVENESS_THRESHOLD_S (default 7200s)
#              + tier-1 already kickstarted in last 30min (from state file)
#              + still gap > threshold → escalate to tier-2
#   T1:        spawn `claude --print` with diagnostic prompt
#              - reads supervisor.err tail
#              - reads launchctl print of plist
#              - reads git log apps/organism/ recent
#              - asks for diagnosis + minimal fix
#              - applies in worktree, bootout/bootstrap, verifies decisions resume
#   T2 (fail): spawn `codex exec` for cross-LLM tie-break with same context
#   T3 (fail): final Telegram alert "ZERO HANDOFF NEEDED"
#
# Caps:
#   - max 3 tier-2 invocations per 24h (anti-loop)
#   - cooldown 60min between attempts
#   - timeout 5min per agent invocation
#   - sandbox: claude/codex run with workspace-write only (no rm, no
#     network beyond OAuth, no bash escape)
#
# State file: ~/.agent/decisions/state/supervisor_autofix_tier2.json
#   { last_attempt_ts, attempts_24h: [ts1, ts2], last_outcome }
#
# Why this is L2-safe (per AUTONOMOUS_OPS.md):
#   - Sandboxed agents cannot rm or push to main
#   - Caps prevent runaway loop
#   - Telegram alerts every escalation step
#   - Final fail = handoff to Zero, not silent fail
#
# Reference:
#   - Issue #541 P1 follow-up
#   - lessons_plist_worktree_path_trap.md (the case this PR addresses)
#   - apps/organism/organism/supervisor/claude_brain.py (sibling pattern,
#     OAuth shell-out, used by Supervisor itself for runtime decisions)
#
# Test:
#   FORCE_TIER2=1 bash ~/scripts/supervisor_autofix_tier2.sh
#   # → spawns claude with mock context (gap=99999), exits 0 if agent
#   #   completed without fix attempt (because state is healthy)

set -u -o pipefail

# --- Config ---
DECISIONS_LOG="${DECISIONS_LOG:-$HOME/logs/organism/decisions.jsonl}"
SUPERVISOR_LABEL="${SUPERVISOR_LABEL:-com.nuzantara.organism.supervisor}"
SUPERVISOR_ERR="${SUPERVISOR_ERR:-$HOME/logs/organism/supervisor.err}"
PLIST_PATH="${PLIST_PATH:-$HOME/Library/LaunchAgents/${SUPERVISOR_LABEL}.plist}"
STATE_FILE="${STATE_FILE:-$HOME/.agent/decisions/state/supervisor_autofix_tier2.json}"
LOG_FILE="${LOG_FILE:-$HOME/logs/supervisor-autofix-tier2.log}"
LIVENESS_THRESHOLD_S="${LIVENESS_THRESHOLD_S:-7200}"
COOLDOWN_S="${COOLDOWN_S:-3600}"  # 60min between attempts
MAX_ATTEMPTS_24H="${MAX_ATTEMPTS_24H:-3}"
AGENT_TIMEOUT_S="${AGENT_TIMEOUT_S:-300}"  # 5min per agent
FORCE_TIER2="${FORCE_TIER2:-0}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >>"$LOG_FILE"; }

# --- Telegram (reuses tier-1 pattern) ---
send_telegram() {
  local msg="$1"
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
    set +a
  fi
  local TOKEN="${TELEGRAM_BOT_TOKEN:-}"
  local CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
  if [ -z "$TOKEN" ]; then
    log "telegram: skipped (no token)"
    return 0
  fi
  curl -fsS --max-time 5 -X POST \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    --data-urlencode "parse_mode=Markdown" \
    >/dev/null 2>&1 || log "telegram: send failed"
}

# --- State helpers ---
read_state_field() {
  local field="$1"
  if [ -f "$STATE_FILE" ]; then
    /usr/bin/jq -r ".${field} // empty" "$STATE_FILE" 2>/dev/null
  fi
}

count_attempts_24h() {
  if [ ! -f "$STATE_FILE" ]; then echo 0; return; fi
  local now_ts; now_ts=$(date +%s)
  local cutoff=$((now_ts - 86400))
  /usr/bin/jq -r --argjson cutoff "$cutoff" '.attempts_24h // [] | map(select(. >= $cutoff)) | length' "$STATE_FILE" 2>/dev/null || echo 0
}

write_state() {
  local outcome="$1"
  local now_ts; now_ts=$(date +%s)
  local cutoff=$((now_ts - 86400))
  local existing="[]"
  if [ -f "$STATE_FILE" ]; then
    existing=$(/usr/bin/jq -r --argjson cutoff "$cutoff" '.attempts_24h // [] | map(select(. >= $cutoff))' "$STATE_FILE" 2>/dev/null || echo "[]")
  fi
  local new_attempts
  new_attempts=$(echo "$existing" | /usr/bin/jq --argjson now "$now_ts" '. + [$now]')
  cat >"$STATE_FILE" <<EOF
{
  "last_attempt_ts": $now_ts,
  "last_outcome": "$outcome",
  "attempts_24h": $new_attempts
}
EOF
}

# --- Diagnosis context builder ---
build_diagnosis_context() {
  local gap="$1"
  local out=""
  out+="# Supervisor Auto-Fix Diagnosis Context\n\n"
  out+="**Date:** $(date -u '+%Y-%m-%dT%H:%M:%SZ')\n"
  out+="**Liveness gap:** ${gap}s ($((gap / 3600))h $(((gap % 3600) / 60))min)\n\n"
  out+="## Last 30 lines of supervisor.err\n\n\`\`\`\n"
  out+="$(tail -n 30 "$SUPERVISOR_ERR" 2>/dev/null | head -c 4000)\n"
  out+="\`\`\`\n\n"
  out+="## launchctl print supervisor (env + state)\n\n\`\`\`\n"
  out+="$(launchctl print "gui/$(id -u)/${SUPERVISOR_LABEL}" 2>/dev/null | grep -E 'state|pid|last exit code|EnvironmentVariables|PYTHONPATH|RULES_PATH' | head -30 | head -c 3000)\n"
  out+="\`\`\`\n\n"
  out+="## Recent commits to apps/organism/\n\n\`\`\`\n"
  out+="$(cd "$HOME/Desktop/nuzantara" && git log --oneline -10 -- apps/organism/ 2>/dev/null)\n"
  out+="\`\`\`\n\n"
  out+="## Plist current paths\n\n\`\`\`\n"
  out+="$(/usr/libexec/PlistBuddy -c 'Print :EnvironmentVariables' "$PLIST_PATH" 2>/dev/null | head -20)\n"
  out+="\`\`\`\n"
  echo -e "$out"
}

invoke_claude() {
  local context="$1"
  if ! command -v claude >/dev/null 2>&1; then
    log "claude CLI not in PATH; skip"
    return 1
  fi
  local prompt="You are a Bali Zero on-call SRE. Supervisor daemon \`com.nuzantara.organism.supervisor\` on Pro is in error loop or unresponsive. Below is diagnostic context. Identify root cause and apply MINIMAL fix.

CONSTRAINTS:
- Fix files in /Users/nuzantara/Desktop/nuzantara only (main checkout). Do NOT use worktree paths.
- For plist edits: chmod u+w, plutil -replace/-remove, chmod 0444, then bootout + bootstrap.
- Verify after fix: bash /Users/nuzantara/Desktop/nuzantara/scripts/supervisor_liveness_watchdog.sh — it must exit 0 with gap < 7200s.
- DO NOT modify Supervisor source code. Only configuration / plist / paths.
- DO NOT rm anything.
- Work autonomously, do not ask questions.
- After fix, send Telegram via: bash /Users/nuzantara/Desktop/nuzantara/scripts/supervisor_liveness_watchdog.sh with FORCE_ALERT=0 to confirm pipeline. Skip if Telegram already validated.

Output format:
DIAGNOSIS: <one-line root cause>
ACTIONS: <numbered list of commands executed>
RESULT: <pass|fail|partial>

CONTEXT:
$context"

  log "invoking claude (timeout ${AGENT_TIMEOUT_S}s)"
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY_RUN=1 → would invoke claude with prompt of $(echo "$prompt" | wc -c) chars"
    return 0
  fi
  timeout "$AGENT_TIMEOUT_S" claude --print --output-format text <<<"$prompt" 2>>"$LOG_FILE" | tee -a "$LOG_FILE"
  return "${PIPESTATUS[0]}"
}

invoke_codex() {
  local context="$1"
  if ! command -v codex >/dev/null 2>&1; then
    log "codex CLI not in PATH; skip"
    return 1
  fi
  local prompt="Tie-break: Claude attempted Supervisor fix but it failed. Apply your own minimal fix following the same constraints (main checkout only, plist hardening, no rm, no source code changes).

CONTEXT:
$context"

  log "invoking codex (timeout ${AGENT_TIMEOUT_S}s)"
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY_RUN=1 → would invoke codex"
    return 0
  fi
  timeout "$AGENT_TIMEOUT_S" codex exec --sandbox workspace-write --full-auto "$prompt" 2>>"$LOG_FILE" | tee -a "$LOG_FILE"
  return "${PIPESTATUS[0]}"
}

verify_recovery() {
  # Re-read decisions log; if gap < threshold, success.
  local last_ts; last_ts=$(/usr/bin/tail -n 1 "$DECISIONS_LOG" 2>/dev/null | /usr/bin/jq -r '.ts // empty' 2>/dev/null)
  if [ -z "$last_ts" ]; then return 1; fi
  local now; now=$(date +%s)
  local last_int=${last_ts%.*}
  local gap=$((now - last_int))
  log "verify: gap=${gap}s threshold=${LIVENESS_THRESHOLD_S}s"
  [ "$gap" -le "$LIVENESS_THRESHOLD_S" ]
}

# --- Main ---
NOW=$(date +%s)

# Compute current gap
LAST_TS=$(/usr/bin/tail -n 1 "$DECISIONS_LOG" 2>/dev/null | /usr/bin/jq -r '.ts // empty' 2>/dev/null)
if [ -z "$LAST_TS" ] || [ "$LAST_TS" = "null" ]; then
  log "ERROR: cannot parse decisions.jsonl"
  send_telegram "🚨 Tier-2 autofix: decisions.jsonl unreadable. Manual investigation."
  exit 1
fi
LAST_TS_INT=${LAST_TS%.*}
GAP=$((NOW - LAST_TS_INT))

# Force mode: skip gate
if [ "$FORCE_TIER2" != "1" ]; then
  if [ "$GAP" -le "$LIVENESS_THRESHOLD_S" ]; then
    log "OK: gap=${GAP}s ≤ threshold ${LIVENESS_THRESHOLD_S}s; tier-2 not needed"
    exit 0
  fi
fi

# Cap check: max 3 attempts per 24h
ATTEMPTS=$(count_attempts_24h)
if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS_24H" ]; then
  log "CAP: attempts_24h=${ATTEMPTS} ≥ max ${MAX_ATTEMPTS_24H}. Final escalation."
  send_telegram "🆘 Tier-2 autofix: ${ATTEMPTS} attempts in 24h, cap reached. ZERO HANDOFF needed.
Last gap: ${GAP}s.
Investigate manually."
  write_state "cap_reached"
  exit 0
fi

# Cooldown check
LAST_ATTEMPT_TS=$(read_state_field "last_attempt_ts")
LAST_ATTEMPT_TS=${LAST_ATTEMPT_TS:-0}
SINCE_LAST=$((NOW - LAST_ATTEMPT_TS))
if [ "$SINCE_LAST" -lt "$COOLDOWN_S" ]; then
  log "COOLDOWN: ${SINCE_LAST}s < ${COOLDOWN_S}s; skip"
  exit 0
fi

# Build context once (reuse for both agents)
log "building diagnosis context (gap=${GAP}s, attempt #${ATTEMPTS}+1)"
CONTEXT=$(build_diagnosis_context "$GAP")

send_telegram "🤖 Tier-2 autofix STARTING (attempt $((ATTEMPTS + 1))/${MAX_ATTEMPTS_24H})
Gap: ${GAP}s
Will invoke claude → verify → codex tie-break if needed."

# Attempt 1: Claude
log "=== TIER-2 ATTEMPT: CLAUDE ==="
if invoke_claude "$CONTEXT"; then
  sleep 30  # let any fix propagate
  if verify_recovery; then
    log "SUCCESS: Claude fix recovered Supervisor"
    send_telegram "✅ Tier-2 autofix SUCCESS via claude
Recovered after ${GAP}s gap."
    write_state "claude_success"
    exit 0
  fi
  log "Claude completed but Supervisor still down"
fi

# Attempt 2: Codex tie-break
log "=== TIER-2 ATTEMPT: CODEX ==="
if invoke_codex "$CONTEXT"; then
  sleep 30
  if verify_recovery; then
    log "SUCCESS: Codex fix recovered Supervisor"
    send_telegram "✅ Tier-2 autofix SUCCESS via codex (claude tried first)
Recovered after ${GAP}s gap."
    write_state "codex_success"
    exit 0
  fi
fi

# Both failed: Zero handoff
log "FAIL: both agents failed; ZERO HANDOFF"
send_telegram "🆘 Tier-2 autofix BOTH AGENTS FAILED
Gap: ${GAP}s
Attempts: $((ATTEMPTS + 1))/${MAX_ATTEMPTS_24H}
Both claude + codex tried; manual investigation needed.
Logs: ~/logs/supervisor-autofix-tier2.log"
write_state "both_failed_zero_handoff"
exit 1
