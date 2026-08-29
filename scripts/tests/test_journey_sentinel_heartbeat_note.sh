#!/bin/bash
# Corpus for the journey_sentinel.sh heartbeat NOTE construction (the
# `heartbeat "degraded" "..."` call on the failure path only). The alert
# text, the dedup key, the exit codes, the healthy `heartbeat "ok"` path,
# and the log lines are all OUT OF SCOPE -- this fix and this corpus touch
# only the heartbeat NOTE.
#
# THE DEFECT (measured live on Mini, 2026-08-29, before this fix -- see
# ~/.organism/last_seen/mini.journey_sentinel.json):
#
#   {"status":"degraded","note":"1 real journey failure(s): ;/prime Google
#    Maps key is valid (currently RED     see file header, needs-ruling
#    item 1)"}
#
# A RED organ publishing a note whose only failure-bearing content is a
# spec TITLE phrased as the DESIRED property ("... key is valid"), with a
# stray leading ';' from using the join separator as a prefix on the first
# element. Only the sidecar's separate `status` field kept it from reading
# as its own opposite. This corpus proves the fix: (1) every entry now says
# FAILED: up front, so the note text alone is unambiguous; (2) the useful
# $error_summary the Telegram alert already carries rides along too,
# instead of being thrown away; (3) truncation under a real budget is
# always MARKED ("+N more (see log)"), never silent; and (4) all of the
# above survives the trip through the REAL scripts/lib/heartbeat.sh (its
# own byte-level ASCII sanitisation and its silent 500-char cut).
#
# WHY EXECUTE INSTEAD OF READ (superscar #2 / W107): "the note-builder is
# armed" is only provable by running it. The note-builder tested below is
# extracted VERBATIM from the shipped scripts/journey_sentinel.sh (the
# exact `python3 -c "..."` payload assigned to NOTE_TAIL) and RUN with the
# same argv shape the wrapper itself uses -- reading the source proves
# intent, not behaviour. Section 4 goes one level further and drives that
# same output through the REAL scripts/lib/heartbeat.sh writer, because the
# ASCII-mangling that caused part of the original defect's confusing shape
# only happens in that writer, never in the wrapper.
#
# ZERO network calls anywhere in this file. Every write goes through
# require_tmpdir/require_tmpfile (mktemp discipline: abort the WHOLE corpus
# loudly on a failed mktemp rather than let a hollow path corrupt every
# downstream check with an unrelated error -- the adversarial-finding
# rationale from test_voa_probe_wrapper.sh applies verbatim here), and
# every scripts/lib/heartbeat.sh invocation below is HOME-scoped to one of
# those temp dirs. This corpus never touches the real ~/.organism/ or the
# real ~/logs/.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_SRC="$REPO/scripts/journey_sentinel.sh"
HEARTBEAT_LIB="$REPO/scripts/lib/heartbeat.sh"

PASS=0
FAIL=0

check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        printf '  PASS  %s\n' "$name"
        PASS=$((PASS + 1))
    else
        printf '  FAIL  %s -- expected [%s], got [%s]\n' "$name" "$expected" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

[ -f "$TARGET_SRC" ] || { echo "FATAL: target not found at $TARGET_SRC"; exit 1; }
[ -f "$HEARTBEAT_LIB" ] || { echo "FATAL: heartbeat.sh not found at $HEARTBEAT_LIB"; exit 1; }

PY_BIN="$(command -v python3 2>/dev/null || true)"
[ -n "$PY_BIN" ] || { echo "FATAL: no python3 interpreter on PATH -- cannot run this corpus"; exit 1; }

command -v bash >/dev/null 2>&1 || { echo "FATAL: no bash on PATH -- heartbeat.sh CLI mode needs it"; exit 1; }

# --- mktemp discipline: abort loudly, never continue on a hollow path -----
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
    d="$(mktemp -d)" || { echo "FATAL: mktemp -d failed -- cannot run this corpus"; exit 1; }
    [ -n "$d" ] && [ -d "$d" ] || { echo "FATAL: mktemp -d returned an unusable path: '$d'"; exit 1; }
    CLEANUP_PATHS+=("$d")
    printf '%s' "$d"
}

