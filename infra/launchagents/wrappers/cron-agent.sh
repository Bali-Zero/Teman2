#!/usr/bin/env bash
# cron-agent.sh — Universal cron wrapper for all automation tiers
#
# Usage:
#   cron-agent.sh exec  <job-name> <script> [args...]   # Tier 0: run script, alert on failure
#   cron-agent.sh agent <job-name> <prompt-file>         # Tier 2: claude -p with account fallback
#
# Features:
#   - Telegram alert on failure (with cooldown)
#   - Claude OAuth fallback (TOKEN_1 → ... → TOKEN_5 → TOKEN_6 [Team, last-resort] → legacy → keychain)
#   - Structured logging to ~/logs/cron-agent/
#   - Timeout enforcement
#   - Lock file (prevents concurrent runs of same job)
#   - Exit code tracking for health report
#
# Environment:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — alerts (loaded from ~/.nuzantara-secrets.env)
#   CLAUDE_CODE_OAUTH_TOKEN_{1,2,3,4,5} — 5 Claude MAX subscription accounts for agent tier
#   CLAUDE_CODE_OAUTH_TOKEN_6 — Claude Team seat (zero@balizero.com), weekly-capped, LAST RESORT ONLY
#   CRON_AGENT_TIMEOUT — override default timeout (default: 300s exec, 600s agent)
#   CRON_AGENT_DRY_RUN — set to "1" to print commands without executing
#
# W89 class-audit fix (2026-07-11, PENDING-ARMS ledger ~68): sonnet-5 in --print mode can
# silently spawn its work as a background task; the CLI kills it at the print-mode ceiling
# and exits 0 with no output (incident: regulatory-watcher 2026-07-05). run_agent() below
# raises the background ceiling and the prompt appends an inline anti-background sentence,
# plus an explicit "used: tier1-<label>" provenance log line per successful attempt.

set -uo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
TIER="${1:-}"
JOB_NAME="${2:-}"
SCRIPT_OR_PROMPT="${3:-}"
shift 3 2>/dev/null || true

if [[ -z "$TIER" || -z "$JOB_NAME" || -z "$SCRIPT_OR_PROMPT" ]]; then
    echo "Usage: cron-agent.sh {exec|agent} <job-name> <script-or-prompt-file> [args...]"
    exit 1
fi

# Paths
LOG_DIR="$HOME/logs/cron-agent"
LOG_FILE="$LOG_DIR/${JOB_NAME}.log"
STATE_DIR="$HOME/.cron-agent"
LOCK_FILE="$STATE_DIR/${JOB_NAME}.lock"
STATE_FILE="$STATE_DIR/${JOB_NAME}.state.json"
COOLDOWN_FILE="$STATE_DIR/${JOB_NAME}.cooldown"
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
# Repo-tracked job->fingerprint map (P2 no-op suppression, arm-without-crontab-edit).
# Deploy convention: this is a plain copy of infra/launchagents/cron-agent-fingerprints.json,
# same as cron-agent.sh itself is a HOME-fork copy of its repo source (declared-pairs.json).
FINGERPRINT_MAP="${CRON_AGENT_FINGERPRINT_MAP:-$STATE_DIR/fingerprints.json}"

mkdir -p "$LOG_DIR" "$STATE_DIR"

# Load secrets
[[ -f "$SECRETS_FILE" ]] && { set -a; source "$SECRETS_FILE"; set +a; }

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${TELEGRAM_OWNER_CHAT_ID:-8847435604}}"

# Timeouts
case "$TIER" in
    exec)  DEFAULT_TIMEOUT=300 ;;
    agent) DEFAULT_TIMEOUT=600 ;;
    *)     echo "Unknown tier: $TIER"; exit 1 ;;
esac
TIMEOUT="${CRON_AGENT_TIMEOUT:-$DEFAULT_TIMEOUT}"

