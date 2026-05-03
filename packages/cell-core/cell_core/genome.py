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
    type             TEXT NOT NULL CHECK(type IN ('skill','pattern','scar','insight','trajectory')),
    scope            TEXT NOT NULL DEFAULT 'Project' CHECK(scope IN ('Project','Personal')),

    precondition     TEXT,
    procedure        TEXT NOT NULL,
    success_criterion TEXT,

    valid_from       TEXT NOT NULL,
    valid_to         TEXT,

    confidence       REAL NOT NULL DEFAULT 0.5,
    uses             INTEGER NOT NULL DEFAULT 0,
    last_used        TEXT,

    inherited_from   TEXT,                       -- soft reference (no FK: cross-cell HGT)

    -- Sprint 5.2: Trajectory fields (nullable for skill/pattern/scar/insight)
    outcome          TEXT CHECK(outcome IN ('success','failure','partial') OR outcome IS NULL),
    tokens           INTEGER,
    duration_ms      INTEGER,
    tags             TEXT,  -- JSON array of strings

    -- Sprint 5.2 Week 3-4: Skill Registry tier (NULL | tier1 | tier2)
    tier             TEXT CHECK(tier IN ('tier1','tier2') OR tier IS NULL),

    -- Sprint 5.2 Week 3-4: HGT domain routing (11 canonical domains in hgt/domains.py)
    domain           TEXT DEFAULT 'generic'
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

