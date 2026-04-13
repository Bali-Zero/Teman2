"""Genome — DNA recording for Nuzantara cells.

Every cell accumulates knowledge during its lifetime: skills that worked,
patterns observed, scars from failures. This module records that knowledge
in a structured, queryable form and enables selective transfer to daughter cells.

Biological analogues:
- genome table = DNA (persistent, structured knowledge)
- inherit_genome() = transcription (selective copy at fork time)
- silence_skill() = epigenetic silencing (valid_to set, not deleted)
- scope='Project' vs 'Personal' = germline vs somatic

Usage:
    from cell_core.genome import Genome

    g = Genome(db_path="cell.db")
    g.record_skill(
        cell="akta_archive",
        skill_id="proxy_detection_v1",
        procedure="Use Python regex for 'bertindak berdasarkan' before LLM parsing.",
        precondition="Text contains Indonesian akta with Surat Kuasa references.",
        success_criterion="Zero procuratori appear in founders table.",
        confidence=0.94,
    )

    # When spawning a daughter cell
    inherited = g.inherit_genome(parent_cell="akta_archive", fork_date="2026-04-12")
    for skill in inherited:
        print(skill["skill_id"], skill["confidence"])
"""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("cell_core.genome")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS genome (
    id               TEXT PRIMARY KEY,
    cell_origin      TEXT NOT NULL,
    type             TEXT NOT NULL CHECK(type IN ('skill','pattern','scar','insight')),
    scope            TEXT NOT NULL DEFAULT 'Project' CHECK(scope IN ('Project','Personal')),

    precondition     TEXT,
    procedure        TEXT NOT NULL,
    success_criterion TEXT,

    valid_from       TEXT NOT NULL,
    valid_to         TEXT,

    confidence       REAL NOT NULL DEFAULT 0.5,
    uses             INTEGER NOT NULL DEFAULT 0,
    last_used        TEXT,

    inherited_from   TEXT REFERENCES genome(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS genome_fts USING fts5(
    precondition, procedure, success_criterion,
    content=genome, content_rowid=rowid
);

CREATE TRIGGER IF NOT EXISTS genome_ai AFTER INSERT ON genome BEGIN
    INSERT INTO genome_fts(rowid, precondition, procedure, success_criterion)
    VALUES (new.rowid, new.precondition, new.procedure, new.success_criterion);
END;

CREATE INDEX IF NOT EXISTS idx_genome_cell       ON genome(cell_origin);
CREATE INDEX IF NOT EXISTS idx_genome_type       ON genome(type);
CREATE INDEX IF NOT EXISTS idx_genome_scope      ON genome(scope);
CREATE INDEX IF NOT EXISTS idx_genome_confidence ON genome(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_genome_valid      ON genome(valid_from, valid_to);
"""


class Genome:
    """DNA recording store. One instance per cell (or shared across cells by DB path)."""

    def __init__(self, db_path: str = "cell.db") -> None:
        self._db_path = db_path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._conn()
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()

    # ─────────────────────────────────────────
    # Write operations
    # ─────────────────────────────────────────

    def record_skill(
        self,
        cell: str,
        skill_id: str,
        procedure: str,
        precondition: str = "",
        success_criterion: str = "",
        confidence: float = 0.5,
        scope: str = "Project",
        inherited_from: str | None = None,
        entry_type: str = "skill",
    ) -> bool:
        """Record a skill in the genome. Returns True if inserted, False if already exists."""
        now = datetime.now(timezone.utc).date().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO genome
                   (id, cell_origin, type, scope, precondition, procedure,
                    success_criterion, valid_from, confidence, inherited_from)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (skill_id, cell, entry_type, scope, precondition or None,
                 procedure, success_criterion or None, now, confidence, inherited_from),
            )
            inserted = conn.execute("SELECT changes()").fetchone()[0] > 0
            conn.commit()
            if inserted:
                logger.info(f"[genome] recorded {entry_type} '{skill_id}' for cell '{cell}' (confidence={confidence:.0%})")
            return inserted
        finally:
            conn.close()

    def record_scar(
        self,
        cell: str,
        scar_id: str,
        procedure: str,
        precondition: str = "",
    ) -> bool:
        """Record a failure scar — always Personal scope, confidence 0.9 (strong avoidance)."""
        return self.record_skill(
            cell=cell,
            skill_id=scar_id,
            procedure=procedure,
            precondition=precondition,
            confidence=0.9,
            scope="Personal",
            entry_type="scar",
        )

    def use_skill(self, skill_id: str) -> None:
        """Mark a skill as used. Increases confidence slightly (max 1.0)."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            """UPDATE genome SET
               uses = uses + 1,
               last_used = ?,
               confidence = MIN(1.0, confidence + 0.02)
               WHERE id = ?""",
            (now, skill_id),
        )
        conn.commit()
        conn.close()

    def silence_skill(self, skill_id: str, reason: str = "") -> None:
        """Silence an obsolete skill (non-destructive). Sets valid_to = today."""
        now = datetime.now(timezone.utc).date().isoformat()
        conn = self._conn()
        conn.execute(
            "UPDATE genome SET valid_to = ? WHERE id = ? AND valid_to IS NULL",
            (now, skill_id),
        )
        conn.commit()
        conn.close()
        logger.info(f"[genome] silenced skill '{skill_id}' reason='{reason}'")

    def silence_stale_skills(self, cell: str, unused_days: int = 30) -> int:
        """Silence skills not used in N days with confidence below threshold."""
        cutoff_ts = time.time() - unused_days * 86400
        cutoff_date = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).date().isoformat()
        today = datetime.now(timezone.utc).date().isoformat()
        conn = self._conn()
        conn.execute(
            """UPDATE genome SET valid_to = ?
               WHERE cell_origin = ?
                 AND valid_to IS NULL
                 AND confidence < 0.4
                 AND (last_used IS NULL OR last_used < ?)""",
            (today, cell, cutoff_date),
        )
        n = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        conn.close()
        if n:
            logger.info(f"[genome] silenced {n} stale skills for cell '{cell}'")
        return n

    # ─────────────────────────────────────────
    # Read operations
    # ─────────────────────────────────────────

    def get_active(
        self,
        cell: str,
        entry_type: str | None = None,
        scope: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[dict]:
        """Get active genome entries for a cell."""
        today = datetime.now(timezone.utc).date().isoformat()
        params: list = [cell, today, min_confidence]
        filters = [
            "cell_origin = ?",
            "valid_from <= ?",
            "(valid_to IS NULL OR valid_to > ?)",
            "confidence >= ?",
        ]
        # valid_to > today check needs today again
        params = [cell, today, today, min_confidence]
        if entry_type:
            filters.append("type = ?")
            params.append(entry_type)
        if scope:
            filters.append("scope = ?")
            params.append(scope)
        params.append(limit)

        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM genome WHERE {' AND '.join(filters)} "
            f"ORDER BY confidence DESC, uses DESC LIMIT ?",
            params,
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """FTS5 full-text search across genome. Use before reasoning from scratch."""
        today = datetime.now(timezone.utc).date().isoformat()
        conn = self._conn()
        rows = conn.execute(
            """SELECT g.* FROM genome g
               JOIN genome_fts f ON g.rowid = f.rowid
               WHERE genome_fts MATCH ?
                 AND (g.valid_to IS NULL OR g.valid_to > ?)
               ORDER BY rank, g.confidence DESC
               LIMIT ?""",
            (query, today, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def inherit_genome(
        self,
        parent_cell: str,
        fork_date: str | None = None,
        min_confidence: float = 0.7,
    ) -> list[dict]:
        """
        Transcription: return transferable genome at fork time.

        Filters:
        - scope = 'Project' (not Personal/local)
        - type IN ('skill', 'pattern') (not scars or raw insights)
        - confidence >= min_confidence
        - active at fork_date (valid_from <= fork AND valid_to IS NULL or > fork)

        Returns skills ordered by confidence DESC, uses DESC.
        The daughter cell should store these with a slight confidence decay (×0.9).
        """
        fd = fork_date or datetime.now(timezone.utc).date().isoformat()
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM genome
               WHERE cell_origin = ?
                 AND scope = 'Project'
                 AND type IN ('skill', 'pattern')
                 AND confidence >= ?
                 AND valid_from <= ?
                 AND (valid_to IS NULL OR valid_to > ?)
               ORDER BY confidence DESC, uses DESC""",
            (parent_cell, min_confidence, fd, fd),
        ).fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        logger.info(
            f"[genome] inherit_genome: {len(result)} skills from '{parent_cell}' "
            f"at {fd} (min_confidence={min_confidence:.0%})"
        )
        return result

    def stats(self, cell: str | None = None) -> dict:
        """Summary statistics for monitoring."""
        today = datetime.now(timezone.utc).date().isoformat()
        conn = self._conn()
        where = "WHERE cell_origin = ?" if cell else ""
        params = [cell] if cell else []

        total = conn.execute(f"SELECT COUNT(*) FROM genome {where}", params).fetchone()[0]
        active = conn.execute(
            f"SELECT COUNT(*) FROM genome {where} {'AND' if where else 'WHERE'} "
            f"(valid_to IS NULL OR valid_to > ?)",
            params + [today],
        ).fetchone()[0]
        by_type = conn.execute(
            f"SELECT type, COUNT(*) c, AVG(confidence) avg_conf FROM genome {where} "
            f"GROUP BY type ORDER BY c DESC",
            params,
        ).fetchall()
        conn.close()
        return {
            "total": total,
            "active": active,
            "silenced": total - active,
            "by_type": [{"type": r["type"], "count": r["c"], "avg_confidence": round(r["avg_conf"], 2)} for r in by_type],
        }
