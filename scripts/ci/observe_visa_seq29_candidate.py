#!/usr/bin/env python3
# ruff: noqa: T201
"""Observe the unsigned seq-29 candidate and the consumers that grade it.

# bites-observable — no arguments are accepted; every command and path is a
# literal below.  The seq-29 pack gate and the walk census read the highest
# unsigned source pack on disk, so they bite as soon as the candidate is committed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
CANDIDATE = (
    BACKEND_RAG_DIR
    / "backend/services/visa_engine/contracts/packs/rulepack-prod-029.source.json"
)
TEST_MODULES = (
    "backend/tests/services/visa_engine/test_seq29_pack.py",
    "backend/tests/services/visa_engine/test_interview_walk_census.py",
)


def _backend_rag_python() -> str:
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    if not CANDIDATE.is_file():
        print("observe_visa_seq29_candidate: no seq-29 candidate source on disk")
        return 1
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    interpreter = _backend_rag_python()
    for module in TEST_MODULES:
        cmd = [interpreter, "-m", "pytest", module, "-p", "no:cacheprovider"]
        print(
            f"observe_visa_seq29_candidate: running pytest {module} (cwd=apps/backend-rag)"
        )
        rc = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, check=False).returncode
        if rc != 0:
            print(f"observe_visa_seq29_candidate: {module} FAILED")
            return rc
    print("observe_visa_seq29_candidate: seq-29 candidate gate and census green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