# Indexes that depend on columns added by runtime migration. Applied AFTER
# _migrate_schema has ensured the column exists on legacy DBs.
_SCHEMA_POST_MIGRATION = """
CREATE INDEX IF NOT EXISTS idx_genome_tier   ON genome(tier) WHERE tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_genome_domain ON genome(domain);
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
            # foreign_keys deliberately OFF: inherited_from is a soft reference
            # that may point to skills in other cells' genomes (HGT cross-cell)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        self._migrate_schema(conn)
        conn.executescript(_SCHEMA_POST_MIGRATION)
        conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Apply additive migrations to genome tables created by earlier versions.

        Sprint 5.2 adds outcome/tokens/duration_ms/tags columns and widens the
        type CHECK constraint to include 'trajectory'. CREATE TABLE IF NOT
        EXISTS keeps the old schema untouched on existing DBs, so we patch it
        here. All operations are idempotent.
        """
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(genome)")}
        for col_name, col_def in (
            ("outcome", "TEXT"),
            ("tokens", "INTEGER"),
            ("duration_ms", "INTEGER"),
            ("tags", "TEXT"),
            # Week 3-4: tier promotion. SQLite can't add a column WITH a CHECK
            # constraint via ALTER; the schema-level CHECK on tier applies to
            # fresh tables. For legacy tables we rely on promote_skills() and
            # record_skill to only ever write 'tier1'|'tier2'|NULL.
            ("tier", "TEXT"),
            # Week 3-4: HGT domain routing. 11 canonical domains in hgt/domains.py.
            # NULL-safe for legacy rows (defaults to 'generic' via column default).
            ("domain", "TEXT DEFAULT 'generic'"),
        ):
            if col_name not in cols:
                conn.execute(f"ALTER TABLE genome ADD COLUMN {col_name} {col_def}")

        # SQLite cannot widen a CHECK constraint in place. If the existing
        # table was created before 'trajectory' was allowed, attempting to
        # insert a trajectory row will fail. We detect this by trying an
        # INSERT + ROLLBACK in a savepoint; if it fails we rebuild the table.
        # Keep it lazy: only rebuild if we actually see the old constraint.
        try:
            conn.execute("SAVEPOINT trajectory_check")
            conn.execute(
                "INSERT INTO genome (id, cell_origin, type, procedure, valid_from) "
                "VALUES ('__probe__', '__probe__', 'trajectory', 'probe', '1970-01-01')"
            )
            conn.execute("ROLLBACK TO SAVEPOINT trajectory_check")
            conn.execute("RELEASE SAVEPOINT trajectory_check")
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK TO SAVEPOINT trajectory_check")
            conn.execute("RELEASE SAVEPOINT trajectory_check")
            self._rebuild_table_for_trajectory(conn)

    def _rebuild_table_for_trajectory(self, conn: sqlite3.Connection) -> None:
        """Rebuild the genome table when the old CHECK constraint rejects 'trajectory'.

        SQLite's recommended "12-step" rebuild pattern, scoped to this one
        widening. FTS triggers/table are preserved because they reference
        rowid and are recreated by _SCHEMA on next open if missing.
        """
        logger.info("[genome] widening type CHECK to include 'trajectory'")
        conn.executescript("""
            PRAGMA foreign_keys=OFF;
            BEGIN;
            CREATE TABLE genome_new (
                id               TEXT PRIMARY KEY,
                cell_origin      TEXT NOT NULL,
                type             TEXT NOT NULL CHECK(type IN ('skill','pattern','scar','insight','trajectory')),
                scope            TEXT NOT NULL DEFAULT 'Project' CHECK(scope IN ('Project','Personal')),
                precondition     TEXT,
                procedure        TEXT NOT NULL,
                success_criterion TEXT,
                valid_from       TEXT NOT NULL,
                valid_to         TEXT,
                confidence       REAL NOT NULL DEFAULT 0.5,
                uses             INTEGER NOT NULL DEFAULT 0,
                last_used        TEXT,
                inherited_from   TEXT REFERENCES genome_new(id),
                outcome          TEXT CHECK(outcome IN ('success','failure','partial') OR outcome IS NULL),
                tokens           INTEGER,
                duration_ms      INTEGER,
                tags             TEXT,
                tier             TEXT CHECK(tier IN ('tier1','tier2') OR tier IS NULL)
            );
            INSERT INTO genome_new SELECT
                id, cell_origin, type, scope, precondition, procedure,
                success_criterion, valid_from, valid_to, confidence, uses,
                last_used, inherited_from, NULL, NULL, NULL, NULL, NULL
            FROM genome;
            DROP TABLE genome;
            ALTER TABLE genome_new RENAME TO genome;
            COMMIT;
            PRAGMA foreign_keys=ON;
        """)
        # Recreate indexes + FTS artefacts (idempotent via IF NOT EXISTS in _SCHEMA)
        conn.executescript(_SCHEMA)
        conn.executescript(_SCHEMA_POST_MIGRATION)

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
        domain: str = "generic",
    ) -> str:
        """Record or update a skill in the genome.

        On conflict (same id), updates procedure, precondition,
        success_criterion, domain, and keeps the higher confidence.

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
                    success_criterion, valid_from, confidence, inherited_from, domain)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       procedure        = excluded.procedure,
                       precondition     = excluded.precondition,
                       success_criterion = excluded.success_criterion,
                       confidence       = MAX(genome.confidence, excluded.confidence),
                       domain           = excluded.domain""",
                (skill_id, cell, entry_type, scope, precondition or None,
                 procedure, success_criterion or None, now, confidence,
                 inherited_from, domain),
            )
            conn.commit()
            action = "updated" if exists else "inserted"
            logger.info(
                f"[genome] {action} {entry_type} '{skill_id}' for cell "
                f"'{cell}' (confidence={confidence:.0%}, domain={domain})"
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

    def record_trajectory(
        self,
        cell: str,
        trajectory_id: str,
        outcome: str,
        procedure: str,
        tokens: int | None = None,
        duration_ms: int | None = None,
        tags: list[str] | None = None,
        confidence: float = 0.5,
    ) -> str:
        """Record a trajectory (episode of execution) in the genome.

        Scope rule: failure → Personal (somatic, never inherited); success and
        partial → Project (but inherit_genome excludes type='trajectory' by
        default — episodes are not germline).

        On conflict: procedure/outcome/tags updated, confidence kept at max.
        """
        if outcome not in {"success", "failure", "partial"}:
            raise ValueError(
                f"outcome must be one of success|failure|partial, got {outcome!r}"
            )
        scope = "Personal" if outcome == "failure" else "Project"
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        now = datetime.now(timezone.utc).date().isoformat()

        with self._write_lock:
            conn = self._get_conn()
            exists = conn.execute(
                "SELECT 1 FROM genome WHERE id = ?", (trajectory_id,)
            ).fetchone() is not None
            conn.execute(
                """INSERT INTO genome
                   (id, cell_origin, type, scope, procedure, valid_from,
                    confidence, outcome, tokens, duration_ms, tags)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       procedure   = excluded.procedure,
                       outcome     = excluded.outcome,
                       tokens      = COALESCE(excluded.tokens, genome.tokens),
                       duration_ms = COALESCE(excluded.duration_ms, genome.duration_ms),
                       tags        = excluded.tags,
                       confidence  = MAX(genome.confidence, excluded.confidence)""",
                (trajectory_id, cell, "trajectory", scope, procedure, now,
                 confidence, outcome, tokens, duration_ms, tags_json),
            )
            conn.commit()
            action = "updated" if exists else "inserted"
            logger.info(
                f"[genome] {action} trajectory '{trajectory_id}' for cell "
                f"'{cell}' (outcome={outcome}, confidence={confidence:.0%})"
            )
            return action

    def search_trajectories(
        self,
        query: str,
        outcome: str | None = None,
        cell: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """FTS5 search restricted to trajectories, with optional outcome/cell/tag filters."""
        today = datetime.now(timezone.utc).date().isoformat()
        clauses = [
            "g.type = 'trajectory'",
            "genome_fts MATCH ?",
            "(g.valid_to IS NULL OR g.valid_to > ?)",
        ]
        params: list = [query, today]
        if outcome:
            clauses.append("g.outcome = ?")
            params.append(outcome)
        if cell:
            clauses.append("g.cell_origin = ?")
            params.append(cell)
        if tag:
            # tags is JSON array; use LIKE on the serialised form.
            clauses.append("g.tags LIKE ?")
            params.append(f'%"{tag}"%')
        params.append(limit)

        conn = self._get_conn()
        rows = conn.execute(
            f"""SELECT g.* FROM genome g
                JOIN genome_fts f ON g.rowid = f.rowid
                WHERE {' AND '.join(clauses)}
                ORDER BY rank, g.confidence DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trajectory(self, trajectory_id: str) -> dict | None:
        """Fetch one trajectory row by id. Returns None when the id is
        missing OR when the row exists but has a non-trajectory type."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM genome WHERE id = ? AND type = 'trajectory'",
            (trajectory_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def trajectory_stats(self, cell: str | None = None) -> dict:
        """Count trajectories by outcome (and total) for monitoring."""
        today = datetime.now(timezone.utc).date().isoformat()
        conn = self._get_conn()
        filters = ["type = 'trajectory'", "(valid_to IS NULL OR valid_to > ?)"]
        params: list = [today]
        if cell:
            filters.append("cell_origin = ?")
            params.append(cell)

        total = conn.execute(
            f"SELECT COUNT(*) FROM genome WHERE {' AND '.join(filters)}",
            params,
        ).fetchone()[0]
        by_outcome_rows = conn.execute(
            f"SELECT outcome, COUNT(*) c FROM genome "
            f"WHERE {' AND '.join(filters)} GROUP BY outcome",
            params,
        ).fetchall()
        by_outcome = {"success": 0, "failure": 0, "partial": 0}
        for r in by_outcome_rows:
            if r["outcome"] in by_outcome:
                by_outcome[r["outcome"]] = r["c"]
        return {"total": total, "by_outcome": by_outcome}

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

    def decay_unused_skills(
        self,
        decay_rate: float = 0.95,
        silence_threshold: float = 0.3,
        min_idle_days: int = 7,
    ) -> dict[str, int]:
        """Apply exponential decay to unused skills.

        Formula: ``new_conf = confidence * (decay_rate ** days_unused)``

        Guards:
        - Scars (type='scar') are immune — avoidance memory is permanent
        - Skills used within *min_idle_days* are skipped
        - Skills with last_used=NULL are excluded (never used = never decaying)
        - Already-silenced skills (valid_to IS NOT NULL) are excluded

        Returns counts: ``{"decayed": N, "silenced": M, "skipped": K}``
        """
        now = datetime.now(timezone.utc)
        counts = {"decayed": 0, "silenced": 0, "skipped": 0}

        with self._write_lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT id, confidence, last_used, type FROM genome
                   WHERE valid_to IS NULL AND last_used IS NOT NULL"""
            ).fetchall()

            for row in rows:
                # Scars don't decay
                if row["type"] == "scar":
                    counts["skipped"] += 1
                    continue

                last_used_str = row["last_used"]
                try:
                    last_used = datetime.fromisoformat(last_used_str)
                    # Ensure timezone-aware comparison
                    if last_used.tzinfo is None:
                        last_used = last_used.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    counts["skipped"] += 1
                    continue

                days = (now - last_used).days
                if days < min_idle_days:
                    counts["skipped"] += 1
                    continue

                new_conf = row["confidence"] * (decay_rate ** days)
                if new_conf < silence_threshold:
                    conn.execute(
                        "UPDATE genome SET valid_to = ? WHERE id = ? AND valid_to IS NULL",
                        (now.date().isoformat(), row["id"]),
                    )
                    counts["silenced"] += 1
                    logger.info(
                        f"[genome] decay silenced '{row['id']}' "
                        f"(conf={row['confidence']:.2f}→{new_conf:.4f}, days={days})"
                    )
                else:
                    conn.execute(
                        "UPDATE genome SET confidence = ? WHERE id = ?",
                        (round(new_conf, 4), row["id"]),
                    )
                    counts["decayed"] += 1

            conn.commit()

        if counts["decayed"] or counts["silenced"]:
            logger.info(
                f"[genome] decay_unused_skills: {counts['decayed']} decayed, "
                f"{counts['silenced']} silenced, {counts['skipped']} skipped"
            )
        return counts

    # ─────────────────────────────────────────
    # Week 3-4: Skill Registry (promotion + decay v2)
    # ─────────────────────────────────────────

    # Tier thresholds — kept as class constants so tests and /api/skill/*
    # consumers can read them without hard-coding magic numbers.
    TIER1_MIN_USES = 100
    TIER1_MIN_CONFIDENCE = 0.85
    TIER2_MIN_USES = 30
    TIER2_MIN_CONFIDENCE = 0.70

    def promote_skills(self) -> dict[str, int]:
        """Promote hot & reliable skills to tier1/tier2.

        Rules (applied to type='skill' only, never to trajectories/scars/patterns):
        - uses >= TIER1_MIN_USES AND confidence >= TIER1_MIN_CONFIDENCE → tier1
        - uses >= TIER2_MIN_USES AND confidence >= TIER2_MIN_CONFIDENCE
          AND not already tier1 → tier2

        Monotonic: a skill that once reached tier1 is never downgraded by this
        call. Only ``silence_stale_skills_v2`` (soft silence) or a future
        ``demote_skills`` can undo it — intentionally, to avoid flapping.

        Returns a dict ``{"tier1": N, "tier2": M}`` of newly promoted rows.
        """
        today = datetime.now(timezone.utc).date().isoformat()
        with self._write_lock:
            conn = self._get_conn()
            # Tier1 — only promote rows currently below tier1 (NULL or tier2).
            conn.execute(
                """UPDATE genome SET tier = 'tier1'
                   WHERE type = 'skill'
                     AND (valid_to IS NULL OR valid_to > ?)
                     AND uses >= ?
                     AND confidence >= ?
                     AND (tier IS NULL OR tier = 'tier2')""",
                (today, self.TIER1_MIN_USES, self.TIER1_MIN_CONFIDENCE),
            )
            tier1_n = conn.execute("SELECT changes()").fetchone()[0]

            # Tier2 — only promote rows currently NULL (never downgrade tier1).
            conn.execute(
                """UPDATE genome SET tier = 'tier2'
                   WHERE type = 'skill'
                     AND (valid_to IS NULL OR valid_to > ?)
                     AND uses >= ?
                     AND confidence >= ?
                     AND tier IS NULL""",
                (today, self.TIER2_MIN_USES, self.TIER2_MIN_CONFIDENCE),
            )
            tier2_n = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        if tier1_n or tier2_n:
            logger.info(
                f"[genome] promote_skills: +{tier1_n} tier1, +{tier2_n} tier2"
            )
        return {"tier1": tier1_n, "tier2": tier2_n}

    def silence_stale_skills_v2(
        self,
        unused_days: int = 30,
        min_uses: int = 5,
        min_confidence: float = 0.3,
    ) -> int:
        """Auto-decay (epigenetic silencing) — finer-grained than v1.

        A skill row is silenced (``valid_to = today``) when ANY of:

        1. ``confidence < min_confidence`` — irrespective of uses.
        2. ``uses < min_uses`` AND the row has been dormant for more than
           ``unused_days`` days. Dormancy is measured against ``last_used``
           when set, otherwise against ``valid_from`` (so a skill recorded
           long ago and never used still ages out).

        Applies to ``type='skill'`` only — trajectories/scars are governed
        by their own lifecycle.

        Returns the number of newly silenced rows. Idempotent: running twice
        on a stable DB silences nothing the second time.
        """
        cutoff_ts = time.time() - unused_days * 86400
        cutoff_date = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).date().isoformat()
        today = datetime.now(timezone.utc).date().isoformat()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                """UPDATE genome SET valid_to = ?
                   WHERE type = 'skill'
                     AND valid_to IS NULL
                     AND (
                         confidence < ?
                         OR (
                             uses < ?
                             AND COALESCE(last_used, valid_from) < ?
                         )
                     )""",
                (today, min_confidence, min_uses, cutoff_date),
            )
            n = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        if n:
            logger.info(
                f"[genome] silence_stale_skills_v2: silenced {n} stale skills "
                f"(min_uses={min_uses}, unused_days={unused_days}, "
                f"min_confidence={min_confidence})"
            )
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
        domain: str | None = None,
    ) -> list[dict]:
        """Get active genome entries for a cell."""
        today = datetime.now(timezone.utc).date().isoformat()
        filters = [
            "cell_origin = ?",
            "valid_from <= ?",
            "(valid_to IS NULL OR valid_to > ?)",
            "confidence >= ?",
        ]
        # valid_to > today check needs today again
        params: list = [cell, today, today, min_confidence]
        if entry_type:
            filters.append("type = ?")
            params.append(entry_type)
        if scope:
            filters.append("scope = ?")
            params.append(scope)
        if domain:
            filters.append("domain = ?")
            params.append(domain)
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