require_tmpfile() {
    local f
    f="$(mktemp)" || { echo "FATAL: mktemp failed -- cannot run this corpus"; exit 1; }
    [ -n "$f" ] && [ -f "$f" ] || { echo "FATAL: mktemp returned an unusable path: '$f'"; exit 1; }
    CLEANUP_PATHS+=("$f")
    printf '%s' "$f"
}

echo "== 0. STATIC scar-pin: the pre-fix leading-separator accumulator is gone =="

# The exact buggy accumulation from the shipped pre-fix code
# (`ALL_TITLES="$ALL_TITLES;$title"`, seeded from `ALL_TITLES=""`) always
# produces a leading separator on the first element and carries only the
# bare title, never $error_summary. If either line reappears -- a revert,
# or a future edit reintroducing the same shape under this name -- this
# goes red.
if grep -qF 'ALL_TITLES="$ALL_TITLES;$title"' "$TARGET_SRC"; then
    check "scar-pin: leading-separator accumulator line absent" "absent" "present"
else
    check "scar-pin: leading-separator accumulator line absent" "absent" "absent"
fi

if grep -q 'ALL_TITLES' "$TARGET_SRC"; then
    check "scar-pin: ALL_TITLES symbol fully retired from source" "absent" "present"
else
    check "scar-pin: ALL_TITLES symbol fully retired from source" "absent" "absent"
fi

echo
echo "== 1. extract the REAL note-builder payload -- BOTH the python body alone,"
echo "     for behavioural checks, AND the FULL raw bash construct (wrapper"
echo "     included) for a genuine bash-quoting scar-pin in section 1b =="

# Gate round 3 (Kimi K3 refutation, verified independently): extracting
# only the python BODY and running it via python3 <file> args never
# exercises the bash double-quoting layer production actually uses --
# which is exactly how a backtick-command-substitution defect in the
# payload's own comments (finding B, fixed the same round as the
# byte-budget fix below) shipped past 32 green checks undetected.
# NOTE_TAIL_RAW below keeps the FULL construct, wrapper included, so
# section 1b can run it through REAL bash and prove its stderr is clean --
# the shape production actually executes, not an extraction of it.
NOTE_BUILDER="$(require_tmpfile)"
NOTE_TAIL_RAW="$(require_tmpfile)"
"$PY_BIN" - "$TARGET_SRC" "$NOTE_BUILDER" "$NOTE_TAIL_RAW" <<'EXTRACT'
import re
import sys

target, out_body, out_raw = sys.argv[1], sys.argv[2], sys.argv[3]
with open(target) as f:
    src = f.read()

OPEN_LINE = (
    "NOTE_TAIL=$(python3 - "
    '"'
    "$VERDICT_JSON"
    '"'
    " "
    '"'
    "$NOTE_MAX_TOTAL"
    '"'
    " "
    '"'
    "$NOTE_MAX_TITLE"
    '"'
    " "
    '"'
    "$NOTE_MAX_SUMMARY"
    '"'
    " <<'PYEOF'"
)
pattern = re.escape(OPEN_LINE) + r"\n(.*?)\nPYEOF\n\)"
m = re.search(pattern, src, re.S)
if not m:
    sys.exit(1)
with open(out_raw, "w") as f:
    f.write(src[m.start():m.end()])
with open(out_body, "w") as f:
    f.write(m.group(1))
EXTRACT
EXTRACT_RC=$?

HAVE_BUILDER=0
if [ "$EXTRACT_RC" -eq 0 ] && [ -s "$NOTE_BUILDER" ] && [ -s "$NOTE_TAIL_RAW" ]; then
    check "note-builder payload extracted from the real shipped file" "extracted" "extracted"
    HAVE_BUILDER=1
else
    check "note-builder payload extracted from the real shipped file" "extracted" "NOT-FOUND (reverted shape, or NOTE_TAIL renamed/moved)"
fi

build_note() {
    # build_note <json> [max_total] [max_title] [max_summary]
    local json="$1" max_total="${2:-400}" max_title="${3:-150}" max_summary="${4:-120}"
    "$PY_BIN" "$NOTE_BUILDER" "$json" "$max_total" "$max_title" "$max_summary"
}

