"""Pure watermark-classification tests for the wa-mirror intake sweeper (dossier C-31).

DEFECT: in the media loop, an exception from `enqueue()` and from the CRM phone
upsert did a bare `except Exception: ... break` WITHOUT advancing `max_done`.
That is correct for a TRANSIENT failure (DB/connection hiccup — retry the same
row next tick) but wrong for a PERMANENT one (bad data, a constraint
violation): breaking without advancing the watermark freezes it on that row
forever and starves every later media row behind it.

These tests never touch a real database (W96) — `asyncpg.create_pool` is
monkeypatched to a fake pool, `enqueue()` and `_upsert_client_by_phone()` are
monkeypatched directly so each test controls exactly which row raises what,
and `_load_watermark`/`_save_watermark` are monkeypatched the same way the
existing end-to-end test in this directory already does (never touches
``~/.cell-bridge-state``).
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import asyncpg
import pytest

# test file: apps/backend-rag/backend/tests/scripts/<this>
# parents: [0]=scripts [1]=tests [2]=backend [3]=backend-rag [4]=apps [5]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SWEEPER_PATH = _REPO_ROOT / "scripts" / "wa_mirror_intake_sweeper.py"


def _load_sweeper():
    spec = importlib.util.spec_from_file_location("wms_watermark_under_test", _SWEEPER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Minimal fake pool/conn — just enough surface for run_one_tick()'s media
# loop: one `SELECT` (via conn.fetch, answered with a canned row list) and a
# `conn.transaction()` context manager the CRM-upsert branch enters. The CRM
# upsert itself and enqueue() are monkeypatched directly per-test, so this
# fake conn is never asked a real query.
# --------------------------------------------------------------------------- #
class _NullTx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    async def fetch(self, _query: str, *_args: Any) -> list[dict[str, Any]]:
        return self._rows

    def transaction(self):
        return _NullTx()


class _FakeAcquireCtx:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, rows: list[dict[str, Any]]):
        self._conn = _FakeConn(rows)

    def acquire(self):
        return _FakeAcquireCtx(self._conn)

    async def close(self) -> None:
        pass


def _row(rid: int, *, blob_path: str, bmid: str | None = None) -> dict[str, Any]:
    return {
        "id": rid,
        "baileys_message_id": bmid or f"bmid-{rid}",
        "media_stored_path": blob_path,
        "media_mime": "application/pdf",
        "media_type": "document",
        "team_member_email": "ari@balizero.com",
        "sender_phone": f"+62899000{rid:04d}",
        "counterpart_phone": None,
        "phone_number": None,
        "sender_push_name_snapshot": None,
        "chat_type": "direct",
        "group_jid": None,
        "group_subject_snapshot": None,
    }


def _wire(monkeypatch, wms, *, rows, watermark_seed, upsert=None, enqueue=None):
    """Monkeypatch everything run_one_tick() needs, none of it real I/O."""
    monkeypatch.setattr(wms.asyncpg, "create_pool", _fake_create_pool(rows))
    monkeypatch.setattr(wms, "_sweep_text_clients", _noop_text_sweep)
    monkeypatch.setattr(wms, "_load_watermark", lambda: watermark_seed)
    saved: dict[str, int] = {}
    monkeypatch.setattr(wms, "_save_watermark", lambda v: saved.__setitem__("wm", v))
    monkeypatch.setattr(
        wms, "_upsert_client_by_phone", upsert or _default_upsert
    )
    monkeypatch.setattr(wms, "enqueue", enqueue or _default_enqueue)
    return saved


def _fake_create_pool(rows: list[dict[str, Any]]):
    async def _create(*_a: Any, **_kw: Any) -> _FakePool:
        return _FakePool(rows)

    return _create


async def _noop_text_sweep(_pool: Any, _batch: int) -> dict[str, int]:
    return {"scanned": 0, "resolved": 0, "skipped": 0}


async def _default_upsert(*_a: Any, **_kw: Any) -> int:
    return 1


async def _default_enqueue(*_a: Any, **_kw: Any) -> SimpleNamespace:
    return SimpleNamespace(was_new=True)


def _write_blob(tmp_path: Path, name: str) -> str:
    p = tmp_path / name
    p.write_bytes(b"synthetic")
    return str(p)


# --------------------------------------------------------------------------- #
# The classifier itself.
# --------------------------------------------------------------------------- #
def test_is_transient_classifies_connectivity_errors() -> None:
    wms = _load_sweeper()
    assert wms._is_transient(asyncpg.PostgresConnectionError("conn lost")) is True
    assert wms._is_transient(asyncpg.InterfaceError("bad interface")) is True
    assert wms._is_transient(OSError("disk gone")) is True
    assert wms._is_transient(TimeoutError("timed out")) is True
    assert wms._is_transient(asyncio.TimeoutError()) is True


def test_is_transient_rejects_everything_else_as_permanent() -> None:
    wms = _load_sweeper()
    assert wms._is_transient(ValueError("bad payload")) is False
    assert wms._is_transient(asyncpg.DataError("bad data")) is False
    assert wms._is_transient(KeyError("missing")) is False
    assert wms._is_transient(RuntimeError("assertion")) is False


# --------------------------------------------------------------------------- #
# GUILT — a permanent failure must not freeze the watermark.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_permanent_enqueue_error_advances_watermark_past_poison_row(
    monkeypatch, tmp_path, caplog
) -> None:
    row_n = _row(100, blob_path=_write_blob(tmp_path, "n.pdf"))
    row_n1 = _row(101, blob_path=_write_blob(tmp_path, "n1.pdf"))
    enqueue_calls: list[str] = []

    async def flaky_enqueue(_pool, *, source_ref, **_kw):
        enqueue_calls.append(source_ref)
        if source_ref == f"wa-mirror:{row_n['baileys_message_id']}":
            raise ValueError("malformed payload — permanent")
        return SimpleNamespace(was_new=True)

    wms = _load_sweeper()
    saved = _wire(
        monkeypatch, wms, rows=[row_n, row_n1], watermark_seed=99, enqueue=flaky_enqueue
    )

    with caplog.at_level(logging.INFO, logger="wa_mirror_sweeper"):
        rc = await wms.run_one_tick()

    assert rc == 0
    # N+1 was reached and enqueued in the SAME tick — the poison row didn't block it.
    assert enqueue_calls == [
        f"wa-mirror:{row_n['baileys_message_id']}",
        f"wa-mirror:{row_n1['baileys_message_id']}",
    ]
    # Watermark advances PAST the poison row (to 101), not frozen at 99/100.
    assert saved.get("wm") == 101
    assert any("poison=1" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_permanent_crm_upsert_error_advances_watermark_and_still_enqueues_next(
    monkeypatch, tmp_path, caplog
) -> None:
    row_n = _row(200, blob_path=_write_blob(tmp_path, "n.pdf"))
    row_n1 = _row(201, blob_path=_write_blob(tmp_path, "n1.pdf"))
    upsert_calls: list[int] = []
    enqueue_calls: list[str] = []

    async def flaky_upsert(_conn, *, raw_phone, **_kw):
        upsert_calls.append(1)
        if raw_phone == row_n["sender_phone"]:
            raise RuntimeError("constraint violation — permanent")
        return 1

    async def recording_enqueue(_pool, *, source_ref, **_kw):
        enqueue_calls.append(source_ref)
        return SimpleNamespace(was_new=True)

    wms = _load_sweeper()
    saved = _wire(
        monkeypatch,
        wms,
        rows=[row_n, row_n1],
        watermark_seed=199,
        upsert=flaky_upsert,
        enqueue=recording_enqueue,
    )

    with caplog.at_level(logging.INFO, logger="wa_mirror_sweeper"):
        rc = await wms.run_one_tick()

    assert rc == 0
    # Row N's CRM upsert died -> row N is SKIPPED (never reaches enqueue), but
    # row N+1 still gets a fresh CRM upsert attempt and IS enqueued.
    assert enqueue_calls == [f"wa-mirror:{row_n1['baileys_message_id']}"]
    assert saved.get("wm") == 201
    assert any("poison=1" in r.message for r in caplog.records)


# --------------------------------------------------------------------------- #
# INNOCENCE — a transient failure must still freeze the watermark (unchanged
# pre-fix behavior: retry the same row next tick, don't touch later rows).
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_transient_enqueue_error_does_not_advance_watermark(
    monkeypatch, tmp_path, caplog
) -> None:
    row_n = _row(300, blob_path=_write_blob(tmp_path, "n.pdf"))
    row_n1 = _row(301, blob_path=_write_blob(tmp_path, "n1.pdf"))
    enqueue_calls: list[str] = []

    async def flaky_enqueue(_pool, *, source_ref, **_kw):
        enqueue_calls.append(source_ref)
        raise asyncpg.PostgresConnectionError("connection reset")

    wms = _load_sweeper()
    saved = _wire(
        monkeypatch, wms, rows=[row_n, row_n1], watermark_seed=299, enqueue=flaky_enqueue
    )

    with caplog.at_level(logging.INFO, logger="wa_mirror_sweeper"):
        rc = await wms.run_one_tick()

    assert rc == 0
    # Only row N was even attempted — the transient break stops the tick cold.
    assert enqueue_calls == [f"wa-mirror:{row_n['baileys_message_id']}"]
    # Watermark never moves: no _save_watermark call at all (max_done == seed).
    assert "wm" not in saved
    assert any("poison=0" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_transient_crm_upsert_error_does_not_advance_watermark(
    monkeypatch, tmp_path, caplog
) -> None:
    row_n = _row(400, blob_path=_write_blob(tmp_path, "n.pdf"))
    row_n1 = _row(401, blob_path=_write_blob(tmp_path, "n1.pdf"))
    enqueue_calls: list[str] = []

    async def flaky_upsert(_conn, **_kw):
        raise OSError("disk full")

    async def recording_enqueue(_pool, *, source_ref, **_kw):
        enqueue_calls.append(source_ref)
        return SimpleNamespace(was_new=True)

    wms = _load_sweeper()
    saved = _wire(
        monkeypatch,
        wms,
        rows=[row_n, row_n1],
        watermark_seed=399,
        upsert=flaky_upsert,
        enqueue=recording_enqueue,
    )

    with caplog.at_level(logging.INFO, logger="wa_mirror_sweeper"):
        rc = await wms.run_one_tick()

    assert rc == 0
    # enqueue() is never reached for row N, and row N+1 is never scanned either.
    assert enqueue_calls == []
    assert "wm" not in saved
    assert any("poison=0" in r.message for r in caplog.records)
