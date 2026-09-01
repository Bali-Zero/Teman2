#!/bin/zsh
# claude-cascade.sh — single entry point for autonomous Claude invocations with full fallback cascade.
#
# Tries CLI binaries in this order, falling back on quota/auth/empty/timeout:
#   1. Explicit Claude OAuth seats: token_1, token_2, token_3, token_4, token_5
#      (5 MAX seats, in order), token_6 (zero@ Team, last resort by position),
#      legacy token, then macOS keychain
#   2. agy -p (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
#   3. Kimi Code K3
#   4. codex exec --sandbox read-only (ChatGPT Pro)
#   5. ollama run qwen3.5:9b (Pro/Mini local safety net)
#   6. fm respond (Apple on-device Foundation Model, macOS 27+ — zero-daemon
#      last resort for machines where no Ollama server is running; ~3B quality,
#      grunt shapes only. Benchmarked 2026-08-19: 12/15 vs qwen3.5:9b 14/15 on
#      triage/classify/extract. Kill switch: CLAUDE_CASCADE_FM=0)
#
# Usage:
#   claude-cascade.sh "<prompt text>" [--model MODEL] [--agent AGENT_NAME]
#   claude-cascade.sh "<prompt text>" --claude-only [--model MODEL]
#   echo "prompt" | claude-cascade.sh --stdin [--agent AGENT_NAME]
#
# --claude-only tries every Claude OAuth seat, then exits without crossing the
# provider boundary to Gemini/Kimi/Codex/Ollama. This is load-bearing for jobs
# that require Claude-specific agents, tool permissions, or output contracts.
#
# Output: stdout = LLM response. Stderr = which tier was used + which tiers were skipped.
# Exit codes: 0 = success on any tier. 1 = ALL tiers failed. 2 = bad usage.
#
# Quota-exhaust detection patterns (case-insensitive grep):
#   "out of extra usage", "usage limit", "quota exceeded", "rate.limit", "429", "exhausted"
#
# W89 class-audit fix (2026-07-11, PENDING-ARMS ledger ~68): sonnet-5 in --print mode can
# silently spawn its work as a BACKGROUND task; the CLI kills it at the print-mode ceiling
# and exits 0 with no output on stdout — the caller sees "success" with nothing to show for
# it (incident: regulatory-watcher-run.sh 2026-07-05). Every Claude-tier attempt through
# this cascade shares the same fix: raise the background ceiling so legitimate long work
# survives, and callers must additionally tell the model inline never to background (this
# script cannot inject that into an arbitrary caller-supplied $PROMPT — see each wrapper
# that calls this cascade for its own anti-background sentence).

set -uo pipefail

# Every temporary path and watchdog process is owned by this invocation. The
# EXIT trap is deliberately installed before secrets or prompts are loaded so
# an interrupt cannot strand credential-bearing subprocesses or temp output.
typeset -a CASCADE_TEMP_FILES
CASCADE_TEMP_FILES=()
ACTIVE_CHILD_PID=""
ACTIVE_WATCHER_PID=""
ACTIVE_GROUP_PID=""

terminate_attempt_group() {
    local group_pid="${1:-}"
    local grace_sec="${2:-1}"
    [ -z "$group_pid" ] && return 0

    kill -TERM -- -"$group_pid" 2>/dev/null || true
    sleep "$grace_sec"
    kill -KILL -- -"$group_pid" 2>/dev/null || true
}

cleanup_cascade() {
    if [ -n "${ACTIVE_WATCHER_PID:-}" ]; then
        kill "$ACTIVE_WATCHER_PID" 2>/dev/null || true
        wait "$ACTIVE_WATCHER_PID" 2>/dev/null || true
    fi
    if [ -n "${ACTIVE_GROUP_PID:-}" ]; then
        terminate_attempt_group "$ACTIVE_GROUP_PID" 1
    fi
    if [ -n "${ACTIVE_CHILD_PID:-}" ]; then
        wait "$ACTIVE_CHILD_PID" 2>/dev/null || true
    fi
    local temp_path
    for temp_path in "${CASCADE_TEMP_FILES[@]}"; do
        [ -n "$temp_path" ] && rm -f -- "$temp_path" 2>/dev/null || true
    done
}

trap cleanup_cascade EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

new_temp_file() {
    REPLY="$(mktemp)"
    CASCADE_TEMP_FILES+=("$REPLY")
}

# Anthropic paid API, Bedrock, and Vertex credentials must never reach a Claude
# OAuth child. Patterns are scrubbed after sourcing the runtime secrets file,
# not merely before it.
scrub_non_oauth_provider_credentials() {
    local name
    for name in ${(k)parameters}; do
        case "$name" in
            ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_BASE_URL|\
            ANTHROPIC_BEDROCK_*|ANTHROPIC_VERTEX_*|ANTHROPIC_FOUNDRY_*|\
            AWS_*|VERTEX_AI_*|GOOGLE_APPLICATION_CREDENTIALS|\
            GOOGLE_CLOUD_*|CLOUD_ML_*|CLAUDE_CODE_USE_BEDROCK|\
            CLAUDE_CODE_USE_VERTEX|CLAUDE_CODE_USE_FOUNDRY)
                unset "$name" 2>/dev/null || true
                ;;
        esac
    done
}

