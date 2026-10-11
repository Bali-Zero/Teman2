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
E33F_NAMES = (
    "E33F Second Home Senior (1 Year, Offshore)",
    "E33F Second Home Senior (1 Year, Altus/Onshore)",
)
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


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", E33F_NAMES)
def test_e33f_rows_stay_untouched(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    text = _norm(rows[0]["description_en"])
    assert "non-working residency" in text
    assert "rangkap" not in text


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