# Floor for a single cascade attempt (see run_agent's allocation comment). The
# slowest agent job measured succeeding on Pro takes 118s; 300s is ~2.5x that,
# and the global TIMEOUT above still caps the whole cascade. Per-job override:
# CRON_AGENT_MIN_ATTEMPT_SECONDS.
MIN_ATTEMPT_SECONDS="${CRON_AGENT_MIN_ATTEMPT_SECONDS:-300}"

# ── Helpers ───────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] [$JOB_NAME] $*" >> "$LOG_FILE"; }

_file_mtime() {
    # `stat -f%m` is BSD syntax. On GNU coreutils `-f` means --file-system and
    # `%m` is the MOUNT POINT, so the BSD form does not fail there — it succeeds
    # and prints something that is not a timestamp. A `|| echo 0` fallback keyed
    # to the exit code therefore never fires, and the caller's age arithmetic
    # gets garbage. Judge the VALUE (is it a number?), not the exit code.
    # Pro runs macOS, so the BSD branch is the live one; the GNU branch is what
    # makes the cooldown gate testable on a Linux CI runner instead of silently
    # inert there (W108: a check that only runs on one OS hides defects).
    local m
    m="$(stat -f%m "$1" 2>/dev/null)"
    case "$m" in ''|*[!0-9]*) m="$(stat -c%Y "$1" 2>/dev/null)" ;; esac
    case "$m" in ''|*[!0-9]*) m=0 ;; esac
    printf '%s' "$m"
}

send_telegram() {
    local msg="$1"
    # Notification gateway (post-#2263 canon promotion): tg_notify.py owns token
    # resolution + tiering + 6h dedup; this wrapper keeps its own 30-min cooldown.
    # No env-token gate: an alert must not vanish silently when env lacks the token.
    #
    # JUDGE THE REPLY, NOT THE EXIT CODE (W104). tg_notify.py's main() returns 0
    # unconditionally — its `except Exception` branch is literally commented
    # "NEVER fail the caller", spools best-effort and still returns 0. So an rc
    # check here would be decorative by construction. The verdict is the status
    # word it prints on STDERR, one of six:
    #     sent               -> it reached Telegram
    #     deduped            -> an equivalent message went out recently (silence
    #                           is the intended outcome, so it counts as handled)
    #     logged | spooled | p0_overflow_spooled | p0_unsent_spooled
    #                        -> it did NOT reach Telegram; it is parked for later
    # The old line discarded both channels (`>/dev/null 2>&1`) and then touched
    # the cooldown unconditionally, so a spooled or errored alert also bought 30
    # minutes of silence and left no trace of having done so — a lost alert that
    # suppressed its own successor.
    if [[ -f "$COOLDOWN_FILE" ]]; then
        local age=$(( $(date +%s) - $(_file_mtime "$COOLDOWN_FILE") ))
        [[ $age -lt 1800 ]] && { log "Telegram cooldown active (${age}s < 1800s)"; return; }
    fi
    local gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/nuzantara/scripts/tg_notify.py"
    if [[ ! -f "$gateway" ]]; then
        log "ALERT NOT SENT: notification gateway missing (looked in $(dirname "$0") and $HOME/nuzantara/scripts)"
        return
    fi
    local reply rc
    reply="$(python3 "$gateway" --tier p0 --source cron-agent \
        --dedup-key "cron-agent:${JOB_NAME}:$(hostname -s)" -- "$msg" 2>&1)"
    rc=$?
    # Record what the gateway actually said, always. rc is logged for forensics
    # only — it is never the thing being judged.
    log "Telegram gateway rc=$rc reply=$(printf '%s' "$reply" | tr '\n' ' ' | head -c 200)"
    # Read the status as an ENTITY, not a substring (superscar #3): pull the word
    # off a line that IS the status line. A bare `*"sent"*` would also match the
    # free-form "internal error (...)" branch if an exception message ever carried
    # the word, and `p0_unsent_spooled` is one prefix away from a false positive.
    local status
    status="$(printf '%s\n' "$reply" | sed -n 's/^tg_notify: \([a-z0-9_]*\)$/\1/p' | tail -1)"
    case "$status" in
        sent|deduped)
            touch "$COOLDOWN_FILE"
            ;;
        *)
            # Deliberately NOT touching the cooldown: an alert that did not go out
            # must not buy silence for the next one. Volume is bounded — send_telegram
            # fires at most a handful of times per job run, and these jobs are daily.
            log "ALERT NOT DELIVERED (status='${status:-<unparseable>}') — cooldown deliberately NOT armed so the next attempt is not pre-silenced"
            ;;
    esac
}

