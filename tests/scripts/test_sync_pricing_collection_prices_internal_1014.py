"""Tests for scripts/sync_pricing_collection_prices.py internal-row handling (2026-10-14).

Verifies:
1. Internal rows ('internal': true) are omitted from _iter_service_rows / catalog_prices
   and are never upserted/updated in Qdrant.
2. --purge-internal is dry-run by default: lists the exact Qdrant point IDs of internal
   rows that WOULD be deleted without calling Qdrant delete.
3. --purge-internal --apply deletes ONLY the exact Qdrant point IDs of internal rows
   and leaves public points untouched.
All tests use fakes/mocks with zero network or Qdrant access.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "sync_pricing_collection_prices_internal_1014",
    REPO_ROOT / "scripts" / "sync_pricing_collection_prices.py",
)
assert _SPEC and _SPEC.loader
sync_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sync_mod
_SPEC.loader.exec_module(sync_mod)

INTERNAL_NAMES = frozenset(
    {
        "Retirement (Altus/Onshore)",
        "Retirement (Offshore)",
        "Retirement (Extend)",
    }
)


def _sample_qdrant_points() -> list[dict[str, Any]]:
    return [
        {
            "id": "pt-internal-offshore",
            "payload": {
                "name": "Retirement (Offshore)",
                "price": "99.000.000 IDR",
                "text": "Retirement (Offshore) costs 99.000.000 IDR all-inclusive.",
            },
        },
        {
            "id": "pt-internal-onshore",
            "payload": {
                "name": "Retirement (Altus/Onshore)",
                "price": "16.000.000 IDR",
                "text": "Retirement (Altus/Onshore) costs 16.000.000 IDR all-inclusive.",
            },
        },
        {
            "id": "pt-internal-extend",
            "payload": {
                "name": "Retirement (Extend)",
                "price": "10.000.000 IDR",
                "text": "Retirement (Extend) costs 10.000.000 IDR all-inclusive.",
            },
        },
        {
            "id": "pt-e33f-offshore",
            "payload": {
                "name": "E33F Second Home Senior (1 Year, Offshore)",
                "price": "12.000.000 IDR",
                "text": (
                    "E33F Second Home Senior (1 Year, Offshore) price is "
                    "12.000.000 IDR."
                ),
            },
        },
        {
            "id": "pt-kitap-retire",
            "payload": {
                "name": "Retirement KITAP + MERP",
                "price": "45.000.000 IDR",
                "text": "Retirement KITAP + MERP price is 45.000.000 IDR.",
            },
        },
    ]


def test_real_catalog_excludes_internal_rows_from_sync_prices() -> None:
    catalog = json.loads(sync_mod.DEFAULT_CATALOG.read_text(encoding="utf-8"))
    prices = sync_mod.catalog_prices(catalog)
    internal = sync_mod.internal_catalog_names(catalog)

    assert internal == INTERNAL_NAMES
    for name in INTERNAL_NAMES:
        assert name not in prices

    assert prices["E33F Second Home Senior (1 Year, Offshore)"] == "14.000.000 IDR"
    assert prices["E33F Second Home Senior (1 Year, Altus/Onshore)"] == "16.000.000 IDR"
    assert prices["E33F Second Home Senior (Extend)"] == "10.000.000 IDR"
    assert prices["Retirement KITAP + MERP"] == "45.000.000 IDR"


def test_build_plan_never_upserts_internal_rows_and_plans_deletes_only_when_requested() -> (
    None
):
    catalog = json.loads(sync_mod.DEFAULT_CATALOG.read_text(encoding="utf-8"))
    prices = sync_mod.catalog_prices(catalog)
    internal = sync_mod.internal_catalog_names(catalog)
    points = _sample_qdrant_points()

    default_plan = sync_mod.build_plan(
        points,
        prices,
        "2026-10-14",
        internal_names=internal,
        purge_internal=False,
    )
    assert [u["id"] for u in default_plan.updates] == ["pt-e33f-offshore"]
    assert default_plan.updates[0]["new"] == "14.000.000 IDR"
    assert default_plan.in_sync == 1
    assert default_plan.deletes == []
    assert default_plan.no_catalog_row == []
    assert default_plan.internal_points == [
        {"id": "pt-internal-offshore", "name": "Retirement (Offshore)"},
        {"id": "pt-internal-onshore", "name": "Retirement (Altus/Onshore)"},
        {"id": "pt-internal-extend", "name": "Retirement (Extend)"},
    ]

    purge_plan = sync_mod.build_plan(
        points,
        prices,
        "2026-10-14",
        internal_names=internal,
        purge_internal=True,
    )
    assert [u["id"] for u in purge_plan.updates] == ["pt-e33f-offshore"]
    assert purge_plan.deletes == [
        {"id": "pt-internal-offshore", "name": "Retirement (Offshore)"},
        {"id": "pt-internal-onshore", "name": "Retirement (Altus/Onshore)"},
        {"id": "pt-internal-extend", "name": "Retirement (Extend)"},
    ]
    assert purge_plan.internal_points == []


def test_default_run_reports_internal_points_without_planning_deletes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://fake-qdrant.local")
    monkeypatch.setenv("QDRANT_API_KEY", "fake-key")

    set_calls: list[tuple[Any, dict[str, Any]]] = []
    delete_calls: list[list[Any]] = []

    async def fake_scroll(
        client: Any,
        base_url: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        return _sample_qdrant_points()

    async def fake_set_payload(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_id: Any,
        payload: dict[str, Any],
    ) -> None:
        set_calls.append((point_id, payload))

    async def fake_delete_points(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_ids: list[Any],
    ) -> None:
        delete_calls.append(list(point_ids))

    monkeypatch.setattr(sync_mod, "_scroll_all_points", fake_scroll)
    monkeypatch.setattr(sync_mod, "_set_payload", fake_set_payload)
    monkeypatch.setattr(sync_mod, "_delete_points", fake_delete_points)

    rc = asyncio.run(
        sync_mod.run(
            str(sync_mod.DEFAULT_CATALOG),
            apply=False,
            today="2026-10-14",
            purge_internal=False,
        )
    )
    assert rc == 0
    assert set_calls == []
    assert delete_calls == []

    out = capsys.readouterr().out
    assert (
        "INTERNAL (report only; pass --purge-internal to delete) "
        "id=pt-internal-offshore 'Retirement (Offshore)'"
    ) in out
    assert (
        "INTERNAL (report only; pass --purge-internal to delete) "
        "id=pt-internal-onshore 'Retirement (Altus/Onshore)'"
    ) in out
    assert (
        "INTERNAL (report only; pass --purge-internal to delete) "
        "id=pt-internal-extend 'Retirement (Extend)'"
    ) in out
    assert "DELETE id=" not in out
    assert "NO-CATALOG-ROW" not in out
    assert ("SUMMARY updates=1 deletes=0 internal_points=3 refused=0 in_sync=1 ") in out
    assert "points_without_catalog_row=0" in out


def test_purge_internal_dry_run_default_prints_deletes_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://fake-qdrant.local")
    monkeypatch.setenv("QDRANT_API_KEY", "fake-key")

    set_calls: list[tuple[Any, dict[str, Any]]] = []
    delete_calls: list[list[Any]] = []

    async def fake_scroll(
        client: Any,
        base_url: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        return _sample_qdrant_points()

    async def fake_set_payload(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_id: Any,
        payload: dict[str, Any],
    ) -> None:
        set_calls.append((point_id, payload))

    async def fake_delete_points(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_ids: list[Any],
    ) -> None:
        delete_calls.append(list(point_ids))

    monkeypatch.setattr(sync_mod, "_scroll_all_points", fake_scroll)
    monkeypatch.setattr(sync_mod, "_set_payload", fake_set_payload)
    monkeypatch.setattr(sync_mod, "_delete_points", fake_delete_points)

    rc = asyncio.run(
        sync_mod.run(
            str(sync_mod.DEFAULT_CATALOG),
            apply=False,
            today="2026-10-14",
            purge_internal=True,
        )
    )
    assert rc == 0
    assert set_calls == []
    assert delete_calls == []

    out = capsys.readouterr().out
    assert "DELETE id=pt-internal-offshore 'Retirement (Offshore)'" in out
    assert "DELETE id=pt-internal-onshore 'Retirement (Altus/Onshore)'" in out
    assert "DELETE id=pt-internal-extend 'Retirement (Extend)'" in out
    assert "DELETE id=pt-e33f-offshore" not in out
    assert "DELETE id=pt-kitap-retire" not in out
    assert "Dry-run only (default) - pass --apply to write" in out


def test_purge_internal_with_apply_deletes_only_internal_points_and_updates_public(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://fake-qdrant.local")
    monkeypatch.setenv("QDRANT_API_KEY", "fake-key")

    set_calls: list[tuple[Any, dict[str, Any]]] = []
    delete_calls: list[list[Any]] = []

    async def fake_scroll(
        client: Any,
        base_url: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        return _sample_qdrant_points()

    async def fake_set_payload(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_id: Any,
        payload: dict[str, Any],
    ) -> None:
        set_calls.append((point_id, payload))

    async def fake_delete_points(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_ids: list[Any],
    ) -> None:
        delete_calls.append(list(point_ids))

    monkeypatch.setattr(sync_mod, "_scroll_all_points", fake_scroll)
    monkeypatch.setattr(sync_mod, "_set_payload", fake_set_payload)
    monkeypatch.setattr(sync_mod, "_delete_points", fake_delete_points)

    rc = asyncio.run(
        sync_mod.run(
            str(sync_mod.DEFAULT_CATALOG),
            apply=True,
            today="2026-10-14",
            purge_internal=True,
        )
    )
    assert rc == 0
    assert [point_id for point_id, _payload in set_calls] == ["pt-e33f-offshore"]
    assert delete_calls == [
        [
            "pt-internal-offshore",
            "pt-internal-onshore",
            "pt-internal-extend",
        ]
    ]
    out = capsys.readouterr().out
    assert "DELETED 3 internal point(s) from bali_zero_pricing_hybrid" in out
    assert "APPLIED 1 point(s) in bali_zero_pricing_hybrid" in out


def test_apply_with_purge_internal_false_updates_public_without_deleting_internal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://fake-qdrant.local")
    monkeypatch.setenv("QDRANT_API_KEY", "fake-key")

    set_calls: list[tuple[Any, dict[str, Any]]] = []
    delete_calls: list[list[Any]] = []

    async def fake_scroll(
        client: Any,
        base_url: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        return _sample_qdrant_points()

    async def fake_set_payload(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_id: Any,
        payload: dict[str, Any],
    ) -> None:
        set_calls.append((point_id, payload))

    async def fake_delete_points(
        client: Any,
        base_url: str,
        headers: dict[str, str],
        point_ids: list[Any],
    ) -> None:
        delete_calls.append(list(point_ids))

    monkeypatch.setattr(sync_mod, "_scroll_all_points", fake_scroll)
    monkeypatch.setattr(sync_mod, "_set_payload", fake_set_payload)
    monkeypatch.setattr(sync_mod, "_delete_points", fake_delete_points)

    rc = asyncio.run(
        sync_mod.run(
            str(sync_mod.DEFAULT_CATALOG),
            apply=True,
            today="2026-10-14",
            purge_internal=False,
        )
    )
    assert rc == 0
    assert [point_id for point_id, _payload in set_calls] == ["pt-e33f-offshore"]
    assert delete_calls == []
    out = capsys.readouterr().out
    assert "DELETED" not in out
    assert "APPLIED 1 point(s) in bali_zero_pricing_hybrid" in out

