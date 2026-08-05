#!/usr/bin/env python3
"""A CI job's floor is the CHECKOUT, not the runtime of the thing it runs.

WHY THIS EXISTS (2026-08-06). `docs-sync.yml` and `root-guard.yml` each budgeted
their job at `timeout-minutes: 2`, sized by the work: `root-guard.yml` says so in
its own comment — "the check is fast (~0.2s)". True of the SCRIPT. The JOB also
has to get the repo onto the runner, and `actions/checkout` here normally takes
~20s but intermittently takes ~2 MINUTES.

Measured on the runs it killed — docs-sync 31035447775, 31033448943, 31010616378
(one of them on `main`) — checkout ran 1m58s-2m01s and was cut off, so the step
that was supposed to judge the PR NEVER RAN. `root-guard` lost 1 of its last 30
runs the same way, and that one is a REQUIRED context on main that also runs on
`merge_group`, so it can stall the queue.

THE PART THAT MAKES IT A TRAP RATHER THAN A FLAKE: a blown budget reports as
`cancelled`, not `failure`. A cancelled required check never turns green by
itself and there is nothing red to fix — the PR is simply stuck, and the obvious
reading ("someone cancelled it") is wrong.

SCOPE, DELIBERATELY NARROW. This flags a job only when ALL of:
  - it runs `actions/checkout`, and
  - it DECLARES `timeout-minutes`, and
  - the declared value is below the floor.

A job with no checkout is not exposed (the census that first counted 6 offenders
was counting FILES that contain a checkout, not JOBS that run one — the real
number is 2). A job with no `timeout-minutes` is out of scope too: its default is
360 minutes, which is a different risk and not this one.

Exit codes: 0 clean · 1 a job is under the floor · 2 cannot verify (nothing
scanned, or a workflow would not parse — an empty sweep is not a pass, W84).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# Below this, an ordinary slow checkout eats the whole budget. Not a guess: the
# observed bad checkouts land at ~2 minutes, and the floor has to clear that plus
# the actual work with room left.
FLOOR_MINUTES = 5

WORKFLOW_DIR = Path(".github/workflows")


def job_checks_out(job: dict[str, Any]) -> bool:
    """True when the job runs actions/checkout.

    By the step's `uses`, never by searching the file text: a file-level match
    attributes a checkout in job A to job B, which is how the first census of
    this very defect over-counted 6 where the answer was 2.
    """
    for step in job.get("steps") or []:
        if isinstance(step, dict) and "actions/checkout" in str(step.get("uses", "")):
            return True
    return False


def offenders(root: Path) -> tuple[list[tuple[str, str, int]], list[str], int]:
    """(offending jobs, unparseable files, jobs scanned)."""
    found: list[tuple[str, str, int]] = []
    unparseable: list[str] = []
    scanned = 0

    for path in sorted(root.glob("*.yml")) + sorted(root.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
        except yaml.YAMLError as exc:
            unparseable.append(f"{path.name}: {exc}")
            continue
        if not isinstance(doc, dict):
            continue
        for name, job in (doc.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            scanned += 1
            timeout = job.get("timeout-minutes")
            if not isinstance(timeout, int) or isinstance(timeout, bool):
                continue  # undeclared, or an expression — out of scope
            if timeout < FLOOR_MINUTES and job_checks_out(job):
                found.append((path.name, str(name), timeout))

    return found, unparseable, scanned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(WORKFLOW_DIR))
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"CANNOT VERIFY: {root} is not a directory", file=sys.stderr)
        return 2

    found, unparseable, scanned = offenders(root)

    if unparseable:
        for line in unparseable:
            print(f"CANNOT VERIFY (unparseable): {line}", file=sys.stderr)
        return 2

    if scanned == 0:
        # An empty sweep reads byte-identical to a healthy one. It is not one.
        print(f"CANNOT VERIFY: zero jobs scanned under {root}", file=sys.stderr)
        return 2

    if found:
        print(
            f"{len(found)} job(s) budget the CHECKOUT out of existence "
            f"(floor {FLOOR_MINUTES}m, {scanned} jobs scanned):",
            file=sys.stderr,
        )
        for filename, job, timeout in found:
            print(f"  {filename}::{job}  timeout-minutes: {timeout}", file=sys.stderr)
        print(
            "\nactions/checkout on this repo intermittently takes ~2 minutes. A job "
            "that runs out reports as `cancelled`, not `failure` — a cancelled "
            "required check never turns green by itself and shows nothing red to "
            "fix. Size the budget by the checkout, not by the script.",
            file=sys.stderr,
        )
        return 1

    print(f"workflow timeout floor: clean ({scanned} jobs scanned, floor {FLOOR_MINUTES}m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