save_state() {
    local status="$1" exit_code="$2" duration="$3" error="${4:-}"
    cat > "$STATE_FILE" << STATEEOF
{"job":"$JOB_NAME","tier":"$TIER","ts":$(date +%s),"status":"$status","exit_code":$exit_code,"duration_s":$duration,"error":"$(echo "$error" | head -c 200 | tr '"' "'" | tr '\n' ' ')","host":"$(hostname)"}
STATEEOF
}

acquire_lock() {
    # macOS: use shlock (PID-based lockfile). Stale detection via PID check.
    if [[ -f "$LOCK_FILE" ]]; then
        local old_pid
        old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
            log "SKIP: lock held by PID $old_pid"
            exit 0
        fi
        # Stale lock — previous process died
        log "Removing stale lock (PID $old_pid dead)"
        rm -f "$LOCK_FILE"
    fi
    echo $$ > "$LOCK_FILE"
}

release_lock() {
    rm -f "$LOCK_FILE"
}

claude_stderr_retryable() {
    local stderr_file="$1"
    grep -qiE \
        'rate.?limit|too many requests|(^|[^0-9/])429([^0-9/]|$)|exhausted|quota|usage limit|weekly limit|hit your limit|capacity|overloaded|authentication (failed|required|expired)|auth required|login required|please (log in|login)|not logged in|not authenticated|invalid[_ ](grant|token)|token[_ ]revoked|refresh_token|unauthori[sz]ed|(^|[^0-9/])401([^0-9/]|$)' \
        "$stderr_file"
}

claude_stdout_retryable() {
    local stdout_file="$1"
    # Optional: the exit code the CLI just returned. When non-zero, stdout is a
    # CLI diagnostic rather than an agent answer — see the anchor note below.
    local exit_code="${2:-}"
    python3 - "$stdout_file" "$exit_code" <<'PY'
import json
import re
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
exit_code = sys.argv[2] if len(sys.argv) > 2 else ""
broad = re.compile(
    r"rate.?limit|too many requests|(?<![\d/])429(?![\d/])|exhausted|quota|"
    r"usage limit|weekly limit|hit your limit|capacity|overloaded|"
    r"authentication (?:failed|required|expired)|auth required|login required|"
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
    r"hit your limit|capacity (?:exceeded|unavailable)|overloaded|"
    r"authentication (?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
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

# The whole-text anchor above judges the SHAPE of the sentence: it only fires
# when the entire output IS one of the phrasings it knows. That strictness is
# deliberate and must stay — an agent that SUCCEEDS and happens to discuss
# "rate limits" in its answer must not rotate the seat.
#
# But it made the cascade decorative against the commonest auth failure there
# is. The CLI prints, on stdout, exit 1:
#     Failed to authenticate. API Error: 401 OAuth access token has been revoked.
# The anchor knows "authentication failed", not "Failed to authenticate", so it
# refused to match and the loop broke at the first seat instead of rotating to
# a live one. Measured 2026-08-07 on Pro: three of four numbered seats revoked,
# the fourth alive, and every agent job died on seat 1 regardless.
#
# So bind the severity to the EXIT CODE, not to the wording. A non-zero exit
# means the CLI itself refused; its stdout is a diagnostic, and any auth/quota
# marker anywhere in it is the entity we care about. Exit 0 keeps the anchor.
if not retryable and exit_code not in ("", "0") and not isinstance(payload, dict):
    retryable = bool(broad.search(text))

raise SystemExit(0 if retryable else 1)
PY
}

claude_retryable_files() {
    local stdout_file="$1"
    local stderr_file="$2"
    local exit_code="${3:-}"
    claude_stderr_retryable "$stderr_file" || claude_stdout_retryable "$stdout_file" "$exit_code"
}

claude_oauth_env() {
    local token="$1"
    local -a env_args=(env)
    local provider_var
    while IFS= read -r provider_var; do
        case "$provider_var" in
            CLAUDE_CODE_OAUTH_TOKEN*|CLAUDE_CODE_USE_*|ANTHROPIC_*|AWS_*|VERTEX_AI_*|\
            OPENAI_*|OPENROUTER_*|GEMINI_*|GOOGLE_API_KEY|\
            GOOGLE_APPLICATION_CREDENTIALS|CLOUD_ML_REGION|DEEPSEEK_*|\
            TOGETHER_*|FIREWORKS_*|MISTRAL_*|COHERE_*|GROQ_*|XAI_*|PERPLEXITY_*)
                env_args+=(-u "$provider_var")
                ;;
        esac
    done < <(compgen -e)
    if [[ -n "$token" ]]; then
        env_args+=("CLAUDE_CODE_OAUTH_TOKEN=$token")
    fi
    printf '%s\0' "${env_args[@]}"
}

