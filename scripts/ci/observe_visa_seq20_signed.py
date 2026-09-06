#!/usr/bin/env python3
"""observe_visa_seq20_signed.py — bites: observation for the seq-20 SIGNING lane.

# bites-observable — this script takes NO arguments: every path and command
# below is a literal in this file, so nothing an invoker types can name a
# program to run, a file to write, or a database to reach (the exact bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets for a script
# reachable from a pack.yml `observe:` line).

Sibling of ``observe_visa_seq20_fold.py``, which observed the UNSIGNED source
pack. This one observes the SIGNED bundle, and runs the two consumers named
in this lane's ``Bites:`` line, in order, failing loud on the first red one:

1. ``test_seq20_signed_bundle.py`` — verifies ``rulepack-prod-020.signed.json``
   with the repo's own ``bundle.verify_rule_pack`` against the PINNED
   production trust store, recomputes both digests off disk independently,
   pins the five fold edits inside the signed bytes, and proves five
   tampering shapes are rejected.
2. ``test_interview_walk_census.py`` — the consumer that makes this bundle's
   arrival OBSERVABLE rather than merely present: it reads the HIGHEST SIGNED
   production pack on disk via ``select_highest_repository_pack``, so landing
   seq-20 moves it off seq-19 by itself. Four of its assertions were red
   against the seq-20 bundle before this PR re-pinned them; the walk census
   moved 36 NEEDS_INPUT / 7 SUPPORTED to 21 / 22. A future PR that lands a
   seq-21 bundle without re-pinning this census goes red here, which is the
   whole point of pinning it against "highest signed" rather than a literal
   filename.

Both run inside ``apps/backend-rag`` with ``PYTHONPATH=.`` (the repo's
mandatory invocation shape). No trust-store env var is exported here: the
signed-bundle module sets its own via ``monkeypatch.setenv`` so a
pre-existing value in the invoking process is restored rather than clobbered,
and the census module never verifies a signature.

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
    "backend/tests/services/visa_engine/test_seq20_signed_bundle.py",
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
        cmd = [interpreter, "-m", "pytest", module]
        print(f"observe_visa_seq20_signed: running {' '.join(cmd)} (cwd={BACKEND_RAG_DIR})")
        rc = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, check=False).returncode
        if rc != 0:
            print(f"observe_visa_seq20_signed: {module} FAILED")
            return rc

    print("observe_visa_seq20_signed: both consumers green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
