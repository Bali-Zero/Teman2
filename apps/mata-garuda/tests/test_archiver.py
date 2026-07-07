"""Tests for the archiver worker (#4 — durable cold-store, stdlib SQLite)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mata_garuda.workers import archiver
from mata_garuda.workers.archiver import StreamArchive, run_archiver


def _enriched(msg_id, **data):
    return {"id": msg_id, "data": data}


class TestStreamArchive:
    def test_archive_inserts_new_row(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        assert a.archive("1-0", {"content_hash": "h1", "title": "t", "url": "u"}) is True
        assert a.count() == 1
        a.close()

    def test_archive_idempotent_on_content_hash(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        assert a.archive("1-0", {"content_hash": "h1", "title": "t"}) is True
        # same hash, different stream id → must NOT double-insert
        assert a.archive("2-0", {"content_hash": "h1", "title": "t-again"}) is False
        assert a.count() == 1
        a.close()

    def test_falls_back_to_url_then_title_for_hash(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        # no content_hash → uses url as the dedup key
        assert a.archive("1-0", {"url": "http://x/1", "title": "t"}) is True
        assert a.archive("2-0", {"url": "http://x/1", "title": "t2"}) is False  # same url
        assert a.count() == 1
        a.close()

    def test_persists_across_reopen(self, tmp_path: Path):
        p = tmp_path / "a.db"
        a = StreamArchive(db_path=p)
        a.archive("1-0", {"content_hash": "h1"})
        a.close()
        b = StreamArchive(db_path=p)   # reopen — durable, survives process death
        assert b.count() == 1
        b.close()


class TestRunArchiver:
    def _run(self, items, archive):
        with patch.object(archiver, "stream_read_new", return_value=items), \
             patch.object(archiver, "stream_ack", return_value=True) as m_ack:
            stats = run_archiver(archive, max_items=100)
        return stats, m_ack

    def test_archives_and_acks_new_items(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        stats, m_ack = self._run([
            _enriched("1-0", content_hash="h1", title="a"),
            _enriched("2-0", content_hash="h2", title="b"),
        ], a)
        assert stats["archived"] == 2 and stats["processed"] == 2
        assert m_ack.call_count == 2          # both acked
        assert a.count() == 2
        a.close()

    def test_duplicate_is_acked_not_replayed(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        a.archive("0-0", {"content_hash": "dup"})   # pre-existing
        stats, m_ack = self._run([_enriched("1-0", content_hash="dup", title="x")], a)
        assert stats["duplicates"] == 1 and stats["archived"] == 0
        m_ack.assert_called_once()             # dupe MUST ack (else PEL grows forever)
        a.close()

    def test_empty_stream_no_error(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        stats, _ = self._run([], a)
        assert stats == {"processed": 0, "archived": 0, "duplicates": 0, "errors": 0}
        a.close()

    def test_error_does_not_ack(self, tmp_path: Path):
        a = StreamArchive(db_path=tmp_path / "a.db")
        with patch.object(archiver, "stream_read_new",
                          return_value=[_enriched("1-0", content_hash="h")]), \
             patch.object(a, "archive", side_effect=RuntimeError("boom")), \
             patch.object(archiver, "stream_ack") as m_ack:
            stats = run_archiver(a, max_items=10)
        assert stats["errors"] == 1
        m_ack.assert_not_called()              # at-least-once: no ack on error
        a.close()