# Source secrets so spawned agents have DEEPSEEK_API_KEY, TELEGRAM_*, etc.
# This is the canonical location of all autonomous-runtime secrets.
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null
    set +a
fi
scrub_non_oauth_provider_credentials

# W89 class-audit (2026-07-11): 30min ceiling — same value as regulatory-watcher-run.sh's
# own fix, applied here once so every caller of this cascade (competitor-monitor,
# yield-optimizer, and any future claude-cascade.sh consumer) inherits it uniformly.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

PROMPT=""
MODEL=""
AGENT=""
USE_STDIN=0
CLAUDE_ONLY=0
CLAUDE_CLI_COMPAT="${CLAUDE_CASCADE_CLI_COMPAT:-0}"
EXTRA_ARGS=()

CASCADE_ATTEMPT_TIMEOUT_SEC="${CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC:-900}"
CASCADE_DEADLINE_SEC="${CLAUDE_CASCADE_DEADLINE_SEC:-3600}"
case "$CASCADE_ATTEMPT_TIMEOUT_SEC" in
    ''|*[!0-9]*) echo "invalid CLAUDE_CASCADE_ATTEMPT_TIMEOUT_SEC" >&2; exit 2 ;;
esac
case "$CASCADE_DEADLINE_SEC" in
    ''|*[!0-9]*) echo "invalid CLAUDE_CASCADE_DEADLINE_SEC" >&2; exit 2 ;;
esac
[ "$CASCADE_ATTEMPT_TIMEOUT_SEC" -gt 0 ] || { echo "attempt timeout must be >0" >&2; exit 2; }
[ "$CASCADE_DEADLINE_SEC" -gt 0 ] || { echo "deadline must be >0" >&2; exit 2; }
CASCADE_DEADLINE_AT=$(( $(date +%s) + CASCADE_DEADLINE_SEC ))

[ "${CLAUDE_CASCADE_MODE:-}" = "claude-only" ] && CLAUDE_ONLY=1

# parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --agent) AGENT="$2"; shift 2 ;;
        --claude-only) CLAUDE_ONLY=1; shift ;;
        --stdin) USE_STDIN=1; shift ;;
        -p|--print)
            if [ "$CLAUDE_CLI_COMPAT" = "1" ] && [ $# -gt 1 ]; then
                PROMPT="$2"
                shift 2
            else
                EXTRA_ARGS+=("$1")
                shift
            fi
            ;;
        --) shift; EXTRA_ARGS+=("$@"); break ;;
        -*) EXTRA_ARGS+=("$1"); shift ;;
        *) PROMPT="$1"; shift ;;
    esac
done

if [ "$USE_STDIN" -eq 1 ]; then
    PROMPT="$(cat)"
fi

if [ -z "$PROMPT" ]; then
    echo "usage: $0 \"<prompt>\" [--model M] [--agent A] [--claude-only]" >&2
    exit 2
fi

QUOTA_PATTERN="out of extra usage|usage limit|weekly limit|quota exceeded|rate.limit|429|exhausted|please try again later"
AUTH_PATTERN="authentication required|authentication[_ ]error|not logged in|please (log in|run /login)|unauthorized|invalid (api key|(oauth )?token)|oauth token.*(expired|invalid|revoked)|api[[:space:]]+error[[:space:]:_-]+401|http[[:space:]:_-]+401|http[[:space:]]+(error|status)[[:space:]:_-]+401|error[[:space:]:_-]+401|request failed[^[:digit:]/]{0,20}401|status([[:space:]]+code)?[[:space:]:=_-]+401|401[[:space:]:_-]+(unauthorized|authentication|invalid)|token_revoked|refresh_token(_reused)?"
RETRYABLE_PATTERN="$QUOTA_PATTERN|$AUTH_PATTERN"
RAW_RETRYABLE_PATTERN="out of extra usage|usage limit( reached)?|weekly limit( reached)?|quota exceeded|rate[._ ]?limit( reached)?|429([[:space:]:_-]+(too many requests|quota exceeded))?|exhausted|please try again later|authentication required|authentication[_ ]error|not logged in|please (log in|run /login)|401[[:space:]:_-]+(unauthorized|authentication required|invalid (api key|token))|http[[:space:]]+401([[:space:]:_-]+(unauthorized|authentication|invalid))?|token_revoked|refresh_token(_reused)?|invalid (api key|(oauth )?token)|oauth token (expired|invalid|revoked)"
CLI_LOGIN_BANNER_PATTERN="(not logged in|invalid api key)[[:space:]]*[^[:alnum:][:space:]]+[[:space:]]*(please (log in|run /login)|run /login)[[:space:][:punct:]]*"
RESET_TIME_PATTERN="[0-9]{1,2}(:[0-9]{2})?(am|pm)"
RESET_ZONE_PATTERN="([[:space:]]+\([[:alnum:]_+.-]+/[[:alnum:]_+.-]+\))?"
RESET_HINT_PATTERN="soon|at[[:space:]]+$RESET_TIME_PATTERN$RESET_ZONE_PATTERN|in[[:space:]]+[0-9]+[[:space:]]+(minutes?|hours?|days?)|on[[:space:]]+[[:alpha:]]{3,9}[[:space:]]+[0-9]{1,2}(,[[:space:]]+[0-9]{4})?|$RESET_TIME_PATTERN$RESET_ZONE_PATTERN|[[:alpha:]]{3}[[:space:]]+[0-9]{1,2}[[:space:]]+at[[:space:]]+$RESET_TIME_PATTERN$RESET_ZONE_PATTERN"
CLI_USAGE_BANNER_PATTERN="((you('re| are| have)[[:space:]]+)?out of extra usage[[:space:]]*[^[:alnum:][:space:]]+[[:space:]]*(your[[:space:]]+)?(usage|limit)[[:space:]]+(will[[:space:]]+)?(reset|renew|be available)([[:space:]]+($RESET_HINT_PATTERN))?[[:space:][:punct:]]*|you('ve| have)[[:space:]]+hit your[[:space:]]+(session[[:space:]]+|weekly[[:space:]]+)?limit[[:space:]]*[^[:alnum:][:space:]]+[[:space:]]*resets?[[:space:]]+($RESET_HINT_PATTERN)[[:space:][:punct:]]*)"

