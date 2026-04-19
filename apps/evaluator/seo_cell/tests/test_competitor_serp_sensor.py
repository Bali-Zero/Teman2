"""CompetitorSERPSensor tests — operate on isolated temp SQLite caches."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors.competitor_serp_sensor import (
    CompetitorSERPSensor,
)


def _make_cache(db_path: Path, rows: list[tuple]) -> None:
    """Create schema and insert rows. Rows: (query, vendor, rank, url, title, captured_at)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS competitor_serp (
                query TEXT NOT NULL,
                vendor TEXT NOT NULL,
                rank INTEGER,
                url TEXT,
                title TEXT,
                captured_at TEXT NOT NULL,
                PRIMARY KEY (query, vendor)
            );
            """
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO competitor_serp
              (query, vendor, rank, url, title, captured_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


@pytest.mark.asyncio
async def test_cache_absent_returns_yellow(tmp_path):
    sensor = CompetitorSERPSensor(cache_db=tmp_path / "does-not-exist.db")
    reading = await sensor.read()
    assert isinstance(reading, SensorReading)
    assert reading.status == "yellow"
    assert reading.metadata["error_code"] == "cache_not_populated"
    assert reading.value["fresh_rows"] == 0


@pytest.mark.asyncio
async def test_happy_path_fresh_rows(tmp_path):
    db = tmp_path / "cache.db"
    now = datetime.now(timezone.utc).isoformat()
    _make_cache(
        db,
        [
            ("pt pma capital", "cekindo.com", 2, "https://cekindo.com/a", "Title A", now),
            ("pt pma capital", "emerhub.com", 4, "https://emerhub.com/a", "Title B", now),
            ("kitas e33g", "cekindo.com", 6, "https://cekindo.com/b", "Title C", now),
            ("kitas e33g", "emerhub.com", None, None, None, now),
        ],
    )
    sensor = CompetitorSERPSensor(
        cache_db=db,
        vendors=("cekindo.com", "emerhub.com"),
    )
    reading = await sensor.read()

    assert reading.status == "green"
    assert reading.value["fresh_rows"] == 4
    assert reading.value["query_count"] == 2
    assert reading.value["ranks"]["cekindo.com"]["pt pma capital"] == 2
    assert reading.value["ranks"]["cekindo.com"]["kitas e33g"] == 6
    assert reading.value["ranks"]["emerhub.com"]["kitas e33g"] is None


@pytest.mark.asyncio
async def test_stale_rows_dropped(tmp_path):
    """Rows older than TTL must not appear in the reading but remain in DB."""
    db = tmp_path / "cache.db"
    fresh = datetime.now(timezone.utc).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    _make_cache(
        db,
        [
            ("fresh query", "cekindo.com", 1, "u", "t", fresh),
            ("stale query", "cekindo.com", 2, "u", "t", stale),
        ],
    )
    sensor = CompetitorSERPSensor(
        cache_db=db,
        ttl_seconds=7 * 86400,
    )
    reading = await sensor.read()
    assert reading.value["fresh_rows"] == 1
    assert reading.metadata["stale_rows_dropped"] == 1
    assert "fresh query" in reading.value["ranks"]["cekindo.com"]
    assert "stale query" not in reading.value["ranks"]["cekindo.com"]


@pytest.mark.asyncio
async def test_unknown_vendor_ignored(tmp_path):
    """Rows from vendors not in our tracked set must be silently dropped.

    Keeps the sensor's output surface bounded even if the scraper
    widens its scope without our config being updated.
    """
    db = tmp_path / "cache.db"
    now = datetime.now(timezone.utc).isoformat()
    _make_cache(
        db,
        [
            ("q", "cekindo.com", 1, "u", "t", now),
            ("q", "unknown-vendor.com", 2, "u", "t", now),
        ],
    )
    sensor = CompetitorSERPSensor(
        cache_db=db,
        vendors=("cekindo.com", "emerhub.com"),
    )
    reading = await sensor.read()
    # fresh_rows counts what passed the TTL filter, vendor filter is after
    assert reading.value["fresh_rows"] == 2
    # But ranks only has our two tracked vendors
    assert set(reading.value["ranks"].keys()) == {"cekindo.com", "emerhub.com"}


@pytest.mark.asyncio
async def test_empty_cache_returns_yellow(tmp_path):
    db = tmp_path / "cache.db"
    _make_cache(db, [])  # schema created, no rows
    sensor = CompetitorSERPSensor(cache_db=db)
    reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["fresh_rows"] == 0


@pytest.mark.asyncio
async def test_db_corrupt_returns_red(tmp_path):
    """File exists but isn't a SQLite DB — sensor must return red."""
    db = tmp_path / "cache.db"
    db.write_text("not-a-sqlite-file")
    sensor = CompetitorSERPSensor(cache_db=db)
    reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "db_error"


@pytest.mark.asyncio
async def test_average_age_in_metadata(tmp_path):
    db = tmp_path / "cache.db"
    now = datetime.now(timezone.utc)
    _make_cache(
        db,
        [
            ("q1", "cekindo.com", 1, "u", "t", (now - timedelta(hours=2)).isoformat()),
            ("q2", "cekindo.com", 2, "u", "t", (now - timedelta(hours=6)).isoformat()),
        ],
    )
    sensor = CompetitorSERPSensor(cache_db=db)
    reading = await sensor.read()
    avg = reading.metadata["avg_age_hours"]
    assert avg is not None
    # Mean of 2h and 6h ≈ 4h
    assert 3.5 < avg < 4.5
