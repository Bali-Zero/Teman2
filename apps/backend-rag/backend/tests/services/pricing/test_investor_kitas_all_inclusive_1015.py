"""Investor KITAS rows are all-inclusive, stated on the row itself (Zero 2026-10-15, Q7).

The canonical catalogue and the mouth mirror must both carry ``notes`` "All-inclusive price." on
the three Investor KITAS 2 Years rows, at the unchanged prices 17 / 19 / 18 million IDR, so the
PricingTool / MCP ``search_service_pricing`` and the public site say what the result card says.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[6]
_CANON = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
_MIRROR = _REPO_ROOT / "apps/mouth/data/bali-zero-prices.json"

_EXPECTED = {
    "Investor KITAS 2 Years (Offshore)": "17.000.000 IDR",
    "Investor KITAS 2 Years (Altus/Onshore)": "19.000.000 IDR",
    "Investor KITAS 2 Years (Extend)": "18.000.000 IDR",
}
_NOTE = "All-inclusive price."


def _canon_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and name.startswith("Investor KITAS 2 Years"):
                rows[name] = node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(_CANON.read_text(encoding="utf-8")))
    return rows


def _mirror_rows() -> dict[str, dict]:
    data = json.loads(_MIRROR.read_text(encoding="utf-8"))
    found: dict[str, dict] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            key = node.get("key")
            if isinstance(key, str) and key.startswith("Investor KITAS 2 Years"):
                found[key] = node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found


@pytest.mark.parametrize("loader", [_canon_rows, _mirror_rows], ids=["canonical", "mouth-mirror"])
def test_three_investor_rows_are_all_inclusive_at_unchanged_prices(loader) -> None:
    rows = loader()
    assert set(rows) == set(_EXPECTED), "the Investor KITAS 2 Years row set changed"
    for name, price in _EXPECTED.items():
        assert rows[name]["price"] == price, name
        assert rows[name]["notes"] == _NOTE, name