new_temp_file
PROMPT_FILE="$REPLY"
printf '%s' "$PROMPT" >"$PROMPT_FILE"

stdout_is_retryable_envelope() {
    local output_file="$1"
    local pattern="$2"
    local compact
    [ -s "$output_file" ] || return 1
    [ "$(wc -c <"$output_file" | tr -d ' ')" -le 8192 ] || return 1

    compact="$(tr '\n\r\t' '   ' <"$output_file" | tr -s ' ')"
    # A successful answer may discuss "401", quota, or token failures. Only
    # classify stdout when the entire payload is a known diagnostic shape:
    # a raw diagnostic beginning with the failure, an explicitly framed error,
    # or a JSON error envelope.
    if printf '%s\n' "$compact" | grep -qiE \
        "^[[:space:]]*($RAW_RETRYABLE_PATTERN)[[:space:].!]*$"; then
        return 0
    fi
    # Known Claude CLI banners append a structured login/reset hint. Require
    # that hint instead of matching any answer that merely starts with the same
    # words; keep normal operator-guide and weekly-limit prose valid.
    if printf '%s\n' "$compact" | grep -qiE \
        "^[[:space:]]*($CLI_LOGIN_BANNER_PATTERN|$CLI_USAGE_BANNER_PATTERN)[[:space:]]*$"; then
        return 0
    fi
    if printf '%s\n' "$compact" | grep -qiE \
        '^[[:space:]]*(error|fatal|authentication error|authorization error|quota error|api error|http error|request failed|status)[[:space:]:_-]+' \
        && printf '%s\n' "$compact" | grep -qiE "$pattern"; then
        return 0
    fi
    if printf '%s\n' "$compact" | grep -qiE \
        '^[[:space:]]*\{.*"(error|errors)"[[:space:]]*:' \
        && printf '%s\n' "$compact" | grep -qiE "$pattern" \
        && printf '%s\n' "$compact" | grep -qE '\}[[:space:]]*$'; then
        return 0
    fi
    return 1
}

retryable_failure_detected() {
    local output_file="$1"
    local error_file="$2"
    local exit_code="$3"
    local extra_pattern="${4:-}"
    local pattern="$RETRYABLE_PATTERN"
    [ -n "$extra_pattern" ] && pattern="$pattern|$extra_pattern"

    # stderr is a diagnostic channel, so a matching failure is authoritative.
    grep -qiE "$pattern" "$error_file" && return 0
    # stdout is user content on success. It is retryable only when the whole
    # exit-zero payload is a recognized error envelope.
    [ "$exit_code" -eq 0 ] \
        && stdout_is_retryable_envelope "$output_file" "$pattern"
}

# Every cloud provider in this cascade uses subscription OAuth/config auth.
# Never let an ambient metered API credential choose a different billing path,
# and never expose one provider's credential to another provider's process.
typeset -a ISOLATED_PROVIDER_ENV
build_isolated_provider_env() {
    local name
    ISOLATED_PROVIDER_ENV=(env)
    for name in ${(k)parameters}; do
        case "$name" in
            CLAUDE_CODE_OAUTH_TOKEN|CLAUDE_CODE_OAUTH_TOKEN_*|\
            ANTHROPIC_*|\
            AWS_*|VERTEX_AI_*|GOOGLE_APPLICATION_CREDENTIALS|GOOGLE_CLOUD_*|\
            CLOUD_ML_*|CLAUDE_CODE_USE_BEDROCK|CLAUDE_CODE_USE_VERTEX|\
            CLAUDE_CODE_USE_FOUNDRY|OPENAI_*|OPENROUTER_*|GEMINI_*|\
            GOOGLE_API_KEY|GOOGLE_OAUTH_*|DEEPSEEK_*|TOGETHER_*|\
            FIREWORKS_*|MISTRAL_*|COHERE_*|GROQ_*|XAI_*|PERPLEXITY_*|\
            KIMI_*|MOONSHOT_*)
                ISOLATED_PROVIDER_ENV+=(-u "$name")
                ;;
        esac
    done
}

