#!/usr/bin/env python3
"""Corpus for `scripts/ci/lint_trigger_symmetry.py`.

L06-PR1 follow-through. PR-1 landed RESHAPED as the required-context guard
(#5214), which asserts a required workflow declares BOTH triggers. The subject
the spec actually named — that the two triggers' PATH semantics agree — was never
built, and `scripts/ci/lint_trigger_symmetry.py` did not exist on `origin/main`.

WHY A GUARD WITH ZERO CATCHES IS WORTH SHIPPING HERE, stated because this repo
suspended a PR under Rule 8 for exactly that framing and the distinction matters.
A preventive guard earns its place when its premise is demonstrable: the shape
must be REACHABLE and it must be HARMFUL. Both are, and not hypothetically —
in this same wave, three of the four workflows made queue-aware
(`voa-probe-tests.yml`, `restore-drill-wiring-tests.yml`,
`p1s2-mutation-incremental.yml`) carried `pull_request` `paths:` filters, and
"make it queue-aware" is naturally done by ADDING `merge_group:` and leaving the
filter alone. That is the violation, one keystroke away, on files a squad was
editing this week.

The harm: `merge_group` cannot carry a `paths:` filter at all, so the pull_request
run may be SKIPPED while the queue run always executes — head-green / queue-red.
The author never sees the job, the queue runs it, it fails, and the entry is
ejected with a red nobody was shown. For a required context it is worse: the PR
reports "Expected — waiting for status" forever (W69).

Runs as `python3 scripts/tests/test_lint_trigger_symmetry.py` and under pytest.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

_LINT = pathlib.Path(__file__).resolve().parents[1] / "ci" / "lint_trigger_symmetry.py"
_REPO = pathlib.Path(__file__).resolve().parents[2]


def _run(root: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(_LINT), "--repo-root", str(root)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _world(tmp: pathlib.Path, name: str, body: str) -> pathlib.Path:
    wf = tmp / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / name).write_text(body, encoding="utf-8")
    return tmp


# ------------------------------------------------------------------- guilt

_GUILTY = """name: guilty
on:
  pull_request:
    paths:
      - "src/**"
  merge_group:
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

