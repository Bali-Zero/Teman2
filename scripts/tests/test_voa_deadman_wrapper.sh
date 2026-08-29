#!/usr/bin/env bash
# Corpus for infra/launchagents/wrappers/voa-deadman-wrapper.sh.
#
# WHY EXECUTE INSTEAD OF READ (superscar #2 / W107 — "cure one wrapper out
# of five and call the disease closed, because nobody RAN the other four"):
# a wrapper's VOICE — did it pick the right interpreter, did it capture the
# real exit code, did it map the payload's own state to the RIGHT organism
# status — is only provable by running it. This runs the REAL wrapper
# against the REAL payload (scripts/probes/voa_deadman.py), in a disposable
# HOME + a scratch Telegram spool (TG_DRY_RUN + TG_SPOOL_DIR), so nothing
# here ever touches the real ~/.organism state, the real ~/logs, or the
# network.
#
# mktemp DISCIPLINE (same house rule as scripts/tests/test_voa_probe_wrapper.sh):
# an unchecked mktemp failure continues with an empty path, and every
# subsequent operation on "$EMPTY/..." then fails for a completely
# unrelated reason. Every mktemp call in this file goes through
# require_tmpdir, which aborts the WHOLE corpus loudly on failure rather
# than let a hollow path corrupt every check downstream of it.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO/infra/launchagents/wrappers/voa-deadman-wrapper.sh"
PAYLOAD="$REPO/scripts/probes/voa_deadman.py"

PASS=0
FAIL=0

check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        printf '  PASS  %s\n' "$name"
        PASS=$((PASS + 1))
    else
        printf '  FAIL  %s — expected [%s], got [%s]\n' "$name" "$expected" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

check_contains() {
    local name="$1" haystack="$2" needle="$3"
    if printf '%s' "$haystack" | grep -qF "$needle"; then
        printf '  PASS  %s\n' "$name"
        PASS=$((PASS + 1))
    else
        printf '  FAIL  %s — expected to contain [%s]\n     got: %s\n' "$name" "$needle" "$haystack"
        FAIL=$((FAIL + 1))
    fi
}

CLEANUP_PATHS=()
cleanup_all() {
    local p
    for p in "${CLEANUP_PATHS[@]:-}"; do
        [ -n "$p" ] && rm -rf "$p"
    done
}
trap cleanup_all EXIT

require_tmpdir() {
    local d
    d="$(mktemp -d)" || { echo "FATAL: mktemp -d failed — cannot run this corpus"; exit 1; }
    [ -n "$d" ] && [ -d "$d" ] || { echo "FATAL: mktemp -d returned an unusable path: '$d'"; exit 1; }
    CLEANUP_PATHS+=("$d")
    printf '%s' "$d"
}

[ -f "$WRAPPER" ] || { echo "FATAL: wrapper not found at $WRAPPER"; exit 1; }
[ -f "$PAYLOAD" ] || { echo "FATAL: payload not found at $PAYLOAD"; exit 1; }

write_heartbeat() {  # write_heartbeat <path> <verdict> <age_seconds>
    local path="$1" verdict="$2" age="$3"
    local now ts_epoch
    now="$(python3 -c 'import time; print(int(time.time()))')"
    ts_epoch=$((now - age))
    cat > "$path" << JSONEOF
{"schema":1,"probe":"voa_journey","mode":"full","ts":"2026-08-29T00:00:00.000Z","ts_epoch":$ts_epoch,"verdict":"$verdict","reason":"test-fixture","latency_ms":{},"legs":{},"cleanup":{},"base_url":"https://balizero.com","probe_version":1}
JSONEOF
}

organism_field() {  # organism_field <json-line> <field>
    printf '%s' "$1" | sed -n "s/.*\"$2\":\"\\([^\"]*\\)\".*/\\1/p"
}

echo "== wrapper syntax parses under zsh (a syntax error is a silent dead organ) =="
if zsh -n "$WRAPPER" 2>/dev/null; then
    check "zsh -n WRAPPER" "0" "0"
else
    check "zsh -n WRAPPER" "0" "1"
fi

echo "== guilt: G5 kill switch skips the tick and writes status=disabled, never invokes the payload =="
HOME_DIR="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HB="$HOME_DIR/logs/voa-probe-heartbeat.json"
write_heartbeat "$HB" "fail" 0
HOME="$HOME_DIR" VOA_DEADMAN_ENABLED=false /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
check "kill switch exit code" "0" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check "kill switch organism status" "disabled" "$(organism_field "$hb_json" status)"

echo "== innocence: fresh verdict=pass -> healthy, exit 0, organism=ok, no telegram =="
HOME_DIR="$(require_tmpdir)"
SPOOL="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HB="$HOME_DIR/logs/voa-probe-heartbeat.json"
write_heartbeat "$HB" "pass" 5
HOME="$HOME_DIR" TG_DRY_RUN=1 TG_SPOOL_DIR="$SPOOL" /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
check "fresh pass exit code" "0" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check "fresh pass organism status" "ok" "$(organism_field "$hb_json" status)"
check_contains "fresh pass organism note names the state" "$hb_json" "healthy_pass"
[ -f "$SPOOL/sent-dry.jsonl" ] && check "fresh pass sent NO telegram" "no-file-expected" "unexpected-file-present" \
    || check "fresh pass sent NO telegram" "no-file-expected" "no-file-expected"