# Run one provider attempt under both a per-attempt timeout and a global
# cascade deadline. macOS has no guaranteed timeout(1), so a local watchdog
# owns a dedicated process group (PGID == child PID). TERM/grace/KILL always
# targets the whole group, so a provider grandchild cannot survive a timeout.
# Timeout is retryable; a spent global deadline fails later attempts at once.
run_bounded() {
    local tmpout="$1"
    local tmperr="$2"
    local label="$3"
    shift 3

    local now remaining allowed timeout_marker exit_code child_pid python_bin
    now="$(date +%s)"
    remaining=$(( CASCADE_DEADLINE_AT - now ))
    if [ "$remaining" -le 0 ]; then
        echo "global deadline exhausted before $label" >"$tmperr"
        return 124
    fi
    allowed="$CASCADE_ATTEMPT_TIMEOUT_SEC"
    [ "$remaining" -lt "$allowed" ] && allowed="$remaining"

    timeout_marker="${tmpout}.timeout"
    CASCADE_TEMP_FILES+=("$timeout_marker")
    rm -f -- "$timeout_marker"

    python_bin="$(command -v python3 2>/dev/null || true)"
    if [ -z "$python_bin" ]; then
        echo "python3 is required to isolate provider process groups" >"$tmperr"
        return 127
    fi
    "$python_bin" -c \
        'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
        "$@" <"$PROMPT_FILE" >"$tmpout" 2>"$tmperr" &
    ACTIVE_CHILD_PID=$!
    child_pid="$ACTIVE_CHILD_PID"
    ACTIVE_GROUP_PID="$child_pid"
    # Keep the watchdog single-process. A background shell running a sleep
    # subprocess leaves it reparented to PID 1 when the shell is cancelled after a
    # fast provider success. Python sleeps in-process, so kill+wait below reaps
    # the complete watchdog while the provider remains isolated in its own
    # session/process group.
    "$python_bin" -c \
        'import os, signal, sys, time
group_pid = int(sys.argv[1])
time.sleep(float(sys.argv[2]))
try:
    os.killpg(group_pid, 0)
except ProcessLookupError:
    raise SystemExit(0)
open(sys.argv[3], "a", encoding="utf-8").close()
try:
    os.killpg(group_pid, signal.SIGTERM)
except ProcessLookupError:
    raise SystemExit(0)
time.sleep(1)
try:
    os.killpg(group_pid, signal.SIGKILL)
except ProcessLookupError:
    pass' \
        "$child_pid" "$allowed" "$timeout_marker" \
        </dev/null >/dev/null 2>&1 &
    ACTIVE_WATCHER_PID=$!

    wait "$ACTIVE_CHILD_PID"
    exit_code=$?
    kill "$ACTIVE_WATCHER_PID" 2>/dev/null || true
    wait "$ACTIVE_WATCHER_PID" 2>/dev/null || true
    # A provider that returned should not leave detached work behind.
    kill -KILL -- -"$child_pid" 2>/dev/null || true
    ACTIVE_CHILD_PID=""
    ACTIVE_WATCHER_PID=""
    ACTIVE_GROUP_PID=""

    if [ -e "$timeout_marker" ]; then
        echo "attempt timed out after ${allowed}s" >"$tmperr"
        return 124
    fi
    return "$exit_code"
}

# build claude args (model + agent + extras)
typeset -a CLAUDE_ARGS
build_claude_args() {
    CLAUDE_ARGS=("--print")
    [ -n "$MODEL" ] && CLAUDE_ARGS+=("--model" "$MODEL")
    [ -n "$AGENT" ] && CLAUDE_ARGS+=("--agent" "$AGENT")
    CLAUDE_ARGS+=("${EXTRA_ARGS[@]}")
}

try_claude() {
    local bin="$1"
    local label="$2"
    local oauth_token="${3:-}"
    local config_dir="${4:-}"
    [ ! -x "$bin" ] && { echo "  [skip] $label not installed at $bin" >&2; return 99; }

    # L09-PR1: consult the seat-state ledger before spending a dispatch on a
    # seat already known to be quota-exhausted. Kill switch: SEAT_STATE_PRECHECK=0.
    # 98 is the wrapper's existing "retryable quota failure" code, so the caller
    # advances to the next seat exactly as it would after a live quota rejection.
    if [ "${SEAT_STATE_PRECHECK:-1}" != "0" ] && seat_state_precheck_skip "$label"; then
        echo "  [skip] $label — seat ledger reports this seat exhausted (no dispatch spent)" >&2
        return 98
    fi

    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    build_claude_args
    build_isolated_provider_env

    echo "  [try] $label ($bin)" >&2
    if [ -n "$oauth_token" ]; then
        run_bounded "$tmpout" "$tmperr" "$label" "${ISOLATED_PROVIDER_ENV[@]}" \
            CLAUDE_CONFIG_DIR="$config_dir" \
            CLAUDE_CODE_OAUTH_TOKEN="$oauth_token" \
            "$bin" "${CLAUDE_ARGS[@]}"
        exit_code=$?
    else
        run_bounded "$tmpout" "$tmperr" "$label" "${ISOLATED_PROVIDER_ENV[@]}" \
            CLAUDE_CONFIG_DIR="$config_dir" \
            "$bin" "${CLAUDE_ARGS[@]}"
        exit_code=$?
    fi

    # Some Claude CLI auth/quota failures incorrectly return exit 0. Content
    # classification therefore precedes the exit-code success check.
    if retryable_failure_detected "$tmpout" "$tmperr" "$exit_code"; then
        echo "  [retry] $label quota/auth failure" >&2
        rm -f "$tmpout" "$tmperr"
        return 98
    fi
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] $label exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] $label returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi

    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: $label" >&2
    return 0
}

