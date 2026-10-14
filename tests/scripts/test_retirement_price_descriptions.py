"""The Retirement KITAS price rows say 55+, matching the signed retirement rules in the active rule pack."""
from __future__ import annotations

import json
import re
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

RETIREMENT_ONSHORE = "Retirement (Altus/Onshore)"
RETIREMENT_OFFSHORE = "Retirement (Offshore)"
RETIREMENT_EXTEND = "Retirement (Extend)"
RETIREMENT_AGE_ROWS = (RETIREMENT_ONSHORE, RETIREMENT_OFFSHORE)

PINNED_RETIREMENT = {
    RETIREMENT_ONSHORE: (
        "Retirement KITAS for foreign nationals 55+ meeting income requirements. "
        "Onshore process via Altus."
    ),
    RETIREMENT_OFFSHORE: (
        "Retirement KITAS for foreign nationals 55+ meeting income requirements. "
        "Offshore process for applicants outside Indonesia."
    ),
}

E33_SENIOR_AGE_ROWS = (
    "E33E Second Home Senior (5 Years)",
    "E33F Second Home Senior (1 Year, Offshore)",
    "E33F Second Home Senior (1 Year, Altus/Onshore)",
)

_AGE_PLUS_RE = re.compile(r"\b(\d+)\+")


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


def _kitas_permits(data: dict) -> dict[str, dict]:
    if "services" in data:
        return data["services"]["kitas_permits"]
    return data["services_by_category"]["kitas_permits"]


def _rule_age_lt(rule: dict) -> int:
    found: list[int] = []
    stack = [rule["when"]]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("fact") == "derived.age_years" and node.get("op") == "lt":
                found.append(int(node["value"]))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    assert len(found) == 1, (rule.get("rule_id"), found)
    return found[0]


def _pack_retirement_age_floor() -> int:
    signed = sorted(PACKS.glob("rulepack-prod-*.signed.json"))[-1]
    rules = {
        r["rule_id"]: r
        for r in json.loads(signed.read_text(encoding="utf-8"))["payload"]["rules"]
    }
    e33e_floor = _rule_age_lt(rules["hf.e33e.age-below-55"])
    e33f_floor = _rule_age_lt(rules["hf.e33f.age-below-55"])
    assert e33e_floor == e33f_floor, (e33e_floor, e33f_floor)
    return e33e_floor


def _check_row_age_floor(row: dict, floor: int) -> list[str]:
    """Return any 'NN+' age tokens in description_en that do not match the pack floor."""
    ages = [int(m.group(1)) for m in _AGE_PLUS_RE.finditer(row["description_en"])]
    return [f"{age}+" for age in ages if age != floor]


def _price_list_row(name: str) -> str | None:
    for line in PRICE_LIST_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] == f"**{name}**":
            return cells[1]
    return None


@pytest.mark.parametrize("path", [FILES[0]], ids=lambda p: p.parent.parent.name)
def test_retirement_rows_naming_an_age_match_the_signed_pack_floor(path):
    floor = _pack_retirement_age_floor()
    kitas = _kitas_permits(json.loads(path.read_text(encoding="utf-8")))
    retirement_rows = [
        row for key, row in kitas.items() if key.startswith("Retirement (")
    ]
    age_rows = [
        row for row in retirement_rows if _AGE_PLUS_RE.search(row["description_en"])
    ]
    assert [r["name"] for r in age_rows] == list(RETIREMENT_AGE_ROWS)
    for row in age_rows:
        assert _check_row_age_floor(row, floor) == []


@pytest.mark.parametrize("name", RETIREMENT_AGE_ROWS)
def test_mutation_retirement_row_with_60_plus_is_convicted(name):
    floor = _pack_retirement_age_floor()
    row = dict(_one(_files_data()[0], name))
    mutated = {**row, "description_en": row["description_en"].replace("55+", "60+")}
    assert mutated["description_en"] != row["description_en"]
    assert _check_row_age_floor(mutated, floor) == ["60+"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", E33_SENIOR_AGE_ROWS)
def test_e33e_and_e33f_rows_pass_the_same_age_check(path, name):
    floor = _pack_retirement_age_floor()
    row = _one(json.loads(path.read_text(encoding="utf-8")), name)
    assert f"applicants {floor}+" in _text(row)
    assert _check_row_age_floor(row, floor) == []


@pytest.mark.parametrize("path", [FILES[0]], ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", RETIREMENT_AGE_ROWS)
def test_retirement_rows_are_pinned_as_full_strings(path, name):
    row = _one(json.loads(path.read_text(encoding="utf-8")), name)
    assert row["description_en"] == PINNED_RETIREMENT[name]


@pytest.mark.parametrize("path", [FILES[0]], ids=lambda p: p.parent.parent.name)
def test_retirement_extend_names_no_age_and_is_not_convicted(path):
    floor = _pack_retirement_age_floor()
    row = _one(json.loads(path.read_text(encoding="utf-8")), RETIREMENT_EXTEND)
    assert not _AGE_PLUS_RE.search(row["description_en"])
    assert _check_row_age_floor(row, floor) == []
    assert row["description_en"] == "Onshore extension of an existing Retirement KITAS."


@pytest.mark.parametrize(
    "name",
    (RETIREMENT_ONSHORE, RETIREMENT_OFFSHORE, RETIREMENT_EXTEND),
)
def test_mouth_mirror_omits_retirement_rows(name):
    _, mirror = _files_data()
    assert _rows(mirror, name) == []
    assert name not in _kitas_permits(mirror)


@pytest.mark.parametrize("name", RETIREMENT_AGE_ROWS)
def test_pricing_service_get_all_prices_serves_the_new_description(name):
    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.services.pricing.pricing_service import PricingService

    floor = _pack_retirement_age_floor()
    service = PricingService()
    assert service.loaded
    served = _one(service.get_all_prices(), name)
    assert served["description_en"] == PINNED_RETIREMENT[name]
    assert _check_row_age_floor(served, floor) == []
    assert "60+" not in served["description_en"]


@pytest.mark.parametrize(
    "name",
    (RETIREMENT_ONSHORE, RETIREMENT_OFFSHORE, RETIREMENT_EXTEND),
)
def test_printable_price_list_has_no_retirement_row(name):
    assert _price_list_row(name) is None
