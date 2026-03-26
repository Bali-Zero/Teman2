"""Database connection for CELL pulse logging."""
import asyncpg
import logging
from cell.core.config import settings

logger = logging.getLogger("cell.db")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        logger.info("Creating database connection pool...")
        _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
        logger.info("Database pool created.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
        logger.info("Database pool closed.")
        _pool = None


async def log_pulse(
    pulse_number: int,
    health_status: str,
    response_time_ms: int,
    dna_intact: bool,
    budget_spent: float,
    budget_limit: float,
    memory_stm_count: int = 0,
    memory_ltm_count: int = 0,
    procedures_count: int = 0,
    cells_active: int = 1,
    cells_total: int = 1,
    action_taken: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_pulse_log
               (pulse_number, health_status, response_time_ms, dna_intact,
                budget_spent, budget_limit, memory_stm_count, memory_ltm_count,
                procedures_count, cells_active, cells_total, action_taken, error_message)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            pulse_number, health_status, response_time_ms, dna_intact,
            budget_spent, budget_limit, memory_stm_count, memory_ltm_count,
            procedures_count, cells_active, cells_total, action_taken, error_message,
        )
    except Exception as e:
        logger.error(f"Failed to log pulse to DB: {e}")
