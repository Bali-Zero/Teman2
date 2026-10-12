#!/usr/bin/env python3
# ruff: noqa: T201
"""Observe the signed seq-28 bundle and its three downstream consumers.

# bites-observable — no arguments are accepted; every command and path is a
# literal below.  This observer is intentionally dormant until the separate
# human signing ceremony adds ``rulepack-prod-028.signed.json``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
EXPECTED_SIGNED_SEQUENCE = 28
TEST_MODULES = (
    "backend/tests/services/visa_engine/test_seq28_pack.py",
    "backend/tests/services/visa_engine/test_interview_walk_census.py",
    "backend/tests/scripts/visa_engine/test_review_hold_inventory.py",
)


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
    print(f"observe_visa_seq28_signed: running {_shown(inventory_cmd)} (cwd=apps/backend-rag)")
    result = subprocess.run(
        inventory_cmd,
        cwd=BACKEND_RAG_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"observe_visa_seq28_signed: review_hold_inventory exited {result.returncode}")
        return result.returncode
    inventory = json.loads(result.stdout)
    print(
        f"observe_visa_seq28_signed: highest signed sequence={inventory['sequence']} "
        f"totals={json.dumps(inventory['totals'], sort_keys=True)}"
    )
    if inventory["sequence"] != EXPECTED_SIGNED_SEQUENCE:
        print(
            f"observe_visa_seq28_signed: highest signed pack is seq-{inventory['sequence']}, "
            f"not seq-{EXPECTED_SIGNED_SEQUENCE}"
        )
        return 1

    for module in TEST_MODULES:
        cmd = [interpreter, "-m", "pytest", module, "-p", "no:cacheprovider"]
        print(f"observe_visa_seq28_signed: running {_shown(cmd)} (cwd=apps/backend-rag)")
        rc = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, check=False).returncode
        if rc != 0:
            print(f"observe_visa_seq28_signed: {module} FAILED")
            return rc
    print("observe_visa_seq28_signed: inventory reads seq-28 and all three consumers green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
