#!/usr/bin/env bash
# Guilt + innocence + mode for .claude/hooks/codex-spalla-trigger.sh's secret
# hygiene (cicatrix superscar #4 — secret in the clear).
#
# The defect this pins: the hook logs `tool_input.command` verbatim to
# ~/logs/codex-spalla-trigger.jsonl. Measured on the live file before the
# fix, mode 0644 (world-readable), never redacted: 14 lines match the
# literal `sk-ant-oat`, and the run-length histogram (8x10, 5x13, 1x46,
# 1x87, 1x108) says 3 of those runs carry secret material -- 1 whole token
# (the 108-char run, ending well inside the 200-char field) plus 2
# truncation-clipped partials (the 87-char and 46-char runs, each ending
# EXACTLY at the 200-char truncation boundary, measured by end POSITION not
# by length alone). An earlier draft of this header said "11 values, 108
# chars each" (a LINE count read as a VALUE count); a later draft said "2
# whole tokens" (a truncation artifact read as two more complete secrets).
# Both corrected by the Gear-3 gate. The fix added (a) `umask 077` + an
# explicit `chmod 0600` for a log that already existed at the old mode
# (`>>` does NOT change an existing file's mode), and (b) redaction of the
# secret VALUE before truncation, so the log is safe even if a later
# rotation/copy widens the mode again.
#
# Case 2 below is the load-bearing one: the ORIGINAL redactor (a version
# that never shipped past review) matched `TOKEN=` and missed
# `TOKEN_1=`/`TOKEN_5=` — that exact off-by-one is how real tokens were
# printed by a probe that believed it was redacting. Case 3b is the MIRROR
# off-by-one, found by the Gear-3 gate on this very diff: a first fix
# required >=1 char BEFORE the keyword, so it caught `TOKEN_1=` but missed a
# bare `TOKEN=`. The SHIPPED regex closes both directions the same way: the
# keyword must be a SEGMENT — delimited by `_`/`-`/string-start on the left
# (enforced by a negative lookbehind that also excludes a preceding `.`, so
# `foo.key = x` attribute access stays innocent) and by `_`/`-`/string-end
# on the right (so `keyfile=`/`KEYSPACE=`/`monkey=` do NOT match — "key" is
# not a delimited segment in any of those). A separate rule (3) in the hook
# catches `Authorization: Bearer <value>`, which carries no keyword in a
# variable NAME at all and so cannot be caught by the assignment-shaped rule
# above.
#
# The INNOCENCE corpus below is the gate's other central finding: the suite
# shipped with 10 guilt cases and only ONE innocence case, for a matcher
# that had just been WIDENED to substring-anywhere. Guilt cases without a
# matching innocence corpus is not proof the widening is safe (cicatrix #3,
# guard-over-match). Each innocence case below is a form that LOOKS like it
# should trip the keyword (contains TOKEN/KEY/SECRET/etc as a substring,
# with an `=`/`:` somewhere in the command) but must NOT be redacted,
# because the keyword is not a delimited segment in that form.
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
guilt_n=0
innocence_n=0
mode_n=0

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

case_result() {  # case_result <label> <0=pass|1=fail> <category: guilt|innocence|mode>
    local label="$1" ok="$2" category="${3:?category required}"
    total=$((total + 1))
    case "$category" in
        guilt) guilt_n=$((guilt_n + 1)) ;;
        innocence) innocence_n=$((innocence_n + 1)) ;;
        mode) mode_n=$((mode_n + 1)) ;;
        *) echo "FAIL: unknown case_result category '$category' for [$label]"; fails=$((fails + 1)); return ;;
    esac
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
#    historical leak shape (one 108-char run in the live log, cleartext).
tmp1="$(mktemp -d)"; cleanup_dirs+=("$tmp1")
TOKEN1="sk-ant-oat01-$(python3 -c 'import secrets; print(secrets.token_hex(48))')"  # 96 hex + prefix, 40+ chars
run_hook "$tmp1" "Bash" "echo hello && export X=$TOKEN1"
line1="$(log_line "$tmp1")"
ok=1
[ -n "$line1" ] && ! printf '%s' "$line1" | grep -qF -- "$TOKEN1" && ok=0
case_result "guilt-sk-ant-oat-token-not-in-log" "$ok" guilt

