#!/usr/bin/env python3
"""observe_visa_seq26_e31_options.py — bites: observation for the seq-26 derivation lane.

# bites-observable — this script takes NO arguments: the commands and the program it
# runs are literals in this file, so nothing an invoker types can name a program to run,
# a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets). The only write is the
# derivation's output into a private temporary directory it removes afterwards.

The consumer is the evaluate path's pricing step, driven on the COMMITTED seq-26 source.
Two observations, each failing loud:

1. re-deriving seq-26 from seq-25 gives the committed file (RFC 8785 canonical bytes, so
   Prettier formatting is irrelevant);
2. on BOTH the committed and the re-derived pack, every one of the nine E31 products has
   exactly two options (365 days on its 1-year key, 730 days on the same variant's 2-year
   sibling), a top-level key equal to the first option, a 365 to 730 stay, and prices
   11000000 and 15000000 through the engine. This check is independent of the derivation,
   so a drift shared by the file and its re-derivation is still caught.
"""

# bites-observable — no arguments; one in-tree module and one literal program.

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"

PROGRAM = r"""
import json
import sys
from pathlib import Path

from backend.scripts.visa_engine.derive_seq26_e31_options import check_e31_options
from backend.services.visa_engine.bundle import canonicalize_json

derived = json.loads(Path(sys.argv[1]).read_text())
committed_path = Path("backend/services/visa_engine/contracts/packs/rulepack-prod-026.source.json")
committed = json.loads(committed_path.read_text())
assert canonicalize_json(derived) == canonicalize_json(committed), "re-derived seq-26 differs from the committed source"

catalogue = json.loads(Path("backend/data/bali_zero_official_prices_2026.json").read_text())
for name, pack in (("committed", committed), ("re-derived", derived)):
    problems = check_e31_options(pack, catalogue)
    assert not problems, f"{name}: {problems}"
print("nine E31 products: 365d on the 1-year key, 730d on the 2-year sibling, 11000000 and 15000000")
"""


def _backend_rag_python() -> str:
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    interpreter = _backend_rag_python()
    env = {"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"}
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "rulepack-prod-026.source.json"
        derive = subprocess.run(
            [
                interpreter,
                "-m",
                "backend.scripts.visa_engine.derive_seq26_e31_options",
                "--output",
                str(output),
            ],
            cwd=BACKEND_RAG_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if derive.returncode != 0:
            sys.stdout.write(f"observe_visa_seq26_e31_options: derivation FAILED\n{derive.stderr[-1500:]}\n")
            return derive.returncode or 1
        result = subprocess.run(
            [interpreter, "-c", PROGRAM, str(output)],
            cwd=BACKEND_RAG_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        sys.stdout.write(f"observe_visa_seq26_e31_options: FAILED\n{result.stderr[-1500:]}\n")
        return result.returncode
    sys.stdout.write(f"observe_visa_seq26_e31_options: {result.stdout.strip()}\n")
    sys.stdout.write(
        "observe_visa_seq26_e31_options: re-derived seq-26 equals the committed source "
        "and all nine E31 products price 365d at 11000000 and 730d at 15000000\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
