"""The C1 and C6 price rows say what the official imigrasi.go.id pages say.

C1  https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C1  (Visa Kunjungan Wisata)
C6  https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C6  (Visa Kunjungan Kegiatan Sosial)

Both pages: first stay up to 60 days counted from arrival, extendable to a maximum of 180 days,
visa valid 90 days from issue (validity and stay differ). The C1 page allows MICE, business
discussions, negotiations and signing, and site visits; the C6 page allows tourism and visiting
friends and family. Both prohibit selling goods or services and receiving pay.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "apps" / "backend-rag" / "backend" / "data" / "bali_zero_official_prices_2026.json",
    ROOT / "apps" / "mouth" / "data" / "bali-zero-prices.json",
]
PACKS = ROOT / "apps" / "backend-rag" / "backend" / "services" / "visa_engine" / "contracts" / "packs"
PRICE_LIST_MD = ROOT / "docs" / "pricing" / "Bali_Zero_Price_List_2026.md"
C1 = "C1 Tourism"
C6 = "C6 Social Activity"
PRICES = {C1: "2.300.000 IDR", C6: "2.000.000 IDR"}
# The neighbouring rows are not part of this change: frozen as shipped.
FROZEN = {
    "C1 Tourism — Extension (+60 days)": "Onshore extension of the C1 Tourism visa for an additional 60 days, processed at Indonesian immigration.",
    "C2 Business": "Business visa, single entry, valid 60 days. Suited to business meetings, negotiations and non-employment activities.",
}
STAY_AND_VALIDITY = "first stay up to 60 days, extendable to 180 days in total; the visa is valid 90 days from issue"


def _rows(data, name: str) -> list[dict]:
    found: list[dict] = []
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("name") == name:
                found.append(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def _one(data, name: str) -> dict:
    rows = _rows(data, name)
    assert len(rows) == 1, (name, len(rows))
    return rows[0]


def _text(row: dict) -> str:
    return " ".join(row["description_en"].lower().split())


def _files_data():
    return [json.loads(p.read_text(encoding="utf-8")) for p in FILES]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
def test_c1_allows_what_the_page_allows_and_drops_the_business_ban(path):
    row = _one(json.loads(path.read_text(encoding="utf-8")), C1)
    text = _text(row)
    assert "cannot be used" not in text
    assert "business activities" not in text
    assert STAY_AND_VALIDITY in text
    for allowed in ("tourism", "meetings, incentives, conferences and exhibitions", "business discussions, negotiations and signing", "site visits"):
        assert allowed in text, allowed
    assert "selling goods or services, receiving pay and speaking at events are prohibited" in text
    assert row["price"] == PRICES[C1]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
def test_c6_drops_the_business_meetings_ban_and_separates_stay_from_validity(path):
    row = _one(json.loads(path.read_text(encoding="utf-8")), C6)
    text = _text(row)
    assert "business meetings" not in text
    assert "valid 60 days" not in text
    assert STAY_AND_VALIDITY in text
    assert "sponsored by an individual or organisation" in text
    assert "visiting friends and family" in text
    assert "selling goods or services and receiving pay are prohibited" in text
    assert row["price"] == PRICES[C6]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", tuple(FROZEN))
def test_neighbouring_rows_stay_frozen(path, name):
    assert _one(json.loads(path.read_text(encoding="utf-8")), name)["description_en"] == FROZEN[name]


@pytest.mark.parametrize("name", (C1, C6))
def test_mouth_mirror_matches_canonical_description(name):
    canonical, mirror = _files_data()
    assert _one(mirror, name)["description_en"] == _one(canonical, name)["description_en"]
    assert _one(mirror, name)["price"] == _one(canonical, name)["price"]


@pytest.mark.parametrize("name", (C1, C6))
def test_pricing_service_get_all_prices_serves_the_new_description(name):
    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.services.pricing.pricing_service import PricingService

    service = PricingService()
    assert service.loaded
    served = _one(service.get_all_prices(), name)
    assert served["description_en"] == _one(_files_data()[0], name)["description_en"]
    text = _text(served)
    assert STAY_AND_VALIDITY in text
    assert "business meetings" not in text and "cannot be used" not in text


# --- the printable price list is generated from the canonical JSON: it must not keep the old sentence ---

def _price_list_row(name: str) -> str | None:
    for line in PRICE_LIST_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] == f"**{name}**":
            return cells[1]
    return None


def test_printable_price_list_c1_row_is_the_canonical_description():
    canonical = _one(_files_data()[0], C1)["description_en"]
    row = _price_list_row(C1)
    assert row is not None, "the C1 Tourism row is missing from the printable price list"
    assert row == canonical
    assert "cannot be used for work or business" not in PRICE_LIST_MD.read_text(encoding="utf-8").lower()


# --- price catalogue versus the signed rule pack (the Visa Oracle's own answer on the same product) ---

# What the copy PERMITS, as the pack names the activity. Only an activity the copy affirmatively allows
# is listed; a copy that is silent on an activity cannot contradict the pack.
PERMITTED_BY_COPY = {"business_meetings": ("business discussions",)}
# The one known divergence: the official C1 page allows business discussions, negotiations and signing, while the
# signed pack still lists business_meetings under C1 prohibited_activities. The page is the authority and the
# pack field has no runtime reader (nothing renders or evaluates it); the pack correction is a signing matter for
# the next sequence and is not made here. This test fails the moment the pack drops the field (stale exception)
# or the copy starts to permit something else the pack prohibits (new divergence).
KNOWN_DIVERGENCE = {C1: {"business_meetings"}, C6: set()}


def _pack_prohibited(product_code: str) -> set[str]:
    source = sorted(PACKS.glob("rulepack-prod-*.source.json"))[-1]
    pack = json.loads(source.read_text(encoding="utf-8"))
    found: list[set[str]] = []
    stack = [pack]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("product_code") == product_code and "prohibited_activities" in node:
                found.append(set(node["prohibited_activities"]))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    assert len(found) == 1, (product_code, source.name, len(found))
    return found[0]


@pytest.mark.parametrize("name,code", ((C1, "C1"), (C6, "C6")))
def test_copy_and_pack_diverge_only_where_recorded(name, code):
    text = _text(_one(_files_data()[0], name))
    permitted = {a for a, phrases in PERMITTED_BY_COPY.items() if any(p in text for p in phrases)}
    assert permitted & _pack_prohibited(code) == KNOWN_DIVERGENCE[name]