# ── PATH setup ────────────────────────────────────────────────────────────────
export PATH="/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/Users/nuzantara/.local/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="${CRON_AGENT_HOME:-/Users/nuzantara}"

# sonnet-5 --print + background tasks (W89 class-audit, 2026-07-11): the CLI kills
# backgrounded work after the print-mode ceiling; 30min keeps a legitimate long agent
# run alive across every job that dispatches through the agent tier below.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

# ── Lock ──────────────────────────────────────────────────────────────────────
acquire_lock
trap 'release_lock' EXIT

# ── Tier: exec ────────────────────────────────────────────────────────────────

run_exec() {
    local script="$SCRIPT_OR_PROMPT"
    if [[ ! -f "$script" ]]; then
        # Try expanding ~
        script="${script/#\~/$HOME}"
    fi
    if [[ ! -f "$script" ]]; then
        log "ERROR: script not found: $SCRIPT_OR_PROMPT"
        save_state "error" 127 0 "script not found: $SCRIPT_OR_PROMPT"
        send_telegram "❌ <b>$JOB_NAME</b>: script not found: $SCRIPT_OR_PROMPT"
        exit 127
    fi

    log "START tier=exec script=$script"
    local start_ts=$(date +%s)

    if [[ "${CRON_AGENT_DRY_RUN:-}" == "1" ]]; then
        echo "[DRY RUN] Would execute: bash $script $*"
        log "DRY RUN: bash $script $*"
        save_state "dry_run" 0 0
        return 0
    fi

    local output exit_code
    output=$(timeout "$TIMEOUT" bash "$script" "$@" 2>&1) || exit_code=$?
    exit_code=${exit_code:-0}
    local duration=$(( $(date +%s) - start_ts ))

    # Log output (last 50 lines)
    echo "$output" | tail -50 >> "$LOG_FILE"

    if [[ $exit_code -eq 0 ]]; then
        log "OK duration=${duration}s"
        save_state "ok" 0 "$duration"
    elif [[ $exit_code -eq 124 ]]; then
        log "TIMEOUT after ${TIMEOUT}s"
        save_state "timeout" 124 "$duration" "timeout after ${TIMEOUT}s"
        send_telegram "⏰ <b>$JOB_NAME</b> timeout after ${TIMEOUT}s"
    else
        local err_tail
        err_tail=$(echo "$output" | tail -3 | tr '\n' ' ' | head -c 200)
        log "FAILED exit=$exit_code err=$err_tail"
        save_state "error" "$exit_code" "$duration" "$err_tail"
        send_telegram "❌ <b>$JOB_NAME</b> failed (exit $exit_code)
${err_tail}"
    fi
    return $exit_code
}

