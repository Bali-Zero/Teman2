"""
Mata Garuda — SQLite Knowledge Graph (Layer 3 Nexus).

Minimal local KG: entities + relations + temporal observations.
Designed as the OSINT-blindato graph store (never leaves Pro).

Schema:
- kg_entities(id, type, canonical_name, aliases_json, first_seen, last_seen)
- kg_relations(id, subject_id, predicate, object_id, evidence_url,
               first_seen, last_seen, confidence)
- kg_observations(id, entity_id, field, value, observed_at, source_url)

Why SQLite (not Neo4j):
- Zero JVM + zero new daemon (stay pydantic-only stack)
- Local Pro only (Legge 2 OSINT blindato)
- 108k nodes already sit in backend-rag PG; Mata Garuda KG is for
  *different* semantics (OSINT entities surfaced from garuda:enriched,
  not Bali Zero business KG).
- Scales to ~1M entities on SQLite without perf issues for cron-batch
  query patterns. If that ceiling approaches we reassess.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("mata_garuda.runtime.kg")

DEFAULT_KG_PATH = Path.home() / ".agent" / "mata-garuda" / "kg.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class KnowledgeGraph:
    """Local SQLite KG: entities, relations, observations."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_KG_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kg_entities (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                type            TEXT NOT NULL,
                canonical_name  TEXT NOT NULL,
                aliases_json    TEXT NOT NULL DEFAULT '[]',
                first_seen      TEXT NOT NULL,
                last_seen       TEXT NOT NULL,
                source_count    INTEGER NOT NULL DEFAULT 1,
                UNIQUE(type, canonical_name)
            );
            CREATE INDEX IF NOT EXISTS idx_kg_entities_type
                ON kg_entities(type);
            CREATE INDEX IF NOT EXISTS idx_kg_entities_last_seen
                ON kg_entities(last_seen DESC);

            CREATE TABLE IF NOT EXISTS kg_relations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id      INTEGER NOT NULL REFERENCES kg_entities(id),
                predicate       TEXT NOT NULL,
                object_id       INTEGER NOT NULL REFERENCES kg_entities(id),
                evidence_url    TEXT,
                first_seen      TEXT NOT NULL,
                last_seen       TEXT NOT NULL,
                confidence      REAL NOT NULL DEFAULT 0.5,
                source_count    INTEGER NOT NULL DEFAULT 1,
                UNIQUE(subject_id, predicate, object_id)
            );
            CREATE INDEX IF NOT EXISTS idx_kg_rel_subject
                ON kg_relations(subject_id);
            CREATE INDEX IF NOT EXISTS idx_kg_rel_object
                ON kg_relations(object_id);
            CREATE INDEX IF NOT EXISTS idx_kg_rel_predicate
                ON kg_relations(predicate);

            CREATE TABLE IF NOT EXISTS kg_observations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id    INTEGER NOT NULL REFERENCES kg_entities(id),
                field        TEXT NOT NULL,
                value        TEXT NOT NULL,
                observed_at  TEXT NOT NULL,
                source_url   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_kg_obs_entity
                ON kg_observations(entity_id, observed_at DESC);
            CREATE INDEX IF NOT EXISTS idx_kg_obs_field
                ON kg_observations(entity_id, field, observed_at DESC);
        """)
        conn.commit()

    # ── Entities ──────────────────────────────────────────────────────

    def upsert_entity(
        self, entity_type: str, canonical_name: str,
        aliases: list[str] | None = None,
    ) -> int:
        """Insert entity or bump last_seen + source_count on dup."""
        conn = self._get_conn()
        now = _now()
        aliases_json = json.dumps(aliases or [], ensure_ascii=False)

        cur = conn.execute(
            "SELECT id, aliases_json FROM kg_entities "
            "WHERE type=? AND canonical_name=?",
            (entity_type, canonical_name),
        )
        existing = cur.fetchone()
        if existing:
            ent_id = existing["id"]
            # Merge aliases
            if aliases:
                prior = json.loads(existing["aliases_json"] or "[]")
                merged = sorted(set(prior + aliases))
                aliases_json = json.dumps(merged, ensure_ascii=False)
            conn.execute(
                "UPDATE kg_entities SET last_seen=?, source_count=source_count+1, "
                "aliases_json=? WHERE id=?",
                (now, aliases_json, ent_id),
            )
            conn.commit()
            return ent_id

        cur = conn.execute(
            "INSERT INTO kg_entities(type, canonical_name, aliases_json, "
            "first_seen, last_seen) VALUES (?, ?, ?, ?, ?)",
            (entity_type, canonical_name, aliases_json, now, now),
        )
        conn.commit()
        return cur.lastrowid

    def find_entity(
        self, entity_type: str, canonical_name: str,
    ) -> dict[str, Any] | None:
        conn = self._get_conn()
        cur = conn.execute(
            "SELECT * FROM kg_entities WHERE type=? AND canonical_name=?",
            (entity_type, canonical_name),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # ── Relations ─────────────────────────────────────────────────────

    def upsert_relation(
        self,
        subject_type: str, subject_name: str,
        predicate: str,
        object_type: str, object_name: str,
        *,
        evidence_url: str | None = None,
        confidence: float = 0.5,
    ) -> int:
        """Upsert (subject → predicate → object) triple, bump counters."""
        subj_id = self.upsert_entity(subject_type, subject_name)
        obj_id = self.upsert_entity(object_type, object_name)
        conn = self._get_conn()
        now = _now()

        cur = conn.execute(
            "SELECT id, source_count, confidence FROM kg_relations "
            "WHERE subject_id=? AND predicate=? AND object_id=?",
            (subj_id, predicate, obj_id),
        )
        existing = cur.fetchone()
        if existing:
            rel_id = existing["id"]
            # Reinforcement: confidence toward 1.0, cap at 0.99
            new_conf = min(0.99, existing["confidence"] + (1.0 - existing["confidence"]) * 0.1)
            conn.execute(
                "UPDATE kg_relations SET last_seen=?, source_count=source_count+1, "
                "confidence=? WHERE id=?",
                (now, new_conf, rel_id),
            )
            conn.commit()
            return rel_id

        cur = conn.execute(
            "INSERT INTO kg_relations(subject_id, predicate, object_id, "
            "evidence_url, first_seen, last_seen, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (subj_id, predicate, obj_id, evidence_url, now, now, confidence),
        )
        conn.commit()
        return cur.lastrowid

    def neighbors(
        self, entity_type: str, canonical_name: str,
        *, min_confidence: float = 0.3,
    ) -> list[dict[str, Any]]:
        ent = self.find_entity(entity_type, canonical_name)
        if not ent:
            return []
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT r.predicate, r.confidence, r.source_count,
                   e.type AS object_type, e.canonical_name AS object_name
              FROM kg_relations r
              JOIN kg_entities e ON e.id = r.object_id
             WHERE r.subject_id=? AND r.confidence>=?
             ORDER BY r.confidence DESC, r.source_count DESC
            """,
            (ent["id"], min_confidence),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Observations (temporal) ───────────────────────────────────────

    def record_observation(
        self, entity_type: str, canonical_name: str,
        field: str, value: str,
        *, source_url: str | None = None,
    ) -> int:
        ent_id = self.upsert_entity(entity_type, canonical_name)
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO kg_observations(entity_id, field, value, "
            "observed_at, source_url) VALUES (?, ?, ?, ?, ?)",
            (ent_id, field, value, _now(), source_url),
        )
        conn.commit()
        return cur.lastrowid

    def observation_history(
        self, entity_type: str, canonical_name: str, field: str,
        *, limit: int = 50,
    ) -> list[dict[str, Any]]:
        ent = self.find_entity(entity_type, canonical_name)
        if not ent:
            return []
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT value, observed_at, source_url FROM kg_observations "
            "WHERE entity_id=? AND field=? ORDER BY observed_at DESC LIMIT ?",
            (ent["id"], field, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Stats / maintenance ───────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        conn = self._get_conn()
        out: dict[str, int] = {}
        for tbl in ("kg_entities", "kg_relations", "kg_observations"):
            cur = conn.execute(f"SELECT COUNT(*) AS n FROM {tbl}")
            out[tbl] = cur.fetchone()["n"]
        return out

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
