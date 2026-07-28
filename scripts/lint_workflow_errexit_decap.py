#!/usr/bin/env python3
"""A bare `VAR=$(...)` under Actions' default `bash -e` decapitates its own check.

THE DEFECT THIS EXISTS TO CATCH (scar W101, FOURTH instance, measured 2026-07-28):

GitHub runs every `run:` block as `/usr/bin/bash -e {0}` unless the step declares
its own `shell:`. Under `-e`, a bare assignment from a command substitution —

    out=$(some-tool 2>&1); rc=$?      # <-- the step DIES here

aborts the whole step the instant `some-tool` exits non-zero: before `rc=$?`,
before the `printf`, before the `case` that was written to interpret the
failure. The diagnostic branch exists and can never run.

MEASURED, not theorised. `merge-queue-watch.yml`'s re-arm step (run 30319258460,
2026-07-28 01:05Z) lived 1.0 second, emitted ZERO lines — not its population
line, not the tool's own "queue probe FAILED" message — and died with the
script's rc=3. Every scheduled run had behaved that way since the job was armed,
so the merge-queue re-armer had never once produced a readable verdict. The
reason it was never diagnosed is the bug itself: it eats the evidence.

The cruelty of this scar is that it hides inside correct-looking prudence. The
decapitated block above carried the comment "No `set -e`: the assignment below
must survive a non-zero exit, or the verdict is decapitated before it is ever
read (W101)" — and then wrote `set -uo pipefail`, which does NOT clear the `-e`
GitHub already applied. The comment cited the scar it was reintroducing. Two
other sites in `frontend-live-sentinel.yml` did the same while their comments
correctly warned about *different* scars (pipe-masking, judge-the-reply).

THE CURE, which this repo already owned before this lint existed:

    rc=0
    out=$(some-tool 2>&1) || rc=$?

`||` puts the assignment in a condition context, which errexit ignores by
definition. `docs-inventory-refresh.yml` has used exactly this since its own
W101 fix; three neighbours never picked it up. That is what makes it a class and
not an incident, and why documentation was not enough.

WHAT IT ASSERTS
  1. no `run:` block reachable under errexit captures a command substitution
     into a bare assignment whose exit status it then reads;
  2. the scan actually walked something — zero files or zero run-blocks is a
     broken scanner, never a clean repo (W84 blind-scan guard).

DELIBERATELY NOT FLAGGED (these are innocent, and the corpus pins each one):
  - `VAR=$(...) || VAR_RC=$?`      — the cure itself, including when the `||`
                                     lands on a continuation line;
  - an assignment whose status is never read (errexit killing the step IS the
    intended behaviour there — no diagnostic branch is being decapitated);
  - blocks under an explicit `shell:` that omits `-e`;
  - anything after a `set +e` that is still in force.

Run:  python3 scripts/lint_workflow_errexit_decap.py
      python3 scripts/lint_workflow_errexit_decap.py --path <dir>
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# A shell spec that does NOT carry errexit. Actions' default for `bash` is
# `bash -e {0}`; an explicit `shell: bash {0}` (or sh/pwsh/python) does not.
_ERREXIT_SHELLS = ("bash", "sh")

_ASSIGN = re.compile(r"^(?P<indent>\s*)(?P<var>[A-Za-z_][A-Za-z0-9_]*)=\$\(")


def _shell_has_errexit(shell: str | None) -> bool:
    """Actions applies -e only for the DEFAULT bash/sh, not for a custom spec."""
    if shell is None:
        return True  # default: bash -e {0}
    s = shell.strip()
    if s in _ERREXIT_SHELLS:
        return True  # `shell: bash` still means `bash -e {0}`
    return False  # any explicit command line (`bash {0}`, `python`, ...) opts out


def _statement(lines: list[str], i: int) -> tuple[str, int]:
    """Join backslash-continuations so a multi-line command is ONE statement.

    Without this the `||` of a correctly-cured multi-line `gh pr create` sits on
    a later line and the assignment reads as bare — the exact false positive the
    first draft of this lint produced against docs-inventory-refresh.yml.
    """
    parts = [lines[i]]
    j = i
    while j < len(lines) - 1 and parts[-1].rstrip().endswith("\\"):
        j += 1
        parts.append(lines[j])
    return "\n".join(parts), j


def _status_is_read(statement: str, following: list[str]) -> bool:
    """Does anything consume this assignment's exit status?

    `$?` may sit on the SAME line (`…); rc=$?`) or just below. Looking only at
    the following lines is an under-match — it missed the very site that
    prompted this lint (superscar #3: judge the entity, not the shape).
    """
    if "$?" in statement:
        return True
    return any("$?" in ln for ln in following[:3])


def scan_run_block(body: str) -> list[tuple[int, str]]:
    """Offsets (0-based, within the block) of decapitating assignments."""
    out: list[tuple[int, str]] = []
    lines = body.splitlines()
    errexit_live = True
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("set ") or stripped in ("set +e", "set -e"):
            if re.search(r"set\s+[+][a-z]*e", stripped):
                errexit_live = False
            elif re.search(r"set\s+-[a-z]*e", stripped):
                errexit_live = True
        m = _ASSIGN.match(line)
        if m and errexit_live:
            statement, last = _statement(lines, i)
            if "||" not in statement and _status_is_read(statement, lines[last + 1 :]):
                out.append((i, stripped[:90]))
            i = last + 1
            continue
        i += 1
    return out


def iter_run_blocks(doc: dict):
    """(job_id, step_index, step_name, shell, run_body) for every step."""
    jobs = (doc or {}).get("jobs") or {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        job_shell = ((job.get("defaults") or {}).get("run") or {}).get("shell")
        for idx, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict) or "run" not in step:
                continue
            shell = step.get("shell", job_shell)
            yield job_id, idx, step.get("name", f"step {idx}"), shell, step["run"]


def audit(root: pathlib.Path) -> tuple[list[str], int, int]:
    files = sorted(list(root.glob("*.yml")) + list(root.glob("*.yaml")))
    findings: list[str] = []
    blocks = 0
    for path in files:
        try:
            doc = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue  # malformed YAML is actionlint's job, not ours
        for job_id, _idx, name, shell, body in iter_run_blocks(doc):
            blocks += 1
            if not _shell_has_errexit(shell):
                continue
            for _off, text in scan_run_block(body):
                findings.append(f"{path.name} [{job_id} / {name}]: {text}")
    return findings, len(files), blocks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=str(DEFAULT_WORKFLOWS))
    args = ap.parse_args()

    root = pathlib.Path(args.path)
    if not root.is_dir():
        print(f"::error::workflow directory not found: {root}", file=sys.stderr)
        return 2

    findings, n_files, n_blocks = audit(root)

    # W84: a scan that walked nothing is not a clean scan.
    if n_files == 0 or n_blocks == 0:
        print(
            f"::error::blind scan — {n_files} workflow file(s), {n_blocks} run-block(s). "
            "Zero is a broken scanner, never a clean repo.",
            file=sys.stderr,
        )
        return 2

    print(f"errexit-decap lint: {n_files} workflow file(s), {n_blocks} run-block(s) scanned")
    if not findings:
        print("clean — every status-reading capture is errexit-immune")
        return 0

    print(f"\n{len(findings)} decapitating assignment(s) — the check below them can never run:")
    for f in findings:
        print(f"  {f}")
    print(
        "\nCure: `RC=0` then `VAR=$(...) || RC=$?`. A bare assignment under the default\n"
        "`bash -e` aborts the step before your own failure branch is reached (W101)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
