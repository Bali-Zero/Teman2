#!/bin/zsh
# claude-cascade.sh — single entry point for autonomous Claude invocations with full fallback cascade.
#
# Tries CLI binaries in this order, falling back on quota exhaustion:
#   1. claude          (default OAuth slot, MAX plan #1)
#   2. claude-acct2    (MAX plan #2, if setup-acct-slot.sh 2 + /login completed)
#   3. agy -p (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
#   4. codex exec --sandbox read-only    (ChatGPT Plus / Pro)
#   5. ollama run qwen3.5:9b             (local, always available)
# Note: slot 3 was removed 2026-05-09 — only 2 MAX plans active (kaiser + #2).
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

QUOTA_PATTERN="out of extra usage|usage limit|quota exceeded|rate.limit|429|exhausted|please try again later"

# build claude args (model + agent + extras)
build_claude_args() {
    local args=("--print")
    [ -n "$MODEL" ] && args+=("--model" "$MODEL")
    [ -n "$AGENT" ] && args+=("--agent" "$AGENT")
    args+=("--max-budget-usd" "${CASCADE_MAX_BUDGET_USD:-5}")
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

    cat "$tmpout"
    rm -f "$tmpout"
    echo "[claude-cascade] used: $label" >&2
    return 0
}

try_gemini() {
    local agy="$HOME/.local/bin/agy"
    [ ! -x "$agy" ] && { echo "  [skip] tier3 agy not installed" >&2; return 99; }
    local tmpout=$(mktemp)
    echo "  [try] tier3 agy (Gemini 3.1 Pro)" >&2
    echo "$PROMPT" | "$agy" -p --print-timeout 5m >"$tmpout" 2>&1
    local exit=$?
    if [ $exit -ne 0 ]; then
        echo "  [error] agy exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
    fi
    cat "$tmpout"
    rm -f "$tmpout"
    echo "[claude-cascade] used: tier3 agy-gemini3.1pro" >&2
    return 0
}

try_codex() {
    [ ! -x /opt/homebrew/bin/codex ] && { echo "  [skip] tier4 codex not installed" >&2; return 99; }
    local tmpout=$(mktemp)
    echo "  [try] tier4 codex" >&2
    /opt/homebrew/bin/codex exec --sandbox read-only --skip-git-repo-check "$PROMPT" >"$tmpout" 2>&1
    local exit=$?
    if [ $exit -ne 0 ]; then
        echo "  [error] codex exit=$exit" >&2
        cat "$tmpout" >&2
        rm -f "$tmpout"
        return $exit
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
    cat "$tmpout"
    rm -f "$tmpout"
    echo "[claude-cascade] used: tier5 ollama-qwen3.5:9b-local" >&2
    return 0
}

# ============= CASCADE =============
echo "[claude-cascade] starting (prompt ${#PROMPT} chars, agent='$AGENT', model='$MODEL')" >&2

# Tier 1-2: Claude OAuth slots (if configured)
for slot in "$HOME/.local/bin/claude:tier1-claude-default" \
            "$HOME/.local/bin/claude-acct2:tier2-claude-acct2" \
            "$HOME/.local/bin/claude-acct3:tier2b-claude-acct3"; do
    bin="${slot%:*}"
    label="${slot#*:}"
    try_claude "$bin" "$label"
    rc=$?
    [ $rc -eq 0 ] && exit 0
    [ $rc -eq 99 ] && continue  # not installed
    [ $rc -eq 98 ] && continue  # quota exhausted, try next
    # other errors: try next tier (could be transient; cascade is permissive)
done

# Tier 3: Gemini
try_gemini && exit 0

# Tier 4: Codex
try_codex && exit 0

# Tier 5: Ollama local (always-on safety net)
try_ollama && exit 0

echo "[claude-cascade] ALL TIERS FAILED" >&2
exit 1
