#!/usr/bin/env python3
"""Guilt + innocence suite for the `.husky/pre-push` Python-tests venv guard
(cicatrix-superscar.md #2 "Esiste ≠ Armato" lineage — L243, 2026-07-16).

A bare `git worktree add` does NOT create the `apps/backend-rag/.venv`
symlink the main checkout has. Before this guard, `source
.venv/bin/activate 2>/dev/null` in the pytest branch swallowed the
missing-file error, the `&&` chain aborted mid-subshell, and the hook fell
straight into the generic "tests FAILED — push blocked" branch — blocking
4 legitimate pushes in one session against a worktree that never actually
ran a single test.

The guard condition is extracted LIVE from .husky/pre-push (not re-typed
here) so this test breaks the moment the guard drifts from what actually
runs, and it's exercised via the real bash `[ ... ]` test the hook
evaluates — not a Python reimplementation that could silently diverge in
semantics.

Run:  python3 scripts/tests/test_husky_prepush_venv_guard.py
      pytest scripts/tests/test_husky_prepush_venv_guard.py -q
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK_FILE = REPO_ROOT / ".husky" / "pre-push"
GUARD_ELIF_LINE = "elif [ ! -f apps/backend-rag/.venv/bin/activate ]; then"

# ---------------------------------------------------------------------------
# ORDERING ANCHORS (cicatrix-superscar.md #3 lineage, own family).
#
# Found 2026-07-27: the hook's own prose comments reference `CLONE_DB=$$`
# and `` `python -m pytest` `` as EXPLANATION (line ~291-292, "wraps ONLY the
# `python -m pytest` call below — not the DB clone, already isolated
# per-push via CLONE_DB=$$"), sitting textually BEFORE the real venv-guard
# `elif` line. A bare `text.find("CLONE_DB=")` / `text.find("python -m
# pytest")` matches those comment mentions, not the real assignment/
# invocation, and reports a false ordering: guard AFTER "clone" AFTER
# "pytest" — the opposite of the truth, which is guard(317) < clone(356) <
# pytest(505) by LINE NUMBER. The test was red on main with a green hook.
#
# Anchored on the ACTUAL executable forms instead of a bare label a comment
# can also contain:
#   - the real assignment: `CLONE_DB="..."` (regex, start-of-line, so a
#     mid-comment "CLONE_DB=$$" — no quote character right after the equals
#     sign — cannot match)
#   - the real invocation: `python -m pytest backend/tests/` (the comment
#     only ever says the BARE phrase `python -m pytest`, never followed by
#     the argument list the real call always carries)
# ---------------------------------------------------------------------------
_CLONE_DB_ASSIGNMENT_RE = re.compile(r'^\s*CLONE_DB="', re.MULTILINE)
_PYTEST_INVOCATION_NEEDLE = "python -m pytest backend/tests/"


def _hook_text() -> str:
    return HOOK_FILE.read_text()


def _ordering_anchors(text: str) -> tuple[int, int, int]:
    """(guard_idx, clone_idx, pytest_idx), each -1 if not found."""
    guard_idx = text.find(GUARD_ELIF_LINE)
    m = _CLONE_DB_ASSIGNMENT_RE.search(text)
    clone_idx = m.start() if m else -1
    pytest_idx = text.find(_PYTEST_INVOCATION_NEEDLE)
    return guard_idx, clone_idx, pytest_idx


def _extract_venv_guard_test_expr() -> str:
    m = re.search(
        r"^\s*elif (\[ ! -f apps/backend-rag/\.venv/bin/activate \]); then\s*$",
        _hook_text(),
        re.MULTILINE,
    )
    assert m, f"venv guard elif not found in {HOOK_FILE}"
    return m.group(1)


def _guard_fires(venv_present: bool) -> bool:
    """Run the REAL extracted bash test expression against a synthetic cwd,
    exactly as the hook would evaluate it (cwd = repo root, path relative).
    Returns True if the guard condition is true, i.e. the SKIP branch would
    fire."""
    test_expr = _extract_venv_guard_test_expr()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        if venv_present:
            activate = tmp_path / "apps" / "backend-rag" / ".venv" / "bin" / "activate"
            activate.parent.mkdir(parents=True)
            activate.write_text("# fake venv activate\n")
        r = subprocess.run(
            ["bash", "-c", f'cd "$1" && {test_expr}', "_", str(tmp_path)],
            capture_output=True,
        )
        return r.returncode == 0


CASES: list[tuple[bool, bool, str]] = [
    (False, True, "GUILT: apps/backend-rag/.venv/bin/activate absent (bare worktree) -> guard fires, SKIP taken"),
    (True, False, "INNOCENCE: apps/backend-rag/.venv/bin/activate present -> guard does not fire, falls through toward pytest"),
]


def main() -> int:
    failures = []

    for venv_present, should_fire, label in CASES:
        got = _guard_fires(venv_present)
        if got != should_fire:
            failures.append(
                f"  {label}\n    venv_present={venv_present} expected_fire={should_fire} got={got}"
            )

    text = _hook_text()

    # The guard must live BEFORE the DB clone / pytest invocation, else a
    # missing venv still burns a Postgres clone (or worse, still reaches
    # pytest) before anyone finds out — the whole point is to short-circuit
    # early and cheaply.
    guard_idx, clone_idx, pytest_idx = _ordering_anchors(text)
    if guard_idx == -1 or clone_idx == -1 or pytest_idx == -1:
        failures.append(
            f"  ORDERING: could not locate all 3 anchors (guard={guard_idx} clone={clone_idx} pytest={pytest_idx})"
        )
    elif not (guard_idx < clone_idx < pytest_idx):
        failures.append(
            f"  ORDERING: venv guard must precede DB clone and pytest invocation "
            f"(guard={guard_idx} clone={clone_idx} pytest={pytest_idx})"
        )

    # Fail-loud requirement: the branch must SKIP with a clear, named reason
    # — never a bare/silent pass-through, never the generic "tests FAILED".
    if "SKIP Python tests — worktree has no apps/backend-rag/.venv" not in text:
        failures.append("  MESSAGE: guard branch must echo a SKIP message naming the missing venv path")

    if failures:
        print("FAIL — pre-push venv guard regression:")
        print("\n".join(failures))
        return 1
    print(f"OK — {len(CASES)}/{len(CASES)} guilt+innocence cases pass + ordering/message verified ({HOOK_FILE})")
    return 0


def test_venv_guard_fires_when_venv_absent():
    assert _guard_fires(venv_present=False) is True


def test_venv_guard_does_not_fire_when_venv_present():
    assert _guard_fires(venv_present=True) is False


def test_venv_guard_precedes_db_clone_and_pytest_invocation():
    guard_idx, clone_idx, pytest_idx = _ordering_anchors(_hook_text())
    assert guard_idx != -1 and clone_idx != -1 and pytest_idx != -1
    assert guard_idx < clone_idx < pytest_idx


def test_venv_guard_skip_message_present():
    assert "SKIP Python tests — worktree has no apps/backend-rag/.venv" in _hook_text()


# ---------------------------------------------------------------------------
# GUILT + INNOCENCE on the ordering anchors THEMSELVES (superscar #3: this
# is the guardian of the guardian — the anchor logic needs its own proof
# that it does not repeat the exact false-red it was just cured of).
# ---------------------------------------------------------------------------


def test_innocence_a_comment_mentioning_clone_db_before_the_guard_does_not_trip_ordering():
    """Reproduces the false-red verbatim: a prose comment that says
    `CLONE_DB=$$` and `python -m pytest` (no arguments, backtick-quoted)
    sitting textually BEFORE the guard must NOT be read as "clone/pytest
    happen before the guard". This is what the live hook actually contains,
    which is exactly why the un-anchored version was red on a correct hook.
    """
    synthetic = (
        "# some explanatory comment mentioning CLONE_DB=$$ and the\n"
        "# `python -m pytest` call, written for a human, above the guard.\n"
        f"{GUARD_ELIF_LINE}\n"
        "    echo SKIP\n"
        "else\n"
        '    CLONE_DB="real_assignment_here"\n'
        "    ...\n"
        "    python -m pytest backend/tests/ --ignore=backend/tests/e2e -q\n"
        "fi\n"
    )
    guard_idx, clone_idx, pytest_idx = _ordering_anchors(synthetic)
    assert guard_idx != -1 and clone_idx != -1 and pytest_idx != -1
    assert guard_idx < clone_idx < pytest_idx


def test_guilt_a_genuinely_reordered_hook_still_fails():
    """SCAR-PIN: if the real assignment/invocation were moved BEFORE the
    guard, this must still be caught — the fix must not have swung to the
    opposite failure mode of never firing at all."""
    synthetic = (
        '    CLONE_DB="real_assignment_here"\n'
        "    python -m pytest backend/tests/ --ignore=backend/tests/e2e -q\n"
        f"{GUARD_ELIF_LINE}\n"
        "    echo SKIP\n"
        "fi\n"
    )
    guard_idx, clone_idx, pytest_idx = _ordering_anchors(synthetic)
    assert guard_idx != -1 and clone_idx != -1 and pytest_idx != -1
    assert not (guard_idx < clone_idx < pytest_idx)


def test_guilt_missing_real_assignment_is_reported_as_not_found():
    """A hook with only the comment mention and no real assignment must
    report clone_idx == -1, not silently match the comment as if it were
    real — the -1 sentinel is what test_venv_guard_precedes_db_clone_and_
    pytest_invocation's own guard clause depends on."""
    synthetic = (
        "# a comment mentioning CLONE_DB=$$ but never actually assigning it\n"
        f"{GUARD_ELIF_LINE}\n"
        "    echo SKIP\n"
    )
    _, clone_idx, _ = _ordering_anchors(synthetic)
    assert clone_idx == -1


if __name__ == "__main__":
    sys.exit(main())
