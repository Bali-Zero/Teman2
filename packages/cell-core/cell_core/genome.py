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

import json
import logging
import os
import sqlite3
import threading
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

CREATE TRIGGER IF NOT EXISTS genome_au AFTER UPDATE ON genome BEGIN
    INSERT INTO genome_fts(genome_fts, rowid, precondition, procedure, success_criterion)
    VALUES ('delete', old.rowid, old.precondition, old.procedure, old.success_criterion);
    INSERT INTO genome_fts(rowid, precondition, procedure, success_criterion)
    VALUES (new.rowid, new.precondition, new.procedure, new.success_criterion);
END;

CREATE TRIGGER IF NOT EXISTS genome_ad AFTER DELETE ON genome BEGIN
    INSERT INTO genome_fts(genome_fts, rowid, precondition, procedure, success_criterion)
    VALUES ('delete', old.rowid, old.precondition, old.procedure, old.success_criterion);
END;

CREATE INDEX IF NOT EXISTS idx_genome_cell       ON genome(cell_origin);
CREATE INDEX IF NOT EXISTS idx_genome_type       ON genome(type);
CREATE INDEX IF NOT EXISTS idx_genome_scope      ON genome(scope);
CREATE INDEX IF NOT EXISTS idx_genome_confidence ON genome(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_genome_valid      ON genome(valid_from, valid_to);
"""


class Genome:
    """DNA recording store. One instance per cell (or shared across cells by DB path).

    Thread-safety: a ``threading.Lock`` serialises all write operations.
    Reads go through the same WAL-mode connection (SQLite allows concurrent
    reads under WAL) so they never block writers for long.
    """

    def __init__(self, db_path: str = "cell.db") -> None:
        self._db_path = db_path
        self._write_lock = threading.Lock()
        self._local = threading.local()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a per-thread connection (reused across calls)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

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
    ) -> str:
        """Record or update a skill in the genome.

        On conflict (same id), updates procedure, precondition,
        success_criterion and keeps the higher confidence.

        Returns ``"inserted"`` or ``"updated"``.
        """
        now = datetime.now(timezone.utc).date().isoformat()
        with self._write_lock:
            conn = self._get_conn()
            # Check existence first to reliably detect insert vs update.
            exists = conn.execute(
                "SELECT 1 FROM genome WHERE id = ?", (skill_id,)
            ).fetchone() is not None
            conn.execute(
                """INSERT INTO genome
                   (id, cell_origin, type, scope, precondition, procedure,
                    success_criterion, valid_from, confidence, inherited_from)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       procedure        = excluded.procedure,
                       precondition     = excluded.precondition,
                       success_criterion = excluded.success_criterion,
                       confidence       = MAX(genome.confidence, excluded.confidence)""",
                (skill_id, cell, entry_type, scope, precondition or None,
                 procedure, success_criterion or None, now, confidence, inherited_from),
            )
            conn.commit()
            action = "updated" if exists else "inserted"
            logger.info(
                f"[genome] {action} {entry_type} '{skill_id}' for cell "
                f"'{cell}' (confidence={confidence:.0%})"
            )
            return action

    def record_scar(
        self,
        cell: str,
        scar_id: str,
        procedure: str,
        precondition: str = "",
    ) -> str:
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
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                """UPDATE genome SET
                   uses = uses + 1,
                   last_used = ?,
                   confidence = MIN(1.0, confidence + 0.02)
                   WHERE id = ?""",
                (now, skill_id),
            )
            conn.commit()

    def silence_skill(self, skill_id: str, reason: str = "") -> None:
        """Silence an obsolete skill (non-destructive). Sets valid_to = today."""
        now = datetime.now(timezone.utc).date().isoformat()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE genome SET valid_to = ? WHERE id = ? AND valid_to IS NULL",
                (now, skill_id),
            )
            conn.commit()
        logger.info(f"[genome] silenced skill '{skill_id}' reason='{reason}'")

    def silence_stale_skills(self, cell: str, unused_days: int = 30) -> int:
        """Silence skills not used in N days with confidence below threshold."""
        cutoff_ts = time.time() - unused_days * 86400
        cutoff_date = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).date().isoformat()
        today = datetime.now(timezone.utc).date().isoformat()
        with self._write_lock:
            conn = self._get_conn()
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

        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM genome WHERE {' AND '.join(filters)} "
            f"ORDER BY confidence DESC, uses DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """FTS5 full-text search across genome. Use before reasoning from scratch."""
        today = datetime.now(timezone.utc).date().isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT g.* FROM genome g
               JOIN genome_fts f ON g.rowid = f.rowid
               WHERE genome_fts MATCH ?
                 AND (g.valid_to IS NULL OR g.valid_to > ?)
               ORDER BY rank, g.confidence DESC
               LIMIT ?""",
            (query, today, limit),
        ).fetchall()
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
        conn = self._get_conn()
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
        result = [dict(r) for r in rows]
        logger.info(
            f"[genome] inherit_genome: {len(result)} skills from '{parent_cell}' "
            f"at {fd} (min_confidence={min_confidence:.0%})"
        )
        return result

    def apply_inherited_genome(
        self,
        parent_cell: str,
        daughter_cell: str,
        decay: float = 0.9,
        min_confidence: float = 0.7,
        fork_date: str | None = None,
    ) -> list[dict]:
        """Inherit from *parent_cell* and record each skill into *daughter_cell*.

        Each inherited skill is stored with:
        - id = ``inherited_{original_id}``
        - confidence = original × *decay*
        - inherited_from = original id

        Returns the list of inherited skills (with decayed confidence).
        """
        inherited = self.inherit_genome(
            parent_cell=parent_cell,
            fork_date=fork_date,
            min_confidence=min_confidence,
        )
        applied: list[dict] = []
        for skill in inherited:
            decayed_conf = round(skill["confidence"] * decay, 4)
            self.record_skill(
                cell=daughter_cell,
                skill_id=f"inherited_{skill['id']}",
                procedure=skill["procedure"],
                precondition=skill.get("precondition") or "",
                success_criterion=skill.get("success_criterion") or "",
                confidence=decayed_conf,
                scope=skill["scope"],
                inherited_from=skill["id"],
                entry_type=skill["type"],
            )
            applied.append({**skill, "confidence": decayed_conf})
        logger.info(
            f"[genome] applied {len(applied)} skills from '{parent_cell}' "
            f"to '{daughter_cell}' (decay={decay})"
        )
        return applied

    def stats(self, cell: str | None = None) -> dict:
        """Summary statistics for monitoring."""
        today = datetime.now(timezone.utc).date().isoformat()
        conn = self._get_conn()
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

        db_file_size = 0
        try:
            db_file_size = os.path.getsize(self._db_path)
        except OSError:
            pass

        return {
            "total": total,
            "active": active,
            "silenced": total - active,
            "db_file_size": db_file_size,
            "by_type": [{"type": r["type"], "count": r["c"], "avg_confidence": round(r["avg_conf"], 2)} for r in by_type],
        }

    # ─────────────────────────────────────────
    # Compaction
    # ─────────────────────────────────────────

    def vacuum(self, days_silenced: int = 90) -> int:
        """Permanently delete skills silenced more than *days_silenced* ago.

        Returns the number of rows removed.
        """
        cutoff_ts = time.time() - days_silenced * 86400
        cutoff_date = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).date().isoformat()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM genome WHERE valid_to IS NOT NULL AND valid_to <= ?",
                (cutoff_date,),
            )
            removed = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        if removed:
            logger.info(f"[genome] vacuum: removed {removed} rows silenced before {cutoff_date}")
        return removed

    def compact(self) -> int:
        """Run SQLite VACUUM to reclaim disk space. Returns bytes freed."""
        size_before = 0
        try:
            size_before = os.path.getsize(self._db_path)
        except OSError:
            pass
        with self._write_lock:
            conn = self._get_conn()
            conn.execute("VACUUM")
        size_after = 0
        try:
            size_after = os.path.getsize(self._db_path)
        except OSError:
            pass
        freed = max(0, size_before - size_after)
        logger.info(f"[genome] compact: {size_before} → {size_after} bytes (freed {freed})")
        return freed

    # ─────────────────────────────────────────
    # Import / Export (Pro ↔ Air migration)
    # ─────────────────────────────────────────

    def export_genome(self, cell: str | None = None) -> list[dict]:
        """Export all genome rows (optionally filtered by cell) as dicts.

        Suitable for JSON serialisation and transfer to another machine.
        """
        conn = self._get_conn()
        if cell:
            rows = conn.execute("SELECT * FROM genome WHERE cell_origin = ?", (cell,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM genome").fetchall()
        return [dict(r) for r in rows]

    def import_genome(self, data: list[dict], target_cell: str | None = None) -> dict[str, int]:
        """Import genome rows from a list of dicts (as produced by ``export_genome``).

        If *target_cell* is given, overrides ``cell_origin`` for all imported rows.
        Uses upsert (ON CONFLICT DO UPDATE) so re-imports are safe.

        Returns ``{"inserted": N, "updated": M}``.
        """
        counts = {"inserted": 0, "updated": 0}
        for row in data:
            cell_origin = target_cell or row["cell_origin"]
            action = self.record_skill(
                cell=cell_origin,
                skill_id=row["id"],
                procedure=row["procedure"],
                precondition=row.get("precondition") or "",
                success_criterion=row.get("success_criterion") or "",
                confidence=row.get("confidence", 0.5),
                scope=row.get("scope", "Project"),
                inherited_from=row.get("inherited_from"),
                entry_type=row.get("type", "skill"),
            )
            counts[action] += 1
        logger.info(
            f"[genome] import: {counts['inserted']} inserted, "
            f"{counts['updated']} updated"
        )
        return counts
