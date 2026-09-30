#!/usr/bin/env bash
# test_cron_agent_no_git_commit_prompt.sh — the agent-tier prompt suffix in
# cron-agent.sh must forbid git mutations, the same way it already forbids
# backgrounding (W89). A fake `claude` records the prompt it actually receives,
# so this asserts on what reaches the CLI, not on the source text (grepping the
# script proves the sentence is written, not that run_agent() appends it).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"
[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/crongitprompt.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
FAILED=0
ok()  { echo "  ok   — $1"; }
bad() { echo "  FAIL — $1"; FAILED=1; }

PROMPT="$SANDBOX/prompt.txt"; echo "submit the daily indexing batch" > "$PROMPT"
ARGV_LOG="$SANDBOX/argv.txt"

# fake claude: dump the full argv (prompt is the last positional arg) and exit 0
cat > "$SANDBOX/claude" <<'FAKE'
#!/usr/bin/env bash
printf '%s' "$*" > "$ARGV_LOG"
echo "fake answer"
exit 0
FAKE
chmod +x "$SANDBOX/claude"
# fake timeout: drop the duration arg, exec the rest (macOS has no coreutils timeout)
cat > "$SANDBOX/timeout" <<'FAKE'
#!/usr/bin/env bash
shift
exec "$@"
FAKE
chmod +x "$SANDBOX/timeout"

: > "$ARGV_LOG"
env HOME="$SANDBOX" ARGV_LOG="$ARGV_LOG" \
    CRON_AGENT_CLAUDE_BIN="$SANDBOX/claude" CRON_AGENT_TIMEOUT_BIN="$SANDBOX/timeout" \
    CLAUDE_CODE_OAUTH_TOKEN_1=faketoken \
    TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= \
    bash "$WRAPPER" agent no-git-job "$PROMPT" > "$SANDBOX/stdout.txt" 2>"$SANDBOX/stderr.txt"
rc=$?
argv="$(cat "$ARGV_LOG" 2>/dev/null)"

if [ "$rc" != "0" ]; then
    bad "wrapper exited $rc (stderr: $(tail -5 "$SANDBOX/stderr.txt"))"
elif [[ "$argv" == *"Never run"*"git add"*"git commit"*"git push"* ]]; then
    ok "the received prompt forbids git add/commit/push"
else
    bad "the received prompt does not carry the anti-git-commit sentence (argv: ${argv: -400})"
fi

if [[ "$argv" == *"main checkout is agent-read-only"* ]]; then
    ok "the received prompt explains the main-checkout invariant"
else
    bad "the received prompt is missing the main-checkout-read-only rationale"
fi

echo
[ "$FAILED" -eq 0 ] && { echo "PASS — cron-agent anti-git-commit prompt sentence"; exit 0; } || { echo "FAIL"; exit 1; }
