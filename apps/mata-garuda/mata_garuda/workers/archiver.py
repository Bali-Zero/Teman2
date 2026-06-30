"""
Mata Garuda — Archiver Worker.

Council pattern (Kafka log-compaction / Recorded Future cold-store / Dataminr
Lambda-arch slow path): the Redis streams are a HOT, BOUNDED buffer (now MAXLEN-
capped — bounded RAM). That cap means old entries are trimmed and lost. The
archiver is the DURABLE record: it consumes garuda:enriched via its own consumer
group and appends every item to an on-disk SQLite archive. This gives full-corpus
auditability WITHOUT growing Redis RAM — the cap can trim freely because the
archive holds the history.

Stdlib-only (sqlite3) — mata_garuda vincolo is pydantic+pytest, NO new deps. The
council suggested DuckDB/Parquet, but those would be new dependencies; SQLite is
the stdlib equivalent and matches the existing KnowledgeBase store (data/*.db).
Mirrors runtime/knowledge.py exactly: WAL + synchronous=NORMAL, Row factory,
CREATE TABLE IF NOT EXISTS, data/ dir (gitignored).

Idempotent by content_hash (UNIQUE) — re-archiving an already-stored item is a
no-op INSERT OR IGNORE, so redelivery (PEL replay) never double-counts.

Layer 2.5 — cold-store tap off the enriched stream. Does NOT publish anything
back (terminal Sink — council: don't re-publish to a stream you consume).
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from mata_garuda.config import STREAM_ENRICHED
from mata_garuda.workers.base_worker import stream_ack, stream_read_new

logger = logging.getLogger("mata_garuda.workers")

CONSUMER_GROUP = "archiver"
CONSUMER_NAME = "archiver-1"

DEFAULT_ARCHIVE_PATH = Path(__file__).parent.parent.parent / "data" / "archive.db"


class StreamArchive:
    """On-disk, append-only SQLite archive of every enriched intel item.

    Mirrors runtime.knowledge.KnowledgeBase's connection discipline (WAL +
    synchronous=NORMAL + Row factory) so two writers on the same machine never
    hit the transient 'disk I/O error' (2026-05-06 scar).
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_ARCHIVE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE,
                stream_id TEXT,
                title TEXT,
                url TEXT,
                source TEXT,
                source_type TEXT,
                content TEXT,
                score TEXT,
                agent TEXT,
                harvested_ts TEXT,
                archived_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_archive_source ON archive(source);
            CREATE INDEX IF NOT EXISTS idx_archive_archived ON archive(archived_at);
        """)
        self._conn.commit()

    def archive(self, stream_id: str, data: dict) -> bool:
        """Insert one enriched item. INSERT OR IGNORE on content_hash → idempotent.

        Returns True if a NEW row was inserted, False if it was a duplicate.
        """
        chash = (data.get("content_hash")
                 or data.get("url")
                 or f"{data.get('title','')}{stream_id}")
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO archive "
            "(content_hash, stream_id, title, url, source, source_type, "
            " content, score, agent, harvested_ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                chash,
                stream_id,
                data.get("title", ""),
                data.get("url", ""),
                data.get("source", ""),
                data.get("source_type", data.get("source", "")),
                (data.get("content", "") or "")[:8000],
                str(data.get("score", data.get("relevance", ""))),
                data.get("agent", "unknown"),
                data.get("timestamp", data.get("normalized_at", "")),
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM archive").fetchone()[0]

    def close(self) -> None:
        self._conn.close()


def run_archiver(archive: StreamArchive, max_items: int = 200) -> dict:
    """Run one pass of the archiver.

    Reads garuda:enriched (own consumer group), appends each item to the on-disk
    archive, ACKs. Terminal Sink — publishes nothing back.

    Returns stats dict: {processed, archived, duplicates, errors}.
    """
    stats = {"processed": 0, "archived": 0, "duplicates": 0, "errors": 0}

    items = stream_read_new(
        STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items)
    if not items:
        logger.info("[archiver] No new items in garuda:enriched")
        return stats

    for item in items:
        msg_id = item["id"]
        data = item["data"]
        stats["processed"] += 1
        try:
            is_new = archive.archive(msg_id, data)
            if is_new:
                stats["archived"] += 1
            else:
                stats["duplicates"] += 1
            # ACK in BOTH cases: a duplicate is fully handled (already on disk),
            # so it must leave the PEL — else it redelivers forever and lag grows.
            stream_ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
        except Exception as e:
            logger.error(f"[archiver] Error archiving {msg_id}: {e}")
            stats["errors"] += 1
            # do NOT ack on error → redelivered next pass (at-least-once)

    logger.info(
        f"[archiver] Done: {stats['processed']} processed, "
        f"{stats['archived']} archived, {stats['duplicates']} dupes, "
        f"total={archive.count()}"
    )
    return stats


def main() -> int:
    """Cron entrypoint: one archiver pass. Exit 0 on success, 1 on hard error."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    max_items = int(os.environ.get("GARUDA_ARCHIVE_MAX_ITEMS", "500"))
    archive = StreamArchive()
    try:
        stats = run_archiver(archive, max_items=max_items)
        print(f"[archiver] {stats} total_archived={archive.count()}")
        return 0
    except Exception as e:  # noqa: BLE001 — top-level cron guard
        logger.error(f"[archiver] FATAL: {e}")
        return 1
    finally:
        archive.close()


if __name__ == "__main__":
    raise SystemExit(main())
