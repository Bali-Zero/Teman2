"""Integration regression coverage for migration 132.

The real failure mode was a partially bootstrapped ``lkpm_reports`` table:
``CREATE TABLE IF NOT EXISTS`` skipped table creation, then the migration tried
to relax NOT NULL on cumulative columns that did not exist yet.
"""
from __future__ import annotations

import pathlib

import asyncpg
import pytest

from backend.db.migration_manager import _extract_rollback_sql

pytestmark = pytest.mark.integration


_MIG_DIR = pathlib.Path(__file__).parent.parent.parent / "db" / "migrations_v2"

_REALIZATION_COLUMNS = (
    "realized_equipment_domestic",
    "realized_equipment_import",
    "realized_building_domestic",
    "realized_building_import",
    "realized_vehicle_domestic",
    "realized_vehicle_import",
    "realized_land",
    "realized_working_capital",
    "realized_other",
    "cumulative_equipment_domestic",
    "cumulative_equipment_import",
    "cumulative_building_domestic",
    "cumulative_building_import",
    "cumulative_vehicle_domestic",
    "cumulative_vehicle_import",
    "cumulative_land",
    "cumulative_working_capital",
    "cumulative_other",
)


def _forward_sql(sql_text: str) -> str:
    return sql_text.split("-- === ROLLBACK ===", maxsplit=1)[0].strip()


async def _column_exists(conn: asyncpg.Connection, column_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_attribute
                WHERE attrelid = 'lkpm_reports'::regclass
                  AND attname = $1
                  AND NOT attisdropped
            )
            """,
            column_name,
        ),
    )


async def _column_not_null(conn: asyncpg.Connection, column_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT attnotnull
            FROM pg_attribute
            WHERE attrelid = 'lkpm_reports'::regclass
              AND attname = $1
              AND NOT attisdropped
            """,
            column_name,
        ),
    )


@pytest.mark.asyncio
async def test_migration_132_applies_to_partial_lkpm_reports(
    db_tx: asyncpg.Connection,
) -> None:
    """Migration 132 must converge an existing partial table.

    A temp table shadows the public table on this connection, so the test can
    execute the production SQL without mutating the shared dev schema.
    """
    await db_tx.execute(
        """
        CREATE TEMP TABLE lkpm_reports (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            year INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            realized_equipment_domestic BIGINT NOT NULL DEFAULT 0
        )
        """
    )

    sql_text = (_MIG_DIR / "132_legacy_lkpm_reports.sql").read_text(
        encoding="utf-8",
    )
    assert _extract_rollback_sql(sql_text), "132 must keep a rollback block"

    await db_tx.execute(_forward_sql(sql_text))

    for column_name in _REALIZATION_COLUMNS:
        assert await _column_exists(db_tx, column_name), column_name
        assert not await _column_not_null(db_tx, column_name), column_name

    assert await _column_exists(db_tx, "company_id")