try_gemini() {
    local agy_bin="$HOME/.local/bin/agy"
    local gemini_bin="/opt/homebrew/bin/gemini"
    local bin=""
    local label=""
    if [ -x "$agy_bin" ]; then
        bin="$agy_bin"
        label="agy (Gemini 3.1 Pro)"
    elif [ -x "$gemini_bin" ]; then
        bin="$gemini_bin"
        label="legacy gemini-3.1-pro-preview"
    else
        echo "  [skip] neither agy nor gemini installed" >&2
        return 99
    fi
    if [ -n "$AGENT" ]; then
        echo "  [skip] Gemini $label — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    echo "  [try] Gemini $label" >&2
    build_isolated_provider_env
    if [ "$bin" = "$agy_bin" ]; then
        # `-p`/`--print` TAKES A VALUE (measured live 2026-08-13, both forms exit
        # 0): `-p --print-timeout 5m` binds the literal string "--print-timeout"
        # as the prompt and leaves "5m" a stray positional — agy never reads
        # $PROMPT_FILE from stdin. Prompt must be `-p`'s own argv value;
        # --print-timeout stays a separate flag with its own value.
        # NOTE: agy v1.1.12 has no stdin path, so the prompt now travels on
        # argv — visible via `ps` to every other user on this machine while
        # the process runs (see PR body for the PII disclosure this forces).
        run_bounded "$tmpout" "$tmperr" "$label" \
            "${ISOLATED_PROVIDER_ENV[@]}" "$bin" -p "$PROMPT" --print-timeout 5m
        exit_code=$?
    else
        run_bounded "$tmpout" "$tmperr" "$label" \
            "${ISOLATED_PROVIDER_ENV[@]}" \
            "$bin" -m gemini-3.1-pro-preview -p "$PROMPT"
        exit_code=$?
    fi
    if retryable_failure_detected \
        "$tmpout" "$tmperr" "$exit_code" "TerminalQuotaError"; then
        echo "  [exhausted] $label quota" >&2
        rm -f "$tmpout" "$tmperr"
        return 98
    fi
    # agy's headless auto-deny is a LYING SUCCESS: a tool call needing interactive
    # permission gets auto-denied and agy still exits 0 with a jetski/"no output
    # produced" message instead of a real answer (measured live 2026-08-13). Judge
    # it as a tier failure so the cascade falls through instead of consuming the
    # denial text as if it were Gemini's response.
    if grep -qiE 'auto-denied|headless mode cannot prompt|no output produced' \
        "$tmpout" "$tmperr" 2>/dev/null; then
        echo "  [error] $label auto-denied a tool call in headless mode" >&2
        rm -f "$tmpout" "$tmperr"
        return 96
    fi
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] $label exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] $label returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: Gemini $label" >&2
    return 0
}

try_kimi() {
    local kimi_bin="$HOME/.kimi-code/bin/kimi"
    [ ! -x "$kimi_bin" ] && { echo "  [skip] Kimi K3 not installed" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] Kimi K3 — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    echo "  [try] Kimi Code K3" >&2
    # Fleet config pins default_model to kimi-code/k3. Invoking the configured
    # default is more reliable than repeating the alias on every call.
    build_isolated_provider_env
    run_bounded "$tmpout" "$tmperr" "Kimi Code K3" \
        "${ISOLATED_PROVIDER_ENV[@]}" "$kimi_bin" --prompt "$PROMPT"
    exit_code=$?
    if retryable_failure_detected "$tmpout" "$tmperr" "$exit_code"; then
        echo "  [exhausted] Kimi K3 quota" >&2
        rm -f "$tmpout" "$tmperr"
        return 98
    fi
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] Kimi K3 exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] Kimi K3 returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: Kimi Code K3" >&2
    return 0
}

codex_attempt() {
    local codex_bin="$1"
    local model="$2"
    local label="tier4 codex"
    local -a model_args
    model_args=()
    if [ -n "$model" ]; then
        label="tier4 codex ($model)"
        model_args=(-m "$model")
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    local -a seat_env
    seat_env=()
    if [ -n "${CODEX_SEAT_HOME:-}" ]; then
        seat_env=("CODEX_HOME=$CODEX_SEAT_HOME")
        label="$label [${CODEX_SEAT_HOME:t}]"
    fi
    echo "  [try] $label" >&2
    build_isolated_provider_env
    run_bounded "$tmpout" "$tmperr" "$label" \
        "${ISOLATED_PROVIDER_ENV[@]}" "${seat_env[@]}" \
        "$codex_bin" exec "${model_args[@]}" --sandbox read-only --skip-git-repo-check "$PROMPT"
    exit_code=$?
    if retryable_failure_detected "$tmpout" "$tmperr" "$exit_code"; then
        echo "  [exhausted] $label quota" >&2
        rm -f "$tmpout" "$tmperr"
        return 98
    fi
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] $label exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] $label returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: $label" >&2
    return 0
}

