#!/usr/bin/env python3
"""observe_visa_oracle_penjamin_copy.py — bites: observation for the retirement basis and income copy.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle interview. The observation runs the copy-truth
test file from `apps/mouth` and requires every test in it to pass, with the tests that
prove this change reported as run: the retirement basis options say penjamin (EN and ID)
and the income question says income or an allowance and carries no digit.
Exit 0 only if Vitest reports the file passed with zero failures.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/copy-truth.test.ts"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

MIN_TESTS = 70
# Each must be reported as run and passed, so deleting one cannot hide behind the file total.
REQUIRED_TESTS = (
    "the basis options say penjamin and no longer say family sponsor",
    "the income question names income or an allowance and anchors on no figure",
    "the same journey no longer calls the income only passive",
)


def verdict(report: object) -> list[str]:
    """Problems found in a Vitest JSON report; empty only for a full, complete pass.

    Reads structured data only: printed test output cannot satisfy it.
    """
    if not isinstance(report, dict):
        return ["report is not an object"]
    problems: list[str] = []
    total, passed = report.get("numTotalTests"), report.get("numPassedTests")
    if not isinstance(total, int) or not isinstance(passed, int):
        return ["report has no integer test counts"]
    if report.get("success") is not True:
        problems.append("report success is not true")
    if passed != total or passed < MIN_TESTS:
        problems.append(f"{passed} passed of {total} (need all, at least {MIN_TESTS})")
    for key in ("numFailedTests", "numPendingTests", "numTodoTests"):
        if report.get(key) not in (0, None):
            problems.append(f"{key} is {report.get(key)}")
    status: dict[str, str] = {}
    for suite in report.get("testResults") or []:
        for case in (suite or {}).get("assertionResults") or []:
            status[str(case.get("title"))] = str(case.get("status"))
            status[str(case.get("fullName"))] = str(case.get("status"))
    for title in REQUIRED_TESTS:
        hits = [s for name, s in status.items() if name.endswith(title)]
        if not hits or any(s != "passed" for s in hits):
            problems.append(f"required test not passed: {title}")
    return problems


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out_file = Path(tmp) / "report.json"
        result = subprocess.run(
            ["npx", "vitest", "run", "--reporter=json", f"--outputFile={out_file}", TEST_FILE],
            cwd=MOUTH_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        try:
            report = json.loads(out_file.read_text())
        except (OSError, ValueError):
            report = None
    problems = verdict(report) if result.returncode == 0 else [f"vitest exit {result.returncode}"]
    if report is None:
        problems = problems or ["no JSON report"]
    if problems:
        print(f"observe_visa_oracle_penjamin_copy: FAILED {problems}")
        print(ANSI.sub("", result.stdout + result.stderr)[-1500:])
        return result.returncode or 1
    print(f"observe_visa_oracle_penjamin_copy: Tests {report['numPassedTests']} passed ({report['numTotalTests']})")
    print("observe_visa_oracle_penjamin_copy: penjamin copy holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
