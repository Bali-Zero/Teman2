#!/bin/sh
# test_bash_call_log.sh — guilt+innocence corpus for
# infra/claude-hooks/bash_call_log.sh (per-call-hook-diet, 2026-09-09).
#
# Runs the REAL script against a fake HOME, a stub hotfix-notify.sh (so we
# never touch the real Telegram/jsonl side-effects), and a controlled
# TOOL_CALL payload. Proves the three artifacts land in the expected format
# AND that a fake credential in the command is redacted in
# command-history.log while the (separate, unchanged) hotfix pipe still
# gets the raw command.
#
# Run:  sh scripts/tests/test_bash_call_log.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0
note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="$REPO_ROOT/infra/claude-hooks/bash_call_log.sh"

if [ ! -f "$TARGET" ]; then
    echo "FATAL: $TARGET not found"
    exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/test-bash-call-log.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

setup_world() {
    rm -rf "${WORK:?}/home"
    mkdir -p "$WORK/home/.claude/scripts"
    # Stub hotfix-notify.sh: records whatever JSON it receives on stdin,
    # never touches the network. This is what the ported pipe is graded
    # against — the real hotfix-notify.sh has its own test surface.
    cat > "$WORK/home/.claude/scripts/hotfix-notify.sh" <<'EOF'
#!/usr/bin/env bash
cat > "$HOME/.claude/hotfix-stub-received.json"
EOF
    chmod +x "$WORK/home/.claude/scripts/hotfix-notify.sh"
}

run_hook() {
    # $1 = command text to embed in TOOL_CALL
    payload="$(printf '{"tool_input":{"command":%s}}' "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")"
    HOME="$WORK/home" TOOL_CALL="$payload" PWD="$WORK/home" bash "$TARGET"
}

# ---------------------------------------------------------------------------
# Case 1: plain command — all three artifacts land, in the expected shapes.
# ---------------------------------------------------------------------------
setup_world
run_hook "echo hello world" >/dev/null 2>&1

HIST="$WORK/home/.claude/command-history.log"
if [ -f "$HIST" ] && grep -q "echo hello world" "$HIST"; then
    note_pass "command-history.log carries the plain command"
else
    note_fail "command-history.log missing or wrong content"
fi

if [ -f "$HIST" ]; then
    if head -1 "$HIST" | grep -qE '^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\] '; then
        note_pass "command-history.log line format matches [YYYY-MM-DD HH:MM:SS] <cmd>"
    else
        note_fail "command-history.log line format wrong: $(head -1 "$HIST")"
    fi
    mode="$(stat -f '%Lp' "$HIST" 2>/dev/null || stat -c '%a' "$HIST" 2>/dev/null)"
    if [ "$mode" = "600" ]; then
        note_pass "command-history.log is mode 0600"
    else
        note_fail "command-history.log mode is $mode, expected 600"
    fi
fi

STATUS="$WORK/home/.claude/live-status.json"
if [ -f "$STATUS" ] && python3 -c "
import json
d = json.load(open('$STATUS'))
assert d['tool'] == 'Bash', d
assert 'ts' in d and 'cwd' in d and 'git_branch' in d, d
"; then
    note_pass "live-status.json has ts/tool/cwd/git_branch with tool=Bash"
else
    note_fail "live-status.json missing or malformed: $(cat "$STATUS" 2>/dev/null)"
fi

RECEIVED="$WORK/home/.claude/hotfix-stub-received.json"
if [ -f "$RECEIVED" ] && python3 -c "
import json
d = json.load(open('$RECEIVED'))
assert d['cmd'] == 'echo hello world', d
assert 'cwd' in d, d
"; then
    note_pass "hotfix pipe receives {cmd,cwd} JSON with the raw command"
else
    note_fail "hotfix stub did not receive expected JSON: $(cat "$RECEIVED" 2>/dev/null)"
fi

# ---------------------------------------------------------------------------
# Case 2: a fake credential — redacted in command-history.log, but the
# hotfix pipe (unchanged, unredacted by design) still sees it raw so its
# own DROP/ALTER classifier is not blinded.
# ---------------------------------------------------------------------------
setup_world
FAKE_TOKEN="AKIAFAKEEXAMPLE1234567890"
run_hook "export AWS_SECRET_TOKEN=${FAKE_TOKEN} && aws s3 ls" >/dev/null 2>&1

if [ -f "$HIST" ] && ! grep -q "$FAKE_TOKEN" "$HIST"; then
    note_pass "command-history.log redacts the fake credential"
else
    note_fail "command-history.log LEAKED the fake credential: $(cat "$HIST" 2>/dev/null)"
fi

if [ -f "$HIST" ] && grep -q "REDACTED" "$HIST"; then
    note_pass "command-history.log carries the <REDACTED> marker"
else
    note_fail "command-history.log missing the <REDACTED> marker"
fi

if [ -f "$RECEIVED" ] && grep -q "$FAKE_TOKEN" "$RECEIVED"; then
    note_pass "hotfix pipe still receives the raw command (classifier not blinded)"
else
    note_fail "hotfix pipe payload was unexpectedly redacted/missing: $(cat "$RECEIVED" 2>/dev/null)"
fi

# ---------------------------------------------------------------------------
# Case 3: missing hotfix-notify.sh must not crash the hook (fail-open).
# ---------------------------------------------------------------------------
setup_world
rm -f "$WORK/home/.claude/scripts/hotfix-notify.sh"
if run_hook "echo still fine" >/dev/null 2>&1; then
    note_pass "hook exits 0 even when hotfix-notify.sh is missing"
else
    note_fail "hook exited non-zero when hotfix-notify.sh is missing"
fi
if [ -f "$HIST" ] && grep -q "echo still fine" "$HIST"; then
    note_pass "command-history.log still written when hotfix-notify.sh is missing"
else
    note_fail "command-history.log not written when hotfix-notify.sh is missing"
fi

echo ""
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