# Which ChatGPT Pro seats are actually usable — and in which order.
#
# The list itself lives in scripts/lib/codex_seat.sh, with the measurement that
# justifies it. It is NOT restated here: two copies of a seat list is how a
# machine's second subscription becomes invisible to one caller and not the
# other. `${0:A}` resolves the symlink first — on Pro ~/scripts/claude-cascade.sh
# points into the checkout, so $0 alone would look for the lib under ~/scripts.
#
# If the lib cannot be found we degrade to exactly today's behaviour (the single
# default seat) and say so, loudly. Degrading to "no codex at all" would turn a
# missing file into a lost provider tier; degrading silently would hide a
# HOME-fork (family #1) rather than surface it.
CODEX_SEAT_LIB=""
for _seat_lib in "${0:A:h}/../../../scripts/lib/codex_seat.sh" \
                 "$HOME/nuzantara/scripts/lib/codex_seat.sh"; do
    [ -f "$_seat_lib" ] && { CODEX_SEAT_LIB="$_seat_lib"; break; }
done
if [ -n "$CODEX_SEAT_LIB" ]; then
    . "$CODEX_SEAT_LIB"
else
    echo "  [warn] codex_seat.sh not found (looked next to this wrapper and under ~/nuzantara) — falling back to the single default seat" >&2
    codex_seat_dirs() { [ -f "$HOME/.codex/auth.json" ] && printf '%s\n' "$HOME/.codex"; }
    codex_seat_offset() { printf '0'; }
fi

# L09-PR1: the seat-state ledger (scripts/lib/seat_state.sh) — a pre-dispatch
# check so try_claude() can skip a seat already known to be quota-exhausted
# without spending a live dispatch on it. Same discovery pattern as
# CODEX_SEAT_LIB just above: look next to this wrapper first (repo checkout),
# then under ~/nuzantara (a HOME-fork twin). If neither exists, degrade to a
# no-op stub that never skips anything — fail-open, never fail-closed, so a
# missing library only costs back the pre-check optimization, never the
# cascade itself.
SEAT_STATE_LIB=""
for _seat_state_lib in "${0:A:h}/../../../scripts/lib/seat_state.sh" \
                       "$HOME/nuzantara/scripts/lib/seat_state.sh"; do
    [ -f "$_seat_state_lib" ] && { SEAT_STATE_LIB="$_seat_state_lib"; break; }
done
if [ -n "$SEAT_STATE_LIB" ]; then
    . "$SEAT_STATE_LIB"
    # Say WHICH copy was loaded. The second candidate is the main checkout,
    # which on a worktree may be a DIFFERENT version of this library than the
    # wrapper being exercised — a worktree validating new behaviour could
    # silently run the old library and never know.
    [ "${SEAT_STATE_VERBOSE:-0}" = "1" ] && echo "  [info] seat-state library: $SEAT_STATE_LIB" >&2
else
    echo "  [warn] seat_state.sh not found (looked next to this wrapper and under ~/nuzantara) — seat-state precheck disabled, cascade unaffected" >&2
    seat_state_precheck_skip() { return 1; }
fi