# 2. SUFFIXED variable name — CLAUDE_CODE_OAUTH_TOKEN_5=, not the bare
#    TOKEN= a naive redactor would only catch. Load-bearing (see header).
tmp2="$(mktemp -d)"; cleanup_dirs+=("$tmp2")
run_hook "$tmp2" "Bash" "export CLAUDE_CODE_OAUTH_TOKEN_5=somesecretvalue123"
line2="$(log_line "$tmp2")"
ok=1
[ -n "$line2" ] && ! printf '%s' "$line2" | grep -qF -- "somesecretvalue123" && ok=0
case_result "guilt-suffixed-oauth-token-var-value-not-in-log" "$ok" guilt

# 3. A GitHub PAT (ghp_...) embedded in a command (e.g. a remote URL).
tmp3="$(mktemp -d)"; cleanup_dirs+=("$tmp3")
GHTOKEN="ghp_$(python3 -c 'import secrets; print(secrets.token_hex(18))')"  # 36 hex, real PAT length
run_hook "$tmp3" "Bash" "git remote set-url origin https://x:$GHTOKEN@github.com/org/repo.git"
line3="$(log_line "$tmp3")"
ok=1
[ -n "$line3" ] && ! printf '%s' "$line3" | grep -qF -- "$GHTOKEN" && ok=0
case_result "guilt-github-pat-not-in-log" "$ok" guilt

# 3b. PREFIX off-by-one — the twin of case 2, found by the Gear-3 gate on
#     this very diff. The first shipped regex required at least one char
#     BEFORE the keyword (`[A-Z][A-Z0-9_]*TOKEN`), so it caught
#     CLAUDE_CODE_OAUTH_TOKEN_1= and MISSED a bare TOKEN=. Closing a suffix
#     off-by-one while opening a prefix one is the same family (#3), so each
#     of these forms gets its own case rather than one representative.
for _form in \
    'export TOKEN=barePrefixSecret001' \
    'export KEY=barePrefixSecret002' \
    'SECRET=barePrefixSecret003' \
    'export PASSWORD=barePrefixSecret004' \
    'export my_token=lowercaseNameSecret005' \
    'curl --token=flagFormSecret006'
do
    _tmp="$(mktemp -d)"; cleanup_dirs+=("$_tmp")
    _needle="$(printf '%s' "$_form" | sed 's/.*=//')"
    run_hook "$_tmp" "Bash" "$_form"
    _line="$(log_line "$_tmp")"
    ok=1
    [ -n "$_line" ] && ! printf '%s' "$_line" | grep -qF -- "$_needle" && ok=0
    case_result "guilt-prefix-and-form-variant-not-in-log [${_form%%=*}=]" "$ok" guilt
done

# 3c. Header form: a secret after a colon inside a quoted -H argument. Not a
#     shell assignment at all, which is why the assignment-only branch of the
#     regex missed it before.
tmp3c="$(mktemp -d)"; cleanup_dirs+=("$tmp3c")
run_hook "$tmp3c" "Bash" 'curl -H "X-API-Key: headerFormSecret007" https://example.test'
line3c="$(log_line "$tmp3c")"
ok=1
[ -n "$line3c" ] && ! printf '%s' "$line3c" | grep -qF -- "headerFormSecret007" && ok=0
case_result "guilt-header-form-secret-not-in-log" "$ok" guilt

# 4. Bearer/Authorization — carries no keyword in a variable NAME at all, so
#    the assignment-shaped rule above (cases 1-3c) cannot see it. Only rule 3
#    in the hook (a dedicated Bearer/Authorization pattern) catches this.
tmp4g="$(mktemp -d)"; cleanup_dirs+=("$tmp4g")
run_hook "$tmp4g" "Bash" 'curl -H "Authorization: Bearer abcdefgh12345678" https://x'
line4g="$(log_line "$tmp4g")"
ok=1
[ -n "$line4g" ] && ! printf '%s' "$line4g" | grep -qF -- "abcdefgh12345678" && ok=0
case_result "guilt-bearer-token-not-in-log" "$ok" guilt

# ───────────────────────────────────────────────────────── INNOCENCE ──

# An ordinary command must survive INTACT — no redaction marker anywhere
# near it. This is the guard-over-match twin (cicatrix #3): a redactor
# broad enough to catch every guilt case above must not also eat innocent
# command text. Each form below contains a keyword substring (TOKEN, KEY,
# SECRET, ...) that a naive `if "keyword" in text` guard, or the ORIGINAL
# any-substring regex this diff narrowed, would have wrongly redacted.

