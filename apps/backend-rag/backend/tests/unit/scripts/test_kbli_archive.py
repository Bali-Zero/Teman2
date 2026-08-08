"""Unit tests for ``_kbli_archive.py`` — the shared versioned-archive helper.

No DB, no network: a minimal asyncpg stand-in tracks INSERT calls and
simulates ``ON CONFLICT (kode_kbli, cure_run) DO NOTHING`` idempotency.

These pin the versioning cure (2026-08-08): ``kbli_documents_archive`` was
one-shot per code (``UNIQUE(kode_kbli)`` + ``ON CONFLICT DO NOTHING``), so a
second cure of the same code silently preserved nothing. Migration 269 +
this module replace that with ``UNIQUE(kode_kbli, cure_run)`` so each
successive cure snapshot survives.

KNOWN LIMIT: the fake mirrors the module's SQL textually; the PG-level
contract is exercised only in prod — a real-PG harness is deliberately out
of unit scope.
"""

from __future__ import annotations

import json

import pytest

from backend.scripts._kbli_archive import (
    archive_row,
    ensure_archive_schema,
)


class _FakeArchiveConn:
    """Minimal asyncpg stand-in for the archive table.

    Simulates ``ON CONFLICT (kode_kbli, cure_run) DO NOTHING`` by tracking
    inserted rows in an in-memory list and deduplicating on
    ``(kode_kbli, cure_run)``.
    """

    def __init__(self, *, has_cure_run: bool = True, has_constraint: bool = True) -> None:
        self.has_cure_run = has_cure_run
        self.has_constraint = has_constraint
        self.rows: list[dict] = []
        self.execute_calls: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        if "INSERT INTO kbli_documents_archive" in query:
            self._simulate_insert(query, args)
        return "INSERT 0 1"

    def _simulate_insert(self, query: str, args: tuple) -> None:
        if "archived_reason" in query:
            cure_run = args[7]
            archived_reason = args[6]
        else:
            cure_run = args[6]
            archived_reason = None
        row = {
            "kode_kbli": args[0],
            "judul": args[1],
            "content": args[2],
            "metadata": args[3],
            "original_created_at": args[4],
            "original_updated_at": args[5],
            "cure_run": cure_run,
            "archived_reason": archived_reason,
        }
        exists = any(
            r["kode_kbli"] == row["kode_kbli"] and r["cure_run"] == row["cure_run"]
            for r in self.rows
        )
        if not exists:
            self.rows.append(row)

    async def fetchval(self, query: str, *_args: object) -> bool:
        if "pg_constraint" in query:
            return self.has_constraint
        return self.has_cure_run


_PARAMS = (
    "50113",
    "STALE TITLE",
    "stale fabricated markdown",
    json.dumps({"per_skala": [{"kategori_risiko": "Menengah Tinggi"}]}),
    "2026-02-17T23:20:37",
    "2026-02-17T23:20:37",
)


# ---------------------------------------------------------------------------
# (a) Two DIFFERENT cure_runs on one code => TWO rows, older intact
# ---------------------------------------------------------------------------


async def test_two_different_cure_runs_produce_two_rows_older_intact():
    conn = _FakeArchiveConn()
    await archive_row(conn, "50113", _PARAMS, "kbli_documents_cure:2026-07-19")
    await archive_row(conn, "50113", _PARAMS, "kbli_documents_cure:2026-08-03")

    rows_for_code = [r for r in conn.rows if r["kode_kbli"] == "50113"]
    assert len(rows_for_code) == 2

    cure_runs = {r["cure_run"] for r in rows_for_code}
    assert cure_runs == {"kbli_documents_cure:2026-07-19", "kbli_documents_cure:2026-08-03"}

    # The older row's content survives untouched — the whole point of versioning.
    older = next(r for r in rows_for_code if r["cure_run"] == "kbli_documents_cure:2026-07-19")
    assert older["content"] == "stale fabricated markdown"


# ---------------------------------------------------------------------------
# (b) SAME cure_run twice => ONE row (idempotency within a cure pass)
# ---------------------------------------------------------------------------


async def test_same_cure_run_twice_produces_one_row():
    conn = _FakeArchiveConn()
    await archive_row(conn, "50113", _PARAMS, "kbli_documents_cure:2026-07-19")
    await archive_row(conn, "50113", _PARAMS, "kbli_documents_cure:2026-07-19")

    rows_for_code = [r for r in conn.rows if r["kode_kbli"] == "50113"]
    assert len(rows_for_code) == 1


# ---------------------------------------------------------------------------
# (c) ensure_archive_schema on a table lacking cure_run => RuntimeError
# ---------------------------------------------------------------------------


async def test_ensure_archive_schema_raises_when_cure_run_absent():
    conn = _FakeArchiveConn(has_cure_run=False)
    with pytest.raises(RuntimeError, match="269_kbli_archive_versioning"):
        await ensure_archive_schema(conn)


# ---------------------------------------------------------------------------
# INNOCENCE: ensure_archive_schema passes when cure_run is present
# ---------------------------------------------------------------------------


async def test_ensure_archive_schema_passes_when_cure_run_present():
    conn = _FakeArchiveConn(has_cure_run=True)
    await ensure_archive_schema(conn)
    assert len(conn.execute_calls) >= 1  # DDL ran, no exception


# ---------------------------------------------------------------------------
# ensure_archive_schema on a table lacking the composite constraint => RuntimeError
# ---------------------------------------------------------------------------


async def test_ensure_archive_schema_raises_when_constraint_absent():
    """A partially-migrated table (column present, constraint dropped by a
    ROLLBACK) must fail loudly here rather than at the first confusing INSERT."""
    conn = _FakeArchiveConn(has_cure_run=True, has_constraint=False)
    with pytest.raises(RuntimeError, match="kbli_documents_archive_code_run_key"):
        await ensure_archive_schema(conn)


# ---------------------------------------------------------------------------
# archived_reason is correctly threaded to the INSERT
# ---------------------------------------------------------------------------


async def test_archive_row_passes_archived_reason_when_given():
    conn = _FakeArchiveConn()
    reason = "kbli_documents_phantom_cure: pre-cure KBLI-2020 phantom-row snapshot (2026-07-24)"
    await archive_row(conn, "82920", _PARAMS, "kbli_documents_phantom_cure:2026-07-24",
                     archived_reason=reason)
    assert conn.rows[0]["archived_reason"] == reason


async def test_archive_row_omits_archived_reason_when_none():
    """When archived_reason is None the table default applies — the INSERT
    must not carry a $7 reason placeholder."""
    conn = _FakeArchiveConn()
    await archive_row(conn, "50113", _PARAMS, "kbli_documents_cure:2026-07-19")
    insert_call = next(c for c in conn.execute_calls if "INSERT" in c[0])
    assert "archived_reason" not in insert_call[0]


# ---------------------------------------------------------------------------
# ON CONFLICT target is the composite (kode_kbli, cure_run), not bare kode_kbli
# ---------------------------------------------------------------------------


def test_archive_row_sql_uses_composite_conflict_target():
    """SCAR PIN: the one-shot disease was ``ON CONFLICT (kode_kbli)``. The
    versioning cure lives in the conflict TARGET, not just the column list."""
    import inspect

    from backend.scripts import _kbli_archive

    source = inspect.getsource(_kbli_archive.archive_row)
    assert "ON CONFLICT (kode_kbli, cure_run)" in source
