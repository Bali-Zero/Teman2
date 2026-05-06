"""Tests for KnowledgeBase resilience hardening.

Background (2026-05-06): nlm-feeder logged 2 transient errors out of 106
runs: `sqlite3.OperationalError: disk I/O error` followed once by
`unable to open database file`. Root cause: KB opened with default
busy_timeout=0, returning immediately on any momentary lock contention,
combined with no parent-dir mkdir guard (prompt's claim, currently
already handled but only when parent exists at instance creation time).

Hardening:
  1. busy_timeout > 0 (default 5s) so a lock contention waits, not raises.
  2. journal_mode WAL to allow concurrent reads with a writer.
  3. Parent dir always created idempotently (safety net for
     ~/.mata-garuda/-style alternate paths if user redirects DEFAULT_DB_PATH).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


class TestKnowledgeBaseResilience:
    def test_init_creates_parent_dir(self, tmp_path):
        """KB.__init__ creates the parent directory if missing (idempotent)."""
        from mata_garuda.runtime.knowledge import KnowledgeBase

        nested = tmp_path / "deeply" / "nested" / "data"
        assert not nested.exists()

        kb = KnowledgeBase(db_path=nested / "kb.db")
        try:
            assert nested.exists()
            assert (nested / "kb.db").exists()
        finally:
            kb.close()

    def test_busy_timeout_set_nonzero(self, tmp_path):
        """KB sets busy_timeout > 0 to wait on transient lock contention."""
        from mata_garuda.runtime.knowledge import KnowledgeBase

        kb = KnowledgeBase(db_path=tmp_path / "kb.db")
        try:
            cursor = kb._conn.execute("PRAGMA busy_timeout")
            timeout_ms = cursor.fetchone()[0]
            # We expect at least 1s — current default in code = 0 (the bug).
            assert timeout_ms >= 1000, (
                f"busy_timeout={timeout_ms}ms — must be >= 1000 to ride out "
                "transient WAL lock contention from concurrent writers."
            )
        finally:
            kb.close()

    def test_journal_mode_wal(self, tmp_path):
        """KB uses WAL journal mode for concurrent read while writer holds lock."""
        from mata_garuda.runtime.knowledge import KnowledgeBase

        kb = KnowledgeBase(db_path=tmp_path / "kb.db")
        try:
            cursor = kb._conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal", f"journal_mode={mode}, expected wal"
        finally:
            kb.close()

    def test_concurrent_open_no_io_error(self, tmp_path):
        """Two concurrent KB instances both write without raising disk I/O error.

        Reproduces the failure mode observed 2026-05-06: a feeder run
        spawned while a previous run still held the WAL lock raised
        sqlite3.OperationalError: disk I/O error. With busy_timeout
        and WAL mode, the second open should succeed.
        """
        from mata_garuda.runtime.knowledge import KnowledgeBase

        db_path = tmp_path / "kb.db"

        kb1 = KnowledgeBase(db_path=db_path)
        kb2 = KnowledgeBase(db_path=db_path)
        try:
            kb1.store("a1", "t", "c1", "s1", 0.5)
            kb2.store("a2", "t", "c2", "s2", 0.5)
            # both writes visible to a fresh reader
            kb3 = KnowledgeBase(db_path=db_path)
            try:
                rows = kb3.get_by_type("t", limit=10)
                assert len(rows) == 2
            finally:
                kb3.close()
        finally:
            kb1.close()
            kb2.close()
