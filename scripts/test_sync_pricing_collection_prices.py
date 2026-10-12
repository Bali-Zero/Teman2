#!/usr/bin/env python3
"""Tests for scripts/sync_pricing_collection_prices.py (fake Qdrant, no network).

Guilt: price drift -> planned update, text rewritten exactly once, last_updated set.
Innocence: in-sync point -> no-op; ambiguous text -> refused and NOTHING applied;
unmatched names -> reported only; --only scopes the plan.

Run: apps/backend-rag/.venv/bin/python -m pytest scripts/test_sync_pricing_collection_prices.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "sync_pricing_collection_prices",
    Path(__file__).resolve().parent / "sync_pricing_collection_prices.py",
)
assert _SPEC and _SPEC.loader
m = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = m
_SPEC.loader.exec_module(m)

TODAY = "2026-10-12"


def _point(pid: int, name: str, price: str, text: str | None = None) -> dict[str, Any]:
    return {
        "id": pid,
        "payload": {
            "name": name,
            "price": price,
            "last_updated": "2025-12-31",
            "text": text
            if text is not None
            else f"# {name}\n**Price**: {price}\n\n---\n",
        },
    }


def test_drift_is_planned_and_text_rewritten_once() -> None:
    plan = m.build_plan(
        [_point(1, "New Company (PT PMA)", "20.000.000 IDR")],
        {"New Company (PT PMA)": "25.000.000 IDR"},
        TODAY,
    )
    assert plan.refusals == []
    (u,) = plan.updates
    assert u["old"] == "20.000.000 IDR" and u["new"] == "25.000.000 IDR"
    assert u["payload"]["price"] == "25.000.000 IDR"
    assert (
        u["payload"]["text"]
        == "# New Company (PT PMA)\n**Price**: 25.000.000 IDR\n\n---\n"
    )
    assert u["payload"]["last_updated"] == TODAY
    assert set(u["payload"]) == {"price", "text", "last_updated"}


def test_in_sync_point_is_noop() -> None:
    plan = m.build_plan([_point(1, "X", "1.000 IDR")], {"X": "1.000 IDR"}, TODAY)
    assert plan.updates == [] and plan.refusals == [] and plan.in_sync == 1


def test_ambiguous_or_missing_old_price_in_text_is_refused() -> None:
    twice = _point(1, "X", "1.000 IDR", "a 1.000 IDR b 1.000 IDR")
    absent = _point(2, "Y", "1.000 IDR", "no price here")
    plan = m.build_plan([twice, absent], {"X": "2.000 IDR", "Y": "2.000 IDR"}, TODAY)
    assert plan.updates == [] and len(plan.refusals) == 2


def test_unmatched_names_are_reported_only() -> None:
    plan = m.build_plan([_point(1, "Orphan", "1 IDR")], {"Lonely": "2 IDR"}, TODAY)
    assert plan.updates == [] and plan.refusals == []
    assert plan.no_point == ["Lonely"] and plan.no_catalog_row == ["Orphan"]


def test_only_scopes_the_plan() -> None:
    pts = [_point(1, "A", "1 IDR"), _point(2, "B", "1 IDR")]
    plan = m.build_plan(pts, {"A": "2 IDR", "B": "2 IDR"}, TODAY, frozenset({"A"}))
    assert [u["name"] for u in plan.updates] == ["A"]


def test_tier_price_shape() -> None:
    row = {"name": "T", "price": "", "tier_range": ["5.000.000 IDR", "8.000.000 IDR"]}
    assert m.expected_price(row) == "5.000.000 - 8.000.000 IDR"
    assert m.expected_price({"name": "N", "price": "", "tier_range": None}) is None


def test_catalog_traversal_includes_nested_tax_accounting() -> None:
    cat = {
        "services": {
            "company_services": {"k": {"name": "A", "price": "1 IDR"}},
            "tax_accounting": {"sub": {"k2": {"name": "B", "price": "2 IDR"}}},
        }
    }
    assert m.catalog_prices(cat) == {"A": "1 IDR", "B": "2 IDR"}


def _run_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    points: list[dict[str, Any]],
    apply: bool,
):
    import json

    cat = tmp_path / "c.json"
    cat.write_text(
        json.dumps({"services": {"s": {"a": {"name": "A", "price": "2 IDR"}}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("QDRANT_URL", "http://q")
    monkeypatch.setenv("QDRANT_API_KEY", "k")
    written: list[Any] = []

    async def fake_scroll(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        return points

    async def fake_set(
        _c: Any, _u: Any, _h: Any, pid: Any, payload: dict[str, Any]
    ) -> None:
        written.append((pid, payload))

    monkeypatch.setattr(m, "_scroll_all_points", fake_scroll)
    monkeypatch.setattr(m, "_set_payload", fake_set)
    rc = asyncio.run(m.run(str(cat), apply, today=TODAY))
    return rc, written


def test_dry_run_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rc, written = _run_apply(
        monkeypatch, tmp_path, [_point(1, "A", "1 IDR")], apply=False
    )
    assert rc == 0 and written == []


def test_apply_writes_the_planned_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rc, written = _run_apply(
        monkeypatch, tmp_path, [_point(1, "A", "1 IDR")], apply=True
    )
    assert rc == 0 and len(written) == 1 and written[0][0] == 1


def test_refusal_exits_nonzero_and_applies_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pts = [_point(1, "A", "1 IDR"), _point(2, "A", "1 IDR", "no price")]
    rc, written = _run_apply(monkeypatch, tmp_path, pts, apply=True)
    assert rc == 2 and written == []
