"""Follow-ups from the independent gate of the 2026-10-17 licences PR (#8629).

* the mirror's legacy ``company_services`` map is keyed by ``icon_id`` and carries only the
  ``company-*`` convention; rows sharing another icon used to overwrite each other silently;
* Golongan C is "above 20% up to 55%" (Perpres 74/2013 Pasal 3);
* the alcohol rows answer an Indonesian query through the catalogue's ``keywords`` convention.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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
SYNC_PATH = ROOT / "scripts" / "sync_frontend_prices.py"

ALCOHOL_NAMES = {
    "Alcohol License — Golongan A",
    "Alcohol License — Golongan B + C",
    "Alcohol License — Golongan A + B + C",
}
C_BAND = "Golongan C (above 20% up to 55% alcohol)"

_SPEC = importlib.util.spec_from_file_location(
    "sync_frontend_prices_followup_1017", SYNC_PATH
)
assert _SPEC and _SPEC.loader
sync_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sync_mod
_SPEC.loader.exec_module(sync_mod)


def _company_rows() -> dict:
    return json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))["services"][
        "company_services"
    ]


def test_golongan_c_band_is_stated_with_its_upper_bound():
    row = _company_rows()["Alcohol License — Golongan B + C"]
    assert C_BAND in row["description_en"]
    mirror = json.loads(MIRROR_PATH.read_text(encoding="utf-8"))
    mirrored = mirror["services_by_category"]["company_services"][
        "Alcohol License — Golongan B + C"
    ]
    assert C_BAND in mirrored["description_en"]


def test_no_company_row_states_an_open_ended_golongan_c():
    for row in _company_rows().values():
        assert "(above 20%)" not in row.get("description_en", "")


def test_mirror_legacy_company_map_has_only_company_icons():
    legacy = json.loads(MIRROR_PATH.read_text(encoding="utf-8"))["company_services"]
    assert legacy
    assert all(key.startswith("company-") for key in legacy)
    assert all(row["icon_id"] == key for key, row in legacy.items())
    # the mouth readers' keys are still there
    assert {"company-pma", "company-virtual"} <= set(legacy)


def test_legacy_builder_skips_shared_non_company_icons():
    rows = {
        "A": {"name": "A", "price": "1", "icon_id": "other-domicile"},
        "B": {"name": "B", "price": "2", "icon_id": "other-domicile"},
        "C": {"name": "C", "price": "3", "icon_id": "company-x"},
        "D": {"name": "D", "price": "4"},
    }
    assert list(sync_mod.build_legacy_company_services(rows)) == ["company-x"]


def test_legacy_builder_raises_on_duplicate_company_icon():
    rows = {
        "A": {"name": "A", "price": "1", "icon_id": "company-x"},
        "B": {"name": "B", "price": "2", "icon_id": "company-x"},
    }
    with pytest.raises(ValueError, match="company-x"):
        sync_mod.build_legacy_company_services(rows)


@pytest.fixture(scope="module")
def pricing_service():
    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.services.pricing.pricing_service import PricingService

    service = PricingService()
    assert service.loaded
    return service


def _found_names(result: dict) -> set[str]:
    found = result.get("results", {}).get("company_services", {})
    return {item.get("name") for item in found.values()}


@pytest.mark.parametrize(
    "query",
    ["izin minuman beralkohol", "harga izin minuman beralkohol", "alcohol license"],
)
def test_search_finds_all_three_alcohol_rows(pricing_service, query):
    assert ALCOHOL_NAMES <= _found_names(pricing_service.search_service(query))
