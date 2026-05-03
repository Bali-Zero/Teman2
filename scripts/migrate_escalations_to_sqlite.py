#!/usr/bin/env python3
"""P1-8 — Migrate per-machine escalations JSONL into a local SQLite index.

Architecture (per ADR-3 v3.3 in NB-1, kept INTACT):
- ``shared/escalations_pro.jsonl`` and ``shared/escalations_air.jsonl`` remain
  the **federation bus** (cross-machine eventual consistency via git).
- This SQLite database lives at ``~/.agent/decisions/escalations.sqlite`` —
  **outside** the git tree, on each machine's local filesystem only. It is a
  per-machine **local index/replica** of the JSONL, used to:
    1. Prune disk growth (``shared/escalations_pro.jsonl`` is 4041+ lines).
    2. Provide indexed active-query for consumers (e.g. metabolic collector).
    3. Support deduplication (audit_id where present, else canonical-JSON
       hash).

Subcommands
-----------
- ``import``  : read JSONL → INSERT OR IGNORE (idempotent, dedup_key UNIQUE).
- ``prune``   : DELETE rows where ``resolved_at`` is set and older than N days.
- ``archive`` : export unresolved rows older than N days to a gzip JSONL,
                then DELETE them from the main DB.

The cron LaunchAgent (``infra/launchd/com.nuzantara.escalations-prune.plist``)
runs ``prune`` and ``archive`` daily at 03:00 WITA via
``scripts/escalations_prune_cron.sh``.

This script never touches the canonical JSONL files.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger("migrate_escalations_to_sqlite")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = Path.home() / ".agent" / "decisions" / "escalations.sqlite"
DEFAULT_ARCHIVE_DIR = Path.home() / ".agent" / "decisions"

# Project default JSONL sources. Can be overridden via --source-jsonl.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = [
    _PROJECT_ROOT / "shared" / "escalations_pro.jsonl",
    _PROJECT_ROOT / "shared" / "escalations_air.jsonl",
]

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS escalations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key     TEXT NOT NULL UNIQUE,
    audit_id      TEXT,
    job           TEXT,
    type          TEXT,
    severity      TEXT,
    machine       TEXT,
    error_summary TEXT,
    task_file     TEXT,
    ts            REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    resolved_at   REAL,
    raw_json      TEXT NOT NULL,
    imported_at   REAL NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_escalations_active
    ON escalations(resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_escalations_machine
    ON escalations(machine);
CREATE INDEX IF NOT EXISTS idx_escalations_ts
    ON escalations(ts);
CREATE INDEX IF NOT EXISTS idx_escalations_job_ts
    ON escalations(job, ts);
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------
def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    # WAL: many concurrent cron writers (DLQ autopilot, sentinel, manual).
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")  # 5s — handles cron-burst overlap
    return conn


def ensure_schema(db_path: Path) -> None:
    """Create the table + indexes if they don't exist. Idempotent."""
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------
def dedup_key_for(row: dict) -> str:
    """Return a stable dedup key for an escalation row.

    Strategy:
    - If ``audit_id`` is set (rare today), use ``audit:<audit_id>|<machine>``.
    - Otherwise, hash the canonical JSON (sort_keys=True, no whitespace) of
      the row. The hash is stable across re-serialization but changes if any
      field changes — which is the desired semantics for "same row".

    This solves the original plan's UNIQUE(audit_id, machine) bug: SQLite's
    UNIQUE treats two NULLs as distinct, so rows with NULL audit_id would
    duplicate freely.
    """
    audit_id = row.get("audit_id")
    if audit_id:
        machine = row.get("machine") or "?"
        return f"audit:{audit_id}|{machine}"
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"sha:{digest}"


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------
_INSERT_SQL = """
INSERT OR IGNORE INTO escalations (
    dedup_key, audit_id, job, type, severity, machine,
    error_summary, task_file, ts, status, resolved_at, raw_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _insert_row(
    conn: sqlite3.Connection, row: dict, raw_json_str: Optional[str] = None
) -> bool:
    """Insert one row. Returns True if a new row was inserted, False if dedup'd.

    ``raw_json_str`` lets callers pass the original line verbatim; if omitted,
    we re-serialize the dict (canonical form).
    """
    raw = raw_json_str if raw_json_str is not None else json.dumps(
        row, sort_keys=True, separators=(",", ":")
    )
    severity = row.get("severity") or row.get("priority")
    ts = row.get("ts")
    if ts is None:
        ts = time.time()
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        ts = time.time()

    resolved_at = row.get("resolved_at")
    if resolved_at is not None:
        try:
            resolved_at = float(resolved_at)
        except (TypeError, ValueError):
            resolved_at = None

    cur = conn.execute(
        _INSERT_SQL,
        (
            dedup_key_for(row),
            row.get("audit_id"),
            row.get("job"),
            row.get("type"),
            severity,
            row.get("machine"),
            row.get("error_summary"),
            row.get("task_file"),
            ts,
            row.get("status") or "pending",
            resolved_at,
            raw,
        ),
    )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Subcommand: import
# ---------------------------------------------------------------------------
def import_jsonl(
    sources: Iterable[Path], db_path: Path, batch_size: int = 1000
) -> int:
    """Import every line of every source JSONL into SQLite. Idempotent.

    Returns the number of NEW rows actually inserted (after dedup). The
    canonical JSONL files are not modified.
    """
    ensure_schema(db_path)
    inserted = 0
    skipped_parse = 0
    conn = _connect(db_path)
    try:
        n_in_batch = 0
        for src in sources:
            src = Path(src)
            if not src.exists():
                logger.info("source missing, skipping: %s", src)
                continue
            with src.open("r", encoding="utf-8") as f:
                for line_no, raw in enumerate(f, start=1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        row = json.loads(raw)
                        if not isinstance(row, dict):
                            skipped_parse += 1
                            continue
                    except json.JSONDecodeError:
                        skipped_parse += 1
                        continue
                    try:
                        if _insert_row(conn, row, raw):
                            inserted += 1
                    except sqlite3.Error as exc:  # noqa: BLE001
                        logger.warning(
                            "INSERT failed for %s:%d — %s", src, line_no, exc
                        )
                        continue
                    n_in_batch += 1
                    if n_in_batch >= batch_size:
                        conn.commit()
                        n_in_batch = 0
        conn.commit()
    finally:
        conn.close()
    logger.info(
        "import: inserted=%d skipped_parse=%d sources=%s",
        inserted,
        skipped_parse,
        [str(s) for s in sources],
    )
    return inserted


# ---------------------------------------------------------------------------
# Subcommand: prune
# ---------------------------------------------------------------------------
def prune(db_path: Path, older_than_days: int = 30) -> int:
    """Delete rows that have been *explicitly* resolved more than N days ago.

    Returns the number of rows deleted. Never auto-marks anything resolved —
    that's an operator decision.
    """
    ensure_schema(db_path)
    cutoff = time.time() - older_than_days * 86400
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM escalations "
            "WHERE resolved_at IS NOT NULL AND resolved_at < ?",
            (cutoff,),
        )
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    logger.info("prune: deleted=%d (older than %dd)", deleted, older_than_days)
    return deleted


# ---------------------------------------------------------------------------
# Subcommand: archive
# ---------------------------------------------------------------------------
def archive(
    db_path: Path,
    older_than_days: int = 90,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
) -> Optional[Path]:
    """Export unresolved rows older than N days to gzip JSONL, then delete.

    Returns the archive file path on success, or None if no rows qualified.
    """
    ensure_schema(db_path)
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    cutoff = time.time() - older_than_days * 86400
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT raw_json FROM escalations "
            "WHERE resolved_at IS NULL AND ts < ?",
            (cutoff,),
        ).fetchall()
        if not rows:
            logger.info("archive: nothing to archive (cutoff=%s)", cutoff)
            return None

        date_tag = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        out_path = archive_dir / f"escalations_archive_{date_tag}.jsonl.gz"
        # If multiple cron runs happen on the same day (manual + scheduled),
        # append a counter to keep the existing archive intact.
        suffix = 1
        while out_path.exists():
            out_path = archive_dir / (
                f"escalations_archive_{date_tag}_{suffix}.jsonl.gz"
            )
            suffix += 1

        with gzip.open(out_path, "wt", encoding="utf-8") as gz:
            for (raw_json,) in rows:
                gz.write(raw_json.rstrip("\n") + "\n")

        conn.execute(
            "DELETE FROM escalations "
            "WHERE resolved_at IS NULL AND ts < ?",
            (cutoff,),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "archive: wrote %d rows to %s (older than %dd)",
        len(rows),
        out_path,
        older_than_days,
    )
    return out_path


# ---------------------------------------------------------------------------
# Public writer (used by sentinel_lib.escalations.write_escalation)
# ---------------------------------------------------------------------------
def write_escalation_to_sqlite(
    row: dict, db_path: Optional[Path] = None
) -> bool:
    """Insert one escalation into SQLite. Idempotent. Used by the dual-writer.

    Honors the env var ``ESCALATIONS_SQLITE_PATH`` if ``db_path`` is None.
    Failures raise sqlite3.Error — caller is responsible for catch+log so
    the JSONL append is never blocked by SQLite issues.
    """
    if db_path is None:
        env_path = os.environ.get("ESCALATIONS_SQLITE_PATH")
        db_path = Path(env_path) if env_path else DEFAULT_DB_PATH
    ensure_schema(db_path)
    conn = _connect(db_path)
    try:
        inserted = _insert_row(conn, row)
        conn.commit()
        return inserted
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument(
        "--db-path", type=Path, default=DEFAULT_DB_PATH,
        help=f"SQLite path (default: {DEFAULT_DB_PATH})",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_import = sub.add_parser("import", help="Import JSONL files into SQLite")
    sp_import.add_argument(
        "--source-jsonl", type=Path, action="append", default=None,
        help="Path to a JSONL file (repeatable). Default: shared/escalations_*.jsonl"
    )
    sp_import.add_argument(
        "--batch-size", type=int, default=1000,
        help="Commit every N rows (default 1000)",
    )

    sp_prune = sub.add_parser("prune", help="Delete resolved rows older than N days")
    sp_prune.add_argument(
        "--older-than-days", type=int, default=30,
        help="Delete rows resolved more than N days ago (default 30)",
    )

    sp_archive = sub.add_parser(
        "archive", help="Archive unresolved rows older than N days"
    )
    sp_archive.add_argument(
        "--older-than-days", type=int, default=90,
        help="Archive unresolved rows older than N days (default 90)",
    )
    sp_archive.add_argument(
        "--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR,
        help=f"Archive directory (default: {DEFAULT_ARCHIVE_DIR})",
    )

    args = p.parse_args(argv)

    if args.cmd == "import":
        sources = args.source_jsonl or DEFAULT_SOURCES
        n = import_jsonl(sources=sources, db_path=args.db_path, batch_size=args.batch_size)
        print(f"inserted {n} new rows into {args.db_path}")
        return 0

    if args.cmd == "prune":
        n = prune(db_path=args.db_path, older_than_days=args.older_than_days)
        print(f"deleted {n} rows from {args.db_path}")
        return 0

    if args.cmd == "archive":
        out = archive(
            db_path=args.db_path,
            older_than_days=args.older_than_days,
            archive_dir=args.archive_dir,
        )
        if out is None:
            print("nothing to archive")
        else:
            print(f"archived to {out}")
        return 0

    p.error(f"unknown subcommand: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(_main())