codex_seat_homes() {
    CODEX_SEAT_HOMES=("${(@f)$(codex_seat_dirs)}")
    # No seats at all still yields one EMPTY element from the substitution, and
    # an empty CODEX_HOME reads as "use the default" — the opposite of "none".
    if [ ${#CODEX_SEAT_HOMES[@]} -eq 1 ] && [ -z "${CODEX_SEAT_HOMES[1]}" ]; then
        CODEX_SEAT_HOMES=()
    fi
}

try_codex() {
    local codex_bin="$HOME/.local/bin/codex"
    [ ! -x "$codex_bin" ] && codex_bin="/opt/homebrew/bin/codex"
    [ ! -x "$codex_bin" ] && { echo "  [skip] tier4 codex not installed" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] tier4 codex — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi

    codex_seat_homes
    if [ ${#CODEX_SEAT_HOMES[@]} -eq 0 ]; then
        echo "  [skip] tier4 codex — no logged-in seat (no auth.json under any of ${CODEX_SEAT_DIRS:-~/.codex, ~/.codex-o2, ~/.codex-acct2})" >&2
        return 99
    fi

    # gpt-5.3-codex-spark bills against a weekly bucket SEPARATE from the
    # gpt-5.6-* family, so an exhausted primary says nothing about Spark's
    # headroom — measured 2026-07-25 with sol at 1% and Spark at 100% on both
    # ChatGPT Pro seats. Without this retry the cascade abandons a paid, full
    # bucket and crosses the provider boundary for no reason.
    # Kill switch: export CLAUDE_CASCADE_CODEX_SPARK_MODEL="" to disable.
    local spark_model="${CLAUDE_CASCADE_CODEX_SPARK_MODEL-gpt-5.3-codex-spark}"
    local n=${#CODEX_SEAT_HOMES[@]}
    local off i idx rc
    off=$(codex_seat_offset)

    # Both buckets of seat A, then both buckets of seat B. Exhaustion (98) is
    # the ONLY verdict that moves on: any other outcome — an answer, an error,
    # a timeout — belongs to the caller, because retrying a broken call on a
    # second account just breaks it twice and spends the other subscription.
    for (( i = 0; i < n; i++ )); do
        idx=$(( (off + i) % n + 1 ))          # zsh arrays are 1-based
        CODEX_SEAT_HOME="${CODEX_SEAT_HOMES[idx]}"
        codex_attempt "$codex_bin" ""
        rc=$?
        [ "$rc" -ne 98 ] && { unset CODEX_SEAT_HOME; return "$rc"; }
        if [ -n "$spark_model" ]; then
            echo "  [retry] tier4 codex — primary bucket exhausted on this seat, trying $spark_model (separate weekly quota)" >&2
            codex_attempt "$codex_bin" "$spark_model"
            rc=$?
            [ "$rc" -ne 98 ] && { unset CODEX_SEAT_HOME; return "$rc"; }
        fi
    done
    unset CODEX_SEAT_HOME
    return 98
}

# Verifies the MODEL is actually installed, not just the `ollama` binary. Before
# this check, a missing model reached `ollama run` directly: measured live
# 2026-08-20 on Pro, that spends several seconds attempting a network
# pull-manifest round-trip ("pulling manifest" spinner) before failing with a
# generic `Error: pull model manifest: file does not exist` (exit 1) — a real,
# non-zero exit (so try_ollama's own exit-code check was never silently wrong),
# but slow, unnecessarily network-dependent for a tier whose whole point is
# local/offline, and logged identically to a daemon-down or OOM failure.
# Reads /api/tags (not `ollama list`, which has an independent history in this
# repo of answering empty while the API answers correctly) so a known miss is
# fast, local-only, and distinguishable in the log from "daemon unreachable".
_ollama_model_ready() {
    local model="$1"
    local base="${OLLAMA_API_BASE:-http://127.0.0.1:11434}"
    # Overridable (mirrors the other provider-binary overrides in this cascade) —
    # a hermetic test harness fakes the whole `ollama` binary via PATH-free
    # absolute overrides, but this precheck talks HTTP directly (by design:
    # see the comment above `_ollama_model_ready`, not the `ollama` binary),
    # so without its own seam it always hits a real, unreachable 127.0.0.1
    # in CI and the tier silently vanishes from every test scenario.
    local curl_bin="${CLAUDE_CASCADE_OLLAMA_CURL_BIN:-curl}"
    local tags
    tags="$("$curl_bin" -sf -m 5 "${base}/api/tags" 2>/dev/null)"
    if [ -z "$tags" ]; then
        echo "  [ollama-precheck] daemon unreachable at ${base}" >&2
        return 1
    fi
    if printf '%s' "$tags" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
names = {m.get('name') for m in data.get('models', [])}
sys.exit(0 if '$model' in names else 1)
"; then
        return 0
    fi
    echo "  [ollama-precheck] model '$model' not installed (daemon reachable, tags checked)" >&2
    return 1
}

try_ollama() {
    local ollama_bin="${CLAUDE_CASCADE_OLLAMA_BIN:-/opt/homebrew/bin/ollama}"
    [ ! -x "$ollama_bin" ] && { echo "  [skip] ollama not installed" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] tier5 ollama — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    if ! _ollama_model_ready "qwen3.5:9b"; then
        return 99
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    echo "  [try] tier5 ollama qwen3.5:9b local" >&2
    build_isolated_provider_env
    run_bounded "$tmpout" "$tmperr" "tier5 ollama" \
        "${ISOLATED_PROVIDER_ENV[@]}" \
        "$ollama_bin" run qwen3.5:9b "$PROMPT"
    exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] ollama exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] ollama returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: tier5 ollama-qwen3.5:9b-local" >&2
    return 0
}

# Tier 6: Apple on-device Foundation Model via the fm CLI (ships with macOS 27).
# This is the zero-daemon last resort: unlike tier 5 it needs no Ollama server,
# no model pull, and no RAM residency — the system model is always present on a
# macOS 27 machine once `sudo fm license` has been accepted. Quality is ~3B
# (benchmark 2026-08-19: 12/15 vs qwen3.5:9b 14/15 on grunt shapes), so it adds
# cascade depth for machines/moments where tier 5 is dead (M5 by policy runs no
# Ollama daemon; Pro after a panic), never a preferred seat. An unlicensed fm
# exits non-zero and lands in the fail-visible error path below, same as any
# dead tier. Kill switch: CLAUDE_CASCADE_FM=0.
try_fm() {
    local fm_bin="${CLAUDE_CASCADE_FM_BIN:-/usr/bin/fm}"
    if [ "${CLAUDE_CASCADE_FM:-1}" = "0" ]; then
        echo "  [skip] tier6 fm disabled (CLAUDE_CASCADE_FM=0)" >&2
        return 99
    fi
    [ ! -x "$fm_bin" ] && { echo "  [skip] tier6 fm not installed (macOS 27+ only)" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] tier6 fm — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    echo "  [try] tier6 fm apple-on-device" >&2
    build_isolated_provider_env
    run_bounded "$tmpout" "$tmperr" "tier6 fm" \
        "${ISOLATED_PROVIDER_ENV[@]}" \
        "$fm_bin" respond --no-stream --greedy "$PROMPT"
    exit_code=$?
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] fm exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] fm returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: tier6 fm-apple-on-device" >&2
    return 0
}

# ============= CASCADE =============
echo "[claude-cascade] starting (prompt ${#PROMPT} chars, agent='$AGENT', model='$MODEL')" >&2

# Claude OAuth binary. Credentials are selected explicitly below; the binary's
# ambient default/keychain identity is never consulted before the final step.
DEFAULT_CLAUDE_BIN="${CLAUDE_CASCADE_DEFAULT_BIN:-$HOME/.local/share/mise/shims/claude}"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="$HOME/.local/bin/claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="/opt/homebrew/bin/Claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="/opt/homebrew/bin/claude"

# The authoritative fleet order is explicit and deterministic:
#   1 → 2 → 3 → 4 → 5 → 6 (zero@ Team) → legacy → keychain.
# Each explicit token receives an isolated config directory and each child sees
# only its selected token. Duplicate values are skipped without being logged.
#
# Slot→account mapping verified 2026-08-23 (`claude auth status` per profile +
# setup-token transcript): 1=antonellosiano@gmail.com 2=sianoantonello@gmail.com
# 3=applevisionpro1987@gmail.com 4=antozero1987@gmail.com
# 5=kaiser198719871987@gmail.com (all 5 are MAX) 6=zero@balizero.com (TEAM).
# The Team seat is LAST ON PURPOSE (weekly caps, ruled by Zero) — it is the
# fallback of last resort, never promoted ahead of a MAX slot. Anyone who
# reorders this violates that ruling.
typeset -a SEEN_OAUTH_TOKENS
SEEN_OAUTH_TOKENS=()
oauth_token_seen() {
    local candidate="$1"
    local existing
    for existing in "${SEEN_OAUTH_TOKENS[@]}"; do
        [ "$existing" = "$candidate" ] && return 0
    done
    return 1
}

for index in 1 2 3 4 5 6; do
    case "$index" in
        1)
            label="claude-token-1-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_1:-}"
            config_dir="$HOME/.claude"
            ;;
        2)
            label="claude-token-2-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_2:-}"
            config_dir="$HOME/.claude-acct2"
            ;;
        3)
            label="claude-token-3-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_3:-}"
            config_dir="$HOME/.claude-acct3"
            ;;
        4)
            label="claude-token-4-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_4:-}"
            config_dir="$HOME/.claude-antozero"
            ;;
        5)
            label="claude-token-5-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_5:-}"
            config_dir="$HOME/.claude-kaiser"
            ;;
        6)
            label="claude-token-6-team-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_6:-}"
            config_dir="$HOME/.claude-zero-team"
            ;;
    esac

    if [ -n "$token" ] && ! oauth_token_seen "$token"; then
        SEEN_OAUTH_TOKENS+=("$token")
        try_claude "$DEFAULT_CLAUDE_BIN" "$label" "$token" "$config_dir"
        rc=$?
        [ $rc -eq 0 ] && exit 0
    fi
