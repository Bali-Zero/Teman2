"""Every trusted-classifier extraction list must be IMPORT-CLOSED.

WHY THIS EXISTS. `tests.yml` and `security.yml` each copy a handful of
`scripts/ci/*` files out of the BASE ref into an isolated temp dir, then run the
classifier's own guilt/innocence corpus against that trusted copy — the point
being that a PR cannot edit the logic that decides which jobs its own diff
requires. Both lists are hand-kept, and both run the SAME `test_change_map.py`.

On 2026-08-26, #5070 added `import security_gate_flags as sgf` to
`scripts/ci/test_change_map.py`. `security.yml`'s list already carried that
module, by coincidence of its own scope. `tests.yml`'s did not, and nothing
noticed: the corpus step died on `ModuleNotFoundError`, `CLASSIFIER_TEST_OUTCOME`
went to `failure`, and the workflow's own fail-open — correct in itself, "an
untrusted classifier recommends ALL jobs" — absorbed it. The result was green,
so nobody looked. For nine days EVERY pull request ran the full six-job suite
(Backend Shards, Frontend Tests, E2E, MCP, Evaluator, Shared Core) regardless of
its diff, and the change map reported `changed_file_count: 0` while doing it.

That is cicatrix family #2 in the shape a fail-open makes possible: the net that
catches a broken classifier is also what hides that it is broken. A test that
only asserted "the corpus passes" would not have caught it either, because the
corpus never ran. So this asserts the STRUCTURAL property instead — the list is
closed under the imports of the files in it — which is checkable without a
runner and fails the moment someone adds an import without adding the module.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
CI_DIR = REPO / "scripts" / "ci"

# The extraction loop is a shell `for f in <paths>; do`, not YAML structure, so
# it is read with a regex anchored to that loop. Anchoring on the loop rather
# than on a step name means a renamed step still gets checked.
#
# ONE quantifier, and deliberately so. The first version was
# `((?:scripts/ci/\S+\s*)+)`, which CodeQL flagged HIGH as an inefficient
# regular expression — correctly: `\S+` can swallow the next iteration's own
# `scripts/ci/` prefix, so one input has exponentially many ways to be split
# between the repetitions, and any text reaching `for f in ` without a closing
# `; do` backtracks through all of them. `[^;\n]+` cannot partition
# ambiguously — a single greedy run bounded by characters the body cannot
# contain — so matching is linear. Picking out the `scripts/ci/` tokens moves
# into Python, where it costs a `startswith`.
EXTRACT_RE = re.compile(r"for f in ([^;\n]+);\s*do")
CI_PREFIX = "scripts/ci/"


def _extraction_lists() -> list[tuple[pathlib.Path, tuple[str, ...]]]:
    found = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for m in EXTRACT_RE.finditer(wf.read_text(encoding="utf-8")):
            tokens = m.group(1).split()
            files = tuple(tok for tok in tokens if tok.startswith(CI_PREFIX))
            if files:
                found.append((wf, files, tokens))
    return found


def test_the_extraction_lists_are_still_discoverable() -> None:
    """Innocence for the probe itself: if the regex stops matching, every test
    below passes vacuously and this file becomes decoration. A guard that can
    only ever say yes is not a guard."""
    lists = _extraction_lists()
    assert len(lists) >= 2, (
        "found fewer than two trusted-classifier extraction lists — either the "
        "shell `for f in scripts/ci/...` shape changed, or a workflow lost its "
        "extraction step. Fix this probe before trusting the checks below."
    )
    names = {entry[0].name for entry in lists}
    assert {"tests.yml", "security.yml"} <= names, (
        f"expected tests.yml and security.yml to carry extraction lists, got {sorted(names)}"
    )


@pytest.mark.parametrize("workflow,files,tokens", _extraction_lists(), ids=lambda v: getattr(v, "name", ""))
def test_every_extracted_file_exists(
    workflow: pathlib.Path, files: tuple[str, ...], tokens: list[str]
) -> None:
    for rel in files:
        assert (REPO / rel).is_file(), (
            f"{workflow.name} extracts {rel}, which does not exist. The extraction "
            "loop only warns on a missing file and sets OK=false, so this would "
            "silently mark the classifier untrusted and run every job."
        )


@pytest.mark.parametrize("workflow,files,tokens", _extraction_lists(), ids=lambda v: getattr(v, "name", ""))
def test_the_extraction_list_is_closed_under_its_own_imports(
    workflow: pathlib.Path, files: tuple[str, ...], tokens: list[str]
) -> None:
    """The load-bearing assertion. The extracted files run from an isolated temp
    dir containing ONLY themselves — so any sibling `scripts/ci/` module one of
    them imports must be in the same list, or the import dies at run time."""
    extracted_modules = {pathlib.PurePosixPath(f).stem for f in files}
    siblings = {p.stem for p in CI_DIR.glob("*.py")}

    missing: list[str] = []
    for rel in files:
        path = REPO / rel
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                # `level > 0` is a relative import; there are no packages in the
                # temp dir, so only absolute sibling imports are reachable.
                names = [node.module.split(".")[0]] if node.module and node.level == 0 else []
            else:
                continue
            for name in names:
                if name in siblings and name not in extracted_modules:
                    missing.append(f"{rel} imports `{name}` (scripts/ci/{name}.py)")

    assert not missing, (
        f"{workflow.name}'s trusted-classifier extraction list is NOT import-closed:\n  "
        + "\n  ".join(sorted(set(missing)))
        + f"\n\nAdd the missing scripts/ci/*.py to the `for f in ...` loop in "
        f"{workflow.name}. Left unfixed, the corpus step dies on ModuleNotFoundError, "
        "the classifier is marked untrusted, and the fail-open runs EVERY job on "
        "EVERY pull request — green, silent, and permanent (measured: 9 days, #5070)."
    )


@pytest.mark.parametrize("workflow,files,tokens", _extraction_lists(), ids=lambda v: getattr(v, "name", ""))
def test_a_recognised_list_is_entirely_scripts_ci_and_never_partly_filtered(
    workflow: pathlib.Path, files: tuple[str, ...], tokens: list[str]
) -> None:
    """Reject a MIXED list loudly instead of quietly keeping the part we
    understand (Gear-3 council condition, kimi-code/k3, 2026-09-04).

    `_extraction_lists()` keeps only the `scripts/ci/` tokens of a match. That
    is right for a loop which is not an extraction list at all — e.g.
    `for f in $(git diff --name-only ...); do` elsewhere in
    immune-enforcement.yml, which yields no such token and is correctly
    dropped. It is WRONG for a list that carries some: silently discarding a
    `$VAR` or a sibling path would let a real extraction list shrink past this
    guard, which is the exact silent-narrowing shape the whole file exists to
    prevent.

    So the rule is: contain one, contain only. A list built from a variable
    yields zero and is out of scope here; a list mixing both is a defect
    someone must look at, not something to quietly trim.
    """
    assert tuple(tokens) == files, (
        f"{workflow.name}: a trusted-classifier extraction list mixes "
        f"`{CI_PREFIX}` paths with tokens this guard cannot check: "
        f"{[t for t in tokens if not t.startswith(CI_PREFIX)]}. "
        "Import-closure is only meaningful over a list whose every entry is a "
        "known file — a variable-built or mixed list must be made explicit, "
        "not silently filtered down to the part that happens to be readable."
    )
