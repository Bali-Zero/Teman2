#!/usr/bin/env bash
# hotfix-notify.sh
#
# Invoked from the PostToolUse hook when Claude runs a `fly ssh console -C`
# with DDL/DML against prod, or any other "hotfix"-shaped command. Logs to
# shared/hotfix_audit.jsonl AND sends a Telegram message to Zero so he sees
# in real-time what happened in prod, without having to confirm the action.
#
# Contract: see AUTONOMOUS_OPS.md §"Guardrails that make this safe".
# The notifier is the REAL safety layer for L2 — autonomy without visibility
# would be unsafe; autonomy with instant Telegram visibility is OK.
#
# Env required (loaded from ~/.nuzantara-secrets.env if available):
#   TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID (or TELEGRAM_ZERO_CHAT_ID)
#
# Stdin: a JSON blob with {cmd, cwd, result_snippet} (from the hook).

set -u -o pipefail

# Load secrets if present (harmless if absent — will no-op on send)
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
  set +a
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-}}}"

# Parse input (JSON from hook, or fall back to arg)
INPUT="${1:-}"
if [ -z "$INPUT" ]; then
  INPUT="$(cat)"
fi

CMD="$(echo "$INPUT" | /usr/bin/jq -r '.cmd // ""' 2>/dev/null)"
CWD="$(echo "$INPUT" | /usr/bin/jq -r '.cwd // ""' 2>/dev/null)"
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
TS_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Classify: is this actually a hotfix? (Claude's Bash hook feeds us every
# command; we want to notify only prod-affecting ones.)
IS_HOTFIX=0
if echo "$CMD" | grep -qE 'fly ssh console.*-C.*(ALTER|DROP|DELETE|UPDATE|INSERT|TRUNCATE|CREATE)' ; then
  IS_HOTFIX=1
elif echo "$CMD" | grep -qE 'fly ssh .+(asyncpg|psycopg|psql)' ; then
  IS_HOTFIX=1
elif echo "$CMD" | grep -qE 'fly secrets set' ; then
  IS_HOTFIX=1
elif echo "$CMD" | grep -qE 'fly machines (restart|destroy|stop)' ; then
  IS_HOTFIX=1
fi

if [ "$IS_HOTFIX" -eq 0 ]; then
  exit 0
fi

# Log to repo-local audit file (searchable, version-controlled as artifact).
REPO_ROOT="$(git -C "$CWD" rev-parse --show-toplevel 2>/dev/null || echo "$HOME/Desktop/nuzantara")"
AUDIT_DIR="$REPO_ROOT/shared"
mkdir -p "$AUDIT_DIR" 2>/dev/null
AUDIT_FILE="$AUDIT_DIR/hotfix_audit.jsonl"

/usr/bin/jq -nc \
  --arg ts "$TS_UTC" \
  --arg session "$SESSION_ID" \
  --arg cmd "$CMD" \
  --arg cwd "$CWD" \
  '{ts:$ts, session:$session, cmd:$cmd, cwd:$cwd, follow_up_pr: null}' \
  >> "$AUDIT_FILE" 2>/dev/null || true

# Send Telegram if credentials are present.
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
  exit 0
fi

# Truncate command in message body (Telegram has a 4096 char limit).
SHORT_CMD="$(echo "$CMD" | head -c 1500)"

MSG="🛠️ HOTFIX (Claude, autonomous L2)
ts: $TS_UTC
session: $SESSION_ID

cmd:
\`\`\`
$SHORT_CMD
\`\`\`

audit: $AUDIT_FILE
→ follow-up PR required within 1h (enforced by hook)"

# Fire-and-forget, timeout short so we never block the user's shell.
curl -s --max-time 4 \
  -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="Markdown" \
  --data-urlencode "text=${MSG}" \
  > /dev/null 2>&1 || true

exit 0
