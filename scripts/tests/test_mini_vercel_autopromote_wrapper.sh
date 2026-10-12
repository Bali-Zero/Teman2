#!/bin/bash
# Corpus for infra/launchagents/wrappers/mini-vercel-autopromote.sh
#
# WHY A FAKE WORLD AND NOT A REAL RUN
# W107's lesson, paid for by curing one wrapper out of five and calling the disease closed: a
# wrapper's VOICE is proven by executing it in a fake world, not by reading it. Here the world
# is a temp HOME, a fake `hostname` on PATH, and a stand-in cure script whose exit code and
# output each case chooses. Nothing touches Vercel, the real HOME, or the real organism state.
#
# WHAT IT HAS TO PROVE
# The wrapper's whole job is TRANSLATION: exact cure markers and exit codes become distinct
# heartbeat states a silence-watcher can tell apart. Getting that wrong is invisible — a run
# that reports the wrong success while nothing moved is exactly the green-over-dead shape of
# superscar #2. So: guilt on every outcome, and innocence that the two refusal gates (wrong
# node, kill switch) never let the payload run at all.

set -u
PASS=0; FAIL=0
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/mini-vercel-autopromote.sh"

[ -f "$WRAPPER" ] || { echo "FATAL: wrapper not found at $WRAPPER"; exit 1; }

ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

# Run the wrapper in a disposable world. $1=rc the cure returns, $2=what it prints,
# $3=hostname to report, $4..=extra env assignments. Echoes the sidecar JSON.
run_case() {
    local rc="$1" out="$2" host="$3"; shift 3
    local tmp; tmp="$(mktemp -d)"
    mkdir -p "$tmp/bin" "$tmp/home/nuzantara/scripts"

    printf '#!/bin/bash\necho "%s"\n' "$host" > "$tmp/bin/hostname"
    chmod +x "$tmp/bin/hostname"

    if [ "$rc" != "MISSING" ]; then
        cat > "$tmp/home/nuzantara/scripts/vercel_prod_deploy.py" <<PYEOF
import sys
open("$tmp/cure-ran", "w").write(" ".join(sys.argv[1:]))
print("""$out""")
sys.exit($rc)
PYEOF
    fi

    env -i HOME="$tmp/home" PATH="$tmp/bin:/usr/bin:/bin" "$@" \
        /bin/bash "$WRAPPER" >/dev/null 2>&1

    printf '%s\t%s\t%s' \
        "$(cat "$tmp/home/.organism/last_seen/mini.vercel_autopromote.json" 2>/dev/null)" \
        "$([ -f "$tmp/cure-ran" ] && echo RAN || echo NOT-RUN)" \
        "$tmp"
}

field() { printf '%s' "$1" | sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p"; }

echo "== guilt: exact outcome markers must remain distinct =="

r=$(run_case 0 'OK — kita.balizero.com serves abc123def (promoted dpl_x, no rebuild)' Mini-Pro2)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "promoted" ] \
    && ok "promote-first marker -> ok/promoted" || bad "promote-first marker" "$hb"
[ "$ran" = "RAN" ] && ok "rc=0 case actually invoked the cure" || bad "cure not invoked" "$ran"

r=$(run_case 0 'OK after promote — kita.balizero.com serves abc123def' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "promoted" ] \
    && ok "gitSource promote marker -> ok/promoted" || bad "gitSource promote marker" "$hb"

r=$(run_case 0 'OK - promoted dpl_upload; kita.balizero.com serves abc123def' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "built by upload and promoted" ] \
    && ok "upload promote marker -> ok/built by upload and promoted" || bad "upload promote marker" "$hb"

# This is the guilt case for the old substring guard: the line contains "promoted" only as
# part of "not promoted", so it must never claim that production moved.
r=$(run_case 0 'OK - kita.balizero.com already serves abc123def; dpl_upload stays staged, not promoted' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "already current" ] \
    && ok "upload already-served marker -> ok/already current" || bad "not-promoted innocence" "$hb"

r=$(run_case 0 'production already includes this commit — nothing to do' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "already current" ] \
    && ok "rc=0 + no promote -> ok/already current" || bad "rc=0 no promote" "$hb"

r=$(run_case 0 'upload already in progress — lock busy, skipping this tick' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "build in progress (lock held)" ] \
    && ok "busy upload lock -> ok/build in progress" || bad "busy upload lock" "$hb"

