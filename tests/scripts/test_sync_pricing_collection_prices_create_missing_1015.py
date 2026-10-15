"""Guilt + innocence tests for ``--create-missing`` in scripts/sync_pricing_collection_prices.py (2026-10-15).

The live ``bali_zero_pricing_hybrid`` collection lacked a point for 66 public catalog rows, so
Zantara's price retrieval never saw them. ``--create-missing`` plans one point per such row, built
like ``apps/backend-rag/scripts/prepare_payloads.py`` built the live ones, and ``--apply`` writes
those creates only.

Guilt: internal rows are never created; an existing point is never touched (no create on its
name, no create on its id, no price update applied in create mode); a row with no price is
refused and nothing is written; ``--apply`` without ``--create-missing`` creates nothing; an id
that appears between plan and write aborts the write; ``--purge-internal`` is refused.
Innocence: a normal missing row is created with the live payload shape, the template text, the
md5 point id and a 1536-dim ``dense`` vector; the real catalogue plans one create per priced
public row. Fakes only: no network, no Qdrant, no embedding provider.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "sync_pricing_collection_prices_create_missing_1015",
    REPO_ROOT / "scripts" / "sync_pricing_collection_prices.py",
)
assert _SPEC and _SPEC.loader
sync_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sync_mod
_SPEC.loader.exec_module(sync_mod)
prepare = sync_mod._load_prepare_payloads()

LIVE_PAYLOAD_KEYS = {
    "text",
    "name",
    "category",
    "price",
    "duration",
    "validity",
    "notes",
    "source_type",
    "last_updated",
    "currency",
}
CONTACT = {
    "email": "zero@balizero.com",
    "whatsapp": "+62 821 3454 721",
    "location": "Kerobokan, Bali, Indonesia",
}


def _md5_id(category: str, name: str) -> int:
    return int(hashlib.md5(f"{category}:{name}".encode()).hexdigest()[:16], 16) % (
        2**63
    )


def _catalog(**extra_rows: dict[str, Any]) -> dict[str, Any]:
    kitas: dict[str, Any] = {
        "Investor KITAS": {"name": "Investor KITAS", "price": "17.000.000 IDR"},
        "E33F Offshore": {
            "name": "E33F Second Home Senior (1 Year, Offshore)",
            "price": "14.000.000 IDR",
            "validity": "1 year",
            "notes": "All-inclusive price.",
            "description_en": "Senior route for applicants 55+.",
        },
        "Retirement (Offshore)": {
            "name": "Retirement (Offshore)",
            "price": "14.000.000 IDR",
            "internal": True,
        },
    }
    kitas.update(extra_rows)
    return {
        "metadata": {"currency": "IDR", "contact": CONTACT},
        "services": {"kitas_permits": kitas},
    }


def _existing_point(
    name: str = "Investor KITAS", price: str = "17.000.000 IDR"
) -> dict[str, Any]:
    return {
        "id": _md5_id("kitas_permits", name),
        "payload": {
            "name": name,
            "price": price,
            "text": f"# {name}\n**Price**: {price}",
        },
    }


class _Recorder:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        points: list[dict[str, Any]],
        present: set[Any] | None = None,
    ) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.set_payloads: list[Any] = []
        self.deletes: list[Any] = []
        self.embedded: list[str] = []

        async def scroll(*_a: Any) -> list[dict[str, Any]]:
            return points

        async def set_payload(
            _c: Any, _u: str, _h: Any, point_id: Any, _p: Any
        ) -> None:
            self.set_payloads.append(point_id)

        async def delete(_c: Any, _u: str, _h: Any, ids: list[Any]) -> None:
            self.deletes.extend(ids)

        async def size(*_a: Any) -> int:
            return 1536

        async def existing(_c: Any, _u: str, _h: Any, ids: list[Any]) -> set[Any]:
            return {i for i in ids if i in (present or set())}

        async def upsert(
            _c: Any, _u: str, _h: Any, batch: list[dict[str, Any]]
        ) -> None:
            self.upserts.extend(batch)

        monkeypatch.setenv("QDRANT_URL", "https://fake-qdrant.local")
        monkeypatch.setenv("QDRANT_API_KEY", "fake-key")
        monkeypatch.setattr(sync_mod, "_scroll_all_points", scroll)
        monkeypatch.setattr(sync_mod, "_set_payload", set_payload)
        monkeypatch.setattr(sync_mod, "_delete_points", delete)
        monkeypatch.setattr(sync_mod, "_dense_vector_size", size)
        monkeypatch.setattr(sync_mod, "_existing_ids", existing)
        monkeypatch.setattr(sync_mod, "_upsert_points", upsert)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [[0.001] * 1536 for _ in texts]


def _run(tmp_path: Path, rec: _Recorder, catalog: dict[str, Any], **kwargs: Any) -> int:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return asyncio.run(
        sync_mod.run(str(path), today="2026-10-15", embed=rec.embed, **kwargs)
    )


# --- guilt -----------------------------------------------------------------------------


def test_internal_rows_are_never_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _Recorder(monkeypatch, [_existing_point()])
    rc = _run(tmp_path, rec, _catalog(), apply=True, create_missing=True)
    assert rc == 0
    names = [p["payload"]["name"] for p in rec.upserts]
    assert names == ["E33F Second Home Senior (1 Year, Offshore)"]
    assert "Retirement (Offshore)" not in "".join(rec.embedded)


def test_existing_point_is_never_touched_even_when_its_price_drifted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    drifted = _existing_point(price="15.000.000 IDR")
    rec = _Recorder(monkeypatch, [drifted])
    rc = _run(tmp_path, rec, _catalog(), apply=True, create_missing=True)
    assert rc == 0
    assert rec.set_payloads == [] and rec.deletes == []
    assert drifted["id"] not in [p["id"] for p in rec.upserts]
    assert "1 UPDATE(s) reported, not applied" in capsys.readouterr().out


def test_a_create_whose_id_is_already_taken_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    squatter = {
        "id": _md5_id("kitas_permits", "E33F Second Home Senior (1 Year, Offshore)"),
        "payload": {"name": "Some Other Name", "price": "1 IDR", "text": "1 IDR"},
    }
    rec = _Recorder(monkeypatch, [_existing_point(), squatter])
    rc = _run(tmp_path, rec, _catalog(), apply=True, create_missing=True)
    assert rc == 2
    assert rec.upserts == [] and rec.embedded == []
    assert "is already taken" in capsys.readouterr().out


def test_a_row_with_no_price_is_refused_and_nothing_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = _catalog(
        Unpriced={"name": "Unpriced Permit", "price": "", "tier_range": None}
    )
    rec = _Recorder(monkeypatch, [_existing_point()])
    rc = _run(tmp_path, rec, catalog, apply=True, create_missing=True)
    assert rc == 2
    assert rec.upserts == [] and rec.embedded == []
    out = capsys.readouterr().out
    assert "REFUSED create 'Unpriced Permit': catalog row has no price" in out
    assert "nothing applied" in out


def test_apply_without_create_missing_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _Recorder(monkeypatch, [_existing_point()])
    rc = _run(tmp_path, rec, _catalog(), apply=True)
    assert rc == 0
    assert rec.upserts == [] and rec.embedded == []
    out = capsys.readouterr().out
    assert "CREATE" not in out
    assert "creates=0" in out
    assert (
        "NO-POINT (report only) catalog row 'E33F Second Home Senior (1 Year, Offshore)'"
        in out
    )


def test_an_id_that_appears_before_the_write_aborts_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    late = _md5_id("kitas_permits", "E33F Second Home Senior (1 Year, Offshore)")
    rec = _Recorder(monkeypatch, [_existing_point()], present={late})
    rc = _run(tmp_path, rec, _catalog(), apply=True, create_missing=True)
    assert rc == 2
    assert rec.upserts == [] and rec.embedded == []
    assert "already present" in capsys.readouterr().out


def test_create_missing_refuses_purge_internal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _Recorder(monkeypatch, [_existing_point()])
    rc = _run(
        tmp_path, rec, _catalog(), apply=True, create_missing=True, purge_internal=True
    )
    assert rc == 1
    assert rec.upserts == [] and rec.deletes == []


# --- innocence -------------------------------------------------------------------------


def test_dry_run_plans_the_create_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rec = _Recorder(monkeypatch, [_existing_point()])
    rc = _run(tmp_path, rec, _catalog(), apply=False, create_missing=True)
    assert rc == 0
    assert rec.upserts == [] and rec.embedded == []
    out = capsys.readouterr().out
    expected_id = _md5_id("kitas_permits", "E33F Second Home Senior (1 Year, Offshore)")
    assert (
        f"CREATE id={expected_id} 'E33F Second Home Senior (1 Year, Offshore)': 14.000.000 IDR"
        in out
    )
    assert "updates=0 deletes=0" in out and out.rstrip().endswith(
        "pass --apply to write"
    )
    assert "creates=1" in out


def test_a_missing_row_is_created_with_the_live_payload_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = _catalog()
    rec = _Recorder(monkeypatch, [_existing_point()])
    rc = _run(tmp_path, rec, catalog, apply=True, create_missing=True)
    assert rc == 0
    [point] = rec.upserts
    name = "E33F Second Home Senior (1 Year, Offshore)"
    row = catalog["services"]["kitas_permits"]["E33F Offshore"]
    assert point["id"] == _md5_id("kitas_permits", name)
    assert set(point["payload"]) == LIVE_PAYLOAD_KEYS
    assert point["payload"] == {
        "text": prepare.generate_semantic_text(name, "kitas_permits", row, CONTACT),
        "name": name,
        "category": "kitas_permits",
        "price": "14.000.000 IDR",
        "duration": "",
        "validity": "1 year",
        "notes": "All-inclusive price.",
        "source_type": "bali_zero_pricing",
        "last_updated": "2026-10-15",
        "currency": "IDR",
    }
    assert list(point["vector"]) == ["dense"] and len(point["vector"]["dense"]) == 1536
    assert rec.embedded == [point["payload"]["text"]]
    assert "CREATED 1 point(s) in bali_zero_pricing_hybrid" in capsys.readouterr().out


def test_tier_rows_carry_the_sync_price_shape_once_in_their_text() -> None:
    catalog = {
        "metadata": {"currency": "IDR", "contact": CONTACT},
        "services": {
            "tax_accounting": {
                "monthly_tax_basic": {
                    "Tier 0-50": {
                        "name": "Monthly Tax Report — 0 to 50 transactions",
                        "price": "",
                        "tier_range": ["1.800.000 IDR", "2.000.000 IDR"],
                    }
                }
            }
        },
    }
    [create], refusals = sync_mod.plan_creates([], catalog, "2026-10-15")
    assert refusals == []
    assert create["payload"]["category"] == "tax_accounting/monthly_tax_basic"
    assert create["payload"]["price"] == "1.800.000 - 2.000.000 IDR"
    assert create["payload"]["text"].count("1.800.000 - 2.000.000 IDR") == 1


def test_the_real_catalogue_plans_one_create_per_priced_public_row() -> None:
    catalog = json.loads(sync_mod.DEFAULT_CATALOG.read_text(encoding="utf-8"))
    public = [
        row.get("name", key)
        for _c, key, row in sync_mod._iter_service_rows(catalog["services"])
    ]
    creates, refusals = sync_mod.plan_creates([], catalog, "2026-10-15")
    assert refusals == []
    assert sorted(c["name"] for c in creates) == sorted(public)
    assert not {c["name"] for c in creates} & sync_mod.internal_catalog_names(catalog)
    assert len({c["id"] for c in creates}) == len(creates)
    assert all(c["payload"]["text"].count(c["payload"]["price"]) == 1 for c in creates)
