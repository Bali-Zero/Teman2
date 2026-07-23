#!/bin/zsh
# claude-cascade.sh — single entry point for autonomous Claude invocations with full fallback cascade.
#
# Tries CLI binaries in this order, falling back on quota/auth/empty/timeout:
#   1. Explicit Claude OAuth seats: token_1, token_2, token_3, token_4,
#      token_5 (zero@ Team), legacy token, then macOS keychain
#   2. agy -p (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
#   3. Kimi Code K3
#   4. codex exec --sandbox read-only (ChatGPT Pro)
#   5. ollama run qwen3.5:9b (Pro/Mini local safety net)
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

cleanup_cascade() {
    if [ -n "${ACTIVE_WATCHER_PID:-}" ]; then
        kill "$ACTIVE_WATCHER_PID" 2>/dev/null || true
        wait "$ACTIVE_WATCHER_PID" 2>/dev/null || true
    fi
    if [ -n "${ACTIVE_CHILD_PID:-}" ]; then
        /usr/bin/pkill -TERM -P "$ACTIVE_CHILD_PID" 2>/dev/null || true
        kill "$ACTIVE_CHILD_PID" 2>/dev/null || true
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
AUTH_PATTERN="authentication required|not logged in|please log in|unauthorized|invalid (oauth )?token|oauth token.*(expired|invalid|revoked)|refresh_token_reused"
RETRYABLE_PATTERN="$QUOTA_PATTERN|$AUTH_PATTERN"

new_temp_file
PROMPT_FILE="$REPLY"
printf '%s' "$PROMPT" >"$PROMPT_FILE"

# Run one provider attempt under both a per-attempt timeout and a global
# cascade deadline. macOS has no guaranteed timeout(1), so a local watchdog
# owns the exact child PID. Timeout is a retryable failure; a spent global
# deadline makes every later attempt fail immediately.
run_bounded() {
    local tmpout="$1"
    local tmperr="$2"
    local label="$3"
    shift 3

    local now remaining allowed timeout_marker exit_code child_pid
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

    "$@" <"$PROMPT_FILE" >"$tmpout" 2>"$tmperr" &
    ACTIVE_CHILD_PID=$!
    child_pid="$ACTIVE_CHILD_PID"
    (
        sleep "$allowed"
        if kill -0 "$child_pid" 2>/dev/null; then
            : >"$timeout_marker"
            /usr/bin/pkill -TERM -P "$child_pid" 2>/dev/null || true
            kill -TERM "$child_pid" 2>/dev/null || true
            sleep 1
            /usr/bin/pkill -KILL -P "$child_pid" 2>/dev/null || true
            kill -KILL "$child_pid" 2>/dev/null || true
        fi
    ) </dev/null >/dev/null 2>&1 &
    ACTIVE_WATCHER_PID=$!

    wait "$ACTIVE_CHILD_PID"
    exit_code=$?
    kill "$ACTIVE_WATCHER_PID" 2>/dev/null || true
    wait "$ACTIVE_WATCHER_PID" 2>/dev/null || true
    ACTIVE_CHILD_PID=""
    ACTIVE_WATCHER_PID=""

    if [ -e "$timeout_marker" ]; then
        /usr/bin/pkill -KILL -P "$child_pid" 2>/dev/null || true
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

    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    build_claude_args
    local -a clean_env
    clean_env=(
        env
        -u CLAUDE_CODE_OAUTH_TOKEN
        -u CLAUDE_CODE_OAUTH_TOKEN_1
        -u CLAUDE_CODE_OAUTH_TOKEN_2
        -u CLAUDE_CODE_OAUTH_TOKEN_3
        -u CLAUDE_CODE_OAUTH_TOKEN_4
        -u CLAUDE_CODE_OAUTH_TOKEN_5
    )

    echo "  [try] $label ($bin)" >&2
    if [ -n "$oauth_token" ]; then
        run_bounded "$tmpout" "$tmperr" "$label" "${clean_env[@]}" \
            CLAUDE_CONFIG_DIR="$config_dir" \
            CLAUDE_CODE_OAUTH_TOKEN="$oauth_token" \
            "$bin" "${CLAUDE_ARGS[@]}"
        exit_code=$?
    else
        run_bounded "$tmpout" "$tmperr" "$label" "${clean_env[@]}" \
            CLAUDE_CONFIG_DIR="$config_dir" \
            "$bin" "${CLAUDE_ARGS[@]}"
        exit_code=$?
    fi

    # Some Claude CLI auth/quota failures incorrectly return exit 0. Content
    # classification therefore precedes the exit-code success check.
    if grep -qiE "$RETRYABLE_PATTERN" "$tmpout" "$tmperr"; then
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
    if [ "$bin" = "$agy_bin" ]; then
        run_bounded "$tmpout" "$tmperr" "$label" \
            "$bin" -p --print-timeout 5m
        exit_code=$?
    else
        run_bounded "$tmpout" "$tmperr" "$label" \
            "$bin" -m gemini-3.1-pro-preview -p "$PROMPT"
        exit_code=$?
    fi
    if grep -qiE "$QUOTA_PATTERN|TerminalQuotaError" "$tmpout" "$tmperr"; then
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
    run_bounded "$tmpout" "$tmperr" "Kimi Code K3" \
        "$kimi_bin" --prompt "$PROMPT"
    exit_code=$?
    if grep -qiE "$QUOTA_PATTERN" "$tmpout" "$tmperr"; then
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

try_codex() {
    local codex_bin="$HOME/.local/bin/codex"
    [ ! -x "$codex_bin" ] && codex_bin="/opt/homebrew/bin/codex"
    [ ! -x "$codex_bin" ] && { echo "  [skip] tier4 codex not installed" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] tier4 codex — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    echo "  [try] tier4 codex" >&2
    run_bounded "$tmpout" "$tmperr" "tier4 codex" \
        "$codex_bin" exec --sandbox read-only --skip-git-repo-check "$PROMPT"
    exit_code=$?
    if grep -qiE "$QUOTA_PATTERN" "$tmpout" "$tmperr"; then
        echo "  [exhausted] codex quota" >&2
        rm -f "$tmpout" "$tmperr"
        return 98
    fi
    if [ "$exit_code" -ne 0 ]; then
        echo "  [error] codex exit=$exit_code" >&2
        rm -f "$tmpout" "$tmperr"
        return "$exit_code"
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] codex returned empty output" >&2
        rm -f "$tmpout" "$tmperr"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout" "$tmperr"
    echo "[claude-cascade] used: tier4 codex" >&2
    return 0
}

try_ollama() {
    [ ! -x /opt/homebrew/bin/ollama ] && { echo "  [skip] ollama not installed" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] tier5 ollama — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    local tmpout tmperr exit_code
    new_temp_file
    tmpout="$REPLY"
    new_temp_file
    tmperr="$REPLY"
    echo "  [try] tier5 ollama qwen3.5:9b local" >&2
    run_bounded "$tmpout" "$tmperr" "tier5 ollama" \
        /opt/homebrew/bin/ollama run qwen3.5:9b "$PROMPT"
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

# ============= CASCADE =============
echo "[claude-cascade] starting (prompt ${#PROMPT} chars, agent='$AGENT', model='$MODEL')" >&2

# Claude OAuth binary. Credentials are selected explicitly below; the binary's
# ambient default/keychain identity is never consulted before the final step.
DEFAULT_CLAUDE_BIN="${CLAUDE_CASCADE_DEFAULT_BIN:-$HOME/.local/share/mise/shims/claude}"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="$HOME/.local/bin/claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="/opt/homebrew/bin/Claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="/opt/homebrew/bin/claude"

# The authoritative fleet order is explicit and deterministic:
#   1 → 2 → 3 → 4 → 5 (zero@ Team) → legacy → keychain.
# Each explicit token receives an isolated config directory and each child sees
# only its selected token. Duplicate values are skipped without being logged.
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

for index in 1 2 3 4 5; do
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
            config_dir="$HOME/.claude-acct4"
            ;;
        5)
            label="claude-token-5-team-env"
            token="${CLAUDE_CODE_OAUTH_TOKEN_5:-}"
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

# The protected Team wrapper is a compatibility fallback only when token_5 is
# unavailable. It is never tried ahead of the explicit subscription chain.
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN_5:-}" ]; then
    try_claude "$HOME/.local/bin/claude-zero-team" \
        "claude-token-5-team-wrapper" "" "$HOME/.claude-zero-team"
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
if [ "$CLAUDE_ONLY" -eq 1 ] || [ -n "$AGENT" ]; then
    if [ -n "$AGENT" ]; then
        echo "[claude-cascade] agent '$AGENT' cannot be preserved cross-family" >&2
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

echo "[claude-cascade] ALL TIERS FAILED" >&2
exit 1
