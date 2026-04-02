#!/usr/bin/env python3
"""SQLite checkpoint database for KBLI enrichment pipeline.
Each code has a state: PENDING → TRIAGED → GENERATING → GENERATED → VALIDATING → COMPLETED | FAILED
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "kbli_enrich.db"

STATES = ("PENDING", "TRIAGED", "GENERATING", "GENERATED", "VALIDATING", "COMPLETED", "FAILED")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kbli_enrichment (
            code TEXT PRIMARY KEY,
            tier TEXT DEFAULT 'PENDING',       -- HIGH / MEDIUM / LOW
            state TEXT DEFAULT 'PENDING',
            triage_score REAL DEFAULT 0,
            triage_reasoning TEXT DEFAULT '',
            nlm_context TEXT DEFAULT '',        -- NLM regulatory intel (HIGH tier only)
            generated_content TEXT DEFAULT '',  -- JSON blob of 6 fields
            validation_errors TEXT DEFAULT '',  -- JSON array of errors
            retry_count INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn


def init_codes(conn: sqlite3.Connection, codes: list[dict]) -> int:
    """Initialize all codes as PENDING. Returns count of newly inserted codes."""
    inserted = 0
    for c in codes:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO kbli_enrichment (code) VALUES (?)",
                (c["kode_kbli_2025"],)
            )
            inserted += conn.total_changes
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


def set_triage(conn: sqlite3.Connection, code: str, tier: str, score: float, reasoning: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET tier=?, triage_score=?, triage_reasoning=?, state='TRIAGED', updated_at=datetime('now') WHERE code=?",
        (tier, score, reasoning, code)
    )
    conn.commit()


def set_state(conn: sqlite3.Connection, code: str, state: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET state=?, updated_at=datetime('now') WHERE code=?",
        (state, code)
    )
    conn.commit()


def set_nlm_context(conn: sqlite3.Connection, code: str, context: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET nlm_context=?, updated_at=datetime('now') WHERE code=?",
        (context, code)
    )
    conn.commit()


def set_generated(conn: sqlite3.Connection, code: str, content: dict) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET generated_content=?, state='GENERATED', updated_at=datetime('now') WHERE code=?",
        (json.dumps(content, ensure_ascii=False), code)
    )
    conn.commit()


def set_validated(conn: sqlite3.Connection, code: str) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET state='COMPLETED', updated_at=datetime('now') WHERE code=?",
        (code,)
    )
    conn.commit()


def set_failed(conn: sqlite3.Connection, code: str, errors: list[str]) -> None:
    conn.execute(
        "UPDATE kbli_enrichment SET state='FAILED', validation_errors=?, retry_count=retry_count+1, updated_at=datetime('now') WHERE code=?",
        (json.dumps(errors), code)
    )
    conn.commit()


def get_codes_by_state(conn: sqlite3.Connection, state: str) -> list[dict]:
    cur = conn.execute("SELECT * FROM kbli_enrichment WHERE state=?", (state,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_codes_by_tier(conn: sqlite3.Connection, tier: str) -> list[dict]:
    cur = conn.execute("SELECT * FROM kbli_enrichment WHERE tier=?", (tier,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_stats(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT state, COUNT(*) FROM kbli_enrichment GROUP BY state")
    return dict(cur.fetchall())


def get_tier_stats(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT tier, COUNT(*) FROM kbli_enrichment GROUP BY tier")
    return dict(cur.fetchall())


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO pipeline_meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    cur = conn.execute("SELECT value FROM pipeline_meta WHERE key=?", (key,))
    row = cur.fetchone()
    return row[0] if row else None