_GUILTY_IGNORE = """name: guilty-ignore
on:
  pull_request:
    paths-ignore:
      - "docs/**"
  merge_group:
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def _case_paths_plus_merge_group_is_a_violation() -> list[str]:
    """GUILT: the exact shape — a `paths:` filter the queue cannot mirror."""
    fails: list[str] = []
    for label, body in (("paths", _GUILTY), ("paths-ignore", _GUILTY_IGNORE)):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _run(_world(pathlib.Path(td), "w.yml", body))
            if rc != 1:
                fails.append(f"{label}: rc={rc}, expected 1 — the asymmetry was not caught")
            if "w.yml" not in out:
                fails.append(f"{label}: the violation does not name the file — an operator cannot act on it")
    return fails


def _case_unparseable_is_a_violation_not_a_skip() -> list[str]:
    """A workflow the linter cannot read is a workflow it is not guarding.
    Reporting clean over it would be exists-!=-armed (superscar #2)."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(_world(pathlib.Path(td), "broken.yml", "on: [\n  unclosed"))
        if rc != 1:
            fails.append(f"an unparseable workflow gave rc={rc}, expected 1 — it was silently skipped")
        if "broken.yml" not in out:
            fails.append("the unparseable workflow is not named in the output")
    return fails


# --------------------------------------------------------------- innocence

_CLEAN_CASES = {
    "no-filter.yml": """name: clean
on:
  pull_request:
  merge_group:
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    # A `paths:` filter with NO merge_group trigger is not this trap: the queue
    # never runs the workflow at all, so the two triggers cannot disagree.
    "paths-no-queue.yml": """name: clean-2
on:
  pull_request:
    paths:
      - "src/**"
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    # DECLARED SCOPE LIMIT, asserted rather than merely documented: a
    # `push.paths` filter of any shape is out of scope, because a push to main
    # happens after a PR has merged and gates no PR. A guard that flagged it
    # would be an over-match (superscar #3) on a legitimate cost optimisation.
    "push-paths.yml": """name: clean-3
on:
  pull_request:
  merge_group:
  push:
    branches: [main]
    paths:
      - "src/**"
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    # No pull_request trigger at all — nothing to be asymmetric with.
    "queue-only.yml": """name: clean-4
on:
  merge_group:
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
}


def _case_clean_shapes_are_not_flagged() -> list[str]:
    """INNOCENCE, four shapes. Without these the guard could be a bare
    `if "paths" in text` and still pass every guilt case above."""
    fails: list[str] = []
    for name, body in _CLEAN_CASES.items():
        with tempfile.TemporaryDirectory() as td:
            rc, out = _run(_world(pathlib.Path(td), name, body))
            if rc != 0:
                fails.append(f"{name}: rc={rc}, expected 0 — over-match on a legitimate shape. Output: {out.strip()[:200]}")
    return fails


def _case_operational_failure_is_not_zero_violations() -> list[str]:
    """An empty or missing workflow directory must NOT read as "0 violations".
    A guard that cannot find its subject and reports clean is the purest form of
    exists-!=-armed."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(pathlib.Path(td))  # no .github/workflows at all
        if rc != 2:
            fails.append(f"an empty repo gave rc={rc}, expected 2 (operational failure), not a clean 0")
    return fails


# ------------------------------------------------------------- the live tree

def _case_live_tree_is_clean_and_the_linter_saw_it() -> list[str]:
    """The live tree has ZERO violations, and this asserts BOTH halves.

    Asserting only rc==0 would pass on a linter that scanned nothing. The
    workflow count is asserted too — a floor, not an equality, so adding
    workflows never turns this red, but a linter that suddenly sees five files
    where it used to see a hundred does.
    """
    fails: list[str] = []
    rc, out = _run(_REPO)
    if rc != 0:
        fails.append(f"the live tree is not clean: rc={rc} — {out.strip()[:400]}")
    import re
    m = re.search(r"(\d+) workflow\(s\) checked", out)
    if not m:
        fails.append("the linter printed no count — this case cannot tell scanning from not-scanning")
    elif int(m.group(1)) < 100:
        fails.append(f"the linter saw only {m.group(1)} workflows; the tree has >100 — it is not scanning them all")
    return fails



# ------------------------------------------- the refuter's four, each pinned

_PR_TARGET = """name: guilty-target
on:
  pull_request_target:
    paths:
      - "src/**"
  merge_group:
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def _case_pull_request_target_carries_the_same_trap() -> list[str]:
    """GUILT on the rarer, more dangerous trigger. `pull_request_target` starts
    a run on a PR and supports `paths:` exactly as `pull_request` does, so it
    carries the identical divergence — and checking only the commoner name was
    an under-match a blind refuter found. This repo has one workflow using it."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(_world(pathlib.Path(td), "t.yml", _PR_TARGET))
        if rc != 1:
            fails.append(f"pull_request_target + paths + merge_group gave rc={rc}, expected 1")
        if "pull_request_target" not in out:
            fails.append("the violation does not name pull_request_target — a reader would look at the wrong trigger")
    return fails


_OPT_OUT_OK = _GUILTY.replace("name: guilty\n",
    "name: excused\n# trigger-symmetry: intentional - the merge_group job self-skips via an in-job path filter\n")
_OPT_OUT_NO_REASON = _GUILTY.replace("name: guilty\n",
    "name: excused-badly\n# trigger-symmetry: intentional\n")


def _case_opt_out_marker_excuses_only_with_a_reason() -> list[str]:
    """The escape exists because the rule judges FORM where the hazard is about
    ENTITY, and that gap is not statically decidable (superscar #3 pointed at
    this lint's own rule). But an exemption is a guard running in reverse: a
    marker with no reason does not excuse anything."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(_world(pathlib.Path(td), "w.yml", _OPT_OUT_OK))
        if rc != 0:
            fails.append(f"a marker WITH a reason did not excuse: rc={rc} — {out.strip()[:200]}")
        if "EXEMPT" not in out:
            fails.append("the exemption was silent — an exemption nobody can see is one nobody can revisit")
    with tempfile.TemporaryDirectory() as td:
        rc, _ = _run(_world(pathlib.Path(td), "w.yml", _OPT_OUT_NO_REASON))
        if rc != 1:
            fails.append(f"a marker WITHOUT a reason excused the violation: rc={rc}, expected 1")
    return fails


_NO_ON = """name: no-triggers
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

_TRUE_KEY = """name: literal-true-key
true: something
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def _case_missing_on_is_not_reported_as_unparseable() -> list[str]:
    """A workflow that parses perfectly but has no `on:` key is NOT a syntax
    error, and saying so sends a reader hunting for one that is not there. It is
    still a violation — this lint cannot guard a file it cannot read triggers
    from — but it must be named for what it is."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(_world(pathlib.Path(td), "w.yml", _NO_ON))
        if rc != 1:
            fails.append(f"a workflow with no on: block gave rc={rc}, expected 1")
        if "unparseable" in out:
            fails.append("a valid YAML file was mislabelled 'unparseable' — the reader is sent to a syntax error that does not exist")
        if "no `on:`" not in out:
            fails.append("the real cause (no trigger block) is not named")
    return fails


def _case_a_literal_true_key_does_not_satisfy_the_yaml11_fallback() -> list[str]:
    """PyYAML 1.1 reads a bare `on:` as the boolean True, so the fallback
    `doc.get(True)` is necessary — and a refuter found its edge: a document with
    NO `on:` but a literal `true:` key would satisfy the fallback with an
    arbitrary scalar and sail through. The fallback is taken only when what it
    finds is trigger-shaped."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(_world(pathlib.Path(td), "w.yml", _TRUE_KEY))
        if rc != 1:
            fails.append(f"a literal `true:` scalar satisfied the on:-block fallback: rc={rc}, expected 1")
    return fails


_CASES = (
    ("guilt: paths/paths-ignore + merge_group is a violation", _case_paths_plus_merge_group_is_a_violation),
    ("guilt: an unparseable workflow is a violation, never a skip", _case_unparseable_is_a_violation_not_a_skip),
    ("innocence: four legitimate shapes are not flagged", _case_clean_shapes_are_not_flagged),
    ("guilt: an operational failure never reads as 0 violations", _case_operational_failure_is_not_zero_violations),
    ("guilt: pull_request_target carries the same trap", _case_pull_request_target_carries_the_same_trap),
    ("opt-out: excuses only with a reason, and says so", _case_opt_out_marker_excuses_only_with_a_reason),
    ("guilt: a missing on: block is not called 'unparseable'", _case_missing_on_is_not_reported_as_unparseable),
    ("guilt: a literal `true:` key does not satisfy the YAML-1.1 fallback", _case_a_literal_true_key_does_not_satisfy_the_yaml11_fallback),
    ("live: the tree is clean AND the linter actually scanned it", _case_live_tree_is_clean_and_the_linter_saw_it),
)


def test_paths_plus_merge_group_is_a_violation() -> None:
    assert not _case_paths_plus_merge_group_is_a_violation()


def test_unparseable_is_a_violation_not_a_skip() -> None:
    assert not _case_unparseable_is_a_violation_not_a_skip()


def test_clean_shapes_are_not_flagged() -> None:
    assert not _case_clean_shapes_are_not_flagged()


def test_operational_failure_is_not_zero_violations() -> None:
    assert not _case_operational_failure_is_not_zero_violations()


def test_pull_request_target_carries_the_same_trap() -> None:
    assert not _case_pull_request_target_carries_the_same_trap()


def test_opt_out_marker_excuses_only_with_a_reason() -> None:
    assert not _case_opt_out_marker_excuses_only_with_a_reason()


def test_missing_on_is_not_reported_as_unparseable() -> None:
    assert not _case_missing_on_is_not_reported_as_unparseable()


def test_a_literal_true_key_does_not_satisfy_the_yaml11_fallback() -> None:
    assert not _case_a_literal_true_key_does_not_satisfy_the_yaml11_fallback()


def test_live_tree_is_clean_and_the_linter_saw_it() -> None:
    assert not _case_live_tree_is_clean_and_the_linter_saw_it()


if __name__ == "__main__":
    fails: list[str] = []
    for label, fn in _CASES:
        f = fn()
        fails.extend(f"{label}: {x}" for x in f)
        print(f"  [{'FAIL' if f else ' ok '}] {label}")
    if fails:
        print(f"=== {len(fails)} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    print("=== trigger-symmetry OK (guilt on paths/paths-ignore+merge_group, unparseable, "
          "and an operational failure; innocence on four legitimate shapes; live tree clean and scanned) ===")
    sys.exit(0)
