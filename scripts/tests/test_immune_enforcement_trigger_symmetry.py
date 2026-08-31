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
    r"^\s+(scripts/[A-Za-z0-9_./-]+\.py)\s*(?:\\|;\s*do)$", re.MULTILINE
)
# The pytest loop, and ONLY it. `_LOOP_RE` alone matches any indented
# `scripts/*.py ; do` line anywhere in the YAML, so an unrelated shell loop over
# non-test scripts would be demanded to have sentinel trigger paths and turn this
# check red on a correct workflow (kimi-code/k3, 2026-08-31 — the over-match twin
# of the under-match fixed two lines above, exactly as W94 predicts).
_LOOP_OPEN_RE = re.compile(r"^\s*for\s+\w+\s+in\s*\\?\s*$", re.MULTILINE)


def _workflow_text() -> str:
    return WORKFLOW.read_text()


# The sentinel `case` alternation, and ONLY it. `_SENTINEL_RE` alone matches an
# indented path ANYWHERE in the YAML — a `run:` block that merely mentions a test
# file would satisfy it, so a looped test could read as "triggered" because its
# name happens to appear in a shell line that has nothing to do with the path
# filter (Codex sol, 2026-08-31). The case block runs from the `case ... in` line
# to the line that closes the alternation with `)`.
_CASE_OPEN_RE = re.compile(r"^\s*case\s+.*\s+in\s*$", re.MULTILINE)


def _case_regions(text: str) -> list[str]:
    regions: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not _CASE_OPEN_RE.match(line):
            continue
        block: list[str] = []
        for nxt in lines[i + 1 :]:
            block.append(nxt)
            if nxt.rstrip().endswith(")"):
                break
        regions.append("\n".join(block))
    return regions


def sentinel_paths(text: str) -> set[str]:
    """Paths that TRIGGER the job — read only from inside the `case` alternation."""
    found: set[str] = set()
    for region in _case_regions(text):
        found |= set(_SENTINEL_RE.findall(region))
    return found


def _loop_regions(text: str) -> list[str]:
    """Each `for t in ... ; do` block, from the `for` line to the line closing
    the list with `; do`."""
    regions: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not _LOOP_OPEN_RE.match(line):
            continue
        block: list[str] = []
        for nxt in lines[i + 1 :]:
            block.append(nxt)
            if re.search(r";\s*do\s*$", nxt):
                break
        regions.append("\n".join(block))
    return regions


def loop_tests(text: str) -> set[str]:
    """Test files the job RUNS — read only from inside a `for ... in` loop."""
    found: set[str] = set()
    for region in _loop_regions(text):
        found |= set(_LOOP_RE.findall(region))
    return found


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
        '            case "$CHANGED" in\n'
        "              scripts/lint_home_fork.py|\\\n"
        "              scripts/tests/test_lint_home_fork.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "          for t in \\\n"
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
        '            case "$CHANGED" in\n'
        "              scripts/tests/test_wired.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "          for t in \\\n"
        "            scripts/tests/test_wired.py \\\n"
        "            scripts/tests/test_last_and_untriggered.py ; do\n"
    )
    assert "scripts/tests/test_last_and_untriggered.py" in loop_tests(synthetic)
    assert missing_triggers(synthetic) == ["scripts/tests/test_last_and_untriggered.py"]


def test_innocence_a_wired_LAST_entry_reports_nothing() -> None:
    synthetic = (
        '            case "$CHANGED" in\n'
        "              scripts/tests/test_last_and_wired.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "          for t in \\\n"
        "            scripts/tests/test_last_and_wired.py ; do\n"
    )
    assert missing_triggers(synthetic) == []


def test_innocence_a_fully_wired_pair_reports_nothing() -> None:
    synthetic = (
        '            case "$CHANGED" in\n'
        "              scripts/lint_home_fork.py|\\\n"
        "              scripts/tests/test_lint_home_fork.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "          for t in \\\n"
        "            scripts/tests/test_lint_home_fork.py \\\n"
    )
    assert missing_triggers(synthetic) == []