r=$(run_case 3 'no READY production build for abc123def' Mini-Pro2 MINI_VERCEL_AUTOPROMOTE_MODE=promote-only)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "warning" ] \
    && ok "promote-only rc=3 -> warning (NOT ok, NOT error)" || bad "promote-only rc=3 must be warning" "$hb"

r=$(run_case 4 'SUSPENDED abc123def — 2 failed upload builds; waiting for the target sha to change' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && [ "$(field "$hb" note)" = "upload suspended for abc123def after 2 failed builds" ] \
    && ok "rc=4 suspended marker -> error with sha" || bad "rc=4 suspended marker" "$hb"

# A SUCCESSFUL promote off a DEGRADED target. Found by running the real cure on Mini with a
# poisoned fetch, not by reading the code: main HEAD happened to have a READY build, so the
# broken-fetch run promoted it and exited 0. Reading the marker only under rc=3 wrote a clean
# `ok` over a dead fetch - green while blind (superscar #2). The first case in this file is the
# innocence half: an ordinary promote, no marker, must still be plain `ok`.
r=$(run_case 0 'target commit   : deadbeef0
  chosen as     : main HEAD — git fetch failed (ssh: Connection refused), could not filter by path
OK — kita.balizero.com serves deadbeef0 (promoted dpl_x, no rebuild)' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "warning" ] \
    && ok "rc=0 + degraded target -> warning (not a clean ok)" \
    || bad "a promote off a degraded target must not read as healthy" "$hb"

# rc=0 off a degraded target has TWO histories — it promoted main HEAD's build, or main HEAD was
# already what production served — and the wrapper cannot tell them apart. Raised by a
# cross-family refuter on the diff: a note reading "promoted" would misdescribe the second one.
# The status must still be warning, and the note must not claim an action.
r=$(run_case 0 'target commit   : deadbeef0
  chosen as     : main HEAD — git fetch failed (ssh: Connection refused), could not filter by path
production already includes this commit — nothing to do' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "warning" ] \
    && ok "rc=0 + degraded + nothing promoted -> still warning" \
    || bad "a degraded already-current run must not read as healthy" "$hb"
case "$(field "$hb" note)" in
    *promoted*) bad "the note claims a promote that never happened" "$hb" ;;
    *) ok "the note names the degraded state, not an action it cannot know" ;;
esac

# The THIRD fallback, the one that does not say "git". `_deploy_relevant_head` degrades three
# ways and the original marker matched only two, so this run -- an identical fall back to main
# HEAD -- wrote a clean `ok`. Raised by a cross-family refuter: widening the exit codes while
# leaving the pattern narrow closed one axis under a comment that claimed both.
r=$(run_case 0 'target commit   : deadbeef0
  chosen as     : main HEAD — no commit in history touches a bundle path
OK — kita.balizero.com serves deadbeef0 (promoted dpl_x, no rebuild)' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "warning" ] \
    && ok "the non-git fallback is caught too (all three, not two)" \
    || bad "a degrade that does not say 'git' still read as healthy" "$hb"

# INNOCENCE for the widened pattern (superscar #3: a wider net catches the innocent). The good
# path names the bundle-relevant commit and must never trip it.
r=$(run_case 0 'target commit   : deadbeef0
  chosen as     : newest bundle-relevant commit on main
OK — kita.balizero.com serves deadbeef0 (promoted dpl_x, no rebuild)' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "promoted" ] \
    && ok "a healthy promote is still a plain ok (widened marker does not over-match)" \
    || bad "the widened marker accused an innocent run" "$hb"

# The one a code-only mapping gets wrong. argparse exits 2 when the cure does not know
# --promote-only: nothing ran. If that wore "warning" it would read as the benign
# nothing-to-promote and stay green over a dead organ for as long as nobody looked.
r=$(run_case 2 'usage: vercel_prod_deploy.py [-h]
vercel_prod_deploy.py: error: unrecognized arguments: --upload --auto-build' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && ok "rc=2 (argparse usage) -> error, NEVER warning" || bad "rc=2 must be error" "$hb"

r=$(run_case 1 'diagnostic prelude
refusing upload: temp filesystem has 2.50 GiB free; at least 3 GiB is required' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && [ "$(field "$hb" note)" = "refusing upload: temp filesystem has 2.50 GiB free; at least 3 GiB is required" ] \
    && ok "rc=1 -> error with last meaningful line" || bad "rc=1 last meaningful line" "$hb"

r=$(run_case 1 'upload failed
diagnostic VERCEL_TOKEN=sample-value' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
case "$(field "$hb" note)" in
    *sample-value*) bad "rc=1 heartbeat copied a credential value" "$hb" ;;
    'diagnostic VERCEL_TOKEN=[REDACTED]') ok "rc=1 redacts credential values from the heartbeat" ;;
    *) bad "rc=1 credential redaction" "$hb" ;;
esac

r=$(run_case MISSING '' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && ok "cure script absent -> error (armed at nothing, W81)" || bad "missing cure" "$hb"

echo "== mode switch: autobuild defaults on, promote-only remains instant fallback =="
r=$(run_case 0 'production already includes this commit — nothing to do' Mini-Pro2); tmp=$(echo "$r" | cut -f3)
[ "$(cat "$tmp/cure-ran" 2>/dev/null)" = "--upload --auto-build" ] \
    && ok "default mode passes --upload --auto-build" || bad "default mode flags" "$(cat "$tmp/cure-ran" 2>/dev/null)"
grep -q 'mode=autobuild.*run start' "$tmp/home/logs/mini-vercel_autopromote/run.log" \
    && grep -q 'mode=autobuild.*run done rc=0' "$tmp/home/logs/mini-vercel_autopromote/run.log" \
    && ok "default mode is logged at run start and run done" || bad "default mode log" "$(tail -n 4 "$tmp/home/logs/mini-vercel_autopromote/run.log")"

r=$(run_case 3 'no READY production build for abc123def' Mini-Pro2 MINI_VERCEL_AUTOPROMOTE_MODE=promote-only); tmp=$(echo "$r" | cut -f3)
[ "$(cat "$tmp/cure-ran" 2>/dev/null)" = "--promote-only" ] \
    && ok "promote-only mode passes --promote-only" || bad "promote-only flags" "$(cat "$tmp/cure-ran" 2>/dev/null)"
grep -q 'mode=promote-only.*run start' "$tmp/home/logs/mini-vercel_autopromote/run.log" \
    && grep -q 'mode=promote-only.*run done rc=3' "$tmp/home/logs/mini-vercel_autopromote/run.log" \
    && ok "fallback mode is logged at run start and run done" || bad "fallback mode log" "$(tail -n 4 "$tmp/home/logs/mini-vercel_autopromote/run.log")"

# A blind organ is not a quiet one. When the cure cannot work out WHICH commit to promote it
# falls back to main HEAD — which Vercel skips for all but a few merges a day — so rc=3 would
# repeat benignly forever while nothing is ever promoted (W106b: could-not-verify is not
# nothing-to-do). This also pins the if/else: an early `break` here is a no-op in bash and the
# benign heartbeat would overwrite the error.
r=$(run_case 3 'target commit   : deadbeef0
  chosen as     : main HEAD — git fetch failed, could not filter by path
no READY production build for deadbeef0' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && ok "rc=3 with a DEGRADED target -> error, not warning" || bad "degraded target" "$hb"

# A live pid is healthy only inside the build window. After 35 minutes it is a stuck run, not
# an eternally-green build. The pidfile path is fixed and outside HOME, so these cases save
# and restore it.
PIDFILE=/tmp/nuzantara-mini-vercel_autopromote.pid
SAVED=""; [ -f "$PIDFILE" ] && SAVED="$(cat "$PIDFILE")"
sleep 30 & LIVE_PID=$!
echo "$LIVE_PID" > "$PIDFILE"
r=$(run_case 0 'nothing to do' Mini-Pro2)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "previous run still building" ] && [ "$ran" = "NOT-RUN" ] \
    && ok "young live pidfile -> ok/previous run still building AND cure skipped" || bad "young pidfile" "$hb / $ran"

touch -t 200001010000 "$PIDFILE"
r=$(run_case 0 'nothing to do' Mini-Pro2)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "warning" ] && [ "$(field "$hb" note)" = "previous run alive > 35 min" ] && [ "$ran" = "NOT-RUN" ] \
    && ok "old live pidfile -> warning/previous run alive > 35 min AND cure skipped" || bad "old pidfile" "$hb / $ran"
kill "$LIVE_PID" 2>/dev/null; wait "$LIVE_PID" 2>/dev/null
rm -f "$PIDFILE"; [ -n "$SAVED" ] && echo "$SAVED" > "$PIDFILE"

echo "== innocence: neither refusal gate may run the payload =="

r=$(run_case 0 'nothing to do' Nuzantara)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "disabled" ] && [ "$ran" = "NOT-RUN" ] \
    && ok "wrong node -> disabled AND cure never ran (#10)" || bad "node guard" "$hb / $ran"

r=$(run_case 0 'nothing to do' Mini-Pro2 MINI_VERCEL_AUTOPROMOTE_ENABLED=false)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "disabled" ] && [ "$ran" = "NOT-RUN" ] \
    && ok "kill switch -> disabled AND cure never ran" || bad "kill switch" "$hb / $ran"

echo "== cadence: a 120s tick must not grow the log without bound =="

# The plist is the other half of the cadence promise the wrapper's comments make. Read the
# number out of the file rather than trusting the comment (superscar #2: exists != armed).
PLIST="$REPO_ROOT/infra/launchagents/com.nuzantara.vercel-autopromote.plist"
grep -qE '<key>StartInterval</key><integer>120</integer>' "$PLIST" \
    && ok "plist StartInterval is 120s (the cadence the wrapper documents)" || bad "plist cadence" "$(grep StartInterval "$PLIST")"

# Guilt: a run.log over 5 MB is rotated to run.log.1 before the tick writes, and the tick
# still lands in a fresh run.log. Innocence: a small log is left alone (no .1 appears).
rot_case() { # $1 = bytes to pre-seed; echoes "<has .1>\t<run.log has run start>\t<.1 size>"
    local seed="$1" tmp; tmp="$(mktemp -d)"
    mkdir -p "$tmp/bin" "$tmp/home/nuzantara/scripts" "$tmp/home/logs/mini-vercel_autopromote"
    printf '#!/bin/bash\necho Mini-Pro2\n' > "$tmp/bin/hostname"; chmod +x "$tmp/bin/hostname"
    printf 'import sys\nprint("nothing to do")\nsys.exit(0)\n' > "$tmp/home/nuzantara/scripts/vercel_prod_deploy.py"
    # Seed the log with a MARKER line and a pre-existing .1 (7 bytes), so the corpus proves
    # both directions of the promise: a small log is PRESERVED (marker still there, .1
    # untouched), a big one OVERWRITES .1 (its size becomes the seed's, not 7).
    { printf 'MARKER-PRE-EXISTING\n'; head -c "$seed" /dev/zero | tr '\0' 'x'; } > "$tmp/home/logs/mini-vercel_autopromote/run.log"
    printf 'old .1\n' > "$tmp/home/logs/mini-vercel_autopromote/run.log.1"
    env -i HOME="$tmp/home" PATH="$tmp/bin:/usr/bin:/bin" /bin/bash "$WRAPPER" >/dev/null 2>&1
    local one="NO"; grep -q "MARKER-PRE-EXISTING" "$tmp/home/logs/mini-vercel_autopromote/run.log.1" 2>/dev/null && one="YES"
    local fresh="NO"; grep -q "run start" "$tmp/home/logs/mini-vercel_autopromote/run.log" 2>/dev/null && fresh="YES"
    local kept="NO"; grep -q "MARKER-PRE-EXISTING" "$tmp/home/logs/mini-vercel_autopromote/run.log" 2>/dev/null && kept="YES"
    local size; size="$(wc -c < "$tmp/home/logs/mini-vercel_autopromote/run.log.1" | tr -d ' ')"
    printf '%s\t%s\t%s\t%s' "$one" "$fresh" "$size" "$kept"
}
r=$(rot_case 5242881)
[ "$(echo "$r" | cut -f1)" = "YES" ] && [ "$(echo "$r" | cut -f2)" = "YES" ] && [ "$(echo "$r" | cut -f3)" = "5242901" ] && [ "$(echo "$r" | cut -f4)" = "NO" ] \
    && ok "run.log over 5 MB -> rotated to run.log.1 intact (old .1 overwritten), tick lands in a fresh run.log" || bad "log rotation (guilt)" "$r"
r=$(rot_case 1024)
[ "$(echo "$r" | cut -f1)" = "NO" ] && [ "$(echo "$r" | cut -f2)" = "YES" ] && [ "$(echo "$r" | cut -f3)" = "7" ] && [ "$(echo "$r" | cut -f4)" = "YES" ] \
    && ok "run.log under 5 MB -> preserved in place (marker kept, old .1 untouched)" || bad "log rotation (innocence)" "$r"

echo
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