echo
echo "== 1b. SCAR-PIN (finding B): the RAW bash construct, run through REAL"
echo "      bash (not extracted-then-python3), produces ZERO stderr =="

# The extraction in section 1 pulls the python BODY out for convenience
# (build_note() above runs it via `python3 <file> args`, sidestepping bash
# entirely) -- which is exactly why 32 earlier checks all passed while
# finding B's backtick-command-substitution defect shipped undetected: none
# of them ever asked bash to interpret the payload the way production
# really does. This section runs $NOTE_TAIL_RAW -- the FULL construct,
# `NOTE_TAIL=$(python3 - ... <<'PYEOF' ... PYEOF)`, wrapper included --
# through a REAL bash process and inspects its stderr. Reproduced against
# the pre-this-round shipped file before writing this check: the buggy
# `-c "..."` form (backticks in two of its own comments) printed 4 lines of
# "syntax error near unexpected token" noise on stderr for this exact
# invocation, even though stdout (NOTE_TAIL's value) was correct throughout
# -- the defect is invisible in the output, only visible in stderr.
if [ "$HAVE_BUILDER" -eq 1 ]; then
    RAWRUN_SCRIPT="$(require_tmpfile)"
    RAWRUN_STDOUT="$(require_tmpfile)"
    RAWRUN_STDERR="$(require_tmpfile)"

    {
        printf 'set -uo pipefail\n'
        printf 'VERDICT_JSON=%q\n' '{"real_failures":[{"title":"/dream loads","fingerprint":"x","error_summary":""}]}'
        # Fixed representative values, not the section-10 extracted
        # NOTE_MAX_*_VAL (those are not yet defined at this point in the
        # corpus, and this check's purpose -- proving the raw construct
        # runs cleanly through real bash -- does not depend on them).
        printf 'NOTE_MAX_TOTAL=400\n'
        printf 'NOTE_MAX_TITLE=150\n'
        printf 'NOTE_MAX_SUMMARY=120\n'
        cat "$NOTE_TAIL_RAW"
        printf '\n'
        printf %s 'printf "%s" "$NOTE_TAIL"'
        printf '\n'
    } > "$RAWRUN_SCRIPT"

    bash "$RAWRUN_SCRIPT" 1>"$RAWRUN_STDOUT" 2>"$RAWRUN_STDERR"

    check "(scar-pin, finding B) raw construct through REAL bash produces ZERO stderr" "0" "$(wc -c < "$RAWRUN_STDERR" | tr -d ' ')"
    check "(scar-pin, finding B) NOTE_TAIL still correct when run as real bash" "FAILED: /dream loads" "$(cat "$RAWRUN_STDOUT")"
    if [ -s "$RAWRUN_STDERR" ]; then
        echo "  --- stderr from the raw-construct run (should have been empty) ---"
        sed 's/^/  | /' "$RAWRUN_STDERR"
    fi
else
    echo "  (skipped -- note-builder not found, see section 1)"
fi

if [ "$HAVE_BUILDER" -eq 1 ]; then

echo
echo "== 2. BEHAVIOURAL guilt/innocence: the live-case shape, driven for real =="

LIVE_JSON='{"real_failures":[{"title":"/prime Google Maps key is valid","fingerprint":"deadbeef","error_summary":"window.google.maps never loaded"}]}'
live_out="$(build_note "$LIVE_JSON")"
check "(guilt) live-case note does NOT start with a bare separator" "no" "$(if [[ "$live_out" == ';'* ]]; then echo yes; else echo no; fi)"
check "(guilt) live-case note is unambiguously a failure, not its own opposite" "FAILED: /prime Google Maps key is valid :: window.google.maps never loaded" "$live_out"

echo
echo "== 3. innocence: single failure, no error_summary =="

out="$(build_note '{"real_failures":[{"title":"/dream loads","fingerprint":"x","error_summary":""}]}')"
check "empty error_summary produces a plain FAILED: entry (no :: suffix)" "FAILED: /dream loads" "$out"

echo
echo "== 4. innocence: multiple failures, honestly separated, no leading separator =="

out="$(build_note '{"real_failures":[{"title":"A ok","fingerprint":"f1","error_summary":"boom1"},{"title":"B ok","fingerprint":"f2","error_summary":"boom2"}]}')"
check "two failures joined by '; ', each carrying its own summary" "FAILED: A ok :: boom1; FAILED: B ok :: boom2" "$out"