def test_innocence_sentinel_may_list_non_looped_subjects() -> None:
    """The converse direction must NOT be asserted: the sentinel rightly lists
    the SUBJECTS under test and shell corpora that the pytest loop never
    names. If this ever starts failing, someone made the check bidirectional."""
    synthetic = (
        '            case "$CHANGED" in\n'
        "              .husky/pre-push|\\\n"
        "              scripts/prepush_classify.py|\\\n"
        "              infra/doc-lint/*|\\\n"
        "              scripts/tests/test_prepush_classify.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "          for t in \\\n"
        "            scripts/tests/test_prepush_classify.py \\\n"
    )
    assert missing_triggers(synthetic) == []


def main() -> int:
    text = _workflow_text()
    sent, loop = sentinel_paths(text), loop_tests(text)
    if len(sent) < 20 or len(loop) < 10:
        print(
            f"FAIL — apparatus: parsed {len(sent)} sentinel / {len(loop)} loop entries"
        )
        return 1
    missing = missing_triggers(text)
    if missing:
        print("FAIL — looped tests with no trigger path:")
        for m in missing:
            print(f"    {m}")
        return 1
    print(
        f"OK — all {len(loop)} looped tests are trigger paths ({len(sent)} sentinel entries)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


def test_a_shell_loop_over_NON_test_scripts_is_not_mistaken_for_the_pytest_loop() -> (
    None
):
    """`_LOOP_RE` alone matches any indented `scripts/*.py ; do` line anywhere in
    the YAML. Unscoped, an unrelated loop over non-test scripts would be demanded
    to carry sentinel trigger paths and turn this check red on a correct
    workflow — the over-match twin of the under-match fixed above, exactly as
    W94 predicts a cure for one produces (kimi-code/k3, 2026-08-31)."""
    synthetic = (
        '            case "$CHANGED" in\n'
        "              scripts/tests/test_wired.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "          for t in \\\n"
        "            scripts/tests/test_wired.py ; do\n"
        "      - name: An unrelated step\n"
        "        run: |\n"
        "            scripts/regen_repomap.py ; do\n"
    )
    assert loop_tests(synthetic) == {"scripts/tests/test_wired.py"}
    assert missing_triggers(synthetic) == []


def test_the_apparatus_still_parses_the_REAL_workflow_after_both_scopings() -> None:
    """Non-vacuity for the two regional scopings: narrowing where each set is
    read is exactly the change that can silently reduce both to nothing, and an
    empty-vs-empty comparison reports 'all wired' forever."""
    text = _workflow_text()
    assert len(sentinel_paths(text)) >= 100, len(sentinel_paths(text))
    assert len(loop_tests(text)) >= 40, len(loop_tests(text))


def test_a_test_NAMED_outside_the_case_block_does_not_count_as_a_trigger() -> None:
    """`_SENTINEL_RE` alone matches an indented path ANYWHERE in the YAML, so a
    `run:` line that merely mentions a test file would satisfy it — and a looped
    test would read as triggered because its name happens to appear in a shell
    command that has nothing to do with the path filter (Codex sol, 2026-08-31).
    The trigger set must be read from the `case` alternation and nowhere else."""
    synthetic = (
        '            case "$CHANGED" in\n'
        "              scripts/tests/test_something_else.py|\\\n"
        "              .github/workflows/immune-enforcement.yml)\n"
        "      - name: A step that merely NAMES the file\n"
        "        run: |\n"
        "          echo checking\n"
        "              scripts/tests/test_untriggered.py\n"
        "          for t in \\\n"
        "            scripts/tests/test_untriggered.py ; do\n"
    )
    assert "scripts/tests/test_untriggered.py" not in sentinel_paths(synthetic)
    assert missing_triggers(synthetic) == ["scripts/tests/test_untriggered.py"]
