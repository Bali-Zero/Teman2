"""The E33 and E33E price rows must not call the permit non-working (official imigrasi.go.id pages)."""
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
# (the E33F official page never mentions work or study, so the rows stay as they were).
E33F_FROZEN = {
    "E33F Second Home Senior (1 Year, Offshore)": "Second Home Visa / KITAS senior route (E33F) for applicants 55+ with proven USD 3,000/month passive income (pension or equivalent); no deposit required. Valid 1 year, renewable; non-working residency. Offshore process for applicants outside Indonesia.",
    "E33F Second Home Senior (1 Year, Altus/Onshore)": "Second Home Visa / KITAS senior route (E33F) for applicants 55+ with proven USD 3,000/month passive income (pension or equivalent); no deposit required. Valid 1 year, renewable; non-working residency. Onshore process via Altus.",
    "E33F Second Home Senior (Extend)": "Onshore annual extension of an existing E33F Second Home senior permit. USD 3,000/month passive income proof is re-validated at each extension."
}
E33F_NAMES = tuple(E33F_FROZEN)
NAMES = ("E33 Second Home (5 Years)", "E33E Second Home Senior (5 Years)")


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


_BAN = re.compile(r"stay permit\. selling goods or services is prohibited\.")


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", NAMES)
def test_row_carries_the_full_conditional_work_study_clause(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    text = _norm(rows[0]["description_en"])
    assert "non-working" not in text
    assert _CLAUSE.search(text), text
    assert _BAN.search(text), text


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", E33F_NAMES)
def test_e33f_descriptions_stay_frozen(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    assert rows[0]["description_en"] == E33F_FROZEN[name]


@pytest.mark.parametrize("name", NAMES)
def test_mouth_mirror_matches_canonical_description(name):
    canonical = _rows(FILES[0], name)[0]["description_en"]
    assert _rows(FILES[1], name)[0]["description_en"] == canonical


@pytest.mark.parametrize("name", NAMES)
def test_pricing_service_get_all_prices_serves_the_new_description(name):
    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.services.pricing.pricing_service import PricingService

    service = PricingService()
    assert service.loaded
    rows = _rows_in(service.get_all_prices(), name)
    assert len(rows) == 1
    text = _norm(rows[0]["description_en"])
    assert "non-working" not in text
    assert _CLAUSE.search(text), text
    assert _BAN.search(text), text


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
