#!/usr/bin/env python3
"""observe_pajak_monitor_tests.py — bites: observation for the pajak-monitor tests workflow.

# bites-observable — this script takes NO arguments: the interpreter, the working directory
# and both test paths are fixed below, so nothing an invoker types can name a program to run,
# a file to write, or a database to reach (the bar `scripts/ci/bites_parse.py`'s
# `_guard_observable_script` sets for a script reachable from a pack.yml `observe:` line).

Runs exactly what `.github/workflows/pajak-monitor-tests.yml` runs: the parser and monitor
suites that pin the deadline arm, the excerpt anchor and the real-host lake label. Exit code is
pytest's, so zero collected tests (5) or a collection error (2) is a failure too.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = (
    "scripts/tests/test_pajak_parse.py",
    "scripts/tests/test_pajak_monitor.py",
)


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", *TESTS, "-q"]
    print(f"observe_pajak_monitor_tests: running {' '.join(cmd)} (cwd={REPO_ROOT})", flush=True)
    return subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
