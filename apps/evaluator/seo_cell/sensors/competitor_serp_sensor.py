"""Competitor SERP Sensor — reads cached SERP snapshots.

The v2.1 memo is explicit on this sensor's boundaries:
  - max 2 vendors (Cekindo + Emerhub) — the "industry" is tiny and
    adding more vendors creates noise, not signal
  - 7-day cache TTL — daily SERP scraping would create decision
    contamination (we'd see competitors react to OUR changes before
    real users do, polluting the calibrator)
  - NEVER scrape on the pulse path — the cell pulses every 24h and
    must stay fast and deterministic; scraping is a separate cron
    job that populates the cache

This file is the READER only. The WRITER lives in
`scripts/scrape_competitor_serp.py` (Sprint 2f).

Cache shape (SQLite at DATA_DIR/competitor_serp_cache.db):
  CREATE TABLE IF NOT EXISTS competitor_serp (
    query         TEXT NOT NULL,
    vendor        TEXT NOT NULL,
    rank          INTEGER,          -- NULL means "not in top 100"
    url           TEXT,
    title         TEXT,
    captured_at   TIMESTAMP NOT NULL,
    PRIMARY KEY (query, vendor)
  )
  CREATE INDEX IF NOT EXISTS idx_captured ON competitor_serp (captured_at);

The sensor:
  - returns rows only where captured_at is within the TTL window
  - aggregates per vendor: {vendor: {query: rank}}
  - reports captured_at age distribution for staleness visibility
  - never creates the file; if absent → yellow (cache not populated)

Failure policy mirrors other sensors: never raises.
  - cache file absent             → yellow, cache_not_populated
  - sqlite3 ImportError (never)   → red,    import_error
  - DB corruption / query error   → red,    db_error
  - any other exception           → red,    unexpected
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cell_core.types import SensorReading

from apps.evaluator.seo_cell.config import (
    COMPETITOR_CACHE_DB,
    COMPETITOR_CACHE_TTL_SECONDS,
    COMPETITOR_DOMAINS,
)

logger = logging.getLogger("seo_cell.sensors.competitor_serp")


class CompetitorSERPSensor:
    name = "competitor_serp"

    def __init__(
        self,
        vendors: tuple[str, ...] = COMPETITOR_DOMAINS,
        cache_db: Path = COMPETITOR_CACHE_DB,
        ttl_seconds: int = COMPETITOR_CACHE_TTL_SECONDS,
    ) -> None:
        self._vendors = vendors
        self._cache_db = cache_db
        self._ttl_seconds = ttl_seconds

    async def read(self, **context) -> SensorReading:
        if not self._cache_db.exists():
            return self._yellow(
                "cache_not_populated",
                f"SERP cache DB absent at {self._cache_db}",
            )

        try:
            rows = self._read_cache_blocking()
        except _SERPError as e:
            return self._red(e.code, str(e))
        except Exception as e:  # noqa: BLE001 — sensor must not raise
            logger.exception("[competitor_serp] unexpected failure")
            return self._red("unexpected", repr(e))

        # Aggregate: {vendor: {query: rank}}
        ranks: dict[str, dict[str, int | None]] = {v: {} for v in self._vendors}
        captured_ages: list[float] = []  # seconds since captured
        now = datetime.now(timezone.utc)
        fresh_rows = 0
        stale_rows_dropped = 0

        cutoff = now - timedelta(seconds=self._ttl_seconds)
        for r in rows:
            captured = _parse_ts(r["captured_at"])
            if captured is None or captured < cutoff:
                stale_rows_dropped += 1
                continue
            fresh_rows += 1
            vendor = r["vendor"]
            if vendor not in ranks:
                # Scraper wrote a vendor we don't track — ignore silently
                # to avoid widening our surface
                continue
            ranks[vendor][r["query"]] = r["rank"]
            captured_ages.append((now - captured).total_seconds())

        query_count = len({q for vendor_map in ranks.values() for q in vendor_map})
        avg_age_hours = (
            sum(captured_ages) / len(captured_ages) / 3600.0
            if captured_ages
            else None
        )

        status = "green" if fresh_rows > 0 else "yellow"
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value={
                "ranks": ranks,
                "vendors": list(self._vendors),
                "query_count": query_count,
                "fresh_rows": fresh_rows,
            },
            metadata={
                "cache_db": str(self._cache_db),
                "ttl_seconds": self._ttl_seconds,
                "stale_rows_dropped": stale_rows_dropped,
                "avg_age_hours": avg_age_hours,
            },
        )

    # ── internal ──────────────────────────────────────────────────────────

    def _read_cache_blocking(self) -> list[dict[str, Any]]:
        try:
            conn = sqlite3.connect(str(self._cache_db))
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise _SERPError("db_error", f"open failed: {e!r}") from e

        try:
            # Reader-only: query the table, tolerate schema drift by
            # selecting named columns and letting a failure surface as red
            cursor = conn.execute(
                """
                SELECT query, vendor, rank, url, title, captured_at
                FROM competitor_serp
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            # Table missing = sensor yellow (cache not initialized), but we
            # hit this path only if the DB file exists but the table doesn't.
            # Re-raise as structured error so the caller can decide.
            raise _SERPError("db_error", f"query failed: {e!r}") from e
        except Exception as e:
            raise _SERPError("db_error", f"query failed: {e!r}") from e
        finally:
            conn.close()

    def _yellow(self, code: str, msg: str) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={
                "ranks": {v: {} for v in self._vendors},
                "vendors": list(self._vendors),
                "query_count": 0,
                "fresh_rows": 0,
            },
            metadata={
                "cache_db": str(self._cache_db),
                "ttl_seconds": self._ttl_seconds,
                "error_code": code,
                "error": msg,
            },
        )

    def _red(self, code: str, msg: str) -> SensorReading:
        logger.warning("[competitor_serp] red: %s — %s", code, msg)
        return SensorReading(
            sensor_name=self.name,
            status="red",
            value={
                "ranks": {v: {} for v in self._vendors},
                "vendors": list(self._vendors),
                "query_count": 0,
                "fresh_rows": 0,
            },
            metadata={
                "cache_db": str(self._cache_db),
                "ttl_seconds": self._ttl_seconds,
                "error_code": code,
                "error": msg,
            },
        )


class _SERPError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _parse_ts(v: Any) -> datetime | None:
    """Accepts ISO strings, datetime, or unix epoch seconds."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None
