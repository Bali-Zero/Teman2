#!/bin/sh
# test_prepush_failclosed.sh — regression test for the sh -e fail-closed
# defect in .husky/pre-push (scar W101, cicatrix-superscar.md famiglia #2).
#
# Husky's wrapper (.husky/_/h) executes every hook via `sh -e "$s"`. Under
# that errexit, a BARE command-substitution assignment
#   VAR="$(some_command)"
# aborts the WHOLE script the instant some_command exits non-zero — the
# assignment's exit status IS the command's exit status, and a plain
# assignment statement is not exempt from set -e the way an if/while
# condition or an AND/OR list is. Any code below that assignment meant to
# INSPECT the failure (a subsequent `$?` check, a fail-closed branch, a
# cleanup step) can therefore never run: the process is already dead.
#
# .husky/pre-push's own path-aware classifier gate documents "a non-zero
# classifier exit forces the FULL suite" — but until this fix, the bare
# `VERDICT_OUTPUT="$(...)"` assignment made that fallback dead code. Any
# worktree on a branch predating scripts/prepush_classify.py (missing file
# -> classifier exits non-zero) hard-blocked the push with husky's generic
# "code 2" instead of degrading to the full suite as documented.
#
# This script proves, at the shell-semantics level (no repo state needed),
# WHY the bug fires under the OLD pattern and that the NEW pattern
# (`VAR="$(cmd)" || VAR_RC=$?`) survives to let the fail-closed check run.
# It also tripwires the live hook file so the old bare pattern can never
# silently return on VERDICT_OUTPUT specifically.
#
# Run:  sh scripts/tests/test_prepush_failclosed.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

# ---------------------------------------------------------------------------
# Case 1 (guilt, NEW pattern): errexit-immune capture must survive a failing
# command substitution and let the script report the real exit code.
# ---------------------------------------------------------------------------
out1="$(sh -e -c 'RC=0; OUT="$(exit 2)" || RC=$?; echo "RC=$RC"' 2>/dev/null)"
if [ "$out1" = "RC=2" ]; then
    note_pass "guilt (NEW pattern) — script survives to report RC=2 (got: $out1)"
else
    note_fail "guilt (NEW pattern) — expected RC=2, got: $out1"
fi

# ---------------------------------------------------------------------------
# Case 2 (guilt, OLD pattern): documents WHY the fix is needed. A bare
# assignment with no || guard must abort BEFORE the next statement runs —
# "unreachable" must never be printed, and the sh -e process must exit
# non-zero.
# ---------------------------------------------------------------------------
out2="$(sh -e -c 'OUT="$(exit 2)"; echo "unreachable"' 2>/dev/null)"
rc2=$?
if [ "$rc2" != "0" ] && [ "$out2" != "unreachable" ]; then
    note_pass "guilt-2 (OLD pattern) — sh -e aborted before printing 'unreachable' (rc=$rc2, out='$out2')"
else
    note_fail "guilt-2 (OLD pattern) — expected non-zero exit and no 'unreachable' output, got rc=$rc2 out='$out2'"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence, NEW pattern): a SUCCEEDING command substitution must
# behave exactly as before — RC stays 0, OUT captures stdout normally. The
# `|| VAR_RC=$?` guard must not perturb the happy path.
# ---------------------------------------------------------------------------
out3="$(sh -e -c 'RC=0; OUT="$(echo full)" || RC=$?; echo "RC=$RC OUT=$OUT"' 2>/dev/null)"
if [ "$out3" = "RC=0 OUT=full" ]; then
    note_pass "innocence (NEW pattern) — happy path unperturbed (got: $out3)"
else
    note_fail "innocence (NEW pattern) — expected 'RC=0 OUT=full', got: $out3"
fi

# ---------------------------------------------------------------------------
# Case 4 (tripwire): grep the LIVE hook file — a bare unguarded
# VERDICT_OUTPUT="$(  ...  )" (no "|| VERDICT_RC=" on the same line) must
# never reappear. Anchors on the repo root two levels above this script.
# ---------------------------------------------------------------------------
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
HOOK_FILE="$REPO_ROOT/.husky/pre-push"

