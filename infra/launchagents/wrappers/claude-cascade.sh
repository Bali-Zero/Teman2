#!/bin/zsh
# claude-cascade.sh — single entry point for autonomous Claude invocations with full fallback cascade.
#
# Tries CLI binaries in this order, falling back on quota exhaustion:
#   1. Claude OAuth seats: default, acct2, acct3, acct4, zero-team
#   2. agy -p (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
#   3. Kimi Code K3
#   4. codex exec --sandbox read-only (ChatGPT Pro)
#   5. ollama run qwen3.5:9b (Pro/Mini local safety net)
#
# Usage:
#   claude-cascade.sh "<prompt text>" [--model MODEL] [--agent AGENT_NAME]
#   echo "prompt" | claude-cascade.sh --stdin [--agent AGENT_NAME]
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

unset ANTHROPIC_API_KEY  # defense-in-depth: never pay-per-token Anthropic

# Source secrets so spawned agents have DEEPSEEK_API_KEY, TELEGRAM_*, etc.
# This is the canonical location of all autonomous-runtime secrets.
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null
    set +a
fi
# Re-strip ANTHROPIC_API_KEY in case secrets file accidentally contained it
unset ANTHROPIC_API_KEY

# W89 class-audit (2026-07-11): 30min ceiling — same value as regulatory-watcher-run.sh's
# own fix, applied here once so every caller of this cascade (competitor-monitor,
# yield-optimizer, and any future claude-cascade.sh consumer) inherits it uniformly.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

PROMPT=""
MODEL=""
AGENT=""
USE_STDIN=0
EXTRA_ARGS=()

# parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --agent) AGENT="$2"; shift 2 ;;
        --stdin) USE_STDIN=1; shift ;;
        --) shift; EXTRA_ARGS+=("$@"); break ;;
        -*) EXTRA_ARGS+=("$1"); shift ;;
        *) PROMPT="$1"; shift ;;
    esac
done

if [ "$USE_STDIN" -eq 1 ]; then
    PROMPT="$(cat)"
fi

if [ -z "$PROMPT" ]; then
    echo "usage: $0 \"<prompt>\" [--model M] [--agent A]" >&2
    exit 2
fi

QUOTA_PATTERN="out of extra usage|usage limit|weekly limit|quota exceeded|rate.limit|429|exhausted|please try again later"

# build claude args (model + agent + extras)
build_claude_args() {
    local args=("--print")
    [ -n "$MODEL" ] && args+=("--model" "$MODEL")
    [ -n "$AGENT" ] && args+=("--agent" "$AGENT")
    args+=("${EXTRA_ARGS[@]}")
    echo "${args[@]}"
}

