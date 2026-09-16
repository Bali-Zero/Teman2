#!/usr/bin/env python3
"""observe_visa_seq22_signed.py — bites: observation for the seq-22 SIGNING lane.

# bites-observable — this script takes NO arguments: every path and command
# below is a literal in this file, so nothing an invoker types can name a
# program to run, a file to write, or a database to reach (the exact bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets for a script
# reachable from a pack.yml `observe:` line).

Sibling of ``observe_visa_seq20_signed.py``. Runs the two backend consumers
named in this lane's ``Bites:`` line, in order, failing loud on the first red:

1. ``test_seq22_pack.py`` — the seq-22 pack's own gate (fold from signed
   seq-20, no HARD_FILTER on a synthesised twin-basis fact, the Studio rule's
   behaviour on both bases).
2. ``test_interview_walk_census.py`` — the consumer that makes the signed
   bundle's arrival OBSERVABLE rather than merely present: it reads the
   HIGHEST SIGNED production pack on disk via ``select_highest_repository_pack``,
   so landing ``rulepack-prod-022.signed.json`` moves it off seq-20 by
   itself. Two of its assertions were red against the seq-22 bundle before
   this PR pinned the Studio-held walks per signed sequence.

Both run inside ``apps/backend-rag`` with ``PYTHONPATH=.`` (the repo's
mandatory invocation shape). No trust-store env var is exported here.

Exit 0 only if both are green.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"

TEST_MODULES = (
    "backend/tests/services/visa_engine/test_seq22_pack.py",
    "backend/tests/services/visa_engine/test_interview_walk_census.py",
)


def _backend_rag_python() -> str:
    """Prefer the project's own venv (CLAUDE.md: `apps/backend-rag/.venv/`) —
    fall back to whatever interpreter is running this script if the venv is
    absent (e.g. a CI image that installs deps onto the system interpreter
    directly rather than into a checked-out venv)."""
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    interpreter = _backend_rag_python()

    for module in TEST_MODULES:
        cmd = [interpreter, "-m", "pytest", module, "-p", "no:cacheprovider"]
        print(f"observe_visa_seq22_signed: running {' '.join(cmd)} (cwd={BACKEND_RAG_DIR})")
        rc = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, check=False).returncode
        if rc != 0:
            print(f"observe_visa_seq22_signed: {module} FAILED")
            return rc

    print("observe_visa_seq22_signed: both consumers green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
