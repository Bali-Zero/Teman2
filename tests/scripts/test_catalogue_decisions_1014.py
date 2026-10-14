"""Tests for Zero's 2026-10-14 pricing catalogue decisions (guilt and innocence)."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = (
    ROOT / "apps" / "backend-rag" / "backend" / "data" / "bali_zero_official_prices_2026.json"
)
MIRROR_PATH = ROOT / "apps" / "mouth" / "data" / "bali-zero-prices.json"
BOOK_DATA_PATH = ROOT / "apps" / "mouth" / "src" / "components" / "book" / "book-data.ts"
RENEWAL_RULES_PATH = (
    ROOT / "apps" / "backend-rag" / "backend" / "services" / "compliance" / "renewal_rules.py"
)
SYNC_SCRIPT_PATH = ROOT / "scripts" / "sync_frontend_prices.py"
FILES = [CANONICAL_PATH, MIRROR_PATH]

RETIREMENT_ROWS_EXPECTED_PRICES = {
    "Retirement (Altus/Onshore)": "16.000.000 IDR",
    "Retirement (Offshore)": "14.000.000 IDR",
    "Retirement (Extend)": "10.000.000 IDR",
}
RETIREMENT_KEYS = tuple(RETIREMENT_ROWS_EXPECTED_PRICES)

E33F_KEYS = (
    "E33F Second Home Senior (1 Year, Offshore)",
    "E33F Second Home Senior (1 Year, Altus/Onshore)",
    "E33F Second Home Senior (Extend)",
)
NON_E33F_E33_KEYS = (
    "E33 Second Home (5 Years)",
    "E33E Second Home Senior (5 Years)",
    "E33E Second Home Senior (Extend)",
)
SPONSOR_SENTENCE = "A sponsor (penjamin) is required; Bali Zero can act as one."
SPONSOR_SUFFIX = f" {SPONSOR_SENTENCE}"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _kitas_permits(data: dict) -> dict[str, dict]:
    if "services" in data:
        return data["services"]["kitas_permits"]
    return data["services_by_category"]["kitas_permits"]


def _check_mirror_has_no_generic_retirement_rows(mirror_data: dict) -> list[str]:
    """Return any generic Retirement keys present in the public mirror kitas_permits."""
    kitas = mirror_data.get("services_by_category", {}).get("kitas_permits", {})
    return [key for key in RETIREMENT_KEYS if key in kitas]


def _check_e33f_sponsor_sentence(description_en: str) -> list[str]:
    """Return violations if description_en does not end with SPONSOR_SUFFIX exactly once."""
    issues: list[str] = []
    count = description_en.count(SPONSOR_SENTENCE)
    if count != 1:
        issues.append(f"expected count 1, got {count}")
    if not description_en.endswith(SPONSOR_SUFFIX):
        issues.append("missing exact trailing sponsor suffix")
    return issues


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_frontend_prices", SYNC_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 1. GUILT mirror
def test_mirror_has_no_generic_retirement_keys_and_convicts_mutation():
    mirror = _load_json(MIRROR_PATH)
    assert _check_mirror_has_no_generic_retirement_rows(mirror) == []

    for key in RETIREMENT_KEYS:
        mutated = copy.deepcopy(mirror)
        mutated["services_by_category"]["kitas_permits"][key] = {
            "category": "kitas_permits",
            "key": key,
            "name": key,
            "price": RETIREMENT_ROWS_EXPECTED_PRICES[key],
        }
        assert _check_mirror_has_no_generic_retirement_rows(mutated) == [key]


# 2. INNOCENCE backend
def test_canonical_and_backend_consumers_keep_resolving_retirement_rows():
    canonical = _load_json(CANONICAL_PATH)
    kitas = canonical["services"]["kitas_permits"]
    for key, expected_price in RETIREMENT_ROWS_EXPECTED_PRICES.items():
        assert key in kitas
        row = kitas[key]
        assert row.get("internal") is True
        assert row["price"] == expected_price

    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.services.pricing.pricing_service import PricingService
    from backend.services.visa_engine.models import PricingKey
    from backend.services.visa_engine.pricing_adapter import resolve_pricing_key

    service = PricingService()
    assert service.loaded
    all_prices = service.get_all_prices()
    served_kitas = all_prices["services"]["kitas_permits"]
    for key, expected_price in RETIREMENT_ROWS_EXPECTED_PRICES.items():
        assert key in served_kitas
        assert served_kitas[key]["price"] == expected_price
        by_key = service.get_service_by_key(key)
        assert by_key is not None
        assert by_key["price"] == expected_price
        resolution = resolve_pricing_key(
            PricingKey(category="kitas_permits", item_key=key),
            pricing_catalog=service,
            evaluated_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
        )
        assert resolution.status == "AVAILABLE"

    renewal_rules_source = RENEWAL_RULES_PATH.read_text(encoding="utf-8")
    assert "Retirement (Extend)" in renewal_rules_source


# 3. /book retirement card
def test_book_retirement_card_points_to_e33f_offshore_with_same_price():
    book_text = BOOK_DATA_PATH.read_text(encoding="utf-8")
    normalized_book_text = re.sub(r"\s+", " ", book_text)
    normalized_book_text = re.sub(r",\s*\)", ")", normalized_book_text)
    normalized_book_text = re.sub(r"\(\s+", "(", normalized_book_text)
    target_call = (
        'pricingBackedVisaService("kitas_permits", '
        '"E33F Second Home Senior (1 Year, Offshore)")'
    )
    assert target_call in normalized_book_text
    assert '"Retirement (Offshore)"' not in book_text

    canonical = _load_json(CANONICAL_PATH)
    mirror = _load_json(MIRROR_PATH)
    e33f_key = "E33F Second Home Senior (1 Year, Offshore)"
    assert e33f_key in mirror["services_by_category"]["kitas_permits"]
    mirror_e33f_price = mirror["services_by_category"]["kitas_permits"][e33f_key]["price"]
    canonical_retirement_price = canonical["services"]["kitas_permits"][
        "Retirement (Offshore)"
    ]["price"]
    assert mirror_e33f_price == canonical_retirement_price == "14.000.000 IDR"


# 4. Sponsor sentence
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("key", E33F_KEYS)
def test_e33f_rows_carry_sponsor_sentence_once_at_end_and_convict_doubled(path, key):
    kitas = _kitas_permits(_load_json(path))
    desc = kitas[key]["description_en"]
    assert _check_e33f_sponsor_sentence(desc) == []

    doubled = desc + SPONSOR_SUFFIX
    assert _check_e33f_sponsor_sentence(doubled) != []


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("key", NON_E33F_E33_KEYS)
def test_non_e33f_e33_rows_do_not_contain_sponsor_sentence(path, key):
    kitas = _kitas_permits(_load_json(path))
    desc = kitas[key]["description_en"]
    assert SPONSOR_SENTENCE not in desc
    assert "penjamin" not in desc.lower()


# 5. Sync script
def test_sync_script_omits_internal_rows_in_build_payload_and_iter_service_rows():
    sync_mod = _load_sync_module()
    payload = sync_mod.build_payload()
    mirror_kitas = payload["services_by_category"]["kitas_permits"]
    for key in RETIREMENT_KEYS:
        assert key not in mirror_kitas
    for category_rows in payload["services_by_category"].values():
        for row in category_rows.values():
            assert not row.get("internal")

    synthetic_services = {
        "kitas_permits": {
            "Internal Row": {
                "name": "Internal Row",
                "internal": True,
                "price": "10.000.000 IDR",
            },
            "Normal Row": {
                "name": "Normal Row",
                "price": "14.000.000 IDR",
            },
        }
    }
    yielded = list(sync_mod._iter_service_rows(synthetic_services))
    assert len(yielded) == 1
    category, key, row = yielded[0]
    assert category == "kitas_permits"
    assert key == "Normal Row"
    assert row["name"] == "Normal Row"
