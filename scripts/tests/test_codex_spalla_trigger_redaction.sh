#!/usr/bin/env bash
# Guilt + innocence + mode for .claude/hooks/codex-spalla-trigger.sh's secret
# hygiene (cicatrix superscar #4 — secret in the clear).
#
# The defect this pins: the hook logs `tool_input.command` verbatim to
# ~/logs/codex-spalla-trigger.jsonl. Measured on the live file before the
# fix: 11 real `sk-ant-oat...` values, 108 chars each, mode 0644 (world-
# readable), never redacted. The fix added (a) `umask 077` + an explicit
# `chmod 0600` for a log that already existed at the old mode (`>>` does NOT
# change an existing file's mode), and (b) redaction of the secret VALUE
# before truncation, so the log is safe even if a later rotation/copy widens
# the mode again.
#
# Case 2 below is the load-bearing one: the ORIGINAL redactor (a version
# that never shipped past review) matched `TOKEN=` and missed
# `TOKEN_1=`/`TOKEN_5=` — that exact off-by-one is how real tokens were
# printed by a probe that believed it was redacting. The shipped regex
# closes it with a trailing `[A-Z0-9_]*` after the keyword. If this suffix
# guard ever regresses, this case must catch it.
#
# Method: run the REAL hook (not a reimplementation) with a temporary HOME
# per case, feed it a PostToolUse-shaped JSON payload on stdin via python3
# (so a secret-looking string never has to survive bash quoting), and
# inspect the resulting log file's content + mode.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/codex-spalla-trigger.sh"
fails=0
total=0

[ -f "$HOOK" ] || { echo "FAIL: hook missing at $HOOK"; exit 1; }

# run_hook <home_dir> <tool_name> <command_string>
# Feeds a minimal PostToolUse payload to the hook with HOME pointed at a
# scratch dir, so the hook's own $HOME/logs/... path lands there instead of
# the real ~/logs/.
run_hook() {
    local home="$1" tool="$2" cmd="$3"
    local payload
    payload="$(python3 -c '
import json, sys
tool, cmd = sys.argv[1], sys.argv[2]
print(json.dumps({"tool_name": tool, "tool_input": {"command": cmd}}))
' "$tool" "$cmd")"
    HOME="$home" bash "$HOOK" <<<"$payload" >/dev/null 2>&1
}

log_line() {  # log_line <home_dir> — last line of that HOME's log, if any
    local home="$1"
    tail -n1 "$home/logs/codex-spalla-trigger.jsonl" 2>/dev/null
}

case_result() {  # case_result <label> <0=pass|1=fail>
    local label="$1" ok="$2"
    total=$((total + 1))
    if [ "$ok" -eq 0 ]; then
        echo "PASS[$label]"
    else
        echo "FAIL[$label]"
        fails=$((fails + 1))
    fi
}

cleanup_dirs=()
# shellcheck disable=SC2329  # invoked indirectly via `trap cleanup EXIT` below
cleanup() {
    local d
    for d in "${cleanup_dirs[@]:-}"; do
        [ -n "$d" ] && rm -rf "$d"
    done
}
trap cleanup EXIT

# ───────────────────────────────────────────────────────────── GUILT ──

# 1. A live-shaped Anthropic OAuth token inside a Bash command — the exact
#    historical leak shape (11 of these, 108 chars, printed in cleartext).
tmp1="$(mktemp -d)"; cleanup_dirs+=("$tmp1")
TOKEN1="sk-ant-oat01-$(python3 -c 'import secrets; print(secrets.token_hex(48))')"  # 96 hex + prefix, 40+ chars
run_hook "$tmp1" "Bash" "echo hello && export X=$TOKEN1"
line1="$(log_line "$tmp1")"
ok=1
[ -n "$line1" ] && ! printf '%s' "$line1" | grep -qF -- "$TOKEN1" && ok=0
case_result "guilt-sk-ant-oat-token-not-in-log" "$ok"

# 2. SUFFIXED variable name — CLAUDE_CODE_OAUTH_TOKEN_5=, not the bare
#    TOKEN= a naive redactor would only catch. Load-bearing (see header).
tmp2="$(mktemp -d)"; cleanup_dirs+=("$tmp2")
run_hook "$tmp2" "Bash" "export CLAUDE_CODE_OAUTH_TOKEN_5=somesecretvalue123"
line2="$(log_line "$tmp2")"
ok=1
[ -n "$line2" ] && ! printf '%s' "$line2" | grep -qF -- "somesecretvalue123" && ok=0
case_result "guilt-suffixed-oauth-token-var-value-not-in-log" "$ok"

# 3. A GitHub PAT (ghp_...) embedded in a command (e.g. a remote URL).
tmp3="$(mktemp -d)"; cleanup_dirs+=("$tmp3")
GHTOKEN="ghp_$(python3 -c 'import secrets; print(secrets.token_hex(18))')"  # 36 hex, real PAT length
run_hook "$tmp3" "Bash" "git remote set-url origin https://x:$GHTOKEN@github.com/org/repo.git"
line3="$(log_line "$tmp3")"
ok=1
[ -n "$line3" ] && ! printf '%s' "$line3" | grep -qF -- "$GHTOKEN" && ok=0
case_result "guilt-github-pat-not-in-log" "$ok"

# ───────────────────────────────────────────────────────── INNOCENCE ──

# An ordinary command must survive INTACT — no redaction marker anywhere
# near it. This is the guard-over-match twin (cicatrix #3): a redactor
# broad enough to catch every guilt case above must not also eat innocent
# command text.
tmp4="$(mktemp -d)"; cleanup_dirs+=("$tmp4")
run_hook "$tmp4" "Bash" "gh pr create --title fix --body ok"
line4="$(log_line "$tmp4")"
ok=1
if printf '%s' "$line4" | grep -qF -- "gh pr create --title fix --body ok" \
    && ! printf '%s' "$line4" | grep -q "REDACTED"; then
    ok=0
fi
case_result "innocence-ordinary-command-intact-no-redacted-marker" "$ok"

# ──────────────────────────────────────────────────────────────── MODE ──

# A freshly created log must be born 0600 (umask 077), never 0644.
tmp5="$(mktemp -d)"; cleanup_dirs+=("$tmp5")
run_hook "$tmp5" "Bash" "echo fresh"
mode="$(python3 -c 'import os,sys;print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$tmp5/logs/codex-spalla-trigger.jsonl" 2>/dev/null \
    || stat -c '%a' "$tmp5/logs/codex-spalla-trigger.jsonl" 2>/dev/null)"
ok=1
[ "$mode" = "600" ] && ok=0
case_result "mode-fresh-log-is-0600-not-0644 (got: ${mode:-<unreadable>})" "$ok"

echo "---"
if [ "$fails" -eq 0 ]; then
    echo "PASS ($total cases: 3 guilt, 1 innocence, 1 mode)"
    exit 0
fi
echo "FAILED: $fails/$total"
exit 1