# ── Tier: agent ───────────────────────────────────────────────────────────────

run_agent() {
    local prompt_file="$SCRIPT_OR_PROMPT"
    if [[ ! -f "$prompt_file" ]]; then
        prompt_file="${prompt_file/#\~/$HOME}"
    fi
    if [[ ! -f "$prompt_file" ]]; then
        log "ERROR: prompt file not found: $SCRIPT_OR_PROMPT"
        save_state "error" 127 0 "prompt file not found: $SCRIPT_OR_PROMPT"
        send_telegram "❌ <b>$JOB_NAME</b>: prompt file not found: $SCRIPT_OR_PROMPT"
        exit 127
    fi

    local prompt
    prompt=$(cat "$prompt_file")
    # W89 class-audit (2026-07-11): tell the model inline never to background this run —
    # a backgrounded task is killed at the print-mode ceiling, leaving no output at all.
    prompt="${prompt}

Do ALL the work inline in this turn — never spawn a background task or background agent
for this; this is a one-shot print-mode run and backgrounded work is terminated at exit,
leaving no output (W89 class-audit, regulatory-watcher incident 2026-07-05)."

    log "START tier=agent prompt_file=$prompt_file prompt_len=${#prompt}"
    local start_ts=$(date +%s)

    if [[ "${CRON_AGENT_DRY_RUN:-}" == "1" ]]; then
        echo "[DRY RUN] Would run claude -p with prompt from $prompt_file (${#prompt} chars)"
        log "DRY RUN: claude -p (${#prompt} chars)"
        save_state "dry_run" 0 0
        return 0
    fi

    # ── No-op suppression (P2) ────────────────────────────────────────────────
    # The cheapest agent turn is the one that never runs. A job whose INPUT has
    # not changed since its last successful run re-derives the same answer at
    # full context price. Opt-in per job, because only the job knows what its
    # input is: set CRON_AGENT_SKIP_IF_UNCHANGED to a shell command whose STDOUT
    # is a cheap fingerprint of that input (a `git rev-parse HEAD`, a row count,
    # an `ls -la | sha256`). Unchanged fingerprint => skip the LLM, exit 0.
    #
    # Deliberately opt-in and deliberately NOT hashing the prompt file: a prompt
    # that never changes is the norm, so keying on it would silence every job
    # after its first run. Fail-open by construction — if the fingerprint command
    # errors or prints nothing we run the agent, because "I could not measure the
    # input" must never be read as "the input is unchanged" (W106b: cannot-verify
    # is not a verdict).
    #
    # Source of the fingerprint command: an explicit CRON_AGENT_SKIP_IF_UNCHANGED
    # env var wins when set (per-invocation override, e.g. for manual testing).
    # Otherwise fall back to FINGERPRINT_MAP, a repo-tracked job->command table —
    # this is what lets a job get armed by merging a PR, with zero crontab edits
    # (16 HOME-fork crontab lines would otherwise all need the env var pasted in).
    # Missing map file, missing jq, malformed JSON, or no entry for this job all
    # resolve to "no fingerprint configured" — same as today, never a skip.
    local skip_cmd="${CRON_AGENT_SKIP_IF_UNCHANGED:-}"
    if [[ -z "$skip_cmd" && -f "$FINGERPRINT_MAP" ]] && command -v jq >/dev/null 2>&1; then
        skip_cmd="$(jq -r --arg job "$JOB_NAME" '.[$job] // empty' "$FINGERPRINT_MAP" 2>/dev/null)"
        [[ -n "$skip_cmd" ]] && log "no-op check: using repo-mapped fingerprint for $JOB_NAME"
    fi
    if [[ -n "$skip_cmd" ]]; then
        local fp_file="$STATE_DIR/${JOB_NAME}.input-fingerprint"
        local fp_now fp_rc
        fp_now="$(eval "$skip_cmd" 2>/dev/null)"; fp_rc=$?
        if [[ $fp_rc -ne 0 || -z "$fp_now" ]]; then
            log "no-op check: fingerprint command failed (rc=$fp_rc) or empty — running the agent (fail-open)"
        else
            fp_now="$(printf '%s' "$fp_now" | shasum | awk '{print $1}')"
            if [[ -f "$fp_file" && "$(cat "$fp_file" 2>/dev/null)" == "$fp_now" ]]; then
                log "SKIP: input fingerprint unchanged ($fp_now) — agent not invoked"
                echo "[no-op] input unchanged since last run; agent skipped"
                save_state "noop" 0 0
                return 0
            fi
            # Store AFTER the run succeeds, not here: a crash mid-run must not
            # convince the next tick that the work was already done.
            NOOP_FINGERPRINT_FILE="$fp_file"
            NOOP_FINGERPRINT_VALUE="$fp_now"
        fi
    fi

    # Five MAX seats, then the Team seat (6, weekly-capped, last-resort by
    # position — never reorder this ahead of 1-5), then legacy and keychain.
    local tokens=()
    local labels=()
    for i in 1 2 3 4 5 6; do
        local var_name="CLAUDE_CODE_OAUTH_TOKEN_${i}"
        local tok="${!var_name:-}"
        local is_dup=0
        local existing
        for existing in "${tokens[@]:-}"; do
            [[ "$existing" == "$tok" ]] && is_dup=1
        done
        if [[ -n "$tok" && $is_dup -eq 0 ]]; then
            tokens+=("$tok")
            labels+=("token_$i")
        fi
    done
    # Legacy fallback
    if [[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
        local is_dup=0
        for t in "${tokens[@]:-}"; do
            [[ "$t" == "$CLAUDE_CODE_OAUTH_TOKEN" ]] && is_dup=1
        done
        if [[ $is_dup -eq 0 ]]; then
            tokens+=("$CLAUDE_CODE_OAUTH_TOKEN")
            labels+=("token_legacy")
        fi
    fi
    # Keychain fallback (no token = use system keychain)
    tokens+=("")
    labels+=("keychain")

    local output="" exit_code=1 accepted_success=0
    local tried=()
    local deadline=$(( start_ts + TIMEOUT ))
    local attempt_out attempt_err

    for idx in "${!tokens[@]}"; do
        local token="${tokens[$idx]}"
        local label="${labels[$idx]}"
        log "Trying $label..."
        tried+=("$label")
        local remaining=$(( deadline - $(date +%s) ))
        if [[ $remaining -le 0 ]]; then
            exit_code=124
            break
        fi
        local attempts_left=$(( ${#tokens[@]} - idx ))
        local attempt_timeout=$(( remaining / attempts_left ))
        # Equal division assumes every attempt consumes its slice. A cascade is
        # the opposite: a DEAD seat is refused in seconds and costs nothing,
        # while the ONE seat that works needs real time. So an equal split
        # starves the only attempt that was ever going to succeed — and it gets
        # worse the healthier the fleet is. Measured on Pro 2026-08-07, right
        # after all four seats were re-issued: 600s / 5 entries = 120s each,
        # and `indexing-daily` (a job that takes 118s) passed with two seconds
        # to spare while `weekly-dep-audit` was killed on all five in turn —
        # five healthy seats, five timeouts, no work done. The wrapper already
        # grants a legitimate long agent run 30 minutes of background ceiling
        # (see CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS below); a 120s slice
        # contradicts that by 15x.
        #
        # So: floor every attempt at a real working slice. Fast-failing seats
        # never reach the floor (they are refused long before it), so rotation
        # keeps its full depth; only a seat that is genuinely working gets the
        # time. The global deadline is still the hard backstop — the cap on the
        # next line means the floor can never overrun it.
        [[ $attempt_timeout -lt $MIN_ATTEMPT_SECONDS ]] && attempt_timeout=$MIN_ATTEMPT_SECONDS
        [[ $attempt_timeout -gt $remaining ]] && attempt_timeout=$remaining
        [[ $attempt_timeout -lt 1 ]] && attempt_timeout=1

        local env_args=()
        while IFS= read -r -d '' env_part; do
            env_args+=("$env_part")
        done < <(claude_oauth_env "$token")
        attempt_out="$(mktemp "${TMPDIR:-/tmp}/cron-agent-out.XXXXXX")"
        attempt_err="$(mktemp "${TMPDIR:-/tmp}/cron-agent-err.XXXXXX")"

        # --permission-mode bypassPermissions: no approval waits.
        # Note: --bare is incompatible with OAuth tokens (requires ANTHROPIC_API_KEY).
        # --model haiku: Routing A (2026-04-22) — cron automatici usano Haiku,
        # libera quota Opus per sessioni interattive. Override via CLAUDE_CRON_MODEL env var.
        # Data-driven decision: cron = 82% sessions but 0.6% output value (empirical analysis 2026-04-22).
        local cron_model="${CLAUDE_CRON_MODEL:-claude-haiku-4-5-20251001}"
        local claude_bin="${CRON_AGENT_CLAUDE_BIN:-claude}"
        local timeout_bin="${CRON_AGENT_TIMEOUT_BIN:-timeout}"

        # ── Context diet (P1, measured on M5 2026-08-12) ──────────────────────
        # A cron turn is a one-shot prompt, but it was paying the FULL interactive
        # boot context on every invocation: measured 55,881-91,679 tokens of
        # context for a task whose prompt is a few hundred. Two flags cut what a
        # cron can never use, and neither changes what the model is asked to do:
        #
        #   --disable-slash-commands  drops the skill descriptions. Measured
        #       -11,087 tokens (55,881 -> 44,794) and again -11,038 in a second
        #       run. Innocence checked before enabling: all 12 cron prompt files
        #       on Pro were scanned for skill invocations — the only `/token`
        #       hits are FILE PATHS (/tmp/..., /Users/...), zero real skills.
        #   --exclude-dynamic-system-prompt-sections  moves cwd/env/memory-paths/
        #       git-status OUT of the cached prefix. Small on its own (~300), but
        #       those are exactly the per-run-varying bytes that break prefix
        #       identity — the measured baseline swung 55,881 vs 91,679 between
        #       two identical runs, which is cache thrashing, not real work.
        #
        # NOT used: --bare. It skips credential resolution, so with an OAuth seat
        # it returns "Not logged in" and 0 tokens — a zero that means the request
        # never ran (the pre-existing comment above says the same).
        # Kill switch: CRON_AGENT_CONTEXT_DIET=0 restores the old invocation.
        local diet_args=()
        if [[ "${CRON_AGENT_CONTEXT_DIET:-1}" != "0" ]]; then
            diet_args+=(--disable-slash-commands --exclude-dynamic-system-prompt-sections)
        fi

        "${env_args[@]}" "$timeout_bin" "$attempt_timeout" "$claude_bin" -p --model "$cron_model" \
            --permission-mode bypassPermissions \
            ${diet_args[@]+"${diet_args[@]}"} \
            --max-budget-usd "${CLAUDE_CRON_MAX_BUDGET_USD:-5}" "$prompt" \
            >"$attempt_out" 2>"$attempt_err" && exit_code=0 || exit_code=$?
        output="$(cat "$attempt_out")"

        # A timeout is account-local until the shared deadline is exhausted.
        # Rotate immediately; the next loop iteration recomputes the remaining
        # global budget and records a final 124 only when no time remains.
        if [[ $exit_code -eq 124 ]]; then
            log "$label: timed out, trying next account within global budget"
            output=""
            rm -f "$attempt_out" "$attempt_err"
            continue
        fi

        # OAuth quota/auth diagnostics can exit 0: classify before success.
        if claude_retryable_files "$attempt_out" "$attempt_err" "$exit_code"; then
            log "$label: OAuth account unavailable, trying next"
            output=""
            rm -f "$attempt_out" "$attempt_err"
            continue
        fi

        # Check if token is silently exhausted (empty output, any exit code).
        # Claude CLI with exhausted Max-plan token returns empty output with exit 0 or 143.
        # Real errors have messages; real success has non-empty output.
        local output_trimmed="${output//[[:space:]]/}"
        if [[ -z "$output_trimmed" ]]; then
            log "$label: empty output (likely quota/rate issue), trying next"
            rm -f "$attempt_out" "$attempt_err"
            continue
        fi

        if [[ $exit_code -eq 0 ]]; then
            accepted_success=1
        fi
        rm -f "$attempt_out" "$attempt_err"
        # Success or non-retryable error output — stop trying.
        break
    done

    # Every attempted account may return an exit-0 retry diagnostic. Never
    # convert that exhausted chain into a blank successful cron run.
    if [[ $accepted_success -ne 1 && $exit_code -eq 0 ]]; then
        exit_code=1
    fi

    local duration=$(( $(date +%s) - start_ts ))

    # Log output (last 80 lines)
    echo "$output" | tail -80 >> "$LOG_FILE"

    if [[ $accepted_success -eq 1 && $exit_code -eq 0 ]]; then
        log "OK duration=${duration}s label=${labels[$idx]}"
        # Explicit tier-provenance line (W89 class-audit, 2026-07-11): which of the
        # numbered/legacy/keychain fallback slots actually answered.
        log "[cron-agent] used: tier2-claude-${labels[$idx]} (exit=0)"
        save_state "ok" 0 "$duration"
        # P2: persist the input fingerprint ONLY on a real success, so the next
        # tick can skip. Written here and nowhere else — a crashed or refused run
        # must leave the previous fingerprint (or none) in place, or the job would
        # skip work it never actually did.
        if [[ -n "${NOOP_FINGERPRINT_FILE:-}" && -n "${NOOP_FINGERPRINT_VALUE:-}" ]]; then
            printf '%s' "$NOOP_FINGERPRINT_VALUE" > "$NOOP_FINGERPRINT_FILE"
            log "no-op check: fingerprint stored ($NOOP_FINGERPRINT_VALUE)"
        fi
    elif [[ $exit_code -eq 124 ]]; then
        # M4 (2026-07-20): report the slots ACTUALLY tried — the loop can break
        # before exhausting all fallbacks, and "all 3 tokens tried" was false
        # (observed: timeout on token_1 only, message claimed 3).
        local tried_csv
        tried_csv=$(IFS=,; echo "${tried[*]}")
        log "TIMEOUT after ${TIMEOUT}s on: $tried_csv"
        save_state "timeout" 124 "$duration" "timeout after: $tried_csv"
        send_telegram "⏰ <b>$JOB_NAME</b> agent timeout dopo ${TIMEOUT}s (provati: $tried_csv)"
    else
        local err_tail
        err_tail=$(echo "$output" | tail -3 | tr '\n' ' ' | head -c 200)
        log "FAILED exit=$exit_code label=${labels[$idx]:-?} err=$err_tail"
        save_state "error" "$exit_code" "$duration" "$err_tail"
        send_telegram "❌ <b>$JOB_NAME</b> agent failed (exit $exit_code, last token: ${labels[$idx]:-?})
${err_tail}"
    fi
    return $exit_code
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "$TIER" in
    exec)  run_exec "$@" ;;
    agent) run_agent ;;
    *)     echo "Unknown tier: $TIER"; exit 1 ;;
esac
