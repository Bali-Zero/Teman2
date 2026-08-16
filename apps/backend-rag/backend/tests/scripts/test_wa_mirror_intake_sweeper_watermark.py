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
import re
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


def _wire(
    monkeypatch, wms, *, rows, watermark_seed, upsert=None, enqueue=None, tg_notify=None
):
    """Monkeypatch everything run_one_tick() needs, none of it real I/O.

    ``_tg_notify`` defaults to a no-op stub: without it, the poison-breaker
    (verbale #3) would spawn a REAL subprocess against scripts/tg_notify.py
    on every test that hits ANY poison row, writing to the live
    ``~/.organism/tg_spool`` outside tmp_path (W96 — test-writes-prod).
    """
    monkeypatch.setattr(wms.asyncpg, "create_pool", _fake_create_pool(rows))
    monkeypatch.setattr(wms, "_sweep_text_clients", _noop_text_sweep)
    monkeypatch.setattr(wms, "_load_watermark", lambda: watermark_seed)
    saved: dict[str, int] = {}
    monkeypatch.setattr(wms, "_save_watermark", lambda v: saved.__setitem__("wm", v))
    monkeypatch.setattr(
        wms, "_upsert_client_by_phone", upsert or _default_upsert
    )
    monkeypatch.setattr(wms, "enqueue", enqueue or _default_enqueue)
    monkeypatch.setattr(wms, "_tg_notify", tg_notify or _default_tg_notify)
    return saved


def _default_tg_notify(_tier: str, _dedup_key: str, _text: str) -> bool:
    return True


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
    assert wms._is_transient(asyncpg.UndefinedTableError("no such table")) is False
    assert wms._is_transient(asyncpg.UniqueViolationError("dup key")) is False


# --------------------------------------------------------------------------- #
# Widened transient set (verbale #1, post-refuter Qwen 3.8 Max, 2026-08-17):
# retryable Postgres classes the original connectivity-only tuple missed.
# --------------------------------------------------------------------------- #
def test_is_transient_classifies_widened_retryable_postgres_errors() -> None:
    wms = _load_sweeper()
    assert wms._is_transient(asyncpg.QueryCanceledError("canceled")) is True
    assert wms._is_transient(asyncpg.DeadlockDetectedError("deadlock")) is True
    assert wms._is_transient(asyncpg.SerializationError("serialization")) is True
    # OperatorInterventionError family (admin shutdown / crash / maintenance).
    assert wms._is_transient(asyncpg.OperatorInterventionError("intervention")) is True
    assert wms._is_transient(asyncpg.AdminShutdownError("admin shutdown")) is True
    assert wms._is_transient(asyncpg.CrashShutdownError("crash shutdown")) is True
    assert wms._is_transient(asyncpg.CannotConnectNowError("cannot connect now")) is True
    assert wms._is_transient(asyncpg.IdleSessionTimeoutError("idle timeout")) is True
    # InsufficientResourcesError family (OOM / too many conns / disk full).
    assert wms._is_transient(asyncpg.InsufficientResourcesError("resources")) is True
    assert wms._is_transient(asyncpg.OutOfMemoryError("oom")) is True
    assert wms._is_transient(asyncpg.TooManyConnectionsError("too many conns")) is True
    assert wms._is_transient(asyncpg.DiskFullError("disk full")) is True
    assert wms._is_transient(asyncpg.PostgresSystemError("system error")) is True


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
    """Verbale #2 (post-refuter Qwen 3.8 Max, P1): a PERMANENT CRM-upsert
    failure must NOT drop the media document. Only the CRM identity hint is
    lost — row N still reaches ``enqueue()`` with ``client_id_hint=None``
    (review/OCR still happens, it just isn't pre-linked to a client), and
    row N+1 gets its own fresh CRM upsert attempt and its own hint.
    """
    row_n = _row(200, blob_path=_write_blob(tmp_path, "n.pdf"))
    row_n1 = _row(201, blob_path=_write_blob(tmp_path, "n1.pdf"))
    upsert_calls: list[int] = []
    enqueue_calls: list[str] = []
    enqueue_hints: dict[str, int | None] = {}

    async def flaky_upsert(_conn, *, raw_phone, **_kw):
        upsert_calls.append(1)
        if raw_phone == row_n["sender_phone"]:
            raise RuntimeError("constraint violation — permanent")
        return 42

    async def recording_enqueue(_pool, *, source_ref, client_id_hint, **_kw):
        enqueue_calls.append(source_ref)
        enqueue_hints[source_ref] = client_id_hint
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
    ref_n = f"wa-mirror:{row_n['baileys_message_id']}"
    ref_n1 = f"wa-mirror:{row_n1['baileys_message_id']}"
    # Both rows reach enqueue() — row N's document is KEPT despite the CRM
    # failure, just with no client-identity hint; row N+1 gets its real hint.
    assert enqueue_calls == [ref_n, ref_n1]
    assert enqueue_hints[ref_n] is None
    assert enqueue_hints[ref_n1] == 42
    assert saved.get("wm") == 201
    # crm_poison counts the CRM-identity loss; the enqueue-level `poison`
    # counter stays 0 (word-boundary match so `crm_poison=1` in the same
    # message can't make a bare "poison=0" assertion pass by substring —
    # `_` is a word char, so `\bpoison=` never matches inside `crm_poison=`).
    assert any(re.search(r"\bcrm_poison=1\b", r.message) for r in caplog.records)
    assert any(re.search(r"(?<!crm_)\bpoison=0\b", r.message) for r in caplog.records)


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


