"""Tests for #5 summarize-then-store (nlm_rollup) — compaction Sink off the archive."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from mata_garuda.workers import nlm_rollup
from mata_garuda.workers.archiver import StreamArchive


def _seed(db: Path, items):
    """Seed an archive.db with rows. items = list of dicts."""
    a = StreamArchive(db_path=db)
    for it in items:
        a.archive(it.get("content_hash", it.get("url", it["title"])), it)
    a.close()


class TestRollup:
    def _run(self, db, add_return=True):
        with patch.object(nlm_rollup, "_post_digest", return_value=("sid-x" if add_return else None)) as m_add, \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          side_effect=lambda d: (d, f"nb-{d}") if d else ("", "")) as m_route:
            stats = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        return stats, m_add, m_route

    def test_groups_by_day_and_domain_one_source_each(self, tmp_path: Path):
        db = tmp_path / "archive.db"
        _seed(db, [
            {"title": "a", "url": "u1", "domain": "ai_research", "score": "5",
             "timestamp": "2026-06-30"},
            {"title": "b", "url": "u2", "domain": "ai_research", "score": "4",
             "timestamp": "2026-06-30"},
            {"title": "c", "url": "u3", "domain": "press", "score": "5",
             "timestamp": "2026-06-30"},
        ])
        stats, m_add, _ = self._run(db)
        # 2 groups (ai_research, press) → 2 NLM sources, NOT 3 (one per item)
        assert stats["posted"] == 2 and stats["groups"] == 2
        assert m_add.call_count == 2
        assert stats["items"] == 3

    def test_idempotent_second_run_skips(self, tmp_path: Path):
        db = tmp_path / "archive.db"
        _seed(db, [{"title": "a", "url": "u1", "domain": "ai_research", "score": "5",
                    "timestamp": "2026-06-30"}])
        s1, m1, _ = self._run(db)
        assert s1["posted"] == 1
        s2, m2, _ = self._run(db)             # second run: ledger says already posted
        assert s2["posted"] == 0 and s2["skipped_already"] == 1
        m2.assert_not_called()                 # never re-posts

    def test_low_score_excluded_from_digest(self, tmp_path: Path):
        db = tmp_path / "archive.db"
        _seed(db, [
            {"title": "hi", "url": "u1", "domain": "ai_research", "score": "5",
             "timestamp": "2026-06-30"},
            {"title": "lo", "url": "u2", "domain": "ai_research", "score": "1",
             "timestamp": "2026-06-30"},
        ])
        with patch.object(nlm_rollup, "_post_digest", return_value=True) as m_add, \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          return_value=("ai_research", "nb-x")):
            stats = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        # only the high-score item counted (ROLLUP_MIN_SCORE default 3)
        assert stats["items"] == 1
        body = m_add.call_args.args[2]
        assert "hi" in body and "lo" not in body

    def test_null_domain_routes_to_default(self, tmp_path: Path):
        db = tmp_path / "archive.db"
        _seed(db, [{"title": "x", "url": "u1", "domain": "", "score": "5",
                    "timestamp": "2026-06-30"}])
        with patch.object(nlm_rollup, "_post_digest", return_value=True), \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          side_effect=lambda d: (d, f"nb-{d}")) as m_route:
            stats = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        assert stats["posted"] == 1
        # routed with the default domain, not empty string
        assert any(c.args[0] == nlm_rollup.ROLLUP_DEFAULT_DOMAIN
                   for c in m_route.call_args_list)

    def test_failed_post_not_ledgered_retries_next_run(self, tmp_path: Path):
        db = tmp_path / "archive.db"
        _seed(db, [{"title": "a", "url": "u1", "domain": "ai_research", "score": "5",
                    "timestamp": "2026-06-30"}])
        s1, _, _ = self._run(db, add_return=False)   # NLM post fails
        assert s1["posted"] == 0 and s1["errors"] == 1
        # not ledgered → next run retries
        s2, m2, _ = self._run(db, add_return=True)
        assert s2["posted"] == 1
        m2.assert_called_once()

    def test_compaction_ratio_many_items_one_source(self, tmp_path: Path):
        db = tmp_path / "archive.db"
        _seed(db, [{"title": f"t{i}", "url": f"u{i}", "domain": "ai_research",
                    "score": "5", "timestamp": "2026-06-30"} for i in range(200)])
        stats, m_add, _ = self._run(db)
        # 200 items → ONE NLM source (the whole point of #5)
        assert stats["posted"] == 1 and m_add.call_count == 1
        assert stats["items"] == 200


    def test_runs_on_legacy_db_without_domain_column(self, tmp_path):
        """Regression: a DB created before the `domain` column must NOT crash the
        rollup (the live cron died 'no such column: domain' — it opened a raw
        sqlite3.connect, skipping StreamArchive's guarded ALTER). Opening via
        StreamArchive must migrate it first."""
        import sqlite3
        db = tmp_path / "legacy.db"
        # build a pre-domain archive table by hand (no domain column)
        c = sqlite3.connect(str(db))
        c.executescript("""
            CREATE TABLE archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE, stream_id TEXT, title TEXT, url TEXT,
                source TEXT, source_type TEXT, content TEXT, score TEXT,
                agent TEXT, harvested_ts TEXT,
                archived_at TEXT DEFAULT (datetime('now'))
            );
        """)
        c.execute("INSERT INTO archive (content_hash,title,url,score,archived_at) "
                  "VALUES ('h1','t','u','5',datetime('now'))")
        c.commit(); c.close()
        # must run without 'no such column: domain'
        with patch.object(nlm_rollup, "_post_digest", return_value=True), \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          side_effect=lambda d: (d, f"nb-{d}")):
            stats = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        assert stats["errors"] == 0
        assert stats["posted"] == 1   # the row rolled up under the default domain


    def test_skip_when_count_unchanged_but_replace_when_grown(self, tmp_path):
        """Idempotency by COUNT: same count → skip; grew → delete old + re-post
        (prevents the duplicate 'Intel rollup' sources seen live 2026-06-30)."""
        from unittest.mock import patch
        db = tmp_path / "a.db"
        _seed(db, [{"title": "a", "url": "u1", "domain": "ai_research", "score": "5",
                    "timestamp": "2026-06-30"}])
        with patch.object(nlm_rollup, "_post_digest", return_value="sid-1"), \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          return_value=("ai_research", "nb-x")):
            s1 = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        assert s1["posted"] == 1
        # run again, SAME data → unchanged → skip, no delete, no post
        with patch.object(nlm_rollup, "_post_digest", return_value="sid-2") as m_post, \
             patch.object(nlm_rollup, "_delete_source") as m_del, \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          return_value=("ai_research", "nb-x")):
            s2 = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        assert s2["skipped_already"] == 1 and s2["posted"] == 0
        m_post.assert_not_called(); m_del.assert_not_called()
        # now the day GROWS → must delete sid-1 and post fresh
        _seed(db, [{"title": "b", "url": "u2", "domain": "ai_research", "score": "5",
                    "timestamp": "2026-06-30"}])
        with patch.object(nlm_rollup, "_post_digest", return_value="sid-3") as m_post, \
             patch.object(nlm_rollup, "_delete_source") as m_del, \
             patch.object(nlm_rollup, "route_domain_to_notebook",
                          return_value=("ai_research", "nb-x")):
            s3 = nlm_rollup.run_rollup(db_path=db, days_back=3650)
        assert s3["posted"] == 1
        m_del.assert_called_once()                  # old digest deleted
        assert m_del.call_args.args[1] == "sid-1"   # the prior source id
