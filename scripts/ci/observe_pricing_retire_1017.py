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
Molina survives everywhere. Second wave (same day): no catalogue row, mirror
row, price-list row or brochure sentence still carries an urgent-processing
note, and migration 328 clears the four CRM descriptions that did.

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

MIGRATION_NOTES = ROOT / (
    "apps/backend-rag/backend/db/migrations_v2/"
    "328_practice_types_clear_urgent_notes.sql"
)
BROCHURE_PDF = ROOT / "apps/mouth/public/static/brochure_balizero_en.pdf"
NOTE_ROWS = (
    ("other_reset_molina", "Plus 400k urgent"),
    ("other_mutation_passport", "Plus 350k urgent"),
    ("other_epo", "Plus 300k urgent"),
    ("other_erp", "Plus 500k urgent"),
)
# Rows whose description says "Including Urgent": the owner has not ruled on
# them, so migration 328 must not name them.
SPARED_CODES = ("visa_c7_music_art", "kitas_remote_worker_offshore")
# The surcharge note as it was written on every surface ("+ Rp 400.000 for
# urgent processing", "Plus 400k urgent") and the brochure sentence. An
# innocent mention of the word is not a hit.
URGENT_NOTE = re.compile(
    r"(?:\+\s*rp\s*[\d.,]+\s*k?\s*for\s+urgent"
    r"|plus\s*[\d.,]+\s*k?\s*urgent"
    r"|urgent handling is quoted separately)",
    re.IGNORECASE,
)
URGENT_NOTE_SQUEEZED = re.compile(
    r"(?:\+?rp[\d.,]+k?forurgent|plus[\d.,]+k?urgent|urgenthandlingisquotedseparately)",
    re.IGNORECASE,
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


def _iter_notes(node: object, path: str = "") -> "list[tuple[str, str]]":
    """Every `notes` string under `node`, at any depth (tax_accounting nests
    its rows one level deeper than the other categories)."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        note = node.get("notes")
        if isinstance(note, str):
            found.append((path or "<root>", note))
        for key, value in node.items():
            found.extend(_iter_notes(value, f"{path}/{key}" if path else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_iter_notes(value, f"{path}[{index}]"))
    return found


def _pdf_mentions_urgent(pdf_path: Path) -> str | None:
    """The surcharge sentence in the committed brochure PDF, if any. Needs
    pypdf (the brochure text is font-encoded, so a raw byte scan is blind):
    without it the check is announced as skipped, never silently passed;
    backend CI's test_brochure_price_parity reads the same PDF with pypdf.
    pypdf 6.12 splits words of this PDF ("urgen t han dlin g"), so the match
    runs on the text with every whitespace removed."""
    if not pdf_path.exists():
        return "<missing brochure PDF>"
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        print(
            "observe_pricing_retire_1017: NOTICE — pypdf unavailable, brochure PDF not read here"
        )
        return None
    text = " ".join(
        (page.extract_text() or "") for page in PdfReader(str(pdf_path)).pages
    )
    hit = URGENT_NOTE_SQUEEZED.search(re.sub(r"\s+", "", text))
    return hit.group(0) if hit else None


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

    for path, note in _iter_notes(canon):
        if URGENT_NOTE.search(note):
            _fail(f"canonical {path} still carries the urgent surcharge note")
    for path, note in _iter_notes(mirror):
        if URGENT_NOTE.search(note):
            _fail(f"mouth mirror {path} still carries the urgent surcharge note")
    if URGENT_NOTE.search(price_list):
        _fail("price list still carries the urgent surcharge note")

    brochure = BROCHURE.read_text(encoding="utf-8")
    if URGENT_NOTE.search(brochure):
        _fail("brochure template still says urgent handling is quoted separately")
    pdf_hit = _pdf_mentions_urgent(BROCHURE_PDF)
    if pdf_hit:
        _fail(f"committed brochure PDF still carries {pdf_hit!r}")
    if "PRICE_SIM" in brochure:
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

    notes_sql = MIGRATION_NOTES.read_text(encoding="utf-8")
    if "-- === ROLLBACK ===" not in notes_sql:
        _fail("migration 328 has no ROLLBACK marker (the runner refuses it)")
    notes_forward = "\n".join(
        line
        for line in notes_sql.split("-- === ROLLBACK ===")[0].splitlines()
        if not line.lstrip().startswith("--")
    )
    if "description = NULL" not in notes_forward:
        _fail("migration 328 forward section does not clear description")
    for code, text in NOTE_ROWS:
        if f"('{code}', '{text}')" not in notes_forward:
            _fail(f"migration 328 does not pair {code!r} with its surcharge text")
    for code in RETIRED_CODES + SPARED_CODES:
        if f"'{code}'" in notes_forward:
            _fail(f"migration 328 touches {code!r}, which it must leave alone")

    print("observe_pricing_retire_1017: retired rows of 2026-10-17 hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