echo "== innocence: fresh verdict=dark -> healthy, organism=ok (pre-launch NORMAL, not degraded) =="
HOME_DIR="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HB="$HOME_DIR/logs/voa-probe-heartbeat.json"
write_heartbeat "$HB" "dark" 5
HOME="$HOME_DIR" TG_DRY_RUN=1 TG_SPOOL_DIR="$(require_tmpdir)" /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
check "fresh dark exit code" "0" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check "fresh dark organism status" "ok" "$(organism_field "$hb_json" status)"

echo "== guilt: verdict=fail -> fire, exit 1, organism=error/fire_fail, telegram sent+confirmed =="
HOME_DIR="$(require_tmpdir)"
SPOOL="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HB="$HOME_DIR/logs/voa-probe-heartbeat.json"
write_heartbeat "$HB" "fail" 5
HOME="$HOME_DIR" TG_DRY_RUN=1 TG_SPOOL_DIR="$SPOOL" /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
check "verdict=fail exit code" "1" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check "verdict=fail organism status" "error" "$(organism_field "$hb_json" status)"
check_contains "verdict=fail organism note names fire_fail" "$hb_json" "fire_fail"
sent="$(cat "$SPOOL/sent-dry.jsonl" 2>/dev/null || true)"
check_contains "verdict=fail telegram enumerates GARUDA_XENDIT_CALLBACK_TOKEN" "$sent" "GARUDA_XENDIT_CALLBACK_TOKEN"
check_contains "verdict=fail telegram enumerates GARUDA_PUBLIC_ENABLED" "$sent" "GARUDA_PUBLIC_ENABLED"
check_contains "verdict=fail log mentions RESTART" "$(cat "$HOME_DIR/logs/voa-deadman.log")" "RESTART"

echo "== guilt: stale heartbeat -> fire, exit 1, organism=error/fire_silence_stale (distinct note from fire_fail) =="
HOME_DIR="$(require_tmpdir)"
SPOOL="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HB="$HOME_DIR/logs/voa-probe-heartbeat.json"
write_heartbeat "$HB" "pass" 2000
HOME="$HOME_DIR" TG_DRY_RUN=1 TG_SPOOL_DIR="$SPOOL" /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
check "stale heartbeat exit code" "1" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check "stale heartbeat organism status" "error" "$(organism_field "$hb_json" status)"
check_contains "stale heartbeat organism note names fire_silence_stale" "$hb_json" "fire_silence_stale"

echo "== guilt: missing heartbeat file -> fire, exit 1, organism note names fire_silence_absent =="
HOME_DIR="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HOME="$HOME_DIR" TG_DRY_RUN=1 TG_SPOOL_DIR="$(require_tmpdir)" \
    VOA_PROBE_HEARTBEAT="$HOME_DIR/logs/does-not-exist.json" \
    /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
check "missing heartbeat exit code" "1" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check_contains "missing heartbeat organism note names fire_silence_absent" "$hb_json" "fire_silence_absent"

echo "== guilt: missing payload -> FATAL exit 2, organism=error (payload temporarily hidden) =="
HOME_DIR="$(require_tmpdir)"
mkdir -p "$HOME_DIR/logs" "$HOME_DIR/.organism/last_seen"
HIDE_TO="$(require_tmpdir)/voa_deadman.py.hidden"
mv "$PAYLOAD" "$HIDE_TO"
HOME="$HOME_DIR" /bin/zsh "$WRAPPER" >/dev/null 2>&1
rc=$?
mv "$HIDE_TO" "$PAYLOAD"
check "missing payload exit code" "2" "$rc"
hb_json="$(cat "$HOME_DIR/.organism/last_seen/mini.voa_deadman.json" 2>/dev/null || true)"
check "missing payload organism status" "error" "$(organism_field "$hb_json" status)"
[ -f "$PAYLOAD" ] || { echo "FATAL: payload restoration failed — repo is now missing $PAYLOAD"; exit 1; }

echo "== structural: no zsystem flock INVOCATION anywhere (G10 deliberately not taken) =="
# The wrapper's own header PROSE mentions "zsystem flock" by name (explaining
# the defect it does not repeat) -- a bare substring grep would match that
# comment and false-positive here (the exact guard-over-match class this
# corpus's own house discipline warns against). Strip full-line `#` comments
# first, then look for a REAL invocation (the `zsystem flock -t` shape every
# other wrapper in this repo actually uses to take the lock).
non_comment_lines="$(grep -v '^\s*#' "$WRAPPER")"
if printf '%s' "$non_comment_lines" | grep -q "zsystem flock"; then
    check "no flock invocation in wrapper" "absent" "present"
else
    check "no flock invocation in wrapper" "absent" "absent"
fi
# And the reasoning MUST still be documented somewhere in the file (the
# innocence half of this same check: absence of the invocation should be a
# deliberate, explained choice, not a silent gap).
check_contains "flock omission is explained in the header" "$(cat "$WRAPPER")" "DELIBERATELY NOT TAKEN"

echo ""
echo "TOTAL: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
