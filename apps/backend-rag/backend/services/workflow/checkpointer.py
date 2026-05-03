"""
LangGraph PostgreSQL Checkpointer setup.

Uses psycopg3 (NOT asyncpg) — required by langgraph-checkpoint-postgres.
Pool size = 1: checkpointing is write-heavy but not concurrent OLTP.
With asyncpg pool_size=5 + psycopg3 pool_size=1, total = 6 connections/machine.
Well within Fly.io Postgres max_connections=100.

CRITICAL settings (from NB-9 research 2026-03-27):
- autocommit=True   → required for .setup() DDL statements
- row_factory=dict_row → required, otherwise TypeError at checkpoint read
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger("zantara.workflow.checkpointer")

_checkpointer: "AsyncPostgresSaver | None" = None
_psycopg_pool = None


async def get_checkpointer(database_url: str) -> "AsyncPostgresSaver":
    """
    Initialize and return the AsyncPostgresSaver singleton.
    Safe to call multiple times — returns cached instance.
    """
    global _checkpointer, _psycopg_pool

    if _checkpointer is not None:
        return _checkpointer

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    # psycopg3 pool — kept small (checkpointing only, not OLTP)
    _psycopg_pool = AsyncConnectionPool(
        conninfo=database_url,
        kwargs={
            "autocommit": True,  # MANDATORY for .setup() DDL
            "row_factory": dict_row,  # MANDATORY — prevents TypeError on checkpoint read
        },
        min_size=1,
        max_size=2,  # 1-2 connections: 1 active workflow + 1 spare
        open=False,
    )
    await _psycopg_pool.open()

    _checkpointer = AsyncPostgresSaver(_psycopg_pool)
    await _checkpointer.setup()  # Creates checkpoint tables on first run (idempotent)

    logger.info("LangGraph AsyncPostgresSaver initialized (psycopg3 pool_size=1-2)")
    return _checkpointer


async def close_checkpointer() -> None:
    """Close psycopg3 pool on app shutdown."""
    global _checkpointer, _psycopg_pool
    if _psycopg_pool:
        await _psycopg_pool.close()
        logger.info("LangGraph checkpointer pool closed")
    _checkpointer = None
    _psycopg_pool = None