done

# The protected Team wrapper is a compatibility fallback only when token_6 is
# unavailable. It is never tried ahead of the explicit subscription chain.
# (Renumbered 2026-08-23: this used to gate on token_5 back when slot 5 was
# the Team seat. Slot 5 is now a MAX seat — kaiser198719871987@gmail.com — and
# the Team seat moved to slot 6, so the gate moved with it.)
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN_6:-}" ]; then
    try_claude "$HOME/.local/bin/claude-zero-team" \
        "claude-token-6-team-wrapper" "" "$HOME/.claude-zero-team"
    rc=$?
    [ $rc -eq 0 ] && exit 0
fi

LEGACY_TOKEN="${CLAUDE_CODE_OAUTH_TOKEN:-}"
if [ -n "$LEGACY_TOKEN" ] && ! oauth_token_seen "$LEGACY_TOKEN"; then
    SEEN_OAUTH_TOKENS+=("$LEGACY_TOKEN")
    try_claude "$DEFAULT_CLAUDE_BIN" "claude-token-legacy-env" \
        "$LEGACY_TOKEN" "$HOME/.claude"
    rc=$?
    [ $rc -eq 0 ] && exit 0
fi

# Keychain/default login is last because launchd/sshd keychains can be locked
# or stale. All explicit OAuth token variables are removed from this child.
try_claude "$DEFAULT_CLAUDE_BIN" "claude-keychain" "" "$HOME/.claude"
rc=$?
[ $rc -eq 0 ] && exit 0

# Named Claude agents are provider-specific executable contracts. If every
# Claude seat fails, crossing model families would silently drop the agent
# definition/tool policy. Fail closed instead.
if [ "$CLAUDE_ONLY" -eq 1 ] || [ -n "$AGENT" ] \
    || [ "${#EXTRA_ARGS[@]}" -gt 0 ]; then
    if [ -n "$AGENT" ]; then
        echo "[claude-cascade] agent '$AGENT' cannot be preserved cross-family" >&2
    fi
    if [ "${#EXTRA_ARGS[@]}" -gt 0 ]; then
        echo "[claude-cascade] Claude CLI arguments cannot be preserved cross-family" >&2
    fi
    echo "[claude-cascade] ALL CLAUDE SEATS FAILED" >&2
    exit 1
fi

# Gemini
try_gemini && exit 0

# Kimi K3
try_kimi && exit 0

# Codex
try_codex && exit 0

# Tier 5: Ollama local (always-on safety net)
try_ollama && exit 0

# Tier 6: Apple on-device Foundation Model (macOS 27+, zero-daemon last resort)
try_fm && exit 0

echo "[claude-cascade] ALL TIERS FAILED" >&2
exit 1