echo
echo "== 5. guilt/innocence: a title containing a ';' is never mistaken for the separator =="

out="$(build_note '{"real_failures":[{"title":"weird; title; here","fingerprint":"f1","error_summary":""}]}')"
check "embedded ';' survives verbatim, not misparsed as a join point" "FAILED: weird; title; here" "$out"

echo
echo "== 6. budget: a very long error_summary is clipped per-entry, marked with '...' =="

LONGSUM="$("$PY_BIN" -c "print('a' * 300)")"
LONG_JSON="$("$PY_BIN" -c "import json,sys; print(json.dumps({'real_failures':[{'title':'X failed','fingerprint':'f1','error_summary':sys.argv[1]}]}))" "$LONGSUM")"
out="$(build_note "$LONG_JSON")"
expected="FAILED: X failed :: $("$PY_BIN" -c "print('a' * 117 + '...')")"
check "a 300-char summary clips to NOTE_MAX_SUMMARY (120) with a visible '...'" "$expected" "$out"
check "the clipped entry does not silently look complete (ends in '...')" "yes" "$(if [[ "$out" == *'...' ]]; then echo yes; else echo no; fi)"

echo
echo "== 6b. PIN: clip() itself is BYTE-exact for genuinely oversized multi-byte"
echo "       content -- section 6 above never forced it to, and section 11's"
echo "       em-dash fixture is sized to stay UNDER the per-field char cap on"
echo "       purpose (isolating the shown-search loop), so neither exercises"
echo "       clip()'s OWN truncation branch on multi-byte input =="

# Self-caught via this corpus's own mutation battery: reverting clip() to a
# character-slice (finding A's fix applied only to blen()'s callers, not
# clip() itself) passed EVERY check in this file with zero red -- section 6's
# 'a'*300 fixture is pure ASCII (char length == byte length, the mutation is
# invisible), section 11's em-dash fixture is sized to NEVER trigger clip()'s
# truncation branch at all (title_len/summary_len = NOTE_MAX_*_VAL - 2, always
# under the cap), and sections 13/14 use ASCII filler for the same reason as
# section 6. This isolates clip() directly: exec the real extracted builder
# module (suppressing its own top-level print side effect) to get a live
# reference to its clip function, then call clip() on 500 em dashes (1500
# UTF-8 bytes) at limit=120 and assert the byte length of what comes back.
# Measured: fixed clip() returns exactly 120 bytes; the character-slice
# mutation returns 354.
if [ "$HAVE_BUILDER" -eq 1 ]; then
    CLIP_CHECK_SCRIPT="$(require_tmpfile)"
    cat > "$CLIP_CHECK_SCRIPT" <<'CLIPCHECK'
import contextlib
import io
import sys

builder_path, limit = sys.argv[1], int(sys.argv[2])
ns = {}
sys.argv = ["prog", '{"real_failures":[]}', "400", "150", "120"]
with open(builder_path) as f:
    code = f.read()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(compile(code, builder_path, "exec"), ns)

clip = ns["clip"]
huge = u"\u2014" * 500  # 500 em dashes, 1500 UTF-8 bytes, pure python source stays ASCII
result = clip(huge, limit)
print(len(result.encode("utf-8")))
CLIPCHECK
    clip_byte_len="$("$PY_BIN" "$CLIP_CHECK_SCRIPT" "$NOTE_BUILDER" 120)"
    check "(pin) clip(500 em dashes, limit=120) stays AT OR UNDER 120 UTF-8 bytes" "yes" "$([ "${clip_byte_len:-9999}" -le 120 ] 2>/dev/null && echo yes || echo no)"
else
    echo "  (skipped -- note-builder not found, see section 1)"
fi

echo
echo "== 7. budget: several failures that do not all fit are marked '+N more', never silently dropped =="

