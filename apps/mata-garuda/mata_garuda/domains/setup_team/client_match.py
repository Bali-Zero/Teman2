"""Client match — KBLI overlap (Task 7).

Algorithm:
  For each obligation, find clients where
    obligation.kbli_codes_affected ∩ client.kbli_codes != ∅.
  Insert into client_obligation_match.
  Return Match payloads (no Telegram send — that's the cron's job in T9).

SQLite schema additions:

  CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      kbli_codes TEXT NOT NULL,    -- JSON array as text
      active INTEGER NOT NULL DEFAULT 1,
      contact TEXT
  );

  CREATE TABLE IF NOT EXISTS client_obligation_match (
      obligation_id INTEGER NOT NULL,
      client_id INTEGER NOT NULL,
      matched_kbli TEXT NOT NULL,  -- JSON array as text
      alerted_at TEXT,
      human_acknowledged_at TEXT,
      PRIMARY KEY (obligation_id, client_id)
  );

The single Telegram channel `#setup-team-alerts` is the cross-domain
contract per NLM ground-truth (NOT one-channel-per-domain). The cron
in T9 reads matches with alerted_at IS NULL and dispatches; this
module only stages.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from mata_garuda.domains.setup_team.types import Client, Match

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "setup_team.sqlite"
)

CLIENT_MATCH_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kbli_codes TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    contact TEXT
);

CREATE TABLE IF NOT EXISTS client_obligation_match (
    obligation_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    matched_kbli TEXT NOT NULL,
    alerted_at TEXT,
    human_acknowledged_at TEXT,
    PRIMARY KEY (obligation_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_client_match_alerted
    ON client_obligation_match(alerted_at);
"""


def _open_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(CLIENT_MATCH_SCHEMA_DDL)
    conn.commit()
    return conn


def upsert_client(
    name: str,
    kbli_codes: tuple[str, ...],
    *,
    active: bool = True,
    contact: str = "",
    db_path: Path | str | None = None,
) -> int:
    """Insert or update a client row by name. Returns client id."""
    conn = _open_db(db_path)
    try:
        cursor = conn.cursor()
        existing = cursor.execute(
            "SELECT id FROM clients WHERE name=?", (name,)
        ).fetchone()
        kbli_json = json.dumps(list(kbli_codes))
        if existing:
            cursor.execute(
                """UPDATE clients
                   SET kbli_codes=?, active=?, contact=?
                   WHERE id=?""",
                (kbli_json, 1 if active else 0, contact, existing["id"]),
            )
            conn.commit()
            return int(existing["id"])
        cursor.execute(
            "INSERT INTO clients (name, kbli_codes, active, contact) VALUES (?, ?, ?, ?)",
            (name, kbli_json, 1 if active else 0, contact),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def _row_to_client(row) -> Client:
    return Client(
        id=int(row["id"]),
        name=row["name"],
        kbli_codes=tuple(json.loads(row["kbli_codes"])),
        active=bool(row["active"]),
        contact=row["contact"] or "",
    )


def list_active_clients(db_path: Path | str | None = None) -> list[Client]:
    conn = _open_db(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM clients WHERE active=1 ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_client(r) for r in rows]


def _load_obligation(
    conn: sqlite3.Connection, obligation_id: int
) -> Optional[dict]:
    """Load the columns we need for matching. Returns None if not found OR if
    the obligations table doesn't exist yet (client_match opened a fresh DB
    before any obligation was extracted — degrade quietly)."""
    try:
        row = conn.execute(
            """SELECT id, text, obligation_type, article_ref, kbli_codes_affected,
                      regulation_source_id
               FROM obligations WHERE id=?""",
            (obligation_id,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            logger.info("obligations table absent — no extractions yet")
            return None
        raise
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "text": row["text"],
        "obligation_type": row["obligation_type"],
        "article_ref": row["article_ref"],
        "kbli_codes_affected": tuple(json.loads(row["kbli_codes_affected"] or "[]")),
        "regulation_source_id": row["regulation_source_id"],
    }


def match_obligations_to_clients(
    obligation_id: int,
    *,
    db_path: Path | str | None = None,
) -> list[Match]:
    """Match one obligation to all active clients with KBLI overlap.

    Returns Match dataclasses with `alert_payload` populated. The payload
    is a dict suitable for Telegram dispatch; it does NOT include any
    secret/PII beyond client name + KBLI codes (which are public business
    identifiers).

    Side effect: inserts into client_obligation_match (PRIMARY KEY
    (obligation_id, client_id)) — re-running for the same obligation does
    NOT duplicate rows (INSERT OR IGNORE).
    """
    conn = _open_db(db_path)
    try:
        obligation = _load_obligation(conn, obligation_id)
        if obligation is None:
            logger.warning("obligation %s not found, skip match", obligation_id)
            return []
        obl_kbli = set(obligation["kbli_codes_affected"])
        if not obl_kbli:
            return []

        client_rows = conn.execute(
            "SELECT * FROM clients WHERE active=1"
        ).fetchall()

        matches: list[Match] = []
        cursor = conn.cursor()
        for row in client_rows:
            client = _row_to_client(row)
            client_kbli = set(client.kbli_codes)
            overlap = obl_kbli & client_kbli
            if not overlap:
                continue
            matched = tuple(sorted(overlap))
            payload = {
                "channel": "#setup-team-alerts",
                "client_id": client.id,
                "client_name": client.name,
                "obligation_id": obligation["id"],
                "obligation_type": obligation["obligation_type"],
                "obligation_text": obligation["text"],
                "article_ref": obligation["article_ref"],
                "matched_kbli": list(matched),
                "regulation_source_id": obligation["regulation_source_id"],
            }
            cursor.execute(
                """INSERT OR IGNORE INTO client_obligation_match
                   (obligation_id, client_id, matched_kbli)
                   VALUES (?, ?, ?)""",
                (obligation["id"], client.id, json.dumps(list(matched))),
            )
            matches.append(
                Match(
                    obligation_id=obligation["id"],
                    client_id=client.id,
                    matched_kbli=matched,
                    alert_payload=payload,
                )
            )
        conn.commit()
    finally:
        conn.close()
    return matches


def mark_alerted(
    obligation_id: int,
    client_id: int,
    *,
    when: Optional[str] = None,
    db_path: Path | str | None = None,
) -> bool:
    """Stamp alerted_at on a (obligation, client) pair. Idempotent: re-stamping
    is allowed; the cron decides via 'WHERE alerted_at IS NULL' to find
    pending dispatches.
    """
    from datetime import datetime, timezone

    ts = when or datetime.now(timezone.utc).isoformat()
    conn = _open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE client_obligation_match
               SET alerted_at=?
               WHERE obligation_id=? AND client_id=?""",
            (ts, obligation_id, client_id),
        )
        conn.commit()
        return bool(cursor.rowcount)
    finally:
        conn.close()


__all__ = [
    "CLIENT_MATCH_SCHEMA_DDL",
    "list_active_clients",
    "mark_alerted",
    "match_obligations_to_clients",
    "upsert_client",
]