assert_intact() {  # assert_intact <label> <home_dir> <expected substring>
    local label="$1" home="$2" needle="$3"
    local line ok
    line="$(log_line "$home")"
    ok=1
    if printf '%s' "$line" | grep -qF -- "$needle" \
        && ! printf '%s' "$line" | grep -q "REDACTED"; then
        ok=0
    fi
    case_result "$label" "$ok" innocence
}

tmp_i1="$(mktemp -d)"; cleanup_dirs+=("$tmp_i1")
run_hook "$tmp_i1" "Bash" 'gh pr create --title "monkey=patch"'
assert_intact "innocence-monkey-patch-key-substring-not-a-segment" "$tmp_i1" 'monkey=patch'

tmp_i2="$(mktemp -d)"; cleanup_dirs+=("$tmp_i2")
run_hook "$tmp_i2" "Bash" 'openssl x509 --keyfile=/etc/x.pem'
assert_intact "innocence-keyfile-flag-key-not-delimited-on-right" "$tmp_i2" 'openssl x509 --keyfile=/etc/x.pem'

tmp_i3="$(mktemp -d)"; cleanup_dirs+=("$tmp_i3")
run_hook "$tmp_i3" "Bash" "jq '.key = 1' data.json"
assert_intact "innocence-jq-dot-key-attribute-access" "$tmp_i3" "jq '.key = 1' data.json"

tmp_i4="$(mktemp -d)"; cleanup_dirs+=("$tmp_i4")
run_hook "$tmp_i4" "Bash" 'ssh -o StrictHostKeyChecking=no pro'
assert_intact "innocence-stricthostkeychecking-camelcase-no-delimiter" "$tmp_i4" 'ssh -o StrictHostKeyChecking=no pro'

tmp_i5="$(mktemp -d)"; cleanup_dirs+=("$tmp_i5")
run_hook "$tmp_i5" "Bash" 'sed -i "s/keyword=old/keyword=new/" f.txt'
assert_intact "innocence-sed-keyword-key-not-delimited-on-right" "$tmp_i5" 's/keyword=old/keyword=new/'

tmp_i6="$(mktemp -d)"; cleanup_dirs+=("$tmp_i6")
run_hook "$tmp_i6" "Bash" 'docker run -e KEYSPACE=prod myimg'
assert_intact "innocence-keyspace-env-name-key-not-delimited-on-right" "$tmp_i6" 'docker run -e KEYSPACE=prod myimg'

tmp_i7="$(mktemp -d)"; cleanup_dirs+=("$tmp_i7")
run_hook "$tmp_i7" "Bash" 'npm run build -- --publicKeyPath=./pub.pem'
assert_intact "innocence-publickeypath-camelcase-no-delimiter" "$tmp_i7" 'npm run build -- --publicKeyPath=./pub.pem'

tmp_i8="$(mktemp -d)"; cleanup_dirs+=("$tmp_i8")
run_hook "$tmp_i8" "Bash" "redis-cli KEYS '*'"
assert_intact "innocence-redis-keys-command-name-no-assignment" "$tmp_i8" "redis-cli KEYS '*'"

tmp_i9="$(mktemp -d)"; cleanup_dirs+=("$tmp_i9")
run_hook "$tmp_i9" "Bash" "gh pr create --title fix --body ok"
assert_intact "innocence-ordinary-command-intact-no-redacted-marker" "$tmp_i9" "gh pr create --title fix --body ok"

# ──────────────────────────────────────────────────────────────── MODE ──

# A freshly created log must be born 0600 (umask 077), never 0644.
tmp5="$(mktemp -d)"; cleanup_dirs+=("$tmp5")
run_hook "$tmp5" "Bash" "echo fresh"
mode="$(python3 -c 'import os,sys;print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$tmp5/logs/codex-spalla-trigger.jsonl" 2>/dev/null \
    || stat -c '%a' "$tmp5/logs/codex-spalla-trigger.jsonl" 2>/dev/null)"
ok=1
[ "$mode" = "600" ] && ok=0
case_result "mode-fresh-log-is-0600-not-0644 (got: ${mode:-<unreadable>})" "$ok" mode

echo "---"
if [ "$fails" -eq 0 ]; then
    echo "PASS ($total cases: $guilt_n guilt, $innocence_n innocence, $mode_n mode)"
    exit 0
fi
echo "FAILED: $fails/$total"
exit 1
