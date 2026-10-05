#!/usr/bin/env bash
# test_cost_breaker_deadman.sh — falsifiable test for the P9 G5 dead-man's
# switch stale-detection logic (P2-5).
#
# FORCE_ALERT short-circuits the real stale logic in cost_breaker_deadman.sh, so
# the MISSING/STALE/FRESH classification had ZERO coverage. The `--classify`
# mode exposes that logic side-effect-free (no telegram, no state write). This
# test drives it through all three states + exit codes + injected `now`.
#
# Run:  bash scripts/test_cost_breaker_deadman.sh
# Exit: 0 all pass, 1 any failure.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEADMAN="$HERE/cost_breaker_deadman.sh"

fail=0
pass=0

# check <desc> <expected_out> <expected_code> -- <classify args...>
check() {
    local desc="$1" exp_out="$2" exp_code="$3"
    shift 4  # drop desc, exp_out, exp_code, and the literal "--"
    local out code
    out="$(bash "$DEADMAN" --classify "$@" 2>/dev/null)"
    code=$?
    if [[ "$out" == "$exp_out" && "$code" == "$exp_code" ]]; then
        pass=$((pass + 1))
        echo "ok   - $desc (out=$out code=$code)"
    else
        fail=$((fail + 1))
        echo "FAIL - $desc: expected out=$exp_out code=$exp_code, got out=$out code=$code"
    fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fresh_file="$tmpdir/fresh.json"
stale_file="$tmpdir/stale.json"
missing_file="$tmpdir/does-not-exist.json"

touch "$fresh_file"
# Make stale_file old (BSD touch -t: 2020-01-01 00:00).
touch -t 202001010000 "$stale_file"

# FRESH: just-touched file, generous threshold.
check "fresh file is FRESH" "FRESH" "0" -- "$fresh_file" 1800

# STALE: file from 2020, small threshold.
check "old file is STALE" "STALE" "1" -- "$stale_file" 60

# MISSING: file does not exist.
check "missing file is MISSING" "MISSING" "2" -- "$missing_file" 60

# Injected now: with now far in the future, even a fresh file is STALE
# (the injected clock is the comparison anchor — proves now is honored).
check "injected future now makes fresh file STALE" "STALE" "1" -- "$fresh_file" 100 9999999999

# Injected now == file mtime → age 0 → FRESH (boundary).
# Read mtime via Python (stat-flavour-independent — matches mtime_epoch in the
# script under test). `stat -f` on GNU is the *filesystem* flag and prints
# garbage rather than failing cleanly, which previously fed a non-numeric
# `now` into --classify and broke the boundary case on Linux CI.
fresh_mtime="$(python3 -c 'import os,sys; print(int(os.path.getmtime(sys.argv[1])))' "$fresh_file")"
check "injected now == mtime is FRESH (age 0)" "FRESH" "0" -- "$fresh_file" 0 "$fresh_mtime"

# --- The alert path, judged by the gateway's own verdict (FIXBATCH-C #6) ----
# tg_notify.py always exits 0 and names its verdict on stderr
# ("tg_notify: sent" / "p0_unsent_spooled" / "deduped" / ...). The cooldown may
# start only after a delivery the gateway reports as SENT. Sandbox: a copy of
# the dead-man next to a FAKE gateway that answers with the verdict we inject
# and counts its calls; HOME is a temp dir, so no real state, log, secret or
# Telegram is ever touched.
sb="$tmpdir/sandbox"
mkdir -p "$sb/scripts"
cp "$DEADMAN" "$sb/scripts/cost_breaker_deadman.sh"
cat > "$sb/scripts/tg_notify.py" <<'FAKEGW'
import os, sys
with open(os.environ["FAKE_TG_CALLS"], "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\n")
if os.environ.get("FAKE_TG_OUT"):
    sys.stderr.write(os.environ["FAKE_TG_OUT"] + "\n")
FAKEGW
calls="$sb/calls"
sdir="$sb/home/.agent/decisions/state"
cooldown="$sdir/cost_breaker_deadman.cooldown"
state="$sdir/cost_breaker_deadman.json"
dlog="$sb/home/logs/cost-breaker-deadman.log"
unsent=$'tg_notify: P0 unsendable (no token/relay) \xe2\x80\x94 spooled as p0_unsent\ntg_notify: p0_unsent_spooled'

reset_sb() { rm -rf "$sb/home" "$calls"; mkdir -p "$sb/home"; }
# run_tick <fake gateway stderr> [extra env...] — one FORCE_ALERT tick.
run_tick() {
    local out="$1"; shift
    env "$@" FAKE_TG_OUT="$out" FAKE_TG_CALLS="$calls" HOME="$sb/home" FORCE_ALERT=1 \
        bash "$sb/scripts/cost_breaker_deadman.sh" >/dev/null 2>&1
}
ncalls() { if [[ -f "$calls" ]]; then wc -l < "$calls" | tr -d ' '; else echo 0; fi; }
expect() {
    local desc="$1"; shift
    if "$@"; then pass=$((pass + 1)); echo "ok   - $desc"
    else fail=$((fail + 1)); echo "FAIL - $desc"; fi
}
state_field() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' "$state" "$1"
}

# Guilt: an undelivered P0 must not start the cooldown, must say so, and the
# very next tick must try again.
reset_sb
run_tick "$unsent"
expect "undelivered alert (p0_unsent_spooled) starts NO cooldown" test ! -e "$cooldown"
expect "state file names the undelivered verdict" test "$(state_field alert_undelivered)" = "p0_unsent_spooled"
expect "log says the alert was NOT delivered" grep -q 'alert NOT delivered' "$dlog"
run_tick "$unsent"
expect "the next tick retries the undelivered alert (2 gateway calls)" test "$(ncalls)" = "2"

