"""Database connection for CELL pulse logging."""
import asyncpg
import logging
from typing import Any
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


async def create_patterns_table() -> None:
    """Create cell_patterns table if it does not exist."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_patterns (
                id              SERIAL PRIMARY KEY,
                health_status   VARCHAR(16) NOT NULL,
                response_time_ms INTEGER NOT NULL,
                budget_pct      FLOAT NOT NULL,
                action          VARCHAR(64) NOT NULL,
                reason          TEXT NOT NULL,
                confidence      FLOAT NOT NULL,
                tier_used       INTEGER NOT NULL,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_patterns_created_at
            ON cell_patterns (created_at DESC)
        """)
        logger.info("cell_patterns table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_patterns table: {e}")


async def save_pattern(
    health_status: str,
    response_time_ms: int,
    budget_pct: float,
    action: str,
    reason: str,
    confidence: float,
    tier_used: int,
) -> None:
    """Persist a resolved pattern to the DB (fire-and-forget)."""
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_patterns
               (health_status, response_time_ms, budget_pct, action, reason, confidence, tier_used)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            health_status, response_time_ms, budget_pct, action, reason, confidence, tier_used,
        )
    except Exception as e:
        logger.error(f"Failed to save pattern to DB: {e}")


async def load_patterns(limit: int = 500) -> list[dict[str, Any]]:
    """Load most recent patterns from DB. Returns list of dicts."""
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            """SELECT health_status, response_time_ms, budget_pct,
                      action, reason, confidence, tier_used, created_at
               FROM cell_patterns
               ORDER BY created_at DESC
               LIMIT $1""",
            limit,
        )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to load patterns from DB: {e}")
        return []


async def log_alert(
    level: str,
    action: str,
    message: str,
    health_status: str = "",
    pulse_number: int = 0,
) -> None:
    """Write a silent alert to cell_alerts table (for dashboard + alert_silent action)."""
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_alerts (level, action, message, health_status, pulse_number)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT DO NOTHING""",
            level, action, message, health_status, pulse_number,
        )
    except Exception as e:
        logger.error(f"Failed to log alert to DB: {e}")
