"""`.github/workflows/restore-drill.yml`'s own restore/verify/notify steps must
never let a swallowed exit code mask a genuine restore-drill failure.

Split out of test_restore_drill_verify.py (which stays scoped to
restore_drill_verify.py, the Python verifier, in isolation): this file's
subject is the WORKFLOW YAML wiring, not the Python module, and it must ship
together with the workflow diff it pins — a version of this file run against
an unpatched restore-drill.yml fails all five tests below (verified: this is
exactly what happened when the two were first split into separate PRs).

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


def _executable_lines(body: str) -> list[str]:
    """Lines of a step's `run:` body that are not full-line `#` comments.
    Narrow on purpose: this step never puts a trailing comment after real
    shell tokens, so "strip only lines whose STRIPPED form starts with #"
    is enough here and cannot clip a `#` that's part of a string."""
    return [ln for ln in body.splitlines() if not ln.strip().startswith("#")]


def _psql_restore_invocation_lines(body: str) -> list[str]:
    """The line(s) that actually EXECUTE the restore, as opposed to the
    prose that talks about it. See the docstring on the test that calls
    this for the measured reason this distinction is load-bearing."""
    return [ln for ln in _executable_lines(body) if 'psql "$DSN"' in ln]


def _run_failure_notify_step() -> str:
    doc = _load_workflow()
    for step in doc["jobs"]["restore-drill"]["steps"]:
        if step.get("name") == "Telegram alert on failure":
            return step["run"]
    raise AssertionError('no step named "Telegram alert on failure" found -- broken test, not a clean file')


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

    The ON_ERROR_STOP=1 check is anchored to the EXECUTABLE psql invocation
    line, not to the step body as a whole. Measured: the literal string
    "ON_ERROR_STOP=1" occurs FIVE times in this step's `run:` text -- once on
    the `psql "$DSN" -v ON_ERROR_STOP=1` line that actually runs the restore,
    and four more times in prose that merely TALKS about it (three `#`
    comments plus the `echo "::error title=Restore aborted
    (ON_ERROR_STOP=1)::..."` message). A blanket `"ON_ERROR_STOP=1" in body`
    is satisfied by those four prose occurrences alone: flipping ONLY the
    executable psql line to `ON_ERROR_STOP=0` and leaving every comment and
    the echo message untouched left that blanket form green (superscar
    family #3 -- a guard reading the FORM of the string, anywhere in the
    text, instead of the ENTITY that actually executes it). Locating the
    `psql "$DSN"` line among non-comment lines and asserting on THAT line
    closes the gap without becoming brittle to harmless comment rewording,
    since comments are excluded from the scan entirely.

    PIPESTATUS[1], NOT [0]: `gunzip | psql` is a two-stage pipe and index 0 is
    gunzip's own exit code, not psql's -- reading index 0 here would make the
    whole ON_ERROR_STOP=1 change silently inert on a genuinely failing
    restore. Found by a stubbed end-to-end run of the real de-indented script
    with a faked failing psql (see the PR body), not by inspection."""
    body = _run_restore_drill_step()
    psql_lines = _psql_restore_invocation_lines(body)
    assert psql_lines, 'no executable psql "$DSN" restore line found -- broken test, not a clean file'
    assert all("ON_ERROR_STOP=1" in ln for ln in psql_lines), (
        "the executable psql restore invocation must carry ON_ERROR_STOP=1, "
        f"not just a comment/message mentioning it -- got: {psql_lines!r}"
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
    assert "RESTORE_RC=${_PIPE_STATUSES[1]}" in body
    assert "RESTORE_RC=${PIPESTATUS[0]}" not in body, "must not read gunzip's exit code instead of psql's"
    assert 'if [ "$RESTORE_RC" -ne 0 ]' in body
    assert "VERIFY_RC=$?" in body
    assert 'exit "$VERIFY_RC"' in body


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
    a conditional that was never closed before the tail ran."""
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
    failure must not be ABLE to change the drill's own exit code."""
    body = _run_restore_drill_step()
    assert "TG_RC=$?" in body
    assert "::warning::telegram success-notify" in body
    assert "TG_RC" in body and "response=${TG_BODY}" in body
    for line in body.splitlines():
        if "TG_RC" in line:
            assert "exit" not in line, f"a Telegram outcome must never gate an exit: {line!r}"


def test_telegram_failure_notify_captures_rc_and_never_lets_it_gate_the_exit():
    body = _run_failure_notify_step()
    assert "TG_RC=$?" in body
    assert "::warning::telegram failure-notify" in body
    for line in body.splitlines():
        if "TG_RC" in line:
            assert "exit" not in line, f"a Telegram outcome must never gate an exit: {line!r}"


if __name__ == "__main__":
    # Delegate to real pytest (not a hand-rolled loop) so this runs correctly
    # outside a `pytest` invocation too -- matching
    # test_restore_drill_verify.py's own convention.
    raise SystemExit(pytest.main([__file__, "-v"]))
