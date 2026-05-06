"""Tests for the 2026 price list JSON schema validator."""
import json
from pathlib import Path

import pytest

from scripts.pricelist_2026 import schema

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_prices.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def test_valid_fixture_passes():
    data = _load_fixture()
    result = schema.validate(data)
    assert result.ok, f"Expected valid fixture to pass, got errors: {result.errors}"


def test_missing_top_level_version_fails():
    data = _load_fixture()
    del data["version"]
    result = schema.validate(data)
    assert not result.ok
    assert any("version" in e for e in result.errors)


def test_contact_whatsapp_must_match_canonical():
    data = _load_fixture()
    data["metadata"]["contact"]["whatsapp"] = "+62 813 3805 1876"
    result = schema.validate(data)
    assert not result.ok
    assert any("whatsapp" in e for e in result.errors)


def test_service_with_neither_price_nor_tier_range_fails():
    data = _load_fixture()
    data["services"]["single_entry_visas"]["C1 Tourism"]["price"] = ""
    data["services"]["single_entry_visas"]["C1 Tourism"]["tier_range"] = None
    result = schema.validate(data)
    assert not result.ok
    assert any("must have price or tier_range" in e for e in result.errors)


def test_service_with_both_price_and_tier_range_fails():
    data = _load_fixture()
    svc = data["services"]["single_entry_visas"]["C1 Tourism"]
    svc["price"] = "2.300.000 IDR"
    svc["tier_range"] = ["1 IDR", "2 IDR"]
    result = schema.validate(data)
    assert not result.ok
    assert any("not both" in e for e in result.errors)


def test_service_missing_description_en_fails():
    data = _load_fixture()
    del data["services"]["single_entry_visas"]["C1 Tourism"]["description_en"]
    result = schema.validate(data)
    assert not result.ok
    assert any("description_en" in e for e in result.errors)


def test_service_missing_icon_id_fails():
    data = _load_fixture()
    del data["services"]["single_entry_visas"]["C1 Tourism"]["icon_id"]
    result = schema.validate(data)
    assert not result.ok
    assert any("icon_id" in e for e in result.errors)


def test_tier_range_must_be_two_strings():
    data = _load_fixture()
    data["services"]["tax_accounting"]["monthly_tax_basic"]["Tier 0-50"]["tier_range"] = ["only one"]
    result = schema.validate(data)
    assert not result.ok
    assert any("tier_range" in e for e in result.errors)


def test_real_2026_json_validates():
    """Sanity check: the actual file we ship must validate."""
    real = Path("apps/backend-rag/backend/data/bali_zero_official_prices_2026.json")
    if not real.exists():
        pytest.skip("real JSON not yet authored")
    data = json.loads(real.read_text())
    result = schema.validate(data)
    assert result.ok, f"Real 2026 JSON failed validation: {result.errors}"
