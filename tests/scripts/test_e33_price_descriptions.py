"""The E33 and E33E price rows must not call the permit non-working (official imigrasi.go.id pages)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "apps" / "backend-rag" / "backend" / "data" / "bali_zero_official_prices_2026.json",
    ROOT / "apps" / "mouth" / "data" / "bali-zero-prices.json",
]
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


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parent.parent.name)
@pytest.mark.parametrize("name", NAMES)
def test_row_does_not_say_non_working_and_names_rangkap_kegiatan(path, name):
    rows = _rows(path, name)
    assert len(rows) == 1
    text = rows[0]["description_en"].lower()
    assert "non-working" not in text
    assert "rangkap kegiatan" in text