MANY_JSON="$("$PY_BIN" -c "
import json
title = 'A' * 80
summary = 'B' * 100
failures = [{'title': title, 'fingerprint': 'f%d' % i, 'error_summary': summary} for i in range(3)]
print(json.dumps({'real_failures': failures}))
")"
out="$(build_note "$MANY_JSON")"
expected="FAILED: $("$PY_BIN" -c "print('A' * 80)") :: $("$PY_BIN" -c "print('B' * 100)"); +2 more (see log)"
check "3 large failures at NOTE_MAX_TOTAL=400 show 1 whole entry + '+2 more (see log)'" "$expected" "$out"

echo
echo "== 8. budget: when EVERY entry is dropped, the marker still carries no leading separator =="

# Direct regression check for a bug caught while writing this corpus: a
# naive '; '.join(entries[:shown]) + marker(...) still glued a leading
# '; ' onto the marker when shown==0 ('; +3 more (see log)') -- the exact
# separator-as-prefix mistake this whole fix exists to remove, just moved
# one level down. A tiny max_total (50) forces every one of 3 short
# entries to be dropped.
TINY_JSON='{"real_failures":[{"title":"F1","fingerprint":"a","error_summary":""},{"title":"F2","fingerprint":"b","error_summary":""},{"title":"F3","fingerprint":"c","error_summary":""}]}'
out="$(build_note "$TINY_JSON" 50)"
check "all-dropped marker has no leading separator" "+3 more (see log)" "$out"
check "(scar-pin, this fix's own bug) all-dropped marker is not glued with a leading ';'" "no" "$(if [[ "$out" == ';'* ]]; then echo yes; else echo no; fi)"

echo
echo "== 9. ASCII discipline: nothing this wrapper ADDS relies on a non-ASCII byte =="

# The labels this wrapper adds ("FAILED: ", " :: ", "; ", " more (see
# log)") are hardcoded ASCII literals in the source itself -- verified
# statically here. Section 11 below verifies the runtime END-TO-END
# guarantee (the full published note, title/summary content included,
# carries zero non-ASCII bytes once it has gone through the real
# heartbeat.sh writer -- that guarantee comes from heartbeat.sh's own
# sanitiser, not from this wrapper, and is proven there, not duplicated
# here as a second, weaker runtime scan).
check "'FAILED: ' label is a literal ASCII string in source" "present" "$(grep -qF "'FAILED: '" "$TARGET_SRC" && echo present || echo absent)"
check "'more (see log)' marker suffix is a literal ASCII string in source" "present" "$(grep -qF 'more (see log)' "$TARGET_SRC" && echo present || echo absent)"

fi  # HAVE_BUILDER

echo
echo "== 10. STATIC: the note budget constants exist and are sane (>0, well under heartbeat.sh's 500-char cut) =="

check "NOTE_MAX_TOTAL is defined in source" "1" "$(grep -c '^NOTE_MAX_TOTAL=' "$TARGET_SRC")"
check "NOTE_MAX_TITLE is defined in source" "1" "$(grep -c '^NOTE_MAX_TITLE=' "$TARGET_SRC")"
check "NOTE_MAX_SUMMARY is defined in source" "1" "$(grep -c '^NOTE_MAX_SUMMARY=' "$TARGET_SRC")"

NOTE_MAX_TOTAL_VAL="$(grep '^NOTE_MAX_TOTAL=' "$TARGET_SRC" | head -1 | cut -d= -f2)"
check "NOTE_MAX_TOTAL is strictly less than heartbeat.sh's 500-char cut (margin, not exact)" "under-500" "$([ "${NOTE_MAX_TOTAL_VAL:-9999}" -lt 500 ] 2>/dev/null && echo under-500 || echo NOT-under-500)"

# Read alongside NOTE_MAX_TOTAL_VAL, not as separate hardcoded test
# defaults: sections 13/14 below thread these REAL values explicitly into
# build_note(), which is the point -- build_note()'s own bash parameter
# defaults (150/120/400) are a TEST-LOCAL fallback for callers that don't
# care about the exact cap, and are deliberately NOT read from the source;
# a check that wants to prove a specific constant is load-bearing must pass
# that constant's REAL value explicitly, never rely on the fallback.
NOTE_MAX_TITLE_VAL="$(grep '^NOTE_MAX_TITLE=' "$TARGET_SRC" | head -1 | cut -d= -f2)"
NOTE_MAX_SUMMARY_VAL="$(grep '^NOTE_MAX_SUMMARY=' "$TARGET_SRC" | head -1 | cut -d= -f2)"
[[ "$NOTE_MAX_TOTAL_VAL" =~ ^[0-9]+$ ]] || NOTE_MAX_TOTAL_VAL=400
[[ "$NOTE_MAX_TITLE_VAL" =~ ^[0-9]+$ ]] || NOTE_MAX_TITLE_VAL=150
[[ "$NOTE_MAX_SUMMARY_VAL" =~ ^[0-9]+$ ]] || NOTE_MAX_SUMMARY_VAL=120

