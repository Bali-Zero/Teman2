#!/usr/bin/env bash
# Cross-LLM wrapper that injects playwright site context before invoking an LLM.
#
# Usage:
#   cross-llm-wrapper.sh <llm> <site_or_url> [action] -- <prompt>
#
# Examples:
#   cross-llm-wrapper.sh gemini canva -- "edit template DAHE6lx1lf8 slide 3 text"
#   cross-llm-wrapper.sh codex https://www.canva.com/design/XYZ/edit download_design -- "export PNG"
#   cross-llm-wrapper.sh claude gemini generate_image -- "Bali sunset minimalist"
#
# LLMs supported: claude, gemini, codex, ollama.
# The site context is passed via --system / system-prompt flag appropriate to each CLI.

set -euo pipefail

INJECT="$(cd "$(dirname "$0")" && pwd)/inject.py"
if [ ! -f "$INJECT" ]; then
    echo "ERROR: inject.py not found at $INJECT" >&2
    exit 2
fi

usage() {
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
}

[ $# -lt 4 ] && usage

LLM="$1"; shift
SITE_OR_URL="$1"; shift

# Optional action; '--' separator is mandatory before prompt
ACTION=""
if [ "$1" != "--" ]; then
    ACTION="$1"; shift
fi
[ "$1" = "--" ] || usage
shift
PROMPT="$*"

# Build inject args
INJECT_ARGS=()
if echo "$SITE_OR_URL" | grep -q "://"; then
    INJECT_ARGS+=("--url" "$SITE_OR_URL")
else
    INJECT_ARGS+=("--site" "$SITE_OR_URL")
fi
[ -n "$ACTION" ] && INJECT_ARGS+=("--action" "$ACTION")
INJECT_ARGS+=("--format" "markdown")

CTX="$(python3 "$INJECT" "${INJECT_ARGS[@]}")"

if [ -z "$CTX" ]; then
    echo "ERROR: inject returned empty context" >&2
    exit 1
fi

# Route to the LLM
case "$LLM" in
    claude)
        # Claude Code CLI: uses --append-system-prompt or just prepends to user prompt
        # Assumes CLAUDE_CODE_OAUTH_TOKEN is exported
        claude -p "$(printf '%s\n\n---\n\nUser request: %s' "$CTX" "$PROMPT")"
        ;;
    gemini)
        gemini -m gemini-3.1-pro-preview -p "$(printf '%s\n\n---\n\nUser request: %s' "$CTX" "$PROMPT")"
        ;;
    codex)
        codex exec --full-auto "$(printf '%s\n\n---\n\nUser request: %s' "$CTX" "$PROMPT")"
        ;;
    ollama)
        # Ollama generate with system context
        ollama run qwen3.5:9b "$(printf 'System context:\n%s\n\nUser: %s' "$CTX" "$PROMPT")"
        ;;
    *)
        echo "ERROR: unknown LLM '$LLM'. Supported: claude, gemini, codex, ollama" >&2
        exit 2
        ;;
esac
