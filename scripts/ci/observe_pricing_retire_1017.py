#!/usr/bin/env python3
# ruff: noqa: T201
# bites-observable: no arguments; reads fixed repo paths only, writes nothing.
"""Bites observer for the 2026-10-17 pricing retirement.

Zero retired the Urgent 1/2/3 Hari surcharges, the Driving License (SIM)
service and the Created Molina Express service on 2026-10-17. This observer
proves, on the checkout it runs in, that every repo-side surface agrees:
the canonical catalogue, the mouth mirror (what balizero.com/services/visa
renders), the price list, the brochure template and generator, and that
migration 327 retires exactly the five practice_types codes while Reset
Molina survives everywhere.

No arguments. Exit 0 and print the closing sentence only when every check
holds; any failure exits 1 and names it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
MIRROR = ROOT / "apps/mouth/data/bali-zero-prices.json"
PRICE_LIST = ROOT / "docs/pricing/Bali_Zero_Price_List_2026.md"
BROCHURE = ROOT / "apps/backend-rag/scripts/brochure/brochure_en.html"
BROCHURE_GEN = ROOT / "apps/backend-rag/scripts/generate_brochure.py"
MIGRATION = ROOT / (
    "apps/backend-rag/backend/db/migrations_v2/"
    "327_practice_types_retire_urgent_sim_molina_express.sql"
)

RETIRED_NAMES = (
    "Urgent 1 Hari",
    "Urgent 2 Hari",
    "Urgent 3 Hari",
    "Driving License",
    "Created Molina Express",
)
RETIRED_CODES = (
    "urgent_1_day",
    "urgent_2_days",
    "urgent_3_days",
    "other_driving_license",
    "other_create_molina_express",
)
KEPT_NAME = "Reset Molina"
KEPT_CODE = "other_reset_molina"


def _fail(msg: str) -> None:
    print(f"observe_pricing_retire_1017: FAIL — {msg}")
    sys.exit(1)


def main() -> int:
    canon = json.loads(CANON.read_text(encoding="utf-8"))["services"]
    if "urgent_processing" in canon:
        _fail("urgent_processing category still in the canonical catalogue")
    other = canon["other_process"]
    for name in ("Driving License", "Created Molina Express"):
        if name in other:
            _fail(f"{name!r} still in canonical other_process")
    if KEPT_NAME not in other:
        _fail(f"{KEPT_NAME!r} missing from canonical other_process")

    mirror = json.loads(MIRROR.read_text(encoding="utf-8"))["services_by_category"]
    if "urgent_processing" in mirror:
        _fail("urgent_processing category still in the mouth mirror")
    for name in ("Driving License", "Created Molina Express"):
        if name in mirror.get("other_process", {}):
            _fail(f"{name!r} still in the mouth mirror")
    if KEPT_NAME not in mirror.get("other_process", {}):
        _fail(f"{KEPT_NAME!r} missing from the mouth mirror")

    pattern = re.compile(r"\*\*(" + "|".join(map(re.escape, RETIRED_NAMES)) + r")\*\*")
    price_list = PRICE_LIST.read_text(encoding="utf-8")
    hit = pattern.search(price_list)
    if hit:
        _fail(f"price list still carries the row {hit.group(1)!r}")
    if "Urgent Processing" in price_list:
        _fail("price list still carries the Urgent Processing section")
    if f"**{KEPT_NAME}**" not in price_list:
        _fail(f"price list lost the {KEPT_NAME!r} row")

    if "PRICE_SIM" in BROCHURE.read_text(encoding="utf-8"):
        _fail("brochure template still carries PRICE_SIM")
    if "PRICE_SIM" in BROCHURE_GEN.read_text(encoding="utf-8"):
        _fail("brochure generator still maps PRICE_SIM")

    sql = MIGRATION.read_text(encoding="utf-8")
    forward = "\n".join(
        line
        for line in sql.split("-- === ROLLBACK ===")[0].splitlines()
        if not line.lstrip().startswith("--")
    )
    if "is_active = false" not in forward:
        _fail("migration 327 forward section does not set is_active = false")
    for code in RETIRED_CODES:
        if f"'{code}'" not in forward:
            _fail(f"migration 327 does not name {code!r}")
    if f"'{KEPT_CODE}'" in forward:
        _fail(f"migration 327 names the kept code {KEPT_CODE!r}")

    print("observe_pricing_retire_1017: retired rows of 2026-10-17 hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
