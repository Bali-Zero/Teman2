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
2. through the engine, the E31B product prices 365 days at the catalogue's 1-year
   Offshore row and 730 days at its 2-year Offshore row.
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
from datetime import datetime, timezone
from pathlib import Path

from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.models import VisaProductVersion
from backend.services.visa_engine.pricing_adapter import resolve_candidate_pricing

derived = json.loads(Path(sys.argv[1]).read_text())
committed_path = Path("backend/services/visa_engine/contracts/packs/rulepack-prod-026.source.json")
committed = json.loads(committed_path.read_text())
assert canonicalize_json(derived) == canonicalize_json(committed), "re-derived seq-26 differs from the committed source"

catalogue = json.loads(Path("backend/data/bali_zero_official_prices_2026.json").read_text())
rows = catalogue["services"]["kitas_permits"]
product = VisaProductVersion.model_validate(
    next(p for p in committed["products"] if p["product_code"] == "E31B")
)


class Catalog:
    loaded = True

    def get_service_by_key(self, key):
        row = rows.get(key)
        return None if row is None else {**row, "category": "kitas_permits"}

    def get_all_prices(self):
        return {"version": catalogue["version"], "metadata": catalogue["metadata"], "services": rows}


def amount(stay_days):
    return resolve_candidate_pricing(
        product,
        pricing_catalog=Catalog(),
        evaluated_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        stay_days=stay_days,
    ).amount


assert amount(365) == 11_000_000, amount(365)
assert amount(730) == 15_000_000, amount(730)
assert amount(1095) == 15_000_000, amount(1095)
print(f"E31B 365d={amount(365)} 730d={amount(730)} 1095d={amount(1095)}")
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
    sys.stdout.write("observe_visa_seq26_e31_options: re-derived seq-26 equals the committed source and E31B prices 365d at 11000000 and 730d at 15000000\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
