"""Tests for Zero's 2026-10-17 pricing catalogue decisions (guilt and innocence).

Alcohol licences are priced by class (A 4.000.000, B+C 10.000.000, A+B+C 12.000.000 IDR);
SLHS, Halal Certificate and PIRT are quote-only; standalone MERP and the ACC rows are gone
(the KITAP + MERP bundles stay). The six new rows live in ``company_services``, in the
canonical catalogue and in the generated mirror alike.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = (
    ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "data"
    / "bali_zero_official_prices_2026.json"
)
MIRROR_PATH = ROOT / "apps" / "mouth" / "data" / "bali-zero-prices.json"
VISA_ORACLE_PATH = (
    ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_oracle"
    / "visa_oracle_service.py"
)
SYNC_SCRIPT_PATH = ROOT / "scripts" / "sync_pricing_collection_prices.py"

QUOTE_ROW = "Akta Perubahan (Revision Company)"
EXPECTED_PRICES = {
    "Alcohol License — Golongan A": "4.000.000 IDR",
    "Alcohol License — Golongan B + C": "10.000.000 IDR",
    "Alcohol License — Golongan A + B + C": "12.000.000 IDR",
}
QUOTE_NAMES = (
    "SLHS (Sertifikat Laik Higiene Sanitasi)",
    "Halal Certificate",
    "PIRT (Home Industry Food)",
)
NEW_NAMES = (*EXPECTED_PRICES, *QUOTE_NAMES)
RETIRED_VISA_METADATA_KEYS = ("MERP 1 Year", "MERP 2 Year")

_SPEC = importlib.util.spec_from_file_location(
    "sync_pricing_collection_prices_catalogue_1017", SYNC_SCRIPT_PATH
)
assert _SPEC and _SPEC.loader
sync_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sync_mod
_SPEC.loader.exec_module(sync_mod)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_rows() -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield (category, key, row) for every canonical row, internal ones included."""
    for category, payload in _load_json(CANONICAL_PATH)["services"].items():
        if category == "tax_accounting":
            for block, rows in payload.items():
                for key, row in rows.items():
                    yield f"{category}.{block}", key, row
            continue
        for key, row in payload.items():
            yield category, key, row


def _mirror_rows() -> Iterator[tuple[str, str, dict[str, Any]]]:
    mirror = _load_json(MIRROR_PATH)
    for category, rows in mirror["services_by_category"].items():
        for key, row in rows.items():
            yield category, key, row


def _row_names(
    rows: Iterator[tuple[str, str, dict[str, Any]]],
) -> list[tuple[str, str]]:
    return [(category, row.get("name", key)) for category, key, row in rows]


def _standalone_merp_or_acc(names: list[str]) -> list[str]:
    """Names that are a standalone MERP (no KITAP) or an ``ACC `` row."""
    return [
        name
        for name in names
        if ("MERP" in name.upper() and "KITAP" not in name.upper())
        or name.startswith("ACC ")
    ]


def _visa_metadata_keys() -> set[str]:
    tree = ast.parse(VISA_ORACLE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "VISA_METADATA":
            assert isinstance(node.value, ast.Dict)
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    raise AssertionError("VISA_METADATA not found")


# 1. GUILT: exact names, prices, single occurrence, right category
@pytest.mark.parametrize(("name", "price"), sorted(EXPECTED_PRICES.items()))
def test_alcohol_rows_exist_once_in_company_services_with_exact_price(name, price):
    hits = [category for category, n in _row_names(_canonical_rows()) if n == name]
    assert hits == ["company_services"]
    row = _load_json(CANONICAL_PATH)["services"]["company_services"][name]
    assert row["name"] == name
    assert row["price"] == price  # exact equality: a wrong price must fail here
    assert row["tier_range"] is None


def test_alcohol_prices_are_not_swapped_or_rounded():
    company = _load_json(CANONICAL_PATH)["services"]["company_services"]
    prices = {name: company[name]["price"] for name in EXPECTED_PRICES}
    assert prices == {
        "Alcohol License — Golongan A": "4.000.000 IDR",
        "Alcohol License — Golongan B + C": "10.000.000 IDR",
        "Alcohol License — Golongan A + B + C": "12.000.000 IDR",
    }
    assert len(set(prices.values())) == 3


@pytest.mark.parametrize("name", QUOTE_NAMES)
def test_quote_rows_exist_once_and_carry_the_akta_perubahan_price(name):
    company = _load_json(CANONICAL_PATH)["services"]["company_services"]
    assert [n for _c, n in _row_names(_canonical_rows()) if n == name] == [name]
    assert name in company
    assert (
        company[name]["price"]
        == company[QUOTE_ROW]["price"]
        == "Depend (Contact for quote)"
    )
    assert company[name]["tier_range"] is None


# 2. Catalogue and mirror agree
@pytest.mark.parametrize("name", NEW_NAMES)
def test_mirror_agrees_with_canonical_on_the_new_rows(name):
    canonical = _load_json(CANONICAL_PATH)["services"]["company_services"][name]
    mirror = _load_json(MIRROR_PATH)["services_by_category"]["company_services"][name]
    assert mirror["category"] == "company_services"
    assert mirror["name"] == canonical["name"] == name
    assert mirror["price"] == canonical["price"]
    assert mirror["description_en"] == canonical["description_en"]
    assert mirror["icon_id"] == canonical["icon_id"]
    assert [n for _c, n in _row_names(_mirror_rows()) if n == name] == [name]


# 3. Standalone MERP and ACC rows are gone everywhere (bundles stay)
def test_no_standalone_merp_or_acc_row_in_catalogue_or_mirror():
    for rows in (_canonical_rows(), _mirror_rows()):
        names = [name for _category, name in _row_names(rows)]
        assert _standalone_merp_or_acc(names) == []


def test_merp_acc_predicate_convicts_offenders_and_spares_bundles():
    assert _standalone_merp_or_acc(["MERP 1 Year", "merp 2 year"]) == [
        "MERP 1 Year",
        "merp 2 year",
    ]
    assert _standalone_merp_or_acc(["ACC Mutation", "ACC Boarding Pass"]) == [
        "ACC Mutation",
        "ACC Boarding Pass",
    ]
    assert (
        _standalone_merp_or_acc(["Investor KITAP + MERP", "Dependent KITAP MERP"]) == []
    )


def test_kitap_merp_bundles_stay_in_the_catalogue():
    names = {name for _category, name in _row_names(_canonical_rows())}
    assert {
        "Investor KITAP + MERP",
        "Retirement KITAP + MERP",
        "Dependent KITAP + MERP",
    } <= names


def test_visa_metadata_has_no_standalone_merp_key():
    keys = _visa_metadata_keys()
    for retired in RETIRED_VISA_METADATA_KEYS:
        assert retired not in keys
    assert "Investor KITAP + MERP" in keys


# 4. The pricing collection can create a point for each new row
def test_plan_creates_yields_one_clean_create_per_new_row():
    catalog = _load_json(CANONICAL_PATH)
    creates, refusals = sync_mod.plan_creates([], catalog, "2026-10-17")
    assert refusals == []
    by_name = {c["name"]: c for c in creates}
    for name in NEW_NAMES:
        assert name in by_name
        payload = by_name[name]["payload"]
        assert payload["category"] == "company_services"
        assert payload["text"].count(payload["price"]) == 1
    for name, price in EXPECTED_PRICES.items():
        assert by_name[name]["payload"]["price"] == price
    assert len([c for c in creates if c["name"] in NEW_NAMES]) == len(NEW_NAMES)
