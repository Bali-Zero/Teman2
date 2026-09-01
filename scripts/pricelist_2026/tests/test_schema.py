"""Tests for the 2026 price list JSON schema validator."""
import json
import re
from pathlib import Path

import pytest

from scripts.pricelist_2026 import schema

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_prices.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


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


def test_canonical_contact_whatsapp_and_wa_link_share_the_same_digits():
    """Regression guard for the 2026-08-31 scar: `wa_link` drifted to a
    different phone number's digits (a team member's personal wa-mirror
    number) while `whatsapp` (the display text) was updated to the
    Meta-verified Bali Zero number. Because `schema.validate` only checks
    each field against `CANONICAL_CONTACT` by exact string match, a
    mismatch baked into `CANONICAL_CONTACT` itself was invisible to
    validation — both the dict and the shipped JSON agreed on the WRONG
    wa_link. This test checks the underlying invariant directly: the
    digits inside `whatsapp` (human-readable) and `wa_link` (wa.me href)
    must be the same phone number, independent of what either string is
    hand-typed to say.
    """
    contact = schema.CANONICAL_CONTACT
    assert _digits(contact["whatsapp"]) == _digits(contact["wa_link"]), (
        f"whatsapp digits {_digits(contact['whatsapp'])!r} != "
        f"wa_link digits {_digits(contact['wa_link'])!r}"
    )


def test_contact_wa_link_must_match_canonical():
    data = _load_fixture()
    data["metadata"]["contact"]["wa_link"] = "https://wa.me/628213454721"
    result = schema.validate(data)
    assert not result.ok
    assert any("wa_link" in e for e in result.errors)


def test_real_2026_json_whatsapp_and_wa_link_share_the_same_digits():
    """Same guard as above, run against the actual shipped JSON — the file
    `scripts/pricelist_2026/generate.py` reads by default and the one
    `docs/pricing/Bali_Zero_Price_List_2026.md` is rendered from. Catches
    a future edit that updates `whatsapp` without updating `wa_link` (or
    vice versa) directly in the JSON, bypassing `CANONICAL_CONTACT`
    entirely.
    """
    repo_root = Path(__file__).resolve().parents[3]
    real = repo_root / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
    if not real.exists():
        pytest.skip(f"real JSON not yet authored at {real}")
    data = json.loads(real.read_text())
    contact = data["metadata"]["contact"]
    assert _digits(contact["whatsapp"]) == _digits(contact["wa_link"]), (
        f"whatsapp digits {_digits(contact['whatsapp'])!r} != "
        f"wa_link digits {_digits(contact['wa_link'])!r}"
    )


def test_real_2026_json_validates():
    """Sanity check: the actual file we ship must validate.

    Path resolved relative to repo root (parents[3] = repo root from
    scripts/pricelist_2026/tests/test_schema.py) so the test runs
    correctly regardless of CWD.
    """
    repo_root = Path(__file__).resolve().parents[3]
    real = repo_root / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
    if not real.exists():
        pytest.skip(f"real JSON not yet authored at {real}")
    data = json.loads(real.read_text())
    result = schema.validate(data)
    assert result.ok, f"Real 2026 JSON failed validation: {result.errors}"