if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire — $HOOK_FILE not found (cannot verify)"
else
    # Bare pattern = the assignment opens with VERDICT_OUTPUT="$( but the
    # SAME line does not also contain the errexit-immune guard.
    bad_lines="$(grep -n 'VERDICT_OUTPUT="\$(' "$HOOK_FILE" | grep -v '|| VERDICT_RC=' || true)"
    if [ -z "$bad_lines" ]; then
        note_pass "tripwire — no bare unguarded VERDICT_OUTPUT=\"\$(...)\" in $HOOK_FILE"
    else
        note_fail "tripwire — bare unguarded VERDICT_OUTPUT assignment reintroduced in $HOOK_FILE: $bad_lines"
    fi
fi

# ---------------------------------------------------------------------------
# Case 5 (guilt, RANGE_FROM NEW pattern, task #39, 2026-07-26): the sibling
# bug on line 133 — a failing `git merge-base` must degrade cleanly to
# DIFF_ERROR=1 instead of aborting the script before that check runs. Uses a
# REAL `git merge-base` failure (bogus ref, no valid object) rather than a
# synthetic `exit 2`, so this pins the actual command that was broken, not
# just the general shell-semantics shape already covered by Case 1.
# `git merge-base HEAD <bogus>` fails purely on local ref resolution — no
# network, no dependency on an `origin` remote existing.
# ---------------------------------------------------------------------------
out5="$(sh -e -c '
    RANGE_FROM="$(git merge-base HEAD definitely-not-a-valid-ref-xyz123 2>/dev/null)" || RANGE_FROM=""
    if [ -z "$RANGE_FROM" ]; then
        echo "DIFF_ERROR=1"
    else
        echo "DIFF_ERROR=0"
    fi
    echo "reached-end"
' 2>/dev/null)"
if [ "$out5" = "$(printf 'DIFF_ERROR=1\nreached-end')" ]; then
    note_pass "guilt (RANGE_FROM NEW pattern) — failing merge-base degrades to DIFF_ERROR=1 and script continues"
else
    note_fail "guilt (RANGE_FROM NEW pattern) — expected DIFF_ERROR=1 + reached-end, got: $out5"
fi

# ---------------------------------------------------------------------------
# Case 6 (innocence, RANGE_FROM NEW pattern): a SUCCEEDING merge-base (the
# ordinary case — a normal push whose branch has a real common ancestor)
# must behave exactly as before the fix — RANGE_FROM gets a real value,
# DIFF_ERROR stays unset, and execution reaches the classifier. Uses
# `git merge-base HEAD HEAD` — always succeeds, returns HEAD's own sha, zero
# dependency on any particular branch topology or fetched remote.
# ---------------------------------------------------------------------------
out6="$(sh -e -c '
    RANGE_FROM="$(git merge-base HEAD HEAD 2>/dev/null)" || RANGE_FROM=""
    if [ -z "$RANGE_FROM" ]; then
        echo "DIFF_ERROR=1"
    else
        echo "DIFF_ERROR=0 reached-classifier"
    fi
' 2>/dev/null)"
if [ "$out6" = "DIFF_ERROR=0 reached-classifier" ]; then
    note_pass "innocence (RANGE_FROM NEW pattern) — a normal successful merge-base still reaches the classifier"
else
    note_fail "innocence (RANGE_FROM NEW pattern) — expected DIFF_ERROR=0 reached-classifier, got: $out6"
fi

# ---------------------------------------------------------------------------
# Case 7 (tripwire, task #39): grep the LIVE hook file — a bare unguarded
# RANGE_FROM="$( ... )" (no "|| RANGE_FROM=" on the same line) must never
# reappear. Mirrors Case 4's method for the sibling variable.
# ---------------------------------------------------------------------------
if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire (RANGE_FROM) — $HOOK_FILE not found (cannot verify)"
else
    bad_lines5="$(grep -n 'RANGE_FROM="\$(' "$HOOK_FILE" | grep -v '|| RANGE_FROM=' || true)"
    if [ -z "$bad_lines5" ]; then
        note_pass "tripwire (RANGE_FROM) — no bare unguarded RANGE_FROM=\"\$(...)\" in $HOOK_FILE"
    else
        note_fail "tripwire (RANGE_FROM) — bare unguarded RANGE_FROM assignment reintroduced in $HOOK_FILE: $bad_lines5"
    fi

    # TEMPLATE_OWNER's assignment is a line-continued (\) statement — the
    # opening "TEMPLATE_OWNER=\"$(" and the closing "|| TEMPLATE_OWNER=..."
    # guard live on DIFFERENT physical lines, so (unlike Cases 4/7's single-
    # line assignments) a same-line grep would false-positive FAIL even when
    # the guard is present. Widen the window: -A2 pulls the assignment line
    # plus its two continuation lines, then check the guard is anywhere in
    # that block.
    owner_block="$(grep -A2 'TEMPLATE_OWNER="\$(' "$HOOK_FILE" || true)"
    if [ -n "$owner_block" ] && printf '%s' "$owner_block" | grep -q '|| TEMPLATE_OWNER='; then
        note_pass "tripwire (TEMPLATE_OWNER) — no bare unguarded TEMPLATE_OWNER=\"\$(...)\" in $HOOK_FILE"
    else
        note_fail "tripwire (TEMPLATE_OWNER) — bare unguarded TEMPLATE_OWNER assignment reintroduced in $HOOK_FILE: $owner_block"
    fi
fi

# ---------------------------------------------------------------------------
# Case 8 (guilt, task #60, 2026-07-27): CLONE_DB used to be named only
# nuzantara_test_run_$$ — PID alone, which recycles. When a new push's $$
# collides with a STRANDED clone's old name (measured live: 15 stranded
# clones, 561 MB, on this exact box), the CREATE loop below failed 3/3 with
# NO exit 1 — the whole backend suite silently never ran and the push
# succeeded anyway. This case reproduces the collision against REAL
# Postgres (template0, always present, fast) and proves the OLD pattern
# (CREATE with no defensive drop) genuinely fails on it — the failure mode
# #60 exists to fix, not a synthetic stand-in for it. Requires local PG;
# skips itself cleanly if unreachable (same posture the hook itself takes).
# ---------------------------------------------------------------------------
PGCHECK_BIN="$(command -v pg_isready || echo /opt/homebrew/opt/postgresql@17/bin/pg_isready)"
if [ -x "$PGCHECK_BIN" ] && "$PGCHECK_BIN" -h 127.0.0.1 -p 5432 -q 2>/dev/null; then
    PSQL_BIN="$(command -v psql || echo /opt/homebrew/opt/postgresql@17/bin/psql)"
    PROBE_DB="nuzantara_pretest_probe_60_$$"
    "$PSQL_BIN" -h 127.0.0.1 -p 5432 -d postgres -tAc "CREATE DATABASE \"$PROBE_DB\" TEMPLATE template0;" >/dev/null 2>&1
    "$PSQL_BIN" -h 127.0.0.1 -p 5432 -d postgres -tAc "CREATE DATABASE \"$PROBE_DB\" TEMPLATE template0;" >/dev/null 2>&1
    guilt_rc=$?
    if [ "$guilt_rc" != "0" ]; then
        note_pass "guilt (task #60, OLD pattern) — CREATE with no defensive drop fails on a name collision (rc=$guilt_rc), matching the real bug"
    else
        note_fail "guilt (task #60, OLD pattern) — expected CREATE to fail on collision, it succeeded (test setup itself may be broken)"
    fi

    # -----------------------------------------------------------------------
    # Case 9 (innocence, task #60): same collision, NEW pattern — a
    # defensive `DROP DATABASE IF EXISTS ... WITH (FORCE)` immediately
    # before CREATE. Must succeed even though the name is currently taken by
    # the stranded probe DB from Case 8 — proving the fix, not just its
    # absence.
    # -----------------------------------------------------------------------
    "$PSQL_BIN" -h 127.0.0.1 -p 5432 -d postgres -tAc "DROP DATABASE IF EXISTS \"$PROBE_DB\" WITH (FORCE);" >/dev/null 2>&1
    "$PSQL_BIN" -h 127.0.0.1 -p 5432 -d postgres -tAc "CREATE DATABASE \"$PROBE_DB\" TEMPLATE template0;" >/dev/null 2>&1
    innocence_rc=$?
    if [ "$innocence_rc" = "0" ]; then
        note_pass "innocence (task #60, NEW pattern) — defensive DROP IF EXISTS then CREATE succeeds despite the collision"
    else
        note_fail "innocence (task #60, NEW pattern) — expected CREATE to succeed after the defensive drop, rc=$innocence_rc"
    fi
    "$PSQL_BIN" -h 127.0.0.1 -p 5432 -d postgres -tAc "DROP DATABASE IF EXISTS \"$PROBE_DB\" WITH (FORCE);" >/dev/null 2>&1
else
    note_pass "guilt+innocence (task #60) — SKIPPED, no local PostgreSQL reachable (same graceful posture as the hook itself)"
fi

# ---------------------------------------------------------------------------
# Case 10 (tripwire, task #60): the LIVE hook must (a) generate CLONE_DB
# with a random component alongside $$ (PID alone recycles — that is the
# whole bug), and (b) run a defensive `DROP DATABASE IF EXISTS ... WITH
# (FORCE)` on CLONE_DB before the CREATE retry loop, not after.
# ---------------------------------------------------------------------------
if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire (task #60) — $HOOK_FILE not found (cannot verify)"
else
    clone_line="$(grep -n 'CLONE_DB="nuzantara_test_run_' "$HOOK_FILE" | head -1)"
    if printf '%s' "$clone_line" | grep -q 'RANDOM'; then
        note_pass "tripwire (task #60) — CLONE_DB includes a random component, not PID alone: $clone_line"
    else
        note_fail "tripwire (task #60) — CLONE_DB is PID-only again (recycling collision reintroduced): $clone_line"
    fi

    create_line="$(grep -n 'CREATE_OK=0' "$HOOK_FILE" | head -1 | cut -d: -f1)"
    # NOTE: the bare literal 'DROP DATABASE IF EXISTS "$CLONE_DB" WITH
    # (FORCE)' is NOT a unique anchor — cleanup_clone()'s pre-existing trap
    # drop uses the exact same text (task #60's own guard-over-match bug,
    # caught by the mandatory stash-and-rerun non-vacuousness check: this
    # naive grep stayed green even with the fix reverted, because it always
    # found cleanup_clone()'s unrelated drop instead). Anchor on the unique
    # comment marker that only precedes the NEW pre-CREATE drop, then find
    # the drop line nearest AFTER it.
    predrop_marker_line="$(grep -n '# #60 (2026-07-27): defensive pre-drop' "$HOOK_FILE" | head -1 | cut -d: -f1)"
    predrop_line=""
    if [ -n "$predrop_marker_line" ]; then
        predrop_offset="$(tail -n "+$predrop_marker_line" "$HOOK_FILE" | grep -n 'DROP DATABASE IF EXISTS \\"\$CLONE_DB\\" WITH (FORCE)' | head -1 | cut -d: -f1)"
        if [ -n "$predrop_offset" ]; then
            predrop_line=$((predrop_marker_line + predrop_offset - 1))
        fi
    fi
    if [ -n "$predrop_line" ] && [ -n "$create_line" ] && [ "$predrop_line" -lt "$create_line" ]; then
        note_pass "tripwire (task #60) — defensive DROP DATABASE IF EXISTS on CLONE_DB precedes the CREATE loop (line $predrop_line < $create_line)"
    else
        note_fail "tripwire (task #60) — defensive pre-drop missing or not before the CREATE loop (predrop=$predrop_line create=$create_line)"
    fi
fi

# ---------------------------------------------------------------------------
# Case 11 (innocence, task #60): the deliberate "no local PostgreSQL" /
# "not provisioned" / "no venv" skip branches must still be the FIRST
# things checked — #60's new defensive-drop code must sit strictly INSIDE
# the final `else`, never ahead of those three skip checks. A machine with
# no local PG (a normal dev laptop) must keep degrading gracefully, not
# start touching Postgres at all. Structural check: the "no local
# PostgreSQL" skip message's line number must precede the defensive-drop
# line's, with no unmatched top-level `fi` closing that if-chain in
# between (which would mean the drop escaped the gate).
# ---------------------------------------------------------------------------
if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire (task #60, no-PG skip ordering) — $HOOK_FILE not found (cannot verify)"
else
    nopg_line="$(grep -n 'SKIP Python tests — no local PostgreSQL' "$HOOK_FILE" | head -1 | cut -d: -f1)"
    # Same non-unique-literal trap as Case 10 above — anchor on the unique
    # comment marker, not the bare DROP text (matches cleanup_clone()'s
    # pre-existing, unrelated trap drop too).
    predrop_marker_line2="$(grep -n '# #60 (2026-07-27): defensive pre-drop' "$HOOK_FILE" | head -1 | cut -d: -f1)"
    predrop_line2=""
    if [ -n "$predrop_marker_line2" ]; then
        predrop_offset2="$(tail -n "+$predrop_marker_line2" "$HOOK_FILE" | grep -n 'DROP DATABASE IF EXISTS \\"\$CLONE_DB\\" WITH (FORCE)' | head -1 | cut -d: -f1)"
        if [ -n "$predrop_offset2" ]; then
            predrop_line2=$((predrop_marker_line2 + predrop_offset2 - 1))
        fi
    fi
    if [ -n "$nopg_line" ] && [ -n "$predrop_line2" ] && [ "$nopg_line" -lt "$predrop_line2" ]; then
        between_bare_fi="$(sed -n "${nopg_line},${predrop_line2}p" "$HOOK_FILE" | grep -c '^fi$' || true)"
        if [ "${between_bare_fi:-0}" -eq 0 ]; then
            note_pass "innocence (task #60, no-PG skip ordering) — no local PostgreSQL skip (line $nopg_line) still precedes the clone logic (line $predrop_line2), same if-chain (0 closing 'fi' between)"
        else
            note_fail "innocence (task #60, no-PG skip ordering) — $between_bare_fi bare 'fi' between the skip check and the clone logic — the clone logic may have escaped the gate"
        fi
    else
        note_fail "innocence (task #60, no-PG skip ordering) — could not locate both anchors (nopg=$nopg_line predrop=$predrop_line2)"
    fi
fi

echo "---"
echo "$pass passed, $fail failed"

if [ "$fail" -eq 0 ]; then
    exit 0
else
    exit 1
fi