echo
echo "== 11. END-TO-END: the note survives the REAL scripts/lib/heartbeat.sh writer =="

if [ "$HAVE_BUILDER" -eq 1 ]; then
    E2E_HOME="$(require_tmpdir)"

    # Reconstruct the exact wrapper call: heartbeat "degraded" "$FAILURE_COUNT real journey failure(s): $NOTE_TAIL"
    e2e_note_tail="$(build_note "$LIVE_JSON")"
    e2e_full_note="1 real journey failure(s): $e2e_note_tail"

    HOME="$E2E_HOME" bash "$HEARTBEAT_LIB" mini.journey_sentinel degraded "$e2e_full_note"

    PUBLISHED="$E2E_HOME/.organism/last_seen/mini.journey_sentinel.json"
    if [ -f "$PUBLISHED" ]; then
        check "heartbeat.sh published a sidecar file" "yes" "yes"

        parsed_note="$("$PY_BIN" -c "
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
print(d['note'])
" "$PUBLISHED" 2>/dev/null || echo "PARSE-FAILED")"

        check "published sidecar is valid JSON with a readable note field" "no" "$([ "$parsed_note" = "PARSE-FAILED" ] && echo yes || echo no)"
        check "published note is unambiguously a failure (contains FAILED:)" "yes" "$(if [[ "$parsed_note" == *"FAILED:"* ]]; then echo yes; else echo no; fi)"
        check "published note does NOT open with a bare separator (the original defect)" "no" "$(if [[ "$parsed_note" == ';'* ]]; then echo yes; else echo no; fi)"

        # NOT this (gate round 3, Kimi K3 refutation, verified independently):
        # heartbeat.sh strips EVERY non-ASCII byte to a space UNCONDITIONALLY,
        # for any input whatsoever -- asserting the published note has none is
        # true by heartbeat.sh's own construction, not by anything THIS
        # wrapper did. That check could never go red -- superscar #2 inside
        # the very corpus meant to catch it. Replaced below with a check that
        # CAN fail: an em-dash-dense multi-failure fixture, sized off the REAL
        # extracted constants (not a hardcoded density), driven through
        # build_note() with those same real values and then through the REAL
        # heartbeat.sh -- asserting the marker (or a sibling failure) SURVIVES
        # publication. This is finding A end-to-end: budgeting on python
        # character count instead of len(s.encode("utf-8")) let a dense-enough
        # note pass every earlier check while heartbeat.sh's real 500-BYTE
        # (not 500-char) ceiling silently cut the marker -- measured before the
        # byte-budget fix: 297 python chars / 829 UTF-8 bytes, marker present
        # in the builder output, ABSENT from the published note. Two real,
        # non-contrived sources of this density: the live defect's own title
        # already carries an em dash, and this wrapper's SKIPPED-path title
        # ("... [SKIPPED -- never actually ran]") embeds a second one.
        EM_DASH_JSON="$("$PY_BIN" -c "
import json, sys

