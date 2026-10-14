"""The E33-family price rows follow the official imigrasi.go.id pages (work/study, selling exception, income or allowance)."""
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
# Explicit fixture: the full description_en of all three E33F rows, frozen as shipped
# (the E33F official page never mentions work or study, so the work clause stays as it was).
E33F_FROZEN = {
    "E33F Second Home Senior (1 Year, Offshore)": "Second Home Visa / KITAS senior route (E33F) for applicants 55+ with proof of income or allowance of at least USD 3,000/month; no deposit required. Valid 1 year, renewable; non-working residency. Offshore process for applicants outside Indonesia.",
    "E33F Second Home Senior (1 Year, Altus/Onshore)": "Second Home Visa / KITAS senior route (E33F) for applicants 55+ with proof of income or allowance of at least USD 3,000/month; no deposit required. Valid 1 year, renewable; non-working residency. Onshore process via Altus.",
    "E33F Second Home Senior (Extend)": "Onshore annual extension of an existing E33F Second Home senior permit. USD 3,000/month income or allowance proof is re-validated at each extension.",
}
E33F_NAMES = tuple(E33F_FROZEN)
NAMES = ("E33 Second Home (5 Years)", "E33E Second Home Senior (5 Years)")
E33_SENIOR_NAMES = (
    "E33E Second Home Senior (5 Years)",
    "E33E Second Home Senior (Extend)",
    *E33F_NAMES,
)
ALL_E33_NAMES = ("E33 Second Home (5 Years)", *E33_SENIOR_NAMES)


def _rows(path: Path, name: str) -> list[dict]:
    found: list[dict] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            if node.get("name") == name:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return found


_CLAUSE = re.compile(
    r"residency; work or study only after dual-activity \(rangkap kegiatan\) reporting "
    r"to the immigration office that issued the stay permit\.",
)


_BAN = re.compile(
    r"stay permit\. selling goods or services is prohibited unless needed for the work\."
)


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", NAMES)
def test_row_carries_the_full_conditional_work_study_clause(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    text = _norm(rows[0]["description_en"])
    assert "non-working" not in text
    assert "selling goods or services is prohibited." not in text
    assert _CLAUSE.search(text), text
    assert _BAN.search(text), text


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", E33F_NAMES)
def test_e33f_descriptions_stay_frozen(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    desc = rows[0]["description_en"]
    assert desc == E33F_FROZEN[name]
    assert "rangkap" not in _norm(desc)
    if "1 Year" in name:
        assert "non-working residency" in _norm(desc)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", E33_SENIOR_NAMES)
def test_e33e_and_e33f_rows_use_income_or_allowance_wording(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    row = rows[0]
    combined = _norm(f"{row['description_en']} {row['notes']}")
    assert "usd 3,000" in combined
    for field in ("description_en", "notes"):
        text = _norm(row[field])
        assert "pension" not in text, (name, field, text)
        assert "passive income" not in text, (name, field, text)
        if "usd 3,000" in text:
            assert "income or allowance" in text, (name, field, text)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
def test_e33_base_row_names_no_income_and_needs_no_income_clause(path):
    rows = _rows(path, "E33 Second Home (5 Years)")
    assert len(rows) == 1
    row = rows[0]
    for field in ("description_en", "notes"):
        text = _norm(row[field])
        assert "pension" not in text
        assert "passive income" not in text
        assert "usd 3,000" not in text
        assert "income or allowance" not in text


@pytest.mark.parametrize("name", ALL_E33_NAMES)
def test_mouth_mirror_matches_canonical_description(name):
    canonical = _rows(FILES[0], name)[0]
    mirror = _rows(FILES[1], name)[0]
    assert mirror["description_en"] == canonical["description_en"]
    assert mirror["notes"] == canonical["notes"]
    assert mirror["price"] == canonical["price"]


@pytest.mark.parametrize("name", ALL_E33_NAMES)
def test_pricing_service_get_all_prices_serves_the_new_description(name):
    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.services.pricing.pricing_service import PricingService

    service = PricingService()
    assert service.loaded
    rows = _rows_in(service.get_all_prices(), name)
    assert len(rows) == 1
    row = rows[0]
    canonical = _rows(FILES[0], name)[0]
    assert row["description_en"] == canonical["description_en"]
    assert row["notes"] == canonical["notes"]
    if name in NAMES:
        text = _norm(row["description_en"])
        assert "non-working" not in text
        assert "selling goods or services is prohibited." not in text
        assert _CLAUSE.search(text), text
        assert _BAN.search(text), text
    if name in E33_SENIOR_NAMES:
        for field in ("description_en", "notes"):
            ftext = _norm(row[field])
            assert "pension" not in ftext
            assert "passive income" not in ftext
            if "usd 3,000" in ftext:
                assert "income or allowance" in ftext


def _rows_in(data, name: str) -> list[dict]:
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
