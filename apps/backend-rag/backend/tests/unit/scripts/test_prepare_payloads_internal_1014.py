"""Guilt + innocence tests for scripts/prepare_payloads.py internal-row filtering (2026-10-14).

Verifies:
1. Guilt (synthetic): flatten_services on a tiny synthetic catalogue containing internal
   rows ("internal": true) and public rows returns only the public rows (both top-level
   categories and 3-level sub-blocks).
2. Guilt (real catalogue): none of the 3 internal Retirement rows (read dynamically from
   bali_zero_official_prices_2026.json) appears in flatten_services(real_catalog), while
   all canonical E33F Second Home Senior rows do appear.
3. Innocence (real catalogue): every non-internal service row in the real catalogue is
   preserved (len(flatten_services(real_catalog)) equals the count of non-internal rows
   computed independently by walking the JSON).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_RAG_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = BACKEND_RAG_ROOT / "scripts" / "prepare_payloads.py"
CATALOG_PATH = BACKEND_RAG_ROOT / "backend" / "data" / "bali_zero_official_prices_2026.json"

_had_openai_key = "OPENAI_API_KEY" in os.environ
if not _had_openai_key:
    os.environ["OPENAI_API_KEY"] = "test-placeholder-key-not-called"
try:
    _SPEC = importlib.util.spec_from_file_location(
        "prepare_payloads_internal_1014",
        SCRIPT_PATH,
    )
    assert _SPEC and _SPEC.loader
    prepare_mod = importlib.util.module_from_spec(_SPEC)
    sys.modules[_SPEC.name] = prepare_mod
    _SPEC.loader.exec_module(prepare_mod)
finally:
    if not _had_openai_key:
        os.environ.pop("OPENAI_API_KEY", None)


def _walk_catalog_rows(
    catalog: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Independently walk the JSON catalogue and return (public_names, internal_names)."""
    public_names: list[str] = []
    internal_names: list[str] = []
    services = catalog.get("services", {})

    def _is_entry(obj: Any) -> bool:
        return isinstance(obj, dict) and ("price" in obj or "tier_range" in obj)

    for _category, category_items in services.items():
        if not isinstance(category_items, dict):
            continue
        for item_name, item_data in category_items.items():
            if not isinstance(item_data, dict):
                continue
            if (
                not _is_entry(item_data)
                and item_data
                and all(_is_entry(v) for v in item_data.values())
            ):
                for sub_name, sub_entry in item_data.items():
                    if sub_entry.get("internal") is True:
                        internal_names.append(sub_name)
                    else:
                        public_names.append(sub_name)
                continue
            if item_data.get("internal") is True:
                internal_names.append(item_name)
            else:
                public_names.append(item_name)

    return public_names, internal_names


def test_guilt_synthetic_catalog_skips_internal_rows_and_keeps_public() -> None:
    synthetic_catalog: dict[str, Any] = {
        "metadata": {"contact": {"whatsapp": "+628113990045"}},
        "services": {
            "kitas_permits": {
                "Retirement (Offshore)": {
                    "price": "14.000.000 IDR",
                    "internal": True,
                    "notes": "Internal-only row.",
                },
                "E33F Second Home Senior (1 Year, Offshore)": {
                    "price": "14.000.000 IDR",
                    "notes": "Public E33F row.",
                },
            },
            "tax_accounting": {
                "monthly_tax_basic": {
                    "Internal Tax Tier": {
                        "price": "1.000.000 IDR",
                        "internal": True,
                    },
                    "Public Tax Tier": {
                        "price": "1.500.000 IDR",
                    },
                }
            },
        },
    }

    flattened = prepare_mod.flatten_services(synthetic_catalog)
    names = [item["name"] for item in flattened]

    assert names == [
        "E33F Second Home Senior (1 Year, Offshore)",
        "Public Tax Tier",
    ]
    assert "Retirement (Offshore)" not in names
    assert "Internal Tax Tier" not in names


def test_guilt_real_catalog_excludes_all_internal_rows_and_includes_e33f() -> None:
    real_catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    _public_names, internal_names = _walk_catalog_rows(real_catalog)

    assert len(internal_names) == 3, f"Expected 3 internal rows in JSON, got {internal_names}"

    flattened = prepare_mod.flatten_services(real_catalog)
    flattened_names = {item["name"] for item in flattened}

    for internal_name in internal_names:
        assert internal_name not in flattened_names, (
            f"Internal row {internal_name!r} leaked into prepare_payloads.flatten_services"
        )

    expected_e33f_names = {
        name for name in _public_names if name.startswith("E33F Second Home Senior")
    }
    assert len(expected_e33f_names) >= 3
    for e33f_name in expected_e33f_names:
        assert e33f_name in flattened_names


def test_innocence_real_catalog_keeps_all_public_rows() -> None:
    real_catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    expected_public_names, internal_names = _walk_catalog_rows(real_catalog)

    flattened = prepare_mod.flatten_services(real_catalog)
    flattened_names = [item["name"] for item in flattened]

    assert len(flattened) == len(expected_public_names)
    assert flattened_names == expected_public_names
    assert set(flattened_names).isdisjoint(internal_names)