title_len = max(int(sys.argv[1]) - 2, 1)
summary_len = max(int(sys.argv[2]) - 2, 1)
em = u'\u2014'  # em dash, U+2014, 3 UTF-8 bytes -- python source stays pure ASCII
title = em * title_len
summary = em * summary_len
failures = [{'title': title, 'fingerprint': 'f%d' % i, 'error_summary': summary} for i in range(3)]
print(json.dumps({'real_failures': failures}))
" "$NOTE_MAX_TITLE_VAL" "$NOTE_MAX_SUMMARY_VAL")"

        DENSE_HOME="$(require_tmpdir)"
        e2e_note_tail_dense="$(build_note "$EM_DASH_JSON" "$NOTE_MAX_TOTAL_VAL" "$NOTE_MAX_TITLE_VAL" "$NOTE_MAX_SUMMARY_VAL")"
        e2e_full_note_dense="3 real journey failure(s): $e2e_note_tail_dense"
        HOME="$DENSE_HOME" bash "$HEARTBEAT_LIB" mini.journey_sentinel degraded "$e2e_full_note_dense"

        DENSE_PUBLISHED="$DENSE_HOME/.organism/last_seen/mini.journey_sentinel.json"
        if [ -f "$DENSE_PUBLISHED" ]; then
            dense_parsed_note="$("$PY_BIN" -c "
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
print(d['note'])
" "$DENSE_PUBLISHED" 2>/dev/null || echo "PARSE-FAILED")"

            # NOT also asserting "published note <=500 bytes": self-caught via
            # this corpus's own mutation battery (reverting blen() to a
            # character count, defeating finding A) -- that assertion stayed
            # GREEN under the exact mutation the marker-survival check below
            # catches, because heartbeat.sh's OWN truncation makes it true
            # unconditionally for any em-dash/space-only content (no quotes
            # or backslashes to trigger its post-truncation escaping step
            # growing the string back past 500). Same disease finding C
            # named in the check this section replaced -- caught here by
            # running the mutation, not by re-reasoning about it after the
            # fact, and removed rather than kept as false reassurance.
            check "(finding A, end-to-end) em-dash-dense 3-failure note still publishes with a truncation marker" "yes" "$(if [[ "$dense_parsed_note" == *"more (see log)"* ]]; then echo yes; else echo no; fi)"
        else
            check "(finding A, end-to-end) heartbeat.sh published the dense-fixture sidecar" "yes" "no"
        fi
    else
        check "heartbeat.sh published a sidecar file" "yes" "no (nothing written to $PUBLISHED)"
    fi
else
    echo "  (skipped -- note-builder not found, see section 1)"
fi

echo
echo "== 12. HYGIENE: every heartbeat.sh call in THIS corpus is HOME-scoped to a temp dir =="

# A real-filesystem before/after comparison of ~/.organism/last_seen on
# this actual machine would be flaky by construction: journey_sentinel.sh
# itself runs hourly via LaunchAgent on this same host and could
# legitimately touch that file mid-run, for reasons having nothing to do
# with this corpus. The real, non-flaky guarantee is structural: verify
# THIS FILE never invokes scripts/lib/heartbeat.sh without an explicit
# HOME= override on the same line.
#
# Gate round 3 (Kimi K3 refutation, "matches only one exact quoting
# form"): broadened from a literal 'bash "$HEARTBEAT_LIB"' string match to
# a pattern tolerant of unquoted or loosely-spaced forms
# (bash $HEARTBEAT_LIB, bash  "$HEARTBEAT_LIB", ...) -- verified this still
# finds exactly the two real invocations below (both HOME-scoped) and does
# not silently stop matching if either is ever reformatted. Comment lines
# are excluded (`grep -vE '^[0-9]+:[[:space:]]*#'`): the broadened pattern
# immediately self-matched THIS VERY comment block, which illustrates the
# pattern in prose -- caught before shipping by actually running this
# check, not by reasoning about the regex.
UNSCOPED_CALLS="$(grep -nE 'bash[[:space:]]+"?\$HEARTBEAT_LIB"?' "${BASH_SOURCE[0]}" | grep -vE '^[0-9]+:[[:space:]]*#' | grep -v 'HOME=' || true)"
check "no heartbeat.sh invocation in this corpus omits an explicit HOME= override" "0" "$(printf '%s' "$UNSCOPED_CALLS" | grep -c . || true)"

echo
echo "== 13. PIN: NOTE_MAX_SUMMARY is load-bearing -- raising it lets one long summary crowd out a sibling failure entirely =="

