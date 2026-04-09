"""SQLite-backed memory stores — zero external dependencies.

All async methods use asyncio.to_thread() for I/O to keep the event loop clean.
Each store creates its own tables on first use (idempotent).

This is the default backend for lightweight organs like Mata Garuda.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

from cell_core.types import Episode, LearnedRule

logger = logging.getLogger("cell_core.memory.sqlite")


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class SqliteSTM:
    """Short-term memory in SQLite with TTL cleanup."""

    def __init__(self, db_path: str, ttl_seconds: int = 86400) -> None:
        self._db_path = db_path
        self._ttl = ttl_seconds
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = _get_conn(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stm_type ON stm(event_type)")
        conn.commit()
        conn.close()

    def _store_sync(self, event_type: str, data: dict[str, Any]) -> None:
        conn = _get_conn(self._db_path)
        now = time.time()
        conn.execute(
            "INSERT INTO stm (event_type, data_json, created_at) VALUES (?, ?, ?)",
            (event_type, json.dumps(data), now),
        )
        # TTL cleanup
        cutoff = now - self._ttl
        conn.execute("DELETE FROM stm WHERE created_at < ?", (cutoff,))
        conn.commit()
        conn.close()

    def _recent_sync(self, event_type: str, limit: int) -> list[dict[str, Any]]:
        conn = _get_conn(self._db_path)
        if event_type:
            rows = conn.execute(
                "SELECT data_json FROM stm WHERE event_type = ? ORDER BY created_at DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data_json FROM stm ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
        return [json.loads(row["data_json"]) for row in rows]

    async def store(self, event_type: str, data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._store_sync, event_type, data)

    async def recent(self, event_type: str, limit: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._recent_sync, event_type, limit)


class SqliteEpisodic:
    """Episodic memory in SQLite with ACT-R activation scoring."""

    def __init__(self, db_path: str, max_episodes: int = 1000) -> None:
        self._db_path = db_path
        self._max_episodes = max_episodes
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = _get_conn(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                situation_json TEXT NOT NULL,
                emotion TEXT NOT NULL,
                action_taken TEXT NOT NULL,
                outcome TEXT NOT NULL,
                lesson TEXT NOT NULL,
                timestamp REAL NOT NULL,
                recall_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _store_sync(self, episode: Episode) -> int:
        conn = _get_conn(self._db_path)
        ts = episode.timestamp if episode.timestamp > 0 else time.time()
        cursor = conn.execute(
            """INSERT INTO episodes (situation_json, emotion, action_taken, outcome, lesson, timestamp, recall_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (json.dumps(episode.situation), episode.emotion, episode.action_taken,
             episode.outcome, episode.lesson, ts, episode.recall_count),
        )
        conn.commit()
        eid = cursor.lastrowid
        conn.close()
        return eid

    def _recall_sync(self, situation: dict[str, Any], limit: int) -> list[Episode]:
        conn = _get_conn(self._db_path)
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?",
            (limit * 3,),
        ).fetchall()
        episodes = []
        for row in rows:
            ep = Episode(
                id=row["id"],
                situation=json.loads(row["situation_json"]),
                emotion=row["emotion"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
                lesson=row["lesson"],
                timestamp=row["timestamp"],
                recall_count=row["recall_count"],
            )
            ep.activation = ep.compute_activation()
            episodes.append(ep)
        episodes.sort(key=lambda e: e.activation, reverse=True)
        top = episodes[:limit]
        # Increment recall_count
        if top:
            ids = [e.id for e in top if e.id > 0]
            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE episodes SET recall_count = recall_count + 1 WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
        conn.close()
        return top

    def _recall_recent_sync(self, hours: int, limit: int) -> list[Episode]:
        conn = _get_conn(self._db_path)
        cutoff = time.time() - hours * 3600
        rows = conn.execute(
            "SELECT * FROM episodes WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        conn.close()
        episodes = []
        for row in rows:
            ep = Episode(
                id=row["id"],
                situation=json.loads(row["situation_json"]),
                emotion=row["emotion"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
                lesson=row["lesson"],
                timestamp=row["timestamp"],
                recall_count=row["recall_count"],
            )
            ep.activation = ep.compute_activation()
            episodes.append(ep)
        return episodes

    def _forget_weak_sync(self, keep: int) -> int:
        conn = _get_conn(self._db_path)
        count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        if count <= keep:
            conn.close()
            return 0
        # Get all, compute activation, delete weakest
        rows = conn.execute("SELECT id, timestamp, recall_count FROM episodes").fetchall()
        scored = []
        for row in rows:
            ep = Episode(
                situation={}, emotion="calm", action_taken="",
                outcome="", lesson="",
                timestamp=row["timestamp"], recall_count=row["recall_count"],
            )
            scored.append((row["id"], ep.compute_activation()))
        scored.sort(key=lambda x: x[1], reverse=True)
        to_delete = [s[0] for s in scored[keep:]]
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(f"DELETE FROM episodes WHERE id IN ({placeholders})", to_delete)
            conn.commit()
        conn.close()
        return len(to_delete)

    async def store(self, episode: Episode) -> int:
        return await asyncio.to_thread(self._store_sync, episode)

    async def recall(self, situation: dict[str, Any], limit: int) -> list[Episode]:
        return await asyncio.to_thread(self._recall_sync, situation, limit)

    async def recall_recent(self, hours: int, limit: int) -> list[Episode]:
        return await asyncio.to_thread(self._recall_recent_sync, hours, limit)

    async def forget_weak(self, keep: int) -> int:
        return await asyncio.to_thread(self._forget_weak_sync, keep)


class SqliteLTM:
    """Long-term rules in SQLite with FTS5 search."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = _get_conn(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ltm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_text TEXT NOT NULL,
                support_count INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _store_rule_sync(self, rule: LearnedRule) -> None:
        conn = _get_conn(self._db_path)
        conn.execute(
            "INSERT INTO ltm (rule_text, support_count, created_at) VALUES (?, ?, ?)",
            (rule.rule_text, rule.support_count, time.time()),
        )
        conn.commit()
        conn.close()

    def _load_rules_sync(self, limit: int) -> list[LearnedRule]:
        conn = _get_conn(self._db_path)
        rows = conn.execute(
            "SELECT rule_text, support_count, created_at FROM ltm ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            LearnedRule(
                rule_text=row["rule_text"],
                support_count=row["support_count"],
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def _condense_sync(self, episodes: list[Episode]) -> list[LearnedRule]:
        """Extract patterns from episodes — group by action+outcome, count support."""
        patterns: Counter[str] = Counter()
        for ep in episodes:
            key = f"When {ep.emotion}, {ep.action_taken} → {ep.outcome}"
            patterns[key] += 1
        rules = []
        for pattern, count in patterns.most_common():
            if count >= 2:  # minimum support
                rules.append(LearnedRule(rule_text=pattern, support_count=count))
        return rules

    async def store_rule(self, rule: LearnedRule) -> None:
        await asyncio.to_thread(self._store_rule_sync, rule)

    async def load_rules(self, limit: int) -> list[LearnedRule]:
        return await asyncio.to_thread(self._load_rules_sync, limit)

    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]:
        return await asyncio.to_thread(self._condense_sync, episodes)


class SqliteMemoryStack:
    """Convenience: creates all 3 stores from one SQLite DB path."""

    def __init__(self, db_path: str = "cell.db") -> None:
        self.stm = SqliteSTM(db_path)
        self.ltm = SqliteLTM(db_path)
        self.episodic = SqliteEpisodic(db_path)
