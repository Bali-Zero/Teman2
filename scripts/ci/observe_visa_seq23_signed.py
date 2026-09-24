#!/usr/bin/env python3
"""observe_visa_seq23_signed.py — bites: observation for the seq-23 SIGNING lane.

# bites-observable — this script takes NO arguments: every path and command
# below is a literal in this file, so nothing an invoker types can name a
# program to run, a file to write, or a database to reach (the exact bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets for a script
# reachable from a pack.yml `observe:` line).

Sibling of ``observe_visa_seq22_signed.py`` (Slice A9.3). Fails loud on the
first red step:

1. ``review_hold_inventory --json`` must report ``sequence == 23`` — the
   proof that ``rulepack-prod-023.signed.json`` is the HIGHEST SIGNED pack on
   disk, which is what every consumer below reads.
2. ``test_seq23_pack.py`` — the seq-23 pack's own gate, including the
   per-row ENGINE witnesses (gate #7174 F1).
3. ``test_interview_walk_census.py`` — reads the highest signed pack via
   ``select_highest_repository_pack``; its ``_SIGNED_SEQUENCE``-keyed pins
   are the ones this PR moved.
4. ``test_review_hold_inventory.py`` — its count pins are the values step 1
   prints on the signed tree (1 / 0).

All run inside ``apps/backend-rag`` with ``PYTHONPATH=.`` (the repo's
mandatory invocation shape). No trust-store env var is exported here.

Exit 0 only if every step is green.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
EXPECTED_SIGNED_SEQUENCE = 23
TEST_MODULES = (
    "backend/tests/services/visa_engine/test_seq23_pack.py",
    "backend/tests/services/visa_engine/test_interview_walk_census.py",
    "backend/tests/scripts/visa_engine/test_review_hold_inventory.py",
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


def _shown(cmd: list[str]) -> str:
    """The command as it is printed: repo-relative, so the transcript reads the
    same in any checkout (a PR body's proof fence is re-run from another one)."""
    return " ".join(
        str(Path(part).relative_to(REPO_ROOT))
        if part.startswith(str(REPO_ROOT))
        else part
        for part in cmd
    )


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    interpreter = _backend_rag_python()

    cmd = [
        interpreter,
        "-m",
        "backend.scripts.visa_engine.review_hold_inventory",
        "--json",
    ]
    print(f"observe_visa_seq23_signed: running {_shown(cmd)} (cwd=apps/backend-rag)")
    result = subprocess.run(
        cmd, cwd=BACKEND_RAG_DIR, env=env, check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(
            f"observe_visa_seq23_signed: review_hold_inventory exited {result.returncode}"
        )
        return result.returncode
    inventory = json.loads(result.stdout)
    print(
        f"observe_visa_seq23_signed: highest signed sequence={inventory['sequence']} "
        f"totals={json.dumps(inventory['totals'], sort_keys=True)}"
    )
    if inventory["sequence"] != EXPECTED_SIGNED_SEQUENCE:
        print(
            f"observe_visa_seq23_signed: highest signed pack is seq-{inventory['sequence']}, "
            f"not seq-{EXPECTED_SIGNED_SEQUENCE}"
        )
        return 1

    for module in TEST_MODULES:
        cmd = [interpreter, "-m", "pytest", module, "-p", "no:cacheprovider"]
        print(
            f"observe_visa_seq23_signed: running {_shown(cmd)} (cwd=apps/backend-rag)"
        )
        rc = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, check=False).returncode
        if rc != 0:
            print(f"observe_visa_seq23_signed: {module} FAILED")
            return rc
    print(
        "observe_visa_seq23_signed: inventory reads seq-23 and all three consumers green"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
