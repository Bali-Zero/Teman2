#!/usr/bin/env python3
"""observe_visa_engine_prohibited_activities.py — bites: observation for E33 PR-19 (prohibited activities on the display).

# bites-observable — this script takes NO arguments: the program it runs and the
# test class it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the Visa Oracle engine's /evaluate display block
(`_build_display`, DTO `CandidateDisplayDTO`). The observation runs the display test
file and requires every test to pass: each candidate carries `prohibited_activities`
from the signed pack (E33 carries `sale_of_goods_or_services`), the list is empty for a
product with none, and the key is never dropped.
Exit 0 only if pytest reports a full pass with at least the minimum test count.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "apps" / "backend-rag"
TEST_TARGET = "backend/tests/services/visa_engine/test_evaluate_path_display.py"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MIN_TESTS = 4
_SUMMARY = re.compile(r"^(?:=+ )?(\d+) passed(?:, \d+ warnings?)? in [\d.]+s(?: \([\d:]+\))?(?: =+)?$")


def summary_ok(line: str | None) -> bool:
    """True only for a pytest line that is a pure pass (warnings aside), N >= 4.

    Anything else (failed, error, skipped, xfailed, deselected, a reduced count,
    no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line.strip())
    if match is None:
        return False
    return int(match.group(1)) >= MIN_TESTS


def _backend_python() -> str:
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    result = subprocess.run(
        [_backend_python(), "-m", "pytest", TEST_TARGET, "-p", "no:cacheprovider"],
        cwd=BACKEND_DIR,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    lines = [ln for ln in out.splitlines() if re.search(r"\d+ (passed|failed|error|skipped)", ln) and " in " in ln]
    line = lines[-1] if lines else None
    summary = line.strip("= ") if line else "no pytest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(f"observe_visa_engine_prohibited_activities: FAILED ({summary})\n{out[-1500:]}")
        return result.returncode or 1
    print(f"observe_visa_engine_prohibited_activities: {summary}")
    print("observe_visa_engine_prohibited_activities: prohibited activities display holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