# Coordinator finding (gate round 1): every earlier check that exercises
# clip() calls build_note() WITHOUT an explicit max_summary override, so it
# silently runs against build_note()'s own bash-local default (120) no
# matter what NOTE_MAX_SUMMARY actually says in the shipped file --
# NOTE_MAX_SUMMARY could be raised to 9999 in production and nothing above
# would notice. This section threads the REAL extracted NOTE_MAX_SUMMARY_VAL
# (and NOTE_MAX_TOTAL_VAL/NOTE_MAX_TITLE_VAL) explicitly, so it tracks
# whatever the file currently says, not what it said when this test was
# written.
#
# The injected summary is sized at 2x NOTE_MAX_TOTAL_VAL -- comfortably
# larger than the ENTIRE note budget, not just today's 120-char cap -- so
# the fixture stays meaningful even if the cap is moved moderately, and
# still exposes a gross defeat like "raised to 9999": left unclipped, this
# summary alone cannot fit in the note at all, and BOTH failures should
# then vanish behind a bare marker.
if [ "$HAVE_BUILDER" -eq 1 ]; then
    OVERSIZED_SUMMARY="$("$PY_BIN" -c "print('X' * (2 * $NOTE_MAX_TOTAL_VAL))")"
    SUMMARY_PIN_JSON="$("$PY_BIN" -c "
import json, sys
print(json.dumps({'real_failures': [
    {'title': '/a short one', 'fingerprint': 'f1', 'error_summary': sys.argv[1]},
    {'title': '/b also short', 'fingerprint': 'f2', 'error_summary': 'second failure matters'},
]}))
" "$OVERSIZED_SUMMARY")"

    out="$(build_note "$SUMMARY_PIN_JSON" "$NOTE_MAX_TOTAL_VAL" "$NOTE_MAX_TITLE_VAL" "$NOTE_MAX_SUMMARY_VAL")"

    check "(pin) first failure's title still present after its oversized summary is clipped" "yes" "$(if [[ "$out" == *"/a short one"* ]]; then echo yes; else echo no; fi)"
    check "(pin) second failure's title survives -- not crowded out by the first's summary" "yes" "$(if [[ "$out" == *"/b also short"* ]]; then echo yes; else echo no; fi)"
    check "(pin) second failure's own summary survives verbatim" "yes" "$(if [[ "$out" == *"second failure matters"* ]]; then echo yes; else echo no; fi)"
    check "(pin) note has NOT collapsed to a bare marker (real content survived)" "no" "$(if [ "$out" = "+2 more (see log)" ]; then echo yes; else echo no; fi)"
else
    echo "  (skipped -- note-builder not found, see section 1)"
fi

echo
echo "== 14. PIN: NOTE_MAX_TITLE is load-bearing -- raising it lets one long title crowd out a sibling failure entirely =="

# Same shape, same coordinator finding, the other cap: no earlier check
# passed max_title explicitly either, so NOTE_MAX_TITLE could be raised to
# 9999 in production with nothing above noticing. Same 2x-NOTE_MAX_TOTAL_VAL
# sizing rationale as section 13.
if [ "$HAVE_BUILDER" -eq 1 ]; then
    OVERSIZED_TITLE="$("$PY_BIN" -c "print('Y' * (2 * $NOTE_MAX_TOTAL_VAL))")"
    TITLE_PIN_JSON="$("$PY_BIN" -c "
import json, sys
print(json.dumps({'real_failures': [
    {'title': sys.argv[1], 'fingerprint': 'f1', 'error_summary': ''},
    {'title': '/b sibling', 'fingerprint': 'f2', 'error_summary': ''},
]}))
" "$OVERSIZED_TITLE")"

    out="$(build_note "$TITLE_PIN_JSON" "$NOTE_MAX_TOTAL_VAL" "$NOTE_MAX_TITLE_VAL" "$NOTE_MAX_SUMMARY_VAL")"

    check "(pin) the oversized title is visibly clipped (ends in '...')" "yes" "$(if [[ "$out" == *"..."* ]]; then echo yes; else echo no; fi)"
    check "(pin) sibling failure's title survives -- not crowded out by the oversized one" "yes" "$(if [[ "$out" == *"/b sibling"* ]]; then echo yes; else echo no; fi)"
    check "(pin) note has NOT collapsed to a bare marker (real content survived)" "no" "$(if [ "$out" = "+2 more (see log)" ]; then echo yes; else echo no; fi)"
else
    echo "  (skipped -- note-builder not found, see section 1)"
fi

echo
echo "TOTAL $((PASS + FAIL)) FAILED $FAIL"
[ "$FAIL" -eq 0 ]