# Guilt: the 2026-09-26 Pro shape — the gateway itself crashed (ENOSPC).
reset_sb
run_tick 'tg_notify: internal error ([Errno 28] No space left on device) — best-effort spooled'
expect "gateway internal error starts NO cooldown" test ! -e "$cooldown"
expect "gateway internal error is recorded as undelivered" test -n "$(state_field alert_undelivered)"
expect "a gateway that answered is not re-run on another python (1 call)" test "$(ncalls)" = "1"

# Guilt: "deduped" with no proof that the previous alert was delivered is the
# gateway muting its OWN failed attempt — not a delivery.
reset_sb
run_tick 'tg_notify: deduped'
expect "deduped without a delivered stamp starts NO cooldown" test ! -e "$cooldown"

# Guilt: a gateway that printed no verdict at all is not a delivery.
reset_sb
run_tick ''
expect "no gateway verdict starts NO cooldown" test ! -e "$cooldown"
n_py=0
for p in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do [[ -x "$p" ]] && n_py=$((n_py + 1)); done
expect "no verdict: each absolute python3 tried once, no more ($n_py calls)" test "$(ncalls)" = "$n_py"

# Guilt: no gateway anywhere is undelivered, and says so.
reset_sb
mv "$sb/scripts/tg_notify.py" "$sb/scripts/tg_notify.hidden"
run_tick 'tg_notify: sent'
mv "$sb/scripts/tg_notify.hidden" "$sb/scripts/tg_notify.py"
expect "no gateway starts NO cooldown" test ! -e "$cooldown"
expect "no gateway is recorded as undelivered" test "$(state_field alert_undelivered)" = "no_gateway"

# Guilt: an OLD delivered stamp must not launder a NEW failed attempt. The
# gateway stamps its dedup entry before it knows the send failed, so the tick
# after a failure answers "deduped"; that must still read as undelivered.
reset_sb
run_tick 'tg_notify: sent'
touch -t 202001010000 "$cooldown"
run_tick "$unsent"
expect "a failed attempt clears an older delivered stamp" test ! -e "$cooldown"
run_tick 'tg_notify: deduped'
expect "deduped after a failed attempt starts NO cooldown" test ! -e "$cooldown"
expect "deduped after a failed attempt is recorded as undelivered" test "$(state_field alert_undelivered)" = "deduped"

# Innocence: a SENT alert starts the cooldown and the next tick stays quiet.
reset_sb
run_tick 'tg_notify: sent'
expect "sent alert starts the cooldown" test -e "$cooldown"
expect "sent alert leaves no undelivered mark" test -z "$(state_field alert_undelivered)"
run_tick 'tg_notify: sent'
expect "cooldown holds the next tick (1 gateway call)" test "$(ncalls)" = "1"

# Innocence: after a delivered alert, the gateway muting the repeat ("deduped")
# re-arms the cooldown exactly as before.
touch -t 202001010000 "$cooldown"
run_tick 'tg_notify: deduped'
cd_age=$(( $(date +%s) - $(python3 -c 'import os,sys; print(int(os.path.getmtime(sys.argv[1])))' "$cooldown") ))
expect "deduped after a delivered alert re-arms the cooldown" test "$cd_age" -lt 600

# Innocence: the healthy tick is untouched — no gateway call, same state keys.
reset_sb
mkdir -p "$sdir"
touch "$sdir/verify_the_verifiers.json" "$sdir/sentinel_meta_watchdog.json" "$sdir/mcp_integrity.json"
FAKE_TG_CALLS="$calls" HOME="$sb/home" bash "$sb/scripts/cost_breaker_deadman.sh" >/dev/null 2>&1
expect "healthy tick calls no gateway" test "$(ncalls)" = "0"
expect "healthy tick state keys unchanged" test "$(python3 -c 'import json,sys; print(",".join(sorted(json.load(open(sys.argv[1])))))' "$state")" = "_writer,critical_threshold_s,detail,generated_at,status,ts"

# Guilt: the interpreter fallback. The REAL tg_alert body with its first
# interpreter replaced by one that cannot run the gateway; the second must be
# tried. Placeholders first, so a working python3 that IS /usr/bin/python3
# cannot itself be rewritten into the broken one.
reset_sb
printf '#!/bin/sh\nexit 1\n' > "$sb/broken_py"; chmod +x "$sb/broken_py"
good_py="$(python3 -c 'import sys; print(sys.executable)')"
{
    echo 'set -uo pipefail'
    echo "LOG_FILE=$sb/fallback.log"
    echo 'log() { printf "%s\n" "$*" >> "$LOG_FILE"; }'
    awk '/^tg_alert\(\) \{/,/^\}/' "$DEADMAN" \
        | sed -e 's#/usr/bin/python3#@BROKEN@#' -e 's#/opt/homebrew/bin/python3#@GOOD@#' \
        | sed -e "s#@BROKEN@#$sb/broken_py#" -e "s#@GOOD@#$good_py#"
    echo "tg_alert 'probe'"
} > "$sb/scripts/fallback_harness.sh"
FAKE_TG_OUT='tg_notify: sent' FAKE_TG_CALLS="$calls" HOME="$sb/home" bash "$sb/scripts/fallback_harness.sh" >/dev/null 2>&1
fb_rc=$?
expect "a broken first python3 falls through to the next one (gateway reached)" test "$(ncalls)" = "1"
expect "the fallback delivery is reported as delivered (rc 0)" test "$fb_rc" = "0"

echo "----"
echo "passed=$pass failed=$fail"
[[ "$fail" -eq 0 ]]
