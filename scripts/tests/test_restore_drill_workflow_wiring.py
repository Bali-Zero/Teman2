"""`.github/workflows/restore-drill.yml`'s own restore/verify/notify steps must
never let a swallowed exit code mask a genuine restore-drill failure.

Split out of test_restore_drill_verify.py (which stays scoped to
restore_drill_verify.py, the Python verifier, in isolation): this file's
subject is the WORKFLOW YAML wiring, not the Python module, and it must ship
together with the workflow diff it pins — a version of this file run against
an unpatched restore-drill.yml fails all five original tests below (verified:
this is exactly what happened when the two were first split into separate
PRs). Executed on every PR touching the drill by
`.github/workflows/restore-drill-wiring-tests.yml` (added the same day the
BLOCKER/HIGH findings below were cured: before that file existed, `grep -rn
restore_drill .github/workflows/` matched only restore-drill.yml itself — no
workflow named this file at all, and the only sweep over scripts/tests/ is
`continue-on-error: true` and not `pull_request:`-triggered. A guard nothing
can fail is the same disease this file's own tests exist to cure, one level
up — see that workflow's own header).

The plan's own acceptance snippet asserts a blanket `'|| true' not in
Path(...).read_text()` -- a substring check against the literal shell idiom.
This workflow no longer contains that idiom ANYWHERE (restore, log-tail,
query, and BOTH notification steps all capture their own exit status
explicitly instead of a bare `|| true`), so that blanket assertion now PASSES
too -- not because the notification steps' failure-tolerance was dropped, but
because it is implemented with an explicit capture-and-surface pattern rather
than the older bare swallow. The tests below pin the SUBSTANCE (what a future
edit must not silently break), not the surface-level absence of one string.

Run:  pytest scripts/tests/test_restore_drill_workflow_wiring.py -q
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "restore-drill.yml"


def _load_workflow() -> dict[str, Any]:
    return yaml.safe_load(_WORKFLOW.read_text())


def _run_restore_drill_step() -> str:
    doc = _load_workflow()
    for step in doc["jobs"]["restore-drill"]["steps"]:
        if step.get("name") == "Run restore drill":
            return step["run"]
    raise AssertionError('no step named "Run restore drill" found -- broken test, not a clean file')


def _run_failure_notify_step() -> str:
    doc = _load_workflow()
    for step in doc["jobs"]["restore-drill"]["steps"]:
        if step.get("name") == "Telegram alert on failure":
            return step["run"]
    raise AssertionError('no step named "Telegram alert on failure" found -- broken test, not a clean file')


def _strip_trailing_comment(line: str) -> str:
    """Return `line` with any unquoted trailing `#`-comment removed.

    Deliberately NOT a full shell lexer -- backslash-escaped quotes, command
    substitutions, and here-docs are all out of scope, and this workflow's
    own lines never need them. A `#` inside a single- or double-quoted
    string is never comment-start. An unquoted `#` is comment-start only
    when it sits at the very start of the line or is immediately preceded
    by whitespace (bash's own "start of word" rule for when `#` begins a
    comment) -- so `${#arr[@]}` (the `#` directly follows `{`, not
    whitespace) survives untouched, and so does a mid-token `#` like
    `abc#def`. NOT caught (declared, not silently): a `#` immediately after
    `;`/`&`/`|`/`(` with no intervening space also starts a word in real
    bash and would NOT be stripped here -- this workflow's own lines never
    do that, so the narrower rule is enough here without becoming a general
    shell lexer.
    """
    in_single = False
    in_double = False
    prev = ""
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or prev in (" ", "\t"):
                return line[:i]
        prev = ch
    return line


def _executable_lines(body: str) -> list[str]:
    """Lines of a step's `run:` body with any trailing `#`-comment stripped,
    excluding lines that are blank or comment-only after stripping.

    Wider than the old rule of "strip only lines whose STRIPPED form starts
    with #": moving a load-bearing flag into a TRAILING comment (`psql ...
    # -v ON_ERROR_STOP=1`) used to satisfy a substring check against the raw
    line while bash executes none of it -- see
    test_executable_lines_strips_trailing_comment_not_just_full_line_comment
    for the pinned repro of that bypass.
    """
    out: list[str] = []
    for ln in body.splitlines():
        stripped = _strip_trailing_comment(ln)
        if stripped.strip():
            out.append(stripped)
    return out


def _logical_lines(lines: list[str]) -> list[str]:
    """Join `_executable_lines` output on trailing `\\`-continuations so a
    multi-line command invocation counts as ONE unit for the adjacency
    checks below.

    Deliberately narrow: a `\\` at the very end of an (already
    comment-stripped) line is treated as "this command continues on the
    next line" -- this workflow's own multi-line invocations (the
    gunzip|psql pipe, the restore_drill_verify.py call, both Telegram curl
    calls) all use exactly this form and nothing more exotic (no here-doc
    line spanning a continuation, no quoted trailing backslash).
    """
    out: list[str] = []
    buf = ""
    for ln in lines:
        if ln.rstrip().endswith("\\"):
            buf += ln.rstrip()[:-1] + " "
            continue
        out.append(buf + ln)
        buf = ""
    if buf:
        # a dangling continuation with nothing left to join to -- surface it
        # as its own (backslash-stripped) line rather than silently
        # dropping it; malformed input should be visible, not swallowed.
        out.append(buf.rstrip())
    return out


def _restore_pipeline_psql_invocation(body: str) -> str | None:
    """The SPECIFIC psql invocation that IS the restore: the second stage of
    the `gunzip | psql` pipeline whose exit status is captured into
    `_PIPE_STATUSES` on the very next executable line.

    Structural identification, not "any executable line containing psql
    \"$DSN\"" -- the latter both under-matches (a dead/debug line elsewhere
    in the body can carry the same substring and satisfy a check the REAL
    invocation no longer does, e.g. after a refactor to positional
    connection flags that drops `$DSN` entirely) and over-matches (an
    unrelated, correctly flagless second psql call -- a plain sanity probe
    -- would wrongly be required to carry the same flag). See
    test_restore_pipeline_psql_invocation_ignores_dead_lookalike_lines and
    test_restore_pipeline_psql_invocation_ignores_unrelated_second_psql_call
    for both directions, pinned against synthetic bodies.

    Limit: assumes this workflow's own single-pipe-then-capture shape (one
    `gunzip -c ... | ... psql ...` logical line immediately followed by the
    `_PIPE_STATUSES=(...)` capture) -- not a general pipeline-vs-capture
    matcher for arbitrary shell.
    """
    logical = _logical_lines(_executable_lines(body))
    for i, ln in enumerate(logical):
        if "gunzip -c" in ln and "psql" in ln and i + 1 < len(logical):
            if '_PIPE_STATUSES=("${PIPESTATUS[@]}")' in logical[i + 1]:
                return ln
    return None


def _if_block(body: str, if_marker: str) -> str:
    """Return the raw lines from the `if [...]` line containing `if_marker`
    through its matching `fi`, inclusive.

    Balance-counts `if`/`fi` lines the same way
    test_restore_log_tail_is_unconditional_not_gated_on_success does (see
    that test's docstring for the documented bypasses this simple counting
    does not catch: `&&`-chained conditionals, `case`, subshells, functions
    -- this helper inherits the same limit, declared rather than silently
    assumed complete). Raises (broken-test failure, not a silent False) if
    the marker or a balancing `fi` is not found.
    """
    lines = body.splitlines()
    start = next((i for i, ln in enumerate(lines) if if_marker in ln), None)
    if start is None:
        raise AssertionError(f"if-block marker {if_marker!r} not found -- broken test, not a clean file")
    depth = 0
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("if ") or stripped == "if":
            depth += 1
        if stripped == "fi" or stripped.startswith("fi;") or stripped.startswith("fi "):
            depth -= 1
            if depth == 0:
                return "\n".join(lines[start : i + 1])
    raise AssertionError(f"unbalanced if/fi for marker {if_marker!r} -- broken test, not a clean file")


def test_workflow_contains_no_bare_swallow_anywhere():
    """The literal `|| true` idiom this drill used to rely on for restore,
    log-tail, query, AND both notification steps is gone everywhere -- not
    because the notification steps' failure-tolerance was dropped, but
    because it moved to an explicit capture (see the tests below)."""
    text = _WORKFLOW.read_text()
    assert "|| true" not in text


def test_restore_and_verify_capture_their_own_exit_code_not_a_swallow():
    """Pins the actual mechanism that replaced `-v ON_ERROR_STOP=0 ... || true`:
    an explicit PIPESTATUS/`$?` capture bracketed by set+e/set-e, checked, and
    turned into an `exit` -- never a bare `|| true` that discards the fact a
    restore or a verification failed.

    The ON_ERROR_STOP=1 check is anchored to the psql invocation that IS the
    restore -- identified STRUCTURALLY (see `_restore_pipeline_psql_invocation`),
    not by "any executable line containing psql \"$DSN\"" as an earlier
    version of this test did. That earlier form both under-matched (a dead
    debug-only line elsewhere carrying the same substring could satisfy the
    check even after the real invocation stopped using `$DSN`) and
    over-matched (an unrelated, correctly flagless second psql call would be
    wrongly required to carry the flag too) -- see the two dedicated tests
    below for both directions, pinned against synthetic bodies so this
    integration test does not have to fabricate either scenario against the
    real workflow.

    PIPESTATUS[1] is psql's own exit code; PIPESTATUS[0] is gunzip's. Both
    are read from the SAME captured array (GUNZIP_RC and RESTORE_RC) -- a
    truncated/corrupt `.gz` can make gunzip itself exit non-zero while psql,
    fed only the valid PREFIX gunzip managed to emit before dying, still
    exits 0; RESTORE_RC (index 1) alone cannot see that. See
    test_gunzip_failure_is_detected_and_reported_under_its_own_title for the
    dedicated check on that branch."""
    body = _run_restore_drill_step()
    invocation = _restore_pipeline_psql_invocation(body)
    assert invocation is not None, "no restore pipeline psql invocation found -- broken test, not a clean file"
    assert "ON_ERROR_STOP=1" in invocation, (
        "the restore pipeline's psql invocation must carry ON_ERROR_STOP=1, "
        f"not just a comment/message mentioning it -- got: {invocation!r}"
    )
    # Belt-and-braces, NOT sufficient on its own (a deleted flag would also
    # satisfy this): the disabled form must not be lurking anywhere else in
    # the body either, e.g. a second, dead invocation. Scoped to
    # _executable_lines for the same reason as the positive check above --
    # a `#`-comment mentioning "ON_ERROR_STOP=0" (e.g. explaining the OLD
    # value) is prose, not a second invocation, and rewording it must be
    # able to neither satisfy nor break this test.
    assert not any("ON_ERROR_STOP=0" in ln for ln in _executable_lines(body))
    assert "_PIPE_STATUSES=(\"${PIPESTATUS[@]}\")" in body
    assert "GUNZIP_RC=${_PIPE_STATUSES[0]}" in body, "gunzip's own exit status must be read from the captured array"
    assert "RESTORE_RC=${_PIPE_STATUSES[1]}" in body
    assert "RESTORE_RC=${PIPESTATUS[0]}" not in body, "must not read gunzip's exit code instead of psql's"
    assert 'if [ "$RESTORE_RC" -ne 0 ]' in body
    assert "VERIFY_RC=$?" in body
    assert 'exit "$VERIFY_RC"' in body


def test_gunzip_failure_is_detected_and_reported_under_its_own_title():
    """A truncated/corrupt `.gz` can make gunzip exit non-zero while psql,
    fed only the valid PREFIX gunzip managed to emit before dying, still
    exits 0 -- RESTORE_RC (index 1) alone cannot see this class of failure.
    GUNZIP_RC (index 0 of the SAME captured `_PIPE_STATUSES` array) must be
    checked SEPARATELY, and its failure must be reported under its OWN
    title -- folding it into the "Restore aborted (ON_ERROR_STOP=1)"
    message (which specifically means "psql itself rejected a statement")
    would send the reader to fix the wrong component: psql may have exited
    0 on the truncated prefix it actually received.

    (Narrower than "every corrupt .gz" in practice -- a truncation usually
    lands mid-statement, which psql itself rejects under ON_ERROR_STOP=1 and
    reports via RESTORE_RC anyway; the silent case this closes needs the
    truncation to land on a statement boundary. The check does not assume
    or claim otherwise; it closes the gap regardless of how narrow it is.)"""
    body = _run_restore_drill_step()
    assert "GUNZIP_RC=${_PIPE_STATUSES[0]}" in body
    assert 'if [ "$GUNZIP_RC" -ne 0 ]' in body
    block = _if_block(body, 'if [ "$GUNZIP_RC" -ne 0 ]')
    assert "::error" in block, f"gunzip failure must be reported, not just detected -- block: {block!r}"
    assert "exit" in block, f"gunzip failure must abort the step non-zero -- block: {block!r}"
    assert "Restore aborted (ON_ERROR_STOP=1)" not in block, (
        "a gunzip failure must not be reported under the psql-abort title -- "
        f"it misdirects the reader to the wrong component -- block: {block!r}"
    )


def test_restore_rc_nonzero_branch_actually_exits_nonzero():
    """Emptying the body of `if [ "$RESTORE_RC" -ne 0 ]; then ... fi` (e.g.
    dropping `exit 3` while leaving the `::error` echo in place) keeps every
    OTHER assertion in this file green -- a restore that aborts on a LATE
    statement (all data loaded, then e.g. a trailing superuser-only
    `ALTER ... OWNER` rejected) would then flow straight into verify, verify
    passes on the data that DID load, and the drill reports green: the exact
    fail-open this workflow's own ON_ERROR_STOP=1 risk-note names as the
    point of the change in the first place."""
    body = _run_restore_drill_step()
    block = _if_block(body, 'if [ "$RESTORE_RC" -ne 0 ]')
    assert "exit 3" in block, f"the RESTORE_RC-nonzero branch must exit non-zero -- got block: {block!r}"


def test_restore_pipeline_capture_is_bracketed_by_set_plus_minus_e_and_adjacent():
    """The gunzip|psql pipeline and its `_PIPE_STATUSES`/GUNZIP_RC/RESTORE_RC
    captures must sit inside ONE `set +e` / `set -e` bracket with NOTHING
    else between the pipeline and either bracket boundary.

    Bracket: deleting the `set +e` immediately before the pipeline leaves
    every OTHER assertion in this file green while, under the step's live
    `set -euo pipefail`, a failing psql now kills the step INSTANTLY --
    `_PIPE_STATUSES` never executes, the log tail never prints, no
    `::error` is ever emitted (scar W101, errexit decapitation).

    Adjacency: `_PIPE_STATUSES=(...)` must be the line immediately after the
    pipeline -- any intervening command (even a no-op `:`) resets
    $PIPESTATUS to THAT command's own single-element pipeline first (see the
    workflow's own comment on this exact footgun, directly above the
    pipeline). GUNZIP_RC and RESTORE_RC must in turn be read from that SAME
    captured array on the two lines immediately after, for the identical
    reason.

    Checked among LOGICAL lines (comments stripped, blanks dropped,
    `\\`-continuations joined into one unit, since the pipeline itself spans
    three raw lines) -- adjacency-by-substring-in-body would miss all of
    this."""
    body = _run_restore_drill_step()
    logical = _logical_lines(_executable_lines(body))
    idx = next(
        (i for i, ln in enumerate(logical) if 'psql "$DSN" -v ON_ERROR_STOP=1' in ln),
        None,
    )
    assert idx is not None, "restore pipeline line not found -- broken test, not a clean file"
    assert idx - 1 >= 0 and logical[idx - 1].strip() == "set +e", (
        f"the gunzip|psql pipeline must be immediately preceded by `set +e` -- got: {logical[idx - 1 : idx]!r}"
    )
    assert idx + 1 < len(logical) and '_PIPE_STATUSES=("${PIPESTATUS[@]}")' in logical[idx + 1], (
        f"_PIPE_STATUSES capture must be the very next executable line -- got: {logical[idx + 1 : idx + 2]!r}"
    )
    assert idx + 2 < len(logical) and "GUNZIP_RC=${_PIPE_STATUSES[0]}" in logical[idx + 2], (
        f"GUNZIP_RC must be read immediately after the capture -- got: {logical[idx + 2 : idx + 3]!r}"
    )
    assert idx + 3 < len(logical) and "RESTORE_RC=${_PIPE_STATUSES[1]}" in logical[idx + 3], (
        f"RESTORE_RC must be read immediately after GUNZIP_RC -- got: {logical[idx + 3 : idx + 4]!r}"
    )
    assert idx + 4 < len(logical) and logical[idx + 4].strip() == "set -e", (
        f"RESTORE_RC capture must be immediately followed by `set -e` -- got: {logical[idx + 4 : idx + 5]!r}"
    )


def test_verify_capture_is_bracketed_by_set_plus_minus_e_and_adjacent():
    """Same bracket + adjacency requirement as the restore pipeline above,
    applied to the `restore_drill_verify.py` invocation and its VERIFY_RC
    capture: `set +e` immediately before, `VERIFY_RC=$?` as the very next
    executable line (inserting even a no-op `:` between the invocation and
    this capture makes `$?` silently start reading THAT command's exit code
    instead of the verifier's), and `set -e` immediately after."""
    body = _run_restore_drill_step()
    logical = _logical_lines(_executable_lines(body))
    idx = next(
        (i for i, ln in enumerate(logical) if "restore_drill_verify.py" in ln),
        None,
    )
    assert idx is not None, "verifier invocation line not found -- broken test, not a clean file"
    assert idx - 1 >= 0 and logical[idx - 1].strip() == "set +e", (
        f"the verifier invocation must be immediately preceded by `set +e` -- got: {logical[idx - 1 : idx]!r}"
    )
    assert idx + 1 < len(logical) and "VERIFY_RC=$?" in logical[idx + 1], (
        "VERIFY_RC=$? must be the very next executable line after the "
        f"restore_drill_verify.py invocation -- got: {logical[idx + 1 : idx + 2]!r}"
    )
    assert idx + 2 < len(logical) and logical[idx + 2].strip() == "set -e", (
        f"VERIFY_RC capture must be immediately followed by `set -e` -- got: {logical[idx + 2 : idx + 3]!r}"
    )


def test_restore_log_tail_is_unconditional_not_gated_on_success():
    """The old `tail -25 /tmp/restore.log || true` printed regardless of
    restore outcome; the replacement must too, or a failed restore under
    ON_ERROR_STOP=1 goes back to being illegible (the exact failure mode the
    PR's ON_ERROR_STOP=1 risk section names as unresolved without this).

    Checked by BALANCE, not by scanning the tail line alone: an `if` that
    wraps the tail command sits on a SEPARATE, earlier line -- a same-line
    check would miss it entirely (the errexit-decap lint's own lesson:
    "$? may sit on the SAME line ... looking only at following lines is an
    under-match" applies here in the opposite direction -- looking only at
    the SAME line misses a wrap that starts above it). Every `if`/`fi` in the
    body up to and including the tail line must balance to zero: if it does
    not, something between the top of the script and the tail command opened
    a conditional that was never closed before the tail ran.

    DECLARED LIMIT, not silently assumed complete: this is a line-anchored
    `if `/`fi` token counter, not a shell parser. It is blind to a
    conditional expressed any other way -- `[ "$RESTORE_RC" -eq 0 ] && {
    tail -25 /tmp/restore.log; }` (an `&&`-chained gate, no `if`/`fi` token
    at all), a `case ... esac` branch, a subshell `( ... )`, or a function
    definition wrapping the tail call -- every one of those would keep this
    counter's depth at zero while genuinely gating the tail line. A residual
    declared here is debt to be closed later if one of these shapes ever
    shows up in this step; a residual left unstated would be a lie about
    what this test actually proves."""
    body = _run_restore_drill_step()
    lines = body.splitlines()
    tail_idx = next(
        (i for i, ln in enumerate(lines) if "tail -25 /tmp/restore.log" in ln),
        None,
    )
    assert tail_idx is not None, "log-tail line not found -- broken test, not a clean file"
    assert "|| true" not in lines[tail_idx]

    depth = 0
    for ln in lines[: tail_idx + 1]:
        stripped = ln.strip()
        if stripped.startswith("if ") or stripped == "if":
            depth += 1
        if stripped == "fi" or stripped.startswith("fi;") or stripped.startswith("fi "):
            depth -= 1
    assert depth == 0, (
        f"the log-tail line sits inside an unclosed if-block (depth={depth}) -- "
        "it must run unconditionally, restore success or failure"
    )


def test_telegram_success_notify_captures_rc_and_never_lets_it_gate_the_exit():
    """The success-notify curl must capture its own rc into TG_RC and log it,
    but TG_RC must never appear on the same line as `exit` -- a Telegram
    failure must not be ABLE to change the drill's own exit code.

    DECLARED LIMIT: the same-line check below is evadable by a line
    continuation (`exit \\` on one line, `"$TG_RC"` on the next) -- an
    adversarial rewrite, not one this workflow's own style would produce.
    Named here rather than silently assumed impossible; not built out into
    a multi-line parser for a bypass this narrow."""
    body = _run_restore_drill_step()
    assert "TG_RC=$?" in body
    assert "::warning::telegram success-notify" in body
    assert "TG_RC" in body and "response=${TG_BODY}" in body
    for line in body.splitlines():
        if "TG_RC" in line:
            assert "exit" not in line, f"a Telegram outcome must never gate an exit: {line!r}"


def test_telegram_success_notify_rc_capture_is_bracketed_by_set_plus_minus_e():
    """`TG_RC=$?` must sit between a `set +e` (immediately before the curl
    call it captures) and a `set -e` (immediately after) -- deleting either
    bracket leaves every OTHER assertion in this file green while a curl
    timeout (rc=28) under the step's live errexit now kills the step
    mid-run on a HEALTHY drill, reporting success as failure."""
    body = _run_restore_drill_step()
    logical = _logical_lines(_executable_lines(body))
    rc_idx = next((i for i, ln in enumerate(logical) if "TG_RC=$?" in ln), None)
    assert rc_idx is not None, "TG_RC=$? capture not found in success-notify path -- broken test, not a clean file"
    assert rc_idx + 1 < len(logical) and logical[rc_idx + 1].strip() == "set -e", (
        f"TG_RC=$? must be immediately followed by `set -e` -- got: {logical[rc_idx + 1 : rc_idx + 2]!r}"
    )
    assert rc_idx - 1 >= 0 and "TG_BODY=" in logical[rc_idx - 1], (
        "expected the curl/TG_BODY assignment immediately before TG_RC=$? -- broken test, not a clean file"
    )
    assert rc_idx - 2 >= 0 and logical[rc_idx - 2].strip() == "set +e", (
        f"the curl call TG_RC=$? captures must be preceded by `set +e` -- got: {logical[rc_idx - 2 : rc_idx - 1]!r}"
    )


def test_telegram_failure_notify_captures_rc_and_never_lets_it_gate_the_exit():
    """Same requirement as the success-notify test above, applied to the
    'Telegram alert on failure' step.

    DECLARED LIMIT: same line-continuation bypass as the success-notify
    test's docstring names -- not repeated in full here, see that
    docstring."""
    body = _run_failure_notify_step()
    assert "TG_RC=$?" in body
    assert "::warning::telegram failure-notify" in body
    for line in body.splitlines():
        if "TG_RC" in line:
            assert "exit" not in line, f"a Telegram outcome must never gate an exit: {line!r}"


def test_telegram_failure_notify_rc_capture_is_bracketed_by_set_plus_minus_e():
    """Same bracket requirement as the success-notify path above, applied to
    the 'Telegram alert on failure' step."""
    body = _run_failure_notify_step()
    logical = _logical_lines(_executable_lines(body))
    rc_idx = next((i for i, ln in enumerate(logical) if "TG_RC=$?" in ln), None)
    assert rc_idx is not None, "TG_RC=$? capture not found in failure-notify step -- broken test, not a clean file"
    assert rc_idx + 1 < len(logical) and logical[rc_idx + 1].strip() == "set -e", (
        f"TG_RC=$? must be immediately followed by `set -e` -- got: {logical[rc_idx + 1 : rc_idx + 2]!r}"
    )
    assert rc_idx - 1 >= 0 and "TG_BODY=" in logical[rc_idx - 1], (
        "expected the curl/TG_BODY assignment immediately before TG_RC=$? -- broken test, not a clean file"
    )
    assert rc_idx - 2 >= 0 and logical[rc_idx - 2].strip() == "set +e", (
        f"the curl call TG_RC=$? captures must be preceded by `set +e` -- got: {logical[rc_idx - 2 : rc_idx - 1]!r}"
    )


def test_executable_lines_strips_trailing_comment_not_just_full_line_comment():
    """A trailing `# comment` after real shell tokens must be stripped too,
    not just a line that is ENTIRELY a comment -- otherwise moving a
    load-bearing flag into a trailing comment (`psql ... # -v
    ON_ERROR_STOP=1`) satisfies a substring check against the RAW line while
    bash executes NONE of it. A `#` inside a quoted string, and a `#` that
    is part of a parameter-expansion token like `${#arr[@]}` (not preceded
    by whitespace or start-of-line), must both survive untouched -- a
    deliberately narrow rule (bash's own "start of word" comment rule, not
    a full lexer; documented as a limit on `_strip_trailing_comment`, not
    claimed complete)."""
    body = (
        'psql "$DSN" -v ON_ERROR_STOP=1 > /tmp/restore.log 2>&1  '
        "# note: -v ON_ERROR_STOP=1 restores fail-fast\n"
        'ANOTHER=$(echo "has a literal # inside quotes")\n'
        "LEN=${#SOME_ARRAY[@]}\n"
        "# full-line comment, unaffected either way\n"
        "psql \"$DSN\" > /tmp/restore.log 2>&1 # -v ON_ERROR_STOP=1\n"
    )
    lines = _executable_lines(body)

    # line 1: trailing comment stripped, executable prefix (with the REAL
    # flag) preserved, "note:" prose gone.
    assert any('psql "$DSN" -v ON_ERROR_STOP=1' in ln and "note:" not in ln for ln in lines)

    # line 2: `#` inside a double-quoted string must NOT be treated as a
    # comment start -- the whole assignment survives intact.
    assert any("has a literal # inside quotes" in ln for ln in lines)

    # line 3: `${#SOME_ARRAY[@]}` -- `#` not preceded by whitespace, must
    # survive untouched (not a comment start).
    assert any("LEN=${#SOME_ARRAY[@]}" in ln for ln in lines)

    # full-line comment: excluded entirely (unchanged prior behaviour).
    assert not any("full-line comment" in ln for ln in lines)

    # line 5 -- THE BYPASS CASE: the flag lives ONLY in a trailing comment;
    # the executable prefix must NOT contain it after stripping.
    bypass_lines = [ln for ln in lines if 'psql "$DSN" > /tmp/restore.log' in ln]
    assert bypass_lines, "bypass line missing from executable lines entirely"
    assert not any("ON_ERROR_STOP=1" in ln for ln in bypass_lines), (
        "a flag moved into a TRAILING comment must not satisfy an "
        f"executable-line check -- got: {bypass_lines!r}"
    )


def test_restore_pipeline_psql_invocation_ignores_dead_lookalike_lines():
    """UNDER-match direction: a dead/decoy line elsewhere in the body that
    happens to contain the exact substring `psql "$DSN" -v ON_ERROR_STOP=1`
    (e.g. a debug-only branch never reached at runtime) must NOT be picked
    as THE restore invocation -- only the psql that is actually the second
    stage of the CAPTURED gunzip|psql pipeline qualifies. A substring-only
    finder ("any executable line containing psql \"$DSN\"") would pick the
    decoy and stay green even after the real invocation, refactored to
    positional connection flags, silently dropped the flag."""
    body = (
        'if [ -n "${DEBUG_RESTORE:-}" ]; then psql "$DSN" -v ON_ERROR_STOP=1; fi\n'
        'gunzip -c "/tmp/$LATEST" | \\\n'
        '  psql "$DSN" -h 127.0.0.1 -p "$DRILL_PORT" -U drill -d nuzantara_drill \\\n'
        "    > /tmp/restore.log 2>&1\n"
        '_PIPE_STATUSES=("${PIPESTATUS[@]}")\n'
    )
    invocation = _restore_pipeline_psql_invocation(body)
    assert invocation is not None
    assert "DEBUG_RESTORE" not in invocation, (
        f"picked the dead debug line instead of the real pipeline -- got: {invocation!r}"
    )
    assert "ON_ERROR_STOP=1" not in invocation, (
        "this synthetic real invocation deliberately lacks the flag -- the "
        "structural finder must surface THAT, not silently substitute the "
        f"decoy line that happens to carry it -- got: {invocation!r}"
    )


def test_restore_pipeline_psql_invocation_ignores_unrelated_second_psql_call():
    """OVER-match direction: an unrelated, correctly flagless second psql
    invocation elsewhere in the body (e.g. a plain sanity probe) must not be
    folded into the ON_ERROR_STOP=1 requirement -- only the pipeline stage
    whose status feeds `_PIPE_STATUSES` does. A substring-only finder would
    pick up both lines and wrongly fail a workflow that added this harmless
    probe."""
    body = (
        'gunzip -c "/tmp/$LATEST" | \\\n'
        '  psql "$DSN" -v ON_ERROR_STOP=1 \\\n'
        "    > /tmp/restore.log 2>&1\n"
        '_PIPE_STATUSES=("${PIPESTATUS[@]}")\n'
        "GUNZIP_RC=${_PIPE_STATUSES[0]}\n"
        "RESTORE_RC=${_PIPE_STATUSES[1]}\n"
        "psql \"$DSN\" -Atc 'SELECT 1'\n"
    )
    invocation = _restore_pipeline_psql_invocation(body)
    assert invocation is not None
    assert "ON_ERROR_STOP=1" in invocation
    assert "SELECT 1" not in invocation, (
        f"picked the unrelated probe line instead of the real pipeline -- got: {invocation!r}"
    )


if __name__ == "__main__":
    # Delegate to real pytest (not a hand-rolled loop) so this runs correctly
    # outside a `pytest` invocation too -- matching
    # test_restore_drill_verify.py's own convention.
    raise SystemExit(pytest.main([__file__, "-v"]))
