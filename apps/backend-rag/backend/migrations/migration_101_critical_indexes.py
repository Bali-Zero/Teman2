"""
Migration 101: Critical missing indexes — Olympus DB Guardian

Indexes (all CONCURRENTLY):
  1. idx_conversations_session_id ON conversations (session_id)
     — Primary lookup key for session-based queries.
  2. idx_practices_assigned_to_partial ON practices (assigned_to)
       WHERE assigned_to IS NOT NULL
     — Partial index for RBAC filter; replaces plain idx_practices_assigned_to.
  3. idx_practices_client_id ON practices (client_id)
     — Most frequent join column.

Note: CREATE INDEX CONCURRENTLY cannot run inside a transaction,
so each statement is executed separately in apply().
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

MIGRATION_ID = "101_critical_indexes"

# --- UP: individual statements (executed one-by-one, no transaction) ----------

UP_SQL = [
    # 1. conversations.session_id
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_session_id
       ON conversations (session_id)""",

    # 2. practices.assigned_to — partial (RBAC filter)
    #    Drop the old plain index first so the partial replacement can take its name slot.
    "DROP INDEX IF EXISTS idx_practices_assigned_to",
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_assigned_to
       ON practices (assigned_to)
       WHERE assigned_to IS NOT NULL""",

    # 3. practices.client_id
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_client_id
       ON practices (client_id)""",
]

# --- DOWN: drop all three -------------------------------------------------------

DOWN_SQL = [
    "DROP INDEX IF EXISTS idx_conversations_session_id",
    "DROP INDEX IF EXISTS idx_practices_assigned_to",
    "DROP INDEX IF EXISTS idx_practices_client_id",
]


async def apply(conn: Any) -> None:
    """Apply migration: create critical indexes (each statement separate, no txn)."""
    for stmt in UP_SQL:
        await conn.execute(stmt)
    logger.info("Migration %s applied successfully", MIGRATION_ID)


async def rollback(conn: Any) -> None:
    """Rollback migration: drop all three indexes."""
    for stmt in DOWN_SQL:
        await conn.execute(stmt)
    logger.info("Migration %s rolled back successfully", MIGRATION_ID)
