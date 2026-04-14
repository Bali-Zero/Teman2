"""
Mata Garuda — SQLite Knowledge Base.

Unified store for ALL organism knowledge: facts, insights, patterns, skills.
Uses SQLite FTS5 for full-text search (stdlib, zero dependencies).

Design decision: skills are type='skill' rows, NOT separate files.
One source of truth prevents divergence.

Storage: data/knowledge.db (gitignored)
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mata_garuda.runtime")

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "knowledge.db"


class KnowledgeBase:
    """SQLite-backed knowledge base with FTS5 full-text search."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: KB is shared across PulseLoop's event loop
        # and MetaChainActor's asyncio.to_thread() worker threads. All writes
        # serialize through a single connection; SQLite handles concurrent
        # reads via WAL.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT DEFAULT (datetime('now')),
                accessed_count INTEGER DEFAULT 0,
                last_accessed TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(content, source, content='knowledge', content_rowid='id');
            CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                INSERT INTO knowledge_fts(rowid, content, source)
                VALUES (new.id, new.content, new.source);
            END;
            CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, content, source)
                VALUES ('delete', old.id, old.content, old.source);
            END;
        """)
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        return cursor

    def store(
        self,
        agent: str,
        entry_type: str,
        content: str,
        source: str,
        confidence: float = 0.5,
    ) -> int:
        """Store a knowledge entry. Returns the row id."""
        cursor = self._execute(
            "INSERT INTO knowledge (agent, type, content, source, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (agent, entry_type, content, source, confidence),
        )
        logger.info(f"[kb] Stored {entry_type} from {agent}: {content[:60]}...")
        return cursor.lastrowid

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search over knowledge entries."""
        try:
            cursor = self._conn.execute(
                "SELECT k.* FROM knowledge k "
                "JOIN knowledge_fts fts ON k.id = fts.rowid "
                "WHERE knowledge_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (query, limit),
            )
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in cursor.fetchall()]

    def get_by_type(self, entry_type: str, limit: int = 50) -> list[dict]:
        """Get all entries of a specific type (e.g., 'skill')."""
        cursor = self._conn.execute(
            "SELECT * FROM knowledge WHERE type = ? ORDER BY confidence DESC LIMIT ?",
            (entry_type, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_agent(self, agent: str, limit: int = 50) -> list[dict]:
        """Get all entries from a specific agent."""
        cursor = self._conn.execute(
            "SELECT * FROM knowledge WHERE agent = ? ORDER BY created_at DESC LIMIT ?",
            (agent, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def touch(self, entry_id: int) -> None:
        """Increment accessed_count for an entry."""
        self._execute(
            "UPDATE knowledge SET accessed_count = accessed_count + 1, "
            "last_accessed = datetime('now') WHERE id = ?",
            (entry_id,),
        )

    def decrement_confidence(self, entry_id: int, amount: float = 0.1) -> None:
        """Decrease confidence when an entry led to a failed outcome."""
        self._execute(
            "UPDATE knowledge SET confidence = MAX(0.0, confidence - ?) WHERE id = ?",
            (amount, entry_id),
        )

    def decay(self, max_age_days: int = 30, min_access: int = 1) -> int:
        """Remove stale entries: old + never accessed. Returns count removed."""
        cursor = self._execute(
            "DELETE FROM knowledge WHERE accessed_count < ? "
            "AND created_at < datetime('now', ?)",
            (min_access, f"-{max_age_days} days"),
        )
        removed = cursor.rowcount
        if removed > 0:
            logger.info(f"[kb] Decayed {removed} stale entries")
        return removed

    def stats(self) -> dict:
        """Return counts by type."""
        cursor = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM knowledge GROUP BY type"
        )
        result = {row["type"]: row["cnt"] for row in cursor.fetchall()}
        result["total"] = sum(result.values())
        return result

    def close(self) -> None:
        self._conn.close()
