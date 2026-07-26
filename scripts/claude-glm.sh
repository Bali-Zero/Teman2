#!/bin/bash
# claude-glm.sh — run the Claude CLI against the z.ai GLM coding-plan subscription.
#
# WHY THIS EXISTS (2026-07-26)
# `~/.claude-glm/settings.json` sets ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
# but carries NO credential, and nothing else supplied one — so the documented
# invocation `CLAUDE_CONFIG_DIR=~/.claude-glm claude -p …` could never authenticate
# and answered `401 token expired or incorrect`. That 401 was read as "the seat is
# dead"; it was not. The subscription is live: the same endpoint returns HTTP 200 /
# glm-5.2 / PONG once a credential is attached. Built, never armed.
#
# NOT `ANTHROPIC_API_KEY`: that variable is banned repo-wide (it selects Anthropic's
# metered endpoint, which duplicates the MAX subscription). Verified empirically that
# z.ai accepts BOTH `x-api-key` and `Authorization: Bearer`, so the sanctioned
# bearer-token path works and no exception is needed. The Anthropic paid-path
# variables are scrubbed below as defence-in-depth, since a stray one in the ambient
# environment would otherwise choose a different billing path.
#
# The token is read from the Keychain at invocation and never written to disk
# (cicatrix #4: a secret in a settings file is a secret in the clear).
#
# Deployed as a SYMLINK (~/.local/bin/claude-glm -> this file), never a copy, so the
# live wrapper cannot drift from the repo (cicatrix #1).
#
# Usage: claude-glm -p "prompt"      # any claude CLI arguments are passed through
set -euo pipefail

KEYCHAIN_SERVICE="${GLM_KEYCHAIN_SERVICE:-glm-coding-plan-token}"

token="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null || true)"
if [ -z "$token" ]; then
    echo "claude-glm: no token in Keychain service '$KEYCHAIN_SERVICE'." >&2
    echo "  add it with: security add-generic-password -s '$KEYCHAIN_SERVICE' -a \"\$USER\" -w" >&2
    exit 78  # EX_CONFIG — fail loud; never fall through to an unauthenticated call
fi

config_dir="${GLM_CONFIG_DIR:-$HOME/.claude-glm}"
if [ ! -d "$config_dir" ]; then
    echo "claude-glm: config dir '$config_dir' not found (it carries ANTHROPIC_BASE_URL)." >&2
    exit 78
fi

claude_bin="${CLAUDE_BIN:-}"
if [ -z "$claude_bin" ]; then
    for candidate in "$HOME/.local/bin/claude" "$HOME/.local/share/mise/shims/claude" /opt/homebrew/bin/claude; do
        [ -x "$candidate" ] && { claude_bin="$candidate"; break; }
    done
fi
[ -n "$claude_bin" ] || claude_bin="$(command -v claude || true)"
if [ -z "$claude_bin" ]; then
    echo "claude-glm: claude CLI not found." >&2
    exit 127
fi

exec env -u ANTHROPIC_API_KEY -u CLAUDE_CODE_OAUTH_TOKEN -u AWS_BEARER_TOKEN_BEDROCK \
    -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX \
    CLAUDE_CONFIG_DIR="$config_dir" \
    ANTHROPIC_AUTH_TOKEN="$token" \
    "$claude_bin" "$@"
