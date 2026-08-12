#!/usr/bin/env bash
# test_cron_agent_context_diet.sh — P1 (context diet flags) + P2 (no-op suppression)
# in cron-agent.sh's agent tier. A fake `claude` records the argv it was invoked
# with, so the test asserts on what the wrapper ACTUALLY passes, not on the source
# text (grepping the script for a flag proves the flag is written, not that it
# reaches the CLI — the whole point of P1 is what the process receives).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"
[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/crondiet.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
FAILED=0
ok()  { echo "  ok   — $1"; }
bad() { echo "  FAIL — $1"; FAILED=1; }

PROMPT="$SANDBOX/prompt.txt"; echo "say hello" > "$PROMPT"
ARGV_LOG="$SANDBOX/argv.txt"
CALL_LOG="$SANDBOX/calls.log"

# fake claude: append argv, print an answer, exit 0
cat > "$SANDBOX/claude" <<'FAKE'
#!/usr/bin/env bash
# One marker line per invocation. NEVER count lines of the argv dump: the prompt
# is multi-line, so `wc -l` on it counts the PROMPT's newlines and reports five
# calls where there was one (measured 2026-08-12 — the probe measured itself).
echo CALL >> "$CALL_LOG"
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
# fake claude that FAILS (for the "no fingerprint on failure" case)
cat > "$SANDBOX/claude_fail" <<'FAKE'
#!/usr/bin/env bash
echo CALL >> "$CALL_LOG"
printf '%s' "$*" > "$ARGV_LOG"
echo "boom" >&2
exit 9
FAKE
chmod +x "$SANDBOX/claude_fail"

run_agent_job() {  # $1=job name, $2=claude bin, rest = extra env assignments
    local job="$1" bin="$2"; shift 2
    : > "$ARGV_LOG"; : > "$CALL_LOG"
    env HOME="$SANDBOX" ARGV_LOG="$ARGV_LOG" CALL_LOG="$CALL_LOG" \
        CRON_AGENT_CLAUDE_BIN="$bin" CRON_AGENT_TIMEOUT_BIN="$SANDBOX/timeout" \
        CLAUDE_CODE_OAUTH_TOKEN_1=faketoken \
        TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= \
        "$@" \
        bash "$WRAPPER" agent "$job" "$PROMPT" > "$SANDBOX/stdout.txt" 2>"$SANDBOX/stderr.txt"
    echo $?
}

# ── P1.1 guilt: the diet flags reach the CLI by default ──────────────────────
rc=$(run_agent_job diet-on "$SANDBOX/claude")
argv="$(cat "$ARGV_LOG" 2>/dev/null)"
if [ "$rc" = "0" ] && [[ "$argv" == *"--disable-slash-commands"* && "$argv" == *"--exclude-dynamic-system-prompt-sections"* ]]; then
    ok "default: both diet flags passed to claude"
else
    bad "default: flags missing (rc=$rc) argv='${argv:0:160}'"
fi

# ── P1.2 innocence: the kill switch removes them, everything else survives ───
rc=$(run_agent_job diet-off "$SANDBOX/claude" CRON_AGENT_CONTEXT_DIET=0)
argv="$(cat "$ARGV_LOG" 2>/dev/null)"
if [ "$rc" = "0" ] && [[ "$argv" != *"--disable-slash-commands"* && "$argv" == *"--permission-mode"* && "$argv" == *"--max-budget-usd"* ]]; then
    ok "CRON_AGENT_CONTEXT_DIET=0: diet flags gone, existing flags intact"
else
    bad "kill switch: got rc=$rc argv='${argv:0:160}'"
fi

# ── P2.1 guilt: unchanged fingerprint => claude is NEVER invoked ─────────────
rc=$(run_agent_job noop-job "$SANDBOX/claude" CRON_AGENT_SKIP_IF_UNCHANGED="echo CONSTANT")
first_calls=$(wc -l < "$CALL_LOG" | tr -d " ")
rc2=$(run_agent_job noop-job "$SANDBOX/claude" CRON_AGENT_SKIP_IF_UNCHANGED="echo CONSTANT")
second_calls=$(wc -l < "$CALL_LOG" | tr -d ' ')
if [ "$rc" = "0" ] && [ "$first_calls" = "1" ] && [ "$rc2" = "0" ] && [ "$second_calls" = "0" ]; then
    ok "unchanged input: 1st run invokes claude, 2nd run skips it entirely"
else
    bad "no-op: run1(rc=$rc calls=$first_calls) run2(rc=$rc2 calls=$second_calls) — want 1 then 0"
fi

# ── P2.2 innocence: a CHANGED fingerprint must still run ─────────────────────
rc=$(run_agent_job changed-job "$SANDBOX/claude" CRON_AGENT_SKIP_IF_UNCHANGED="echo V1")
rc2=$(run_agent_job changed-job "$SANDBOX/claude" CRON_AGENT_SKIP_IF_UNCHANGED="echo V2")
calls=$(wc -l < "$CALL_LOG" | tr -d ' ')
if [ "$rc2" = "0" ] && [ "$calls" = "1" ]; then
    ok "changed input: agent runs again"
else
    bad "changed input: rc2=$rc2 calls=$calls — want the agent to run"
fi

# ── P2.3 innocence: fingerprint command that FAILS must fail-open (run) ──────
rc=$(run_agent_job failopen-job "$SANDBOX/claude" CRON_AGENT_SKIP_IF_UNCHANGED="exit 3")
calls=$(wc -l < "$CALL_LOG" | tr -d ' ')
if [ "$rc" = "0" ] && [ "$calls" = "1" ]; then
    ok "fingerprint command fails: fail-open, agent still runs"
else
    bad "fail-open: rc=$rc calls=$calls — want the agent to run"
fi

# ── P2.4 the sharp one: a FAILED run must NOT store the fingerprint, so the
#        next tick still does the work (never skip work that never happened) ──
rc=$(run_agent_job failstore-job "$SANDBOX/claude_fail" CRON_AGENT_SKIP_IF_UNCHANGED="echo SAME")
rc2=$(run_agent_job failstore-job "$SANDBOX/claude" CRON_AGENT_SKIP_IF_UNCHANGED="echo SAME")
calls=$(wc -l < "$CALL_LOG" | tr -d ' ')
if [ "$calls" = "1" ]; then
    ok "failed run stores no fingerprint: next tick re-runs the work"
else
    bad "failed-run fingerprint: 2nd tick calls=$calls (rc1=$rc rc2=$rc2) — want 1 (must NOT skip)"
fi

echo
[ "$FAILED" -eq 0 ] && { echo "PASS — cron-agent context diet + no-op suppression"; exit 0; } || { echo "FAIL"; exit 1; }
