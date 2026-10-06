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
    mode="$(stat -c '%a' "$HIST" 2>/dev/null || stat -f '%Lp' "$HIST" 2>/dev/null)"
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

# ---------------------------------------------------------------------------
# Cases 4-9: the redactor itself breaks — the log must fail CLOSED. Each case
# runs a COPY of the hook in a scratch dir with a stub redact_secrets.py beside
# it (or none), because the hook resolves the redactor next to itself. All
# command text is invented; RAW_MARKER must never reach command-history.log.
# ---------------------------------------------------------------------------
RAW_MARKER="zz-invented-raw-marker-4242"
BROKEN_CMD="echo ${RAW_MARKER} && curl -H 'X-Fake: not-a-real-value-0000' https://example.invalid"
HOOKCOPY="$WORK/hookcopy"

run_hook_copy() {
    # $1 = stub redactor mode: missing | real | python source text
    # $2 = command text. Sets: rc, out, elapsed
    rm -rf "$HOOKCOPY"
    mkdir -p "$HOOKCOPY"
    cp "$TARGET" "$HOOKCOPY/bash_call_log.sh"
    case "$1" in
        missing) ;;
        real) cp "$REPO_ROOT/infra/claude-hooks/redact_secrets.py" "$HOOKCOPY/redact_secrets.py" ;;
        *) printf '%s\n' "$1" > "$HOOKCOPY/redact_secrets.py" ;;
    esac
    payload="$(printf '{"tool_input":{"command":%s}}' "$(printf '%s' "$2" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")"
    t0="$(date +%s)"
    out="$(HOME="$WORK/home" TOOL_CALL="$payload" BASH_CALL_LOG_REDACT_TIMEOUT_S=1 bash "$HOOKCOPY/bash_call_log.sh" 2>/dev/null)"
    rc=$?
    elapsed=$(( $(date +%s) - t0 ))
}

assert_fail_closed() {
    # $1 = case label
    if [ "$rc" -eq 0 ] && [ -z "$out" ]; then
        note_pass "$1: hook exit 0 with empty stdout (contract unchanged)"
    else
        note_fail "$1: hook rc=$rc stdout=[$out]"
    fi
    if [ -f "$HIST" ] && ! grep -q "$RAW_MARKER" "$HIST"; then
        note_pass "$1: raw command NOT written to command-history.log"
    else
        note_fail "$1: raw command LEAKED into command-history.log"
    fi
    if [ -f "$HIST" ] && tail -1 "$HIST" | grep -q 'REDACTION-FAILED'; then
        note_pass "$1: placeholder line written instead"
    else
        note_fail "$1: no REDACTION-FAILED placeholder line"
    fi
    if [ -f "$RECEIVED" ] && grep -q "$RAW_MARKER" "$RECEIVED"; then
        note_pass "$1: hotfix pipe still receives the raw command"
    else
        note_fail "$1: hotfix pipe payload missing/changed"
    fi
}

setup_world
run_hook_copy missing "$BROKEN_CMD"
assert_fail_closed "redactor missing"

setup_world
run_hook_copy 'import sys; sys.exit(3)' "$BROKEN_CMD"
assert_fail_closed "redactor crashes"

setup_world
run_hook_copy 'import sys; sys.stdin.read()' "$BROKEN_CMD"
assert_fail_closed "redactor returns empty"

setup_world
run_hook_copy 'import sys; sys.stdout.write(sys.stdin.read()); sys.stdout.flush(); sys.exit(1)' "$BROKEN_CMD"
assert_fail_closed "redactor echoes input then fails"

setup_world
run_hook_copy 'import time; time.sleep(30)' "$BROKEN_CMD"
assert_fail_closed "redactor hangs"
if [ "$elapsed" -le 4 ]; then
    note_pass "redactor hangs: hook returned in ${elapsed}s (bounded)"
else
    note_fail "redactor hangs: hook took ${elapsed}s — a hung redactor stalls every Bash call"
fi

# A zero/garbage timeout must not disarm the bound (alarm(0) cancels it): the
# hook falls back to its default and still returns promptly.
for bad_t in 0 abc -5; do
    setup_world
    rm -rf "$HOOKCOPY"; mkdir -p "$HOOKCOPY"
    cp "$TARGET" "$HOOKCOPY/bash_call_log.sh"
    printf '%s\n' 'import time; time.sleep(30)' > "$HOOKCOPY/redact_secrets.py"
    payload="$(printf '{"tool_input":{"command":"echo %s"}}' "$RAW_MARKER")"
    t0="$(date +%s)"
    HOME="$WORK/home" TOOL_CALL="$payload" BASH_CALL_LOG_REDACT_TIMEOUT_S="$bad_t" bash "$HOOKCOPY/bash_call_log.sh" >/dev/null 2>&1
    elapsed=$(( $(date +%s) - t0 ))
    if [ "$elapsed" -le 5 ] && ! grep -q "$RAW_MARKER" "$HIST" && grep -q 'REDACTION-FAILED' "$HIST"; then
        note_pass "timeout=${bad_t}: default bound applies (${elapsed}s), placeholder logged"
    else
        note_fail "timeout=${bad_t}: elapsed=${elapsed}s or raw/placeholder wrong"
    fi
done

# Innocence: the same hook copy with the REAL redactor logs a plain command
# verbatim and a credential-bearing one redacted, never as a placeholder.
setup_world
run_hook_copy real "git status --short && ls -la infra/claude-hooks"
if [ -f "$HIST" ] && grep -q "git status --short && ls -la infra/claude-hooks" "$HIST" \
    && ! grep -q 'REDACTION-FAILED' "$HIST"; then
    note_pass "real redactor: plain command logged verbatim, no placeholder"
else
    note_fail "real redactor: plain command not logged verbatim: $(cat "$HIST" 2>/dev/null)"
fi
setup_world
run_hook_copy real "export AWS_SECRET_TOKEN=FAKEnotreal1234567890 && aws s3 ls"
if [ -f "$HIST" ] && ! grep -q "FAKEnotreal1234567890" "$HIST" && grep -q "REDACTED" "$HIST" \
    && ! grep -q 'REDACTION-FAILED' "$HIST"; then
    note_pass "real redactor: credential redacted by the redactor, not by the fallback"
else
    note_fail "real redactor: credential case wrong: $(cat "$HIST" 2>/dev/null)"
fi

echo ""
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
