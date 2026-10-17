#!/usr/bin/env python3
# ruff: noqa: T201
"""Observe the signed seq-31 bundle and its three downstream consumers.

# bites-observable — no arguments are accepted; every command, path and floor is
# a literal below, so nothing an invoker types can name a program to run, a file
# to write or a database to reach.  The observation is red until
# ``rulepack-prod-031.signed.json`` is on disk AND ``review_hold_inventory``
# reads it as the highest signed pack.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
EXPECTED_SIGNED_SEQUENCE = 31
# (module, minimum passed, maximum skipped): a reduced count, a failure, an error,
# an xfail or an extra skip is red.
TEST_MODULES = (
    # Floors are the SIGNED-state counts: 35 = 31 unsigned-source tests + the 4 signed-bundle
    # ties; the census is 125 collected, 14 of them candidate-mode tests that skip once no
    # unsigned pack sits above the highest signed one (125 - 14 = 111 passed, 14 skipped).
    ("backend/tests/services/visa_engine/test_seq31_pack.py", 35, 0),
    ("backend/tests/services/visa_engine/test_interview_walk_census.py", 111, 14),
    ("backend/tests/scripts/visa_engine/test_review_hold_inventory.py", 7, 0),
)
_SUMMARY = re.compile(
    r"^=*\s*(\d+) passed(?:, (\d+) skipped)? in [0-9.]+s(?: \([0-9:]+\))?\s*=*$"
)
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def summary_ok(line: str | None, min_passed: int, max_skipped: int = 0) -> bool:
    """True only for a pytest line that is exactly `N passed[, M skipped] in Xs`.

    N >= min_passed and M <= max_skipped.  Anything else (failed, error, xfail,
    warnings, a reduced count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(_ANSI.sub("", line).strip())
    if match is None:
        return False
    return int(match.group(1)) >= min_passed and int(match.group(2) or 0) <= max_skipped


def _backend_rag_python() -> str:
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def _shown(cmd: list[str]) -> str:
    return " ".join(
        str(Path(part).relative_to(REPO_ROOT)) if part.startswith(str(REPO_ROOT)) else part
        for part in cmd
    )


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    interpreter = _backend_rag_python()
    inventory_cmd = [
        interpreter,
        "-m",
        "backend.scripts.visa_engine.review_hold_inventory",
        "--json",
    ]
    print(f"observe_visa_seq31_signed: running {_shown(inventory_cmd)} (cwd=apps/backend-rag)")
    result = subprocess.run(
        inventory_cmd,
        cwd=BACKEND_RAG_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"observe_visa_seq31_signed: review_hold_inventory exited {result.returncode}")
        return result.returncode
    inventory = json.loads(result.stdout)
    print(
        f"observe_visa_seq31_signed: highest signed sequence={inventory['sequence']} "
        f"totals={json.dumps(inventory['totals'], sort_keys=True)}"
    )
    if inventory["sequence"] != EXPECTED_SIGNED_SEQUENCE:
        print(
            f"observe_visa_seq31_signed: highest signed pack is seq-{inventory['sequence']}, "
            f"not seq-{EXPECTED_SIGNED_SEQUENCE}"
        )
        return 1

    for module, min_passed, max_skipped in TEST_MODULES:
        cmd = [interpreter, "-m", "pytest", module, "-p", "no:cacheprovider"]
        print(f"observe_visa_seq31_signed: running {_shown(cmd)} (cwd=apps/backend-rag)")
        run = subprocess.run(
            cmd, cwd=BACKEND_RAG_DIR, env=env, check=False, capture_output=True, text=True
        )
        out = run.stdout + run.stderr
        lines = [ln for ln in out.splitlines() if re.search(r"\bin [0-9.]+s", ln)]
        line = lines[-1] if lines else None
        if run.returncode != 0 or not summary_ok(line, min_passed, max_skipped):
            summary = _ANSI.sub("", line).strip() if line else "no pytest summary"
            print(f"observe_visa_seq31_signed: {module} FAILED ({summary})")
            print(_ANSI.sub("", out)[-1500:])
            return run.returncode or 1
        print(f"observe_visa_seq31_signed: {module}: {_ANSI.sub('', line).strip()}")
    print("observe_visa_seq31_signed: inventory reads seq-31 and all three consumers green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
