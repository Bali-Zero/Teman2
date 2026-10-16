"""Guilt + innocence tests for ``--delete-orphans`` in scripts/sync_pricing_collection_prices.py (2026-10-16).

The live ``bali_zero_pricing_hybrid`` collection holds 17 stale 2025 points with no row in the 2026
catalog (renamed rows, retired services). ``--delete-orphans`` plans the deletion of exactly those
points, matching a point to a row by ``row.get("name", key)`` over public AND internal rows, and
``--apply`` deletes them only when ``--expect-orphans`` equals the count the reviewed dry run printed.

Guilt: a point of a public row is never deleted even when its price drifted (and that update is not
applied in orphan mode); a point of an internal row is never deleted; a point of a public row with no
price is not an orphan; a name duplicated in the catalog is not an orphan; ``--apply`` without
``--expect-orphans`` or with a different count deletes nothing; a point with no name, or a catalog
with no rows, is a refusal that deletes nothing; combining with ``--create-missing``,
``--purge-internal`` or ``--only`` is refused before any write; ``--apply`` without
``--delete-orphans`` deletes nothing.
Innocence: the dry run prints the DELETE line and writes nothing; the matching count deletes exactly
the orphan ids in one call with no set_payload and no upsert; a point named like a catalog KEY whose
row carries another ``name`` is an orphan; the real catalogue has zero orphans among points built
from its own row names. Fakes only: no network, no Qdrant.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "sync_pricing_collection_prices_delete_orphans_1016",
    REPO_ROOT / "scripts" / "sync_pricing_collection_prices.py",
)
assert _SPEC and _SPEC.loader
sync_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sync_mod
_SPEC.loader.exec_module(sync_mod)

STALE = "Dependent KITAP MERP"


def _catalog(**extra_rows: dict[str, Any]) -> dict[str, Any]:
    kitas: dict[str, Any] = {
        "Investor KITAS": {"name": "Investor KITAS", "price": "17.000.000 IDR"},
        "Dependent KITAP": {
            "name": "Dependent KITAP + MERP",
            "price": "20.000.000 IDR",
        },
        "Retirement (Offshore)": {
            "name": "Retirement (Offshore)",
            "price": "14.000.000 IDR",
            "internal": True,
        },
    }
    kitas.update(extra_rows)
    return {
        "metadata": {"currency": "IDR"},
        "services": {"kitas_permits": kitas},
    }


def _point(
    point_id: int, name: Any, price: str = "1 IDR", text: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"price": price, "text": text or f"**Price**: {price}"}
    if name is not None:
        payload["name"] = name
    return {"id": point_id, "payload": payload}


def _live_points() -> list[dict[str, Any]]:
    return [
        _point(1, "Investor KITAS", "17.000.000 IDR"),
        _point(2, "Dependent KITAP + MERP", "20.000.000 IDR"),
        _point(3, "Retirement (Offshore)", "14.000.000 IDR"),
        _point(4, STALE, "9.000.000 IDR"),
    ]


class _Recorder:
    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, points: list[dict[str, Any]]
    ) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.set_payloads: list[Any] = []
        self.delete_calls: list[list[Any]] = []

        async def scroll(*_a: Any) -> list[dict[str, Any]]:
            return points

        async def set_payload(
            _c: Any, _u: str, _h: Any, point_id: Any, _p: Any
        ) -> None:
            self.set_payloads.append(point_id)

        async def delete(_c: Any, _u: str, _h: Any, ids: list[Any]) -> None:
            self.delete_calls.append(list(ids))

        async def upsert(
            _c: Any, _u: str, _h: Any, batch: list[dict[str, Any]]
        ) -> None:
            self.upserts.extend(batch)

        monkeypatch.setenv("QDRANT_URL", "https://fake-qdrant.local")
        monkeypatch.setenv("QDRANT_API_KEY", "fake-key")
        monkeypatch.setattr(sync_mod, "_scroll_all_points", scroll)
        monkeypatch.setattr(sync_mod, "_set_payload", set_payload)
        monkeypatch.setattr(sync_mod, "_delete_points", delete)
        monkeypatch.setattr(sync_mod, "_upsert_points", upsert)

    @property
    def deleted(self) -> list[Any]:
        return [i for call in self.delete_calls for i in call]

    def wrote_nothing(self) -> bool:
        return not (self.delete_calls or self.set_payloads or self.upserts)


def _run(tmp_path: Path, catalog: dict[str, Any], **kwargs: Any) -> int:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return asyncio.run(sync_mod.run(str(path), today="2026-10-16", **kwargs))


# --- guilt -----------------------------------------------------------------------------


def test_a_public_point_is_never_deleted_even_when_its_price_drifted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drifted = _point(
        2, "Dependent KITAP + MERP", "15.000.000 IDR", "**Price**: 15.000.000 IDR"
    )
    rec = _Recorder(monkeypatch, [drifted, _point(4, STALE)])
    rc = _run(tmp_path, _catalog(), apply=True, delete_orphans=True, expect_orphans=1)
    assert rc == 0
    assert rec.deleted == [4]
    assert rec.set_payloads == [] and rec.upserts == []
    assert "1 UPDATE(s) reported, not applied" in capsys.readouterr().out


def test_an_internal_point_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(tmp_path, _catalog(), apply=True, delete_orphans=True, expect_orphans=1)
    assert rc == 0
    assert rec.deleted == [4]
    assert 3 not in rec.deleted


def test_a_public_row_with_no_price_is_not_an_orphan() -> None:
    catalog = _catalog(Unpriced={"name": "Unpriced Permit", "price": ""})
    deletes, refusals = sync_mod.plan_orphan_deletes(
        [_point(5, "Unpriced Permit")], catalog
    )
    assert deletes == [] and refusals == []
    assert "Unpriced Permit" not in sync_mod.catalog_prices(catalog)
    assert "Unpriced Permit" in sync_mod.catalog_names(catalog)


def test_a_name_duplicated_in_the_catalog_is_not_an_orphan() -> None:
    catalog = _catalog(
        Twin={"name": "Twin Permit", "price": "1 IDR"},
        Twin2={"name": "Twin Permit", "price": "2 IDR"},
    )
    deletes, refusals = sync_mod.plan_orphan_deletes(
        [_point(5, "Twin Permit")], catalog
    )
    assert deletes == [] and refusals == []
    assert "Twin Permit" not in sync_mod.catalog_prices(catalog)


def test_apply_without_expect_orphans_deletes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(tmp_path, _catalog(), apply=True, delete_orphans=True)
    assert rc == 1
    assert rec.wrote_nothing()


def test_an_expect_count_mismatch_deletes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(tmp_path, _catalog(), apply=True, delete_orphans=True, expect_orphans=2)
    assert rc == 2
    assert rec.wrote_nothing()
    assert (
        "ORPHAN COUNT 1 != --expect-orphans 2 - nothing applied"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize("bad_name", [None, "", 7])
def test_a_point_with_no_usable_name_is_a_refusal_and_nothing_is_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    bad_name: Any,
) -> None:
    rec = _Recorder(monkeypatch, [*_live_points(), _point(9, bad_name)])
    rc = _run(tmp_path, _catalog(), apply=True, delete_orphans=True, expect_orphans=1)
    assert rc == 2
    assert rec.wrote_nothing()
    out = capsys.readouterr().out
    assert "REFUSED 9: payload name missing or not a string" in out
    assert "nothing applied" in out


def test_a_catalog_with_no_rows_is_a_refusal_and_nothing_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(
        tmp_path, {"services": {}}, apply=True, delete_orphans=True, expect_orphans=4
    )
    assert rc == 2
    assert rec.wrote_nothing()
    assert "the catalog has no rows" in capsys.readouterr().out


@pytest.mark.parametrize(
    "combo",
    [
        {"create_missing": True},
        {"purge_internal": True},
        {"only": frozenset({"Investor KITAS"})},
    ],
)
def test_delete_orphans_refuses_every_other_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, combo: dict[str, Any]
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(
        tmp_path,
        _catalog(),
        apply=True,
        delete_orphans=True,
        expect_orphans=1,
        **combo,
    )
    assert rc == 1
    assert rec.wrote_nothing()


def test_apply_without_delete_orphans_deletes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(tmp_path, _catalog(), apply=True)
    assert rc == 0
    assert rec.delete_calls == [] and rec.upserts == []
    out = capsys.readouterr().out
    assert f"NO-CATALOG-ROW (report only) point '{STALE}'" in out
    assert "deletes=0" in out


# --- innocence -------------------------------------------------------------------------


def test_dry_run_lists_the_orphan_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _Recorder(monkeypatch, _live_points())
    rc = _run(tmp_path, _catalog(), apply=False, delete_orphans=True)
    assert rc == 0
    assert rec.wrote_nothing()
    out = capsys.readouterr().out
    assert f"DELETE id=4 '{STALE}'" in out
    assert "deletes=1" in out
    assert out.rstrip().endswith("pass --apply to write")


def test_apply_with_the_matching_count_deletes_exactly_the_orphans_in_one_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    points = [*_live_points(), _point(5, "Retired 2025 Service")]
    rec = _Recorder(monkeypatch, points)
    rc = _run(tmp_path, _catalog(), apply=True, delete_orphans=True, expect_orphans=2)
    assert rc == 0
    assert rec.delete_calls == [[4, 5]]
    assert rec.set_payloads == [] and rec.upserts == []
    assert (
        "DELETED 2 orphan point(s) from bali_zero_pricing_hybrid"
        in capsys.readouterr().out
    )


def test_a_point_named_like_a_catalog_key_with_another_row_name_is_an_orphan() -> None:
    catalog = _catalog()
    deletes, refusals = sync_mod.plan_orphan_deletes(
        [_point(6, "Dependent KITAP")], catalog
    )
    assert refusals == []
    assert deletes == [{"id": 6, "name": "Dependent KITAP"}]


def test_the_real_catalogue_has_no_orphans_among_its_own_row_names() -> None:
    catalog = json.loads(sync_mod.DEFAULT_CATALOG.read_text(encoding="utf-8"))
    services = catalog["services"]
    names = [
        row.get("name", key)
        for _c, key, row in (
            *sync_mod._iter_service_rows(services),
            *sync_mod._iter_internal_service_rows(services),
        )
    ]
    assert names
    points = [_point(i, n) for i, n in enumerate(names)]
    deletes, refusals = sync_mod.plan_orphan_deletes(points, catalog)
    assert deletes == [] and refusals == []


# --- main() ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--expect-orphans", "1"],
        ["--delete-orphans", "--create-missing"],
        ["--delete-orphans", "--purge-internal"],
        ["--delete-orphans", "--only", "Investor KITAS"],
    ],
)
def test_main_refuses_bad_flag_combinations(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["sync_pricing_collection_prices.py", *argv])
    with pytest.raises(SystemExit) as exc:
        sync_mod.main()
    assert exc.value.code == 2
