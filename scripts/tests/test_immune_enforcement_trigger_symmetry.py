#!/usr/bin/env python3
"""Every test the immune-enforcement unit-test loop RUNS must also be a path
that TRIGGERS the job (cicatrix-superscar.md #2 "Esiste ≠ Armato").

THE DEFECT THIS EXISTS TO CATCH (found live 2026-07-27, one commit after
#3347 merged):

`immune-enforcement.yml` has two independent lists that must agree:

  1. the SENTINEL list  — a shell `case` of paths; if none of the PR's
     changed files match, `relevant=false` and every job step is skipped;
  2. the LOOP list      — the `for t in ... ; do python -m pytest "$t"` set
     of test files the job actually executes.

#3347 added `test_husky_prepush_venv_guard.py` to list 2 and NOT to list 1.
The result reads as armed and is only half-armed: editing `.husky/pre-push`
(which IS a sentinel path) correctly triggers the job and runs the test — but
editing ONLY the test itself does not trigger anything, so a PR that guts,
weakens, or empties that test sails through with the job SKIPPED. The guard
guarding the hook was itself unguarded.

Measured at the time: 24 of the 25 looped tests were correctly listed in the
sentinel; exactly one was not. So this is a per-entry omission that is easy
to make and invisible in review — precisely the shape that deserves a
machine check rather than a convention.

NOTE ON DIRECTION (this test is deliberately one-way): loop ⊆ sentinel is
required, the converse is NOT. The sentinel legitimately lists many paths
that are not themselves looped pytest files — the SUBJECTS under test
(`scripts/prepush_classify.py`, `.husky/pre-push`, `infra/doc-lint/*`,
shell corpora run by other steps, ...). Asserting equality would be wrong
and would fail constantly.

Run:  python3 scripts/tests/test_immune_enforcement_trigger_symmetry.py
      pytest scripts/tests/test_immune_enforcement_trigger_symmetry.py -q
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "immune-enforcement.yml"

# A sentinel entry: an indented path inside the shell `case` alternation,
# ending in `|\` (or the final one, closing with `)`).
_SENTINEL_RE = re.compile(
    r"^\s+([A-Za-z0-9_./*-]+\.(?:py|sh|md|json|txt|yml))\|?\\?$", re.MULTILINE
)
# A loop entry: an indented python test path, either continued with a trailing
# ` \` or — for the LAST entry — closing the list with ` ; do`.
#
# The ` ; do` alternative was added 2026-08-31. Until then this regex required
# the continuation backslash, so the final entry of the loop was invisible to
# this check and could be added without a sentinel path — the exact half-armed
# shape this file exists to catch, in the file that catches it. Measured when
# found: the terminal entry happened to be listed correctly, so nothing was
# broken, but nothing was checking either (superscar #3, under-match).
_LOOP_RE = re.compile(
    r"^\s+(scripts/[A-Za-z0-9_./-]+\.py)(?: \\| ; do)$", re.MULTILINE
)


def _workflow_text() -> str:
    return WORKFLOW.read_text()


def sentinel_paths(text: str) -> set[str]:
    return set(_SENTINEL_RE.findall(text))


def loop_tests(text: str) -> set[str]:
    return set(_LOOP_RE.findall(text))


def missing_triggers(text: str) -> list[str]:
    """Looped tests that no sentinel path would ever trigger."""
    return sorted(loop_tests(text) - sentinel_paths(text))


# ---------------------------------------------------------------------------
# NON-VACUITY FIRST. A repo-wide "nothing is missing" assertion reads exactly
# the same as "my regex matched nothing at all" — this repo has been bitten by
# that blind-scan shape before, so the emptiness of either set is a HARD
# failure, checked before the real assertion can pass.
# ---------------------------------------------------------------------------


def test_apparatus_sentinel_set_is_non_empty() -> None:
    n = len(sentinel_paths(_workflow_text()))
    assert n >= 20, (
        f"parsed only {n} sentinel paths from {WORKFLOW} — the format changed and "
        "this test would otherwise pass vacuously"
    )


def test_apparatus_loop_set_is_non_empty() -> None:
    n = len(loop_tests(_workflow_text()))
    assert n >= 10, (
        f"parsed only {n} looped test files from {WORKFLOW} — the format changed and "
        "this test would otherwise pass vacuously"
    )


def test_every_looped_test_is_also_a_trigger_path() -> None:
    """THE point of this file."""
    missing = missing_triggers(_workflow_text())
    assert not missing, (
        "these tests are RUN by immune-enforcement.yml but no sentinel path "
        "triggers the job, so a PR touching only them skips the job entirely "
        f"and they never execute: {missing}. Add each to the `case` list."
    )


def test_this_test_is_itself_both_looped_and_triggered() -> None:
    """A guard that does not guard itself is the bug it is here to catch,
    one level up."""
    text = _workflow_text()
    me = "scripts/tests/test_immune_enforcement_trigger_symmetry.py"
    assert me in loop_tests(text), f"{me} must be in the unit-test loop"
    assert me in sentinel_paths(text), f"{me} must be a sentinel trigger path"


# ---------------------------------------------------------------------------
# GUILT + INNOCENCE on the detector itself.
# ---------------------------------------------------------------------------


def test_guilt_a_looped_test_absent_from_the_sentinel_is_reported() -> None:
    synthetic = (
        "              scripts/lint_home_fork.py|\\\n"
        "              scripts/tests/test_lint_home_fork.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "            scripts/tests/test_lint_home_fork.py \\\n"
        "            scripts/tests/test_orphaned_never_triggered.py \\\n"
    )
    assert missing_triggers(synthetic) == [
        "scripts/tests/test_orphaned_never_triggered.py"
    ]


def test_guilt_the_LAST_loop_entry_is_parsed_not_skipped() -> None:
    """The terminal entry closes the list with ` ; do` instead of a continuation
    backslash. A parser that only knows the backslash form silently exempts it,
    and the last line of a list is exactly where a new entry gets appended."""
    synthetic = (
        "              scripts/tests/test_wired.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "            scripts/tests/test_wired.py \\\n"
        "            scripts/tests/test_last_and_untriggered.py ; do\n"
    )
    assert "scripts/tests/test_last_and_untriggered.py" in loop_tests(synthetic)
    assert missing_triggers(synthetic) == ["scripts/tests/test_last_and_untriggered.py"]


def test_innocence_a_wired_LAST_entry_reports_nothing() -> None:
    synthetic = (
        "              scripts/tests/test_last_and_wired.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "            scripts/tests/test_last_and_wired.py ; do\n"
    )
    assert missing_triggers(synthetic) == []


def test_innocence_a_fully_wired_pair_reports_nothing() -> None:
    synthetic = (
        "              scripts/lint_home_fork.py|\\\n"
        "              scripts/tests/test_lint_home_fork.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "            scripts/tests/test_lint_home_fork.py \\\n"
    )
    assert missing_triggers(synthetic) == []


def test_innocence_sentinel_may_list_non_looped_subjects() -> None:
    """The converse direction must NOT be asserted: the sentinel rightly lists
    the SUBJECTS under test and shell corpora that the pytest loop never
    names. If this ever starts failing, someone made the check bidirectional."""
    synthetic = (
        "              .husky/pre-push|\\\n"
        "              scripts/prepush_classify.py|\\\n"
        "              infra/doc-lint/*|\\\n"
        "              scripts/tests/test_prepush_classify.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "            scripts/tests/test_prepush_classify.py \\\n"
    )
    assert missing_triggers(synthetic) == []


def main() -> int:
    text = _workflow_text()
    sent, loop = sentinel_paths(text), loop_tests(text)
    if len(sent) < 20 or len(loop) < 10:
        print(f"FAIL — apparatus: parsed {len(sent)} sentinel / {len(loop)} loop entries")
        return 1
    missing = missing_triggers(text)
    if missing:
        print("FAIL — looped tests with no trigger path:")
        for m in missing:
            print(f"    {m}")
        return 1
    print(f"OK — all {len(loop)} looped tests are trigger paths ({len(sent)} sentinel entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
