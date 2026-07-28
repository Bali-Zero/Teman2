#!/usr/bin/env python3
"""Guilt + innocence corpus for the errexit-decapitation lint.

A guard merged without BOTH halves is half a guard (superscar #3): the guilt
cases prove it still bites, the innocence cases prove it does not bite the
legitimate neighbour. Two of the innocence cases below are not hypothetical —
they are the false positives the first draft of the lint actually produced:

  * `docs-inventory-refresh.yml` was flagged because its `|| PR_CREATE_RC=$?`
    sits on a CONTINUATION line, so the first line read as a bare assignment;
  * the site that started the whole hunt was MISSED because its `rc=$?` sits on
    the SAME line as the assignment, while the draft only looked at the lines
    below. Over-match and under-match, one draft, opposite signs.

A third one bit inside this file: `test_the_lint_imports_nothing_third_party`
first grepped for the text `import yaml` and failed on the COMMENT explaining
why that import is absent. Same disease, third surface — so it now judges the
AST. The rule is not "write a careful regex", it is "a form is not an entity",
and it has to be re-applied at every predicate, not once per file.

Run:  python3 scripts/tests/test_lint_workflow_errexit_decap.py
      pytest scripts/tests/test_lint_workflow_errexit_decap.py -q
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lint_workflow_errexit_decap import audit, iter_run_blocks, scan_run_block  # noqa: E402


def _workflows_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows"


def test_the_lint_imports_nothing_third_party() -> None:
    """CI caught this one: `import yaml` is fine locally, ModuleNotFoundError on
    the immune-enforcement runner, which installs nothing. An immune organ that
    needs a pip install dies whenever the install does.

    Judged on the AST, not on a substring. The first draft of THIS test grepped
    for the text `import yaml` and duly failed on the comment that explains why
    the import is absent — form instead of entity, superscar #3, inside the very
    corpus that punishes it. A module name in prose is not an import statement.
    """
    src = (pathlib.Path(__file__).resolve().parents[1] / "lint_workflow_errexit_decap.py").read_text()
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    assert imported, "no imports parsed at all — broken check, not a clean file"
    third_party = sorted(m for m in imported if m not in sys.stdlib_module_names)
    assert not third_party, (
        f"third-party import(s) {third_party} reintroduce a runner-only failure: "
        "the immune-enforcement job installs nothing"
    )


def test_text_walker_matches_a_yaml_parse_on_the_real_workflow_set() -> None:
    """The hand-rolled block-scalar walk must agree with YAML, file by file.

    Pins the defect this equivalence check found: a bare `run:` (i.e.
    `defaults: run:`, a MAPPING) was being treated as a block scalar. Where the
    phantom block swallowed the real `run: |` below it the count came out LOW
    (6 cron-*.yml), where it did not it came out HIGH (2 others) — one defect,
    both signs. A total-only comparison would have partly cancelled them out,
    so this asserts per-file.
    """
    try:
        import yaml  # noqa: PLC0415 — optional: the lint itself must not need it
    except ImportError:  # pragma: no cover - runner without PyYAML
        return

    root = _workflows_dir()
    files = sorted(list(root.glob("*.yml")) + list(root.glob("*.yaml")))
    assert files, "no workflows walked — broken scanner, not a clean repo"

    mismatches = []
    for p in files:
        text = p.read_text()
        walked = len(list(iter_run_blocks(text)))
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        parsed = sum(
            1
            for job in ((doc or {}).get("jobs") or {}).values()
            if isinstance(job, dict)
            for s in (job.get("steps") or [])
            if isinstance(s, dict) and "run" in s
        )
        if walked != parsed:
            mismatches.append(f"{p.name}: walked={walked} yaml={parsed}")
    assert not mismatches, "text walk disagrees with YAML:\n  " + "\n  ".join(mismatches)


def test_a_bare_run_key_is_a_mapping_not_a_script() -> None:
    """`defaults: run:` must contribute NO run-block and must not swallow the next one."""
    wf = (
        "jobs:\n  j:\n    defaults:\n      run:\n        shell: bash\n"
        "    steps:\n      - name: real\n        run: |\n          out=$(x 2>&1); rc=$?\n"
    )
    blocks = list(iter_run_blocks(wf))
    assert len(blocks) == 1, f"expected exactly the real step, got {len(blocks)}"
    assert blocks[0][0] == "real", f"label lost: {blocks[0][0]!r}"


# --------------------------------------------------------------------------
# GUILT — each of these decapitates a check that was written to run
# --------------------------------------------------------------------------

def test_guilt_status_read_on_the_same_line() -> None:
    """The shape that started the hunt: `…); rc=$?` — status read inline."""
    body = 'out=$(some-tool 2>&1); rc=$?\ncase "$rc" in 0) ;; esac\n'
    assert scan_run_block(body), "a bare capture whose rc is read inline must be flagged"


def test_guilt_status_read_on_a_following_line() -> None:
    body = 'out=$(some-tool 2>&1)\nrc=$?\nif [ "$rc" -ne 0 ]; then echo no; fi\n'
    assert scan_run_block(body), "a bare capture whose rc is read below must be flagged"


def test_guilt_multiline_capture_without_the_cure() -> None:
    body = 'out=$(gh pr create --base main \\\n  --title x 2>&1); rc=$?\necho "$rc"\n'
    assert scan_run_block(body), "a multi-line bare capture must still be flagged"


def test_guilt_set_minus_e_re_arms_errexit_after_a_set_plus_e() -> None:
    body = 'set +e\nset -e\nout=$(some-tool 2>&1); rc=$?\n'
    assert scan_run_block(body), "`set -e` after `set +e` puts errexit back in force"


# --------------------------------------------------------------------------
# INNOCENCE — the lint must stay silent on every one of these
# --------------------------------------------------------------------------

def test_innocence_the_cure_itself() -> None:
    body = 'rc=0\nout=$(some-tool 2>&1) || rc=$?\ncase "$rc" in 0) ;; esac\n'
    assert not scan_run_block(body), "`|| rc=$?` is the cure and must never be flagged"


def test_innocence_cure_on_a_continuation_line() -> None:
    """The real docs-inventory-refresh.yml shape — a first-draft false positive."""
    body = (
        'PR_CREATE_RC=0\n'
        'PR_CREATE_OUT=$(gh pr create --base main --head "$BRANCH" \\\n'
        '  --title "t" \\\n'
        '  --body-file "$F" 2>&1) || PR_CREATE_RC=$?\n'
        'if [ "$PR_CREATE_RC" -ne 0 ]; then echo bad; fi\n'
    )
    assert not scan_run_block(body), "the `||` may legitimately land on a continuation line"


def test_innocence_status_never_read() -> None:
    """No diagnostic branch exists, so errexit killing the step IS the intent."""
    body = 'sha=$(git rev-parse HEAD)\necho "$sha"\n'
    assert not scan_run_block(body), "an unread status is not a decapitated check"


def test_innocence_after_set_plus_e() -> None:
    body = 'set +e\nout=$(some-tool 2>&1); rc=$?\necho "$rc"\n'
    assert not scan_run_block(body), "errexit is disarmed, so nothing is decapitated"


# --------------------------------------------------------------------------
# W84 — a scan that walked nothing is not a clean scan
# --------------------------------------------------------------------------

def test_blind_scan_reports_zero_files_and_zero_blocks() -> None:
    with tempfile.TemporaryDirectory() as d:
        findings, n_files, n_blocks = audit(pathlib.Path(d))
        assert findings == [] and n_files == 0 and n_blocks == 0
        # main() turns exactly this state into exit 2; the point here is that
        # the counts are RETURNED, so "clean" can never be reported blindly.


def test_the_real_repo_is_scanned_non_vacuously() -> None:
    root = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows"
    _findings, n_files, n_blocks = audit(root)
    assert n_files > 50, f"expected the real workflow set, walked {n_files} file(s)"
    assert n_blocks > 100, f"expected many run-blocks, walked {n_blocks}"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}\n       {exc}")
    print("PASS" if not failures else f"FAIL ({failures})")
    sys.exit(1 if failures else 0)