# --------------------------------------------------------------------------- #
# Blob pre-check (verbale #4, post-refuter Qwen 3.8 Max, P2).
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_blob_path_is_a_directory_counts_as_missing_and_advances(
    monkeypatch, tmp_path, caplog
) -> None:
    """A directory (or unreadable file) at ``media_stored_path`` must be
    counted as a missing blob and advanced past — NOT treated as a transient
    OSError. ``os.path.exists()`` passes for a directory too, and
    ``compute_blob_hash()``'s bare ``open(blob_path, "rb")`` would then raise
    ``IsADirectoryError`` (an ``OSError`` subclass), which ``_is_transient()``
    misclassifies as retryable — freezing the watermark on that row forever.
    ``os.path.isfile()`` + ``os.access(..., os.R_OK)`` catch it HERE, before
    enqueue()/compute_blob_hash() ever opens the path.
    """
    bad_dir = tmp_path / "not_a_file"
    bad_dir.mkdir()
    row_n = _row(500, blob_path=str(bad_dir))
    enqueue_calls: list[str] = []

    async def recording_enqueue(_pool, *, source_ref, **_kw):
        enqueue_calls.append(source_ref)
        return SimpleNamespace(was_new=True)

    wms = _load_sweeper()
    saved = _wire(
        monkeypatch, wms, rows=[row_n], watermark_seed=499, enqueue=recording_enqueue
    )

    with caplog.at_level(logging.INFO, logger="wa_mirror_sweeper"):
        rc = await wms.run_one_tick()

    assert rc == 0
    assert enqueue_calls == []
    assert saved.get("wm") == 500
    assert any("blob_missing=1" in r.message for r in caplog.records)


# --------------------------------------------------------------------------- #
# Poison breaker (verbale #3, post-refuter Qwen 3.8 Max, P1). The tick used to
# `return 0` unconditionally regardless of how many rows were poisoned.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_poison_breaker_no_call_when_zero_poison(monkeypatch, tmp_path) -> None:
    """Zero poison rows this tick -> the breaker stays completely silent."""
    row_n = _row(600, blob_path=_write_blob(tmp_path, "n.pdf"))
    tg_calls: list[tuple[str, str, str]] = []

    def recording_tg_notify(tier: str, dedup_key: str, text: str) -> bool:
        tg_calls.append((tier, dedup_key, text))
        return True

    wms = _load_sweeper()
    _wire(
        monkeypatch, wms, rows=[row_n], watermark_seed=599, tg_notify=recording_tg_notify
    )

    rc = await wms.run_one_tick()

    assert rc == 0
    assert tg_calls == []


@pytest.mark.asyncio
async def test_poison_breaker_digest_only_below_storm_threshold(
    monkeypatch, tmp_path
) -> None:
    """One poison row, well below the storm threshold (max(5, ceil(0.2*2))=5):
    exactly one digest-tier line, no P0, tick still returns 0."""
    row_n = _row(700, blob_path=_write_blob(tmp_path, "n.pdf"))
    row_n1 = _row(701, blob_path=_write_blob(tmp_path, "n1.pdf"))
    tg_calls: list[tuple[str, str, str]] = []

    def recording_tg_notify(tier: str, dedup_key: str, text: str) -> bool:
        tg_calls.append((tier, dedup_key, text))
        return True

    async def flaky_enqueue(_pool, *, source_ref, **_kw):
        if source_ref == f"wa-mirror:{row_n['baileys_message_id']}":
            raise ValueError("malformed payload — permanent")
        return SimpleNamespace(was_new=True)

    wms = _load_sweeper()
    _wire(
        monkeypatch,
        wms,
        rows=[row_n, row_n1],
        watermark_seed=699,
        enqueue=flaky_enqueue,
        tg_notify=recording_tg_notify,
    )

    rc = await wms.run_one_tick()

    assert rc == 0
    assert [c[0] for c in tg_calls] == ["digest"]
    assert tg_calls[0][1].startswith("wa-mirror-sweeper:poison:")
    assert re.search(r"(?<!crm_)\bpoison=1\b", tg_calls[0][2])
    # Counts only — no row id or phone in the Telegram text (Law 2 / UU-PDP).
    assert str(row_n["id"]) not in tg_calls[0][2]
    assert row_n["sender_phone"] not in tg_calls[0][2]


@pytest.mark.asyncio
async def test_poison_breaker_p0_and_rc2_on_storm(monkeypatch, tmp_path) -> None:
    """poison >= max(5, ceil(0.2*scanned)) is a STORM: a P0 fires (in addition
    to the digest line) and the tick returns 2 so launchd marks the run
    FAILED instead of green — the failure mode this breaker exists to catch.
    """
    rows = [_row(800 + i, blob_path=_write_blob(tmp_path, f"n{i}.pdf")) for i in range(5)]
    tg_calls: list[tuple[str, str, str]] = []

    def recording_tg_notify(tier: str, dedup_key: str, text: str) -> bool:
        tg_calls.append((tier, dedup_key, text))
        return True

    async def always_poison_enqueue(_pool, *, source_ref, **_kw):
        raise ValueError("malformed payload — permanent")

    wms = _load_sweeper()
    _wire(
        monkeypatch,
        wms,
        rows=rows,
        watermark_seed=799,
        enqueue=always_poison_enqueue,
        tg_notify=recording_tg_notify,
    )

    rc = await wms.run_one_tick()

    assert rc == 2
    assert [c[0] for c in tg_calls] == ["digest", "p0"]
    assert tg_calls[1][1] == "wa-mirror-sweeper:poison-storm"
    assert "poison=5/5" in tg_calls[1][2]
