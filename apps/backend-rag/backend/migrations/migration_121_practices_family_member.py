"""Migration 121: practices.family_member_id — tag a practice with the family member it's for.

Use case: a main client (e.g. the KITAS sponsor) has dependents (spouse, children)
who each need their own dependent-KITAS process. Before this migration, the only
workaround was putting the dependent's name in Notes, which loses tracking and
makes a client with 3 dependents look like a single opaque "process" list.

The column is nullable — existing practices stay untagged and practices tied to
the main client (not a specific dependent) continue to work with NULL.

ON DELETE SET NULL: removing a family member unlinks the practice but keeps it
(the practice still happened, the billing/history must survive).

Author: Claude Opus 4.7 (1M context)
Date: 2026-04-22
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        ALTER TABLE practices
        ADD COLUMN IF NOT EXISTS family_member_id BIGINT
            REFERENCES client_family_members(id) ON DELETE SET NULL;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_practices_family_member_id "
        "ON practices (family_member_id) "
        "WHERE family_member_id IS NOT NULL;"
    )

    logger.info("Migration 121: practices.family_member_id + partial index applied")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_practices_family_member_id;")
    await conn.execute("ALTER TABLE practices DROP COLUMN IF EXISTS family_member_id;")
    logger.info("Migration 121 rollback: practices.family_member_id dropped")
