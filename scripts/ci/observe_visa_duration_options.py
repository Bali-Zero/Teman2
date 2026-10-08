#!/usr/bin/env python3
"""observe_visa_duration_options.py — bites: observation for the duration-options engine PR.

# bites-observable — this script takes NO arguments: the program it runs is a
# literal string in this file, so nothing an invoker types can name a program to
# run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the evaluate path's pricing step. The observation takes the signed
seq-25 E31B product, gives it a 365 and a 730 duration option, resolves both
against the REAL official price catalogue file, and asserts that the 730 option
resolves the catalogue's "Dependent 2 Years (Offshore)" row and never the 1-year
row, that a 36-month wish still gets the 730 option, and that a product without
options is untouched. Exit 0 only if every assertion holds.
"""

# bites-observable — no arguments; one in-tree interpreter, one literal program.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"

PROGRAM = r"""
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.services.visa_engine.models import VisaProductVersion
from backend.services.visa_engine.pricing_adapter import (
    resolve_candidate_pricing,
    select_duration_option,
)

root = Path("backend")
pack = json.loads(
    (root / "services/visa_engine/contracts/packs/rulepack-prod-025.source.json").read_text()
)
raw = next(p for p in pack["products"] if p["product_code"] == "E31B")
catalogue = json.loads((root / "data/bali_zero_official_prices_2026.json").read_text())
rows = catalogue["services"]["kitas_permits"]

one = {"category": "kitas_permits", "item_key": "Dependent 1 Year (Offshore)"}
two = {"category": "kitas_permits", "item_key": "Dependent 2 Years (Offshore)"}
assert raw["pricing_key"] == one, raw["pricing_key"]
raw["stay_policy"] = {**raw["stay_policy"], "maximum_days": 730}
raw["duration_options"] = [
    {"days": 365, "pricing_key": one},
    {"days": 730, "pricing_key": two},
]
product = VisaProductVersion.model_validate(raw)


class Catalog:
    loaded = True

    def get_service_by_key(self, key):
        row = rows.get(key)
        return None if row is None else {**row, "category": "kitas_permits"}

    def get_all_prices(self):
        return {"version": catalogue["version"], "metadata": catalogue["metadata"], "services": rows}


def idr(label):
    return int(rows[label]["price"].split()[0].replace(".", ""))


def amount(stay_days):
    return resolve_candidate_pricing(
        product,
        pricing_catalog=Catalog(),
        evaluated_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        stay_days=stay_days,
    ).amount


assert amount(365) == idr(one["item_key"]), amount(365)
assert amount(730) == idr(two["item_key"]), amount(730)
assert amount(730) != amount(365)
assert amount(1095) == idr(two["item_key"])
assert amount(None) == idr(one["item_key"])
assert select_duration_option(product, 730).days == 730
plain = VisaProductVersion.model_validate({**raw, "duration_options": None})
assert select_duration_option(plain, 730) is None
print(f"1y={amount(365)} 2y={amount(730)} 36m={amount(1095)} unknown={amount(None)}")
"""


def _backend_rag_python() -> str:
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    env = {"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [_backend_rag_python(), "-c", PROGRAM],
        cwd=BACKEND_RAG_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"observe_visa_duration_options: FAILED\n{result.stderr[-1500:]}")
        return result.returncode
    print(f"observe_visa_duration_options: {result.stdout.strip()}")
    print("observe_visa_duration_options: the 730-day option resolves the 2-year catalogue row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
