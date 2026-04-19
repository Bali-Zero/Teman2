#!/usr/bin/env python3
"""Competitor SERP cache writer — populates data/seo_cell/competitor_serp_cache.db.

This is the WRITER counterpart to
apps/evaluator/seo_cell/sensors/competitor_serp_sensor.py. It runs
out-of-band from the SEO Cell pulse (daily cron, manual invocation,
etc.) so the sensor never scrapes on the pulse path.

Sprint 2e scope (this file): schema init + optional seed for smoke
testing. Real SERP scraping via Exa/serp-api lands in Sprint 2f.

Usage:
  # Initialize schema only (idempotent)
  python3 scripts/scrape_competitor_serp.py --init

  # Seed a few rows for testing (also creates schema if missing)
  python3 scripts/scrape_competitor_serp.py --seed

  # Show cache stats
  python3 scripts/scrape_competitor_serp.py --stats

Schema contract — MUST match what the sensor expects:
  competitor_serp(query, vendor, rank, url, title, captured_at)
  PRIMARY KEY (query, vendor)
  INDEX on captured_at
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from apps.evaluator.seo_cell.config import (  # noqa: E402
    COMPETITOR_CACHE_DB,
    COMPETITOR_DOMAINS,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS competitor_serp (
    query       TEXT NOT NULL,
    vendor      TEXT NOT NULL,
    rank        INTEGER,
    url         TEXT,
    title       TEXT,
    captured_at TEXT NOT NULL,
    PRIMARY KEY (query, vendor)
);
CREATE INDEX IF NOT EXISTS idx_competitor_serp_captured
    ON competitor_serp (captured_at);
"""


def init_schema(db_path: Path = COMPETITOR_CACHE_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)
    print(f"[serp-cache] schema initialised at {db_path}")


def seed(db_path: Path = COMPETITOR_CACHE_DB) -> None:
    """Insert a handful of realistic rows so the sensor sees signal.

    Uses queries from the CRO audit (the 4 commercial-intent themes).
    Ranks are representative, not scraped — replace with real scraping
    in Sprint 2f.
    """
    init_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()
    # (query, vendor, rank, url, title)
    rows = [
        (
            "pt pma minimum capital indonesia",
            "cekindo.com",
            2,
            "https://cekindo.com/services/company-registration/pt-pma",
            "Setting Up a PT PMA in Indonesia | Cekindo",
        ),
        (
            "pt pma minimum capital indonesia",
            "emerhub.com",
            4,
            "https://emerhub.com/indonesia/pt-pma-setup-indonesia/",
            "PT PMA Setup in Indonesia | Emerhub",
        ),
        (
            "e33g remote worker kitas",
            "cekindo.com",
            6,
            "https://cekindo.com/services/immigration/remote-worker-visa",
            "Remote Worker Visa Indonesia (E33G) | Cekindo",
        ),
        (
            "e33g remote worker kitas",
            "emerhub.com",
            None,  # not in top 100
            None,
            None,
        ),
        (
            "pph 21 expat indonesia",
            "cekindo.com",
            3,
            "https://cekindo.com/services/tax/pph-21",
            "PPh 21 Indonesia Tax Guide | Cekindo",
        ),
        (
            "pph 21 expat indonesia",
            "emerhub.com",
            7,
            "https://emerhub.com/indonesia/tax/",
            "Indonesia Tax Services | Emerhub",
        ),
        (
            "hak pakai vs hgb foreign buyer bali",
            "cekindo.com",
            None,
            None,
            None,
        ),
        (
            "hak pakai vs hgb foreign buyer bali",
            "emerhub.com",
            None,
            None,
            None,
        ),
    ]
    with sqlite3.connect(str(db_path)) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO competitor_serp
              (query, vendor, rank, url, title, captured_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(q, v, r, u, t, now) for q, v, r, u, t in rows],
        )
        conn.commit()
    print(f"[serp-cache] seeded {len(rows)} rows at {db_path}")


def stats(db_path: Path = COMPETITOR_CACHE_DB) -> None:
    if not db_path.exists():
        print(f"[serp-cache] no cache DB at {db_path}")
        return
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) AS n FROM competitor_serp").fetchone()["n"]
        by_vendor = conn.execute(
            "SELECT vendor, COUNT(*) AS n FROM competitor_serp GROUP BY vendor ORDER BY n DESC"
        ).fetchall()
        oldest = conn.execute(
            "SELECT MIN(captured_at) AS t FROM competitor_serp"
        ).fetchone()["t"]
        newest = conn.execute(
            "SELECT MAX(captured_at) AS t FROM competitor_serp"
        ).fetchone()["t"]
    print(f"[serp-cache] total rows: {total}")
    for row in by_vendor:
        print(f"  {row['vendor']:>20s}: {row['n']}")
    print(f"  captured range: {oldest} → {newest}")
    print(f"  tracked vendors (per config): {', '.join(COMPETITOR_DOMAINS)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="create schema and exit")
    group.add_argument("--seed", action="store_true", help="seed demo rows (testing only)")
    group.add_argument("--stats", action="store_true", help="show cache stats")
    args = parser.parse_args()

    if args.init:
        init_schema()
    elif args.seed:
        seed()
    elif args.stats:
        stats()
    return 0


if __name__ == "__main__":
    sys.exit(main())
