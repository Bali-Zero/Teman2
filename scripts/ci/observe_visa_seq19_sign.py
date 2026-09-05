#!/usr/bin/env python3
"""observe_visa_seq19_sign.py — bites: observation for the seq-19
signed-bundle lane.

# bites-observable — this script takes NO arguments: every path and command
# below is a literal in this file, so nothing an invoker types can name a
# program to run, a file to write, or a database to reach (the exact bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets for a script
# reachable from a pack.yml `observe:` line).

Runs the one consumer named in this lane's `Bites:` line:
``apps/backend-rag``'s ``test_seq19_signed_bundle.py`` — the gate suite that
independently verifies ``rulepack-prod-019.signed.json`` against the repo's
own Ed25519 verification code (never the signer's self-report), pins the
chain anchor to seq-18, and proves the guilt half (a tampered in-memory copy
fails verification).

Exit 0 only if the suite is green.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"


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
    python_env = dict(os.environ)
    python_env["PYTHONPATH"] = "backend"
    cmd = [
        _backend_rag_python(),
        "-m",
        "pytest",
        "backend/tests/services/visa_engine/test_seq19_signed_bundle.py",
    ]
    print(f"observe_visa_seq19_sign: running {' '.join(cmd)} (cwd={BACKEND_RAG_DIR})")
    rc = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=python_env, check=False).returncode
    if rc != 0:
        print("observe_visa_seq19_sign: test_seq19_signed_bundle.py FAILED")
        return rc

    print("observe_visa_seq19_sign: consumer green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
