#!/usr/bin/env bash
# Configure and supervise the private ChatGPT Business marketing tunnel on Pro.
#
# The runtime key is read silently and stored in a mode-0600 file referenced by
# tunnel-client. It is never printed, placed on argv, or written into the repo.
# The tunnel starts read-only by default. --arm-writes is an explicit operator
# gate and still leaves every write behind per-call confirmation, idempotency,
# bounded Flow usage, and the server-side no-publish boundary.

set -euo pipefail

TUNNEL_BIN="/Users/nuzantara/.local/bin/tunnel-client"
MCP_BIN="/Users/nuzantara/nuzantara/apps/nuzantara-mcp/.venv/bin/nuzantara-mcp-workspace-marketing"
PROFILE_DIR="/Users/nuzantara/.config/tunnel-client"
KEY_DIR="$PROFILE_DIR/secrets"
KEY_FILE="$KEY_DIR/nuzantara-marketing-runtime-key"
ALIAS="nuzantara-marketing"
PROFILE="nuzantara-marketing"
QUEUE_PATH="/Users/nuzantara/nuzantara/apps/war-room/output/queue/human-review-queue.json"
STATE_DIR="/Users/nuzantara/.nuzantara/workspace-marketing"
TUNNEL_ID=""
WRITES_ENABLED="false"

usage() {
    printf 'Usage: %s --tunnel-id tunnel_... [--arm-writes]\n' "$0" >&2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --tunnel-id)
            [ "$#" -ge 2 ] || { usage; exit 64; }
            TUNNEL_ID="$2"
            shift 2
            ;;
        --arm-writes)
            WRITES_ENABLED="true"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 64
            ;;
    esac
done

if [ "$(hostname)" != "Nuzantara" ]; then
    printf 'This tunnel runtime must be configured on Pro (hostname Nuzantara).\n' >&2
    exit 69
fi
if [[ ! "$TUNNEL_ID" =~ ^tunnel_[A-Za-z0-9]{16,}$ ]]; then
    printf 'Invalid or missing tunnel id. Copy it from Platform tunnel settings.\n' >&2
    exit 64
fi
if [ ! -x "$TUNNEL_BIN" ]; then
    printf 'tunnel-client is not installed at %s\n' "$TUNNEL_BIN" >&2
    exit 69
fi
if [ ! -x "$MCP_BIN" ]; then
    printf 'Marketing MCP entrypoint is not installed at %s\n' "$MCP_BIN" >&2
    printf 'Run: cd /Users/nuzantara/nuzantara/apps/nuzantara-mcp && uv sync --extra test\n' >&2
    exit 69
fi
if ! grep -Eq '^(export[[:space:]]+)?NUZANTARA_WORKSPACE_MARKETING_API_KEY=' \
    /Users/nuzantara/.nuzantara-secrets.env 2>/dev/null; then
    printf 'Dedicated Nuzantara workspace marketing key is not provisioned on Pro.\n' >&2
    exit 78
fi

umask 077
mkdir -p "$PROFILE_DIR" "$KEY_DIR" "$STATE_DIR"
chmod 0700 "$PROFILE_DIR" "$KEY_DIR" "$STATE_DIR"
if [ ! -s "$KEY_FILE" ]; then
    printf 'Paste the dedicated Tunnels Read+Use runtime key (input is hidden): ' >&2
    IFS= read -r -s RUNTIME_KEY
    printf '\n' >&2
    if [ "${#RUNTIME_KEY}" -lt 20 ]; then
        printf 'Runtime key is empty or implausibly short; nothing was stored.\n' >&2
        exit 65
    fi
    KEY_TEMP=$(mktemp "$KEY_DIR/.runtime-key.XXXXXX")
    printf '%s' "$RUNTIME_KEY" > "$KEY_TEMP"
    chmod 0600 "$KEY_TEMP"
    mv "$KEY_TEMP" "$KEY_FILE"
    unset RUNTIME_KEY
fi
chmod 0600 "$KEY_FILE"

if [ "$WRITES_ENABLED" = "true" ]; then
    printf 'Type exactly ARM MARKETING WRITES to enable confirmed draft/generation actions: ' >&2
    IFS= read -r ARM_CONFIRMATION
    if [ "$ARM_CONFIRMATION" != "ARM MARKETING WRITES" ]; then
        printf 'Write arming cancelled. No runtime change was made.\n' >&2
        exit 65
    fi
fi

MCP_COMMAND="/usr/bin/env -i HOME=/Users/nuzantara LANG=en_US.UTF-8 PATH=/opt/homebrew/bin:/Users/nuzantara/.local/bin:/usr/local/bin:/usr/bin:/bin WORKSPACE_MARKETING_WRITES_ENABLED=$WRITES_ENABLED WORKSPACE_MARKETING_FLOW_DAILY_LIMIT=6 WORKSPACE_MARKETING_SOL_DAILY_LIMIT=4 WORKSPACE_MARKETING_SOL_MAX_ACTIVE=1 WORKSPACE_MARKETING_STATE_DIR=$STATE_DIR WR2_QUEUE_PATH=$QUEUE_PATH $MCP_BIN"

"$TUNNEL_BIN" runtimes connect \
    --alias "$ALIAS" \
    --profile "$PROFILE" \
    --profile-dir "$PROFILE_DIR" \
    --tunnel-id "$TUNNEL_ID" \
    --runtime-api-key "file:$KEY_FILE" \
    --mcp-command "$MCP_COMMAND" \
    --json

"$TUNNEL_BIN" runtimes status "$ALIAS" --json