try_claude() {
    local bin="$1"
    local label="$2"
    [ ! -x "$bin" ] && [ ! -L "$bin" ] && { echo "  [skip] $label not installed at $bin" >&2; return 99; }

    local tmpout=$(mktemp)
    local args=$(build_claude_args)

    echo "  [try] $label ($bin)" >&2
    echo "$PROMPT" | $bin ${=args} >"$tmpout" 2>&1
    local exit=$?

    if grep -qiE "$QUOTA_PATTERN" "$tmpout"; then
        echo "  [exhausted] $label quota" >&2
        rm -f "$tmpout"
        return 98
    fi
    if [ $exit -ne 0 ]; then
        echo "  [error] $label exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] $label returned empty output" >&2
        rm -f "$tmpout"
        return 97
    fi

    cat "$tmpout"
    rm -f "$tmpout"
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
    local tmpout=$(mktemp)
    echo "  [try] Gemini $label" >&2
    if [ "$bin" = "$agy_bin" ]; then
        printf '%s' "$PROMPT" | "$bin" -p --print-timeout 5m >"$tmpout" 2>&1
    else
        "$bin" -m gemini-3.1-pro-preview -p "$PROMPT" >"$tmpout" 2>&1
    fi
    local exit=$?
    if grep -qiE "$QUOTA_PATTERN|TerminalQuotaError" "$tmpout"; then
        echo "  [exhausted] $label quota" >&2
        rm -f "$tmpout"
        return 98
    fi
    if [ $exit -ne 0 ]; then
        echo "  [error] $label exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] $label returned empty output" >&2
        rm -f "$tmpout"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout"
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
    local tmpout=$(mktemp)
    echo "  [try] Kimi Code K3" >&2
    # Fleet config pins default_model to kimi-code/k3. Invoking the configured
    # default is more reliable than repeating the alias on every call.
    "$kimi_bin" --prompt "$PROMPT" >"$tmpout" 2>&1
    local exit=$?
    if grep -qiE "$QUOTA_PATTERN" "$tmpout"; then
        echo "  [exhausted] Kimi K3 quota" >&2
        rm -f "$tmpout"
        return 98
    fi
    if [ $exit -ne 0 ]; then
        echo "  [error] Kimi K3 exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] Kimi K3 returned empty output" >&2
        rm -f "$tmpout"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout"
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
    local tmpout=$(mktemp)
    echo "  [try] tier4 codex" >&2
    "$codex_bin" exec --sandbox read-only --skip-git-repo-check "$PROMPT" >"$tmpout" 2>&1
    local exit=$?
    if grep -qiE "$QUOTA_PATTERN" "$tmpout"; then
        echo "  [exhausted] codex quota" >&2
        rm -f "$tmpout"
        return 98
    fi
    if [ $exit -ne 0 ]; then
        echo "  [error] codex exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] codex returned empty output" >&2
        rm -f "$tmpout"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout"
    echo "[claude-cascade] used: tier4 codex" >&2
    return 0
}

try_ollama() {
    [ ! -x /opt/homebrew/bin/ollama ] && { echo "  [skip] ollama not installed" >&2; return 99; }
    if [ -n "$AGENT" ]; then
        echo "  [skip] tier5 ollama — --agent=$AGENT requires Claude tier" >&2
        return 99
    fi
    local tmpout=$(mktemp)
    echo "  [try] tier5 ollama qwen3.5:9b local" >&2
    /opt/homebrew/bin/ollama run qwen3.5:9b "$PROMPT" >"$tmpout" 2>&1
    local exit=$?
    if [ $exit -ne 0 ]; then
        echo "  [error] ollama exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
    fi
    if [ ! -s "$tmpout" ]; then
        echo "  [error] ollama returned empty output" >&2
        rm -f "$tmpout"
        return 97
    fi
    cat "$tmpout"
    rm -f "$tmpout"
    echo "[claude-cascade] used: tier5 ollama-qwen3.5:9b-local" >&2
    return 0
}

# ============= CASCADE =============
echo "[claude-cascade] starting (prompt ${#PROMPT} chars, agent='$AGENT', model='$MODEL')" >&2

# Claude OAuth seats (if configured)
DEFAULT_CLAUDE_BIN="$HOME/.local/share/mise/shims/claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="$HOME/.local/bin/claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="/opt/homebrew/bin/Claude"
[ ! -x "$DEFAULT_CLAUDE_BIN" ] && DEFAULT_CLAUDE_BIN="/opt/homebrew/bin/claude"

for slot in "${DEFAULT_CLAUDE_BIN}:tier1-claude-default" \
            "$HOME/.local/bin/claude-acct2:tier2-claude-acct2" \
            "$HOME/.local/bin/claude-acct3:tier2b-claude-acct3" \
            "$HOME/.local/bin/claude-acct4:tier2c-claude-acct4" \
            "$HOME/.local/bin/claude-zero-team:tier2d-claude-zero-team"; do
    bin="${slot%:*}"
    label="${slot#*:}"
    try_claude "$bin" "$label"
    rc=$?
    [ $rc -eq 0 ] && exit 0
    [ $rc -eq 99 ] && continue  # not installed
    [ $rc -eq 98 ] && continue  # quota exhausted, try next
    # other errors: try next tier (could be transient; cascade is permissive)
done

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
