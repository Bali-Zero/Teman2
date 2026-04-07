"""
Core Guardian V4 — Decision Logger

Central logging utility for all CG components. Every action (check, fix,
rollback, alert) is recorded to PostgreSQL for audit trail and trend analysis.

Falls back to local JSONL if DB is unreachable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("guardian.decision_logger")

# --- Paths ---
_AGENT_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".agent" / "decisions"
_FALLBACK_FILE = _AGENT_DIR / "guardian_decisions_fallback.jsonl"

# --- Pool (lazy init) ---
_pool = None


async def _get_pool():
    """Lazy-init asyncpg pool from DATABASE_URL."""
    global _pool
    if _pool is not None:
        return _pool

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set — decision logging will use local fallback")
        return None

    try:
        import asyncpg
        _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3, timeout=10)
        return _pool
    except Exception as e:
        logger.error(f"Failed to create DB pool: {e}")
        return None


def _fallback_log(record: dict) -> None:
    """Append to local JSONL when DB is unreachable."""
    _FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_FALLBACK_FILE, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        logger.error(f"Fallback log write failed: {e}")


# ============================================================================
# Core async functions
# ============================================================================


async def log_decision(
    run_id: str,
    component: str,
    check_type: str,
    finding: str,
    severity: str,
    action_taken: str,
    rationale: str | None = None,
    rollback_plan: str | None = None,
    risk_score: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log a guardian decision to PostgreSQL."""
    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "check_type": check_type,
        "finding": finding,
        "severity": severity,
        "action_taken": action_taken,
        "rationale": rationale,
        "rollback_plan": rollback_plan,
        "risk_score": risk_score,
        "metadata": metadata or {},
    }

    try:
        pool = await _get_pool()
    except Exception as e:
        logger.warning(f"Pool init failed, using fallback: {e}")
        _fallback_log(record)
        return

    if pool is None:
        _fallback_log(record)
        return

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO guardian_decisions
                    (run_id, component, check_type, finding, severity,
                     action_taken, rationale, rollback_plan, risk_score, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                run_id, component, check_type, finding, severity,
                action_taken, rationale, rollback_plan, risk_score,
                json.dumps(metadata or {}),
            )
    except Exception as e:
        logger.warning(f"DB insert failed, using fallback: {e}")
        _fallback_log(record)


async def log_risk_score(
    overall: int,
    rbac: int,
    api_contract: int,
    cache: int,
    dead_code: int,
    red_team_survival: float | None = None,
    seo_health: float | None = None,
    ragas_quality: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log a unified risk score snapshot to PostgreSQL."""
    pool = await _get_pool()
    if pool is None:
        _fallback_log({
            "type": "risk_score",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall": overall, "rbac": rbac, "api_contract": api_contract,
            "cache": cache, "dead_code": dead_code,
        })
        return

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO guardian_risk_scores
                    (overall_score, rbac_score, api_contract_score, cache_score,
                     dead_code_score, red_team_survival, seo_health, ragas_quality, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                overall, rbac, api_contract, cache, dead_code,
                red_team_survival, seo_health, ragas_quality,
                json.dumps(metadata or {}),
            )
    except Exception as e:
        logger.warning(f"DB risk score insert failed, using fallback: {e}")
        _fallback_log({
            "type": "risk_score",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall": overall, "rbac": rbac, "api_contract": api_contract,
            "cache": cache, "dead_code": dead_code,
        })


async def get_recent_decisions(
    hours: int = 24,
    component: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query recent decisions from PostgreSQL."""
    pool = await _get_pool()
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            query = """
                SELECT id, run_id, timestamp, component, check_type, finding,
                       severity, action_taken, rationale, rollback_plan,
                       risk_score, metadata
                FROM guardian_decisions
                WHERE timestamp > NOW() - ($1 || ' hours')::interval
            """
            params: list[Any] = [str(hours)]
            idx = 2

            if component:
                query += f" AND component = ${idx}"
                params.append(component)
                idx += 1
            if severity:
                query += f" AND severity = ${idx}"
                params.append(severity)
                idx += 1

            query += f" ORDER BY timestamp DESC LIMIT ${idx}"
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"Failed to query decisions: {e}")
        return []


async def get_risk_trend(days: int = 7) -> list[dict]:
    """Get daily risk score averages for trend display."""
    pool = await _get_pool()
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    DATE(timestamp) as date,
                    ROUND(AVG(overall_score)) as avg_overall,
                    ROUND(AVG(rbac_score)) as avg_rbac,
                    ROUND(AVG(api_contract_score)) as avg_api_contract,
                    ROUND(AVG(cache_score)) as avg_cache,
                    ROUND(AVG(dead_code_score)) as avg_dead_code,
                    COUNT(*) as samples
                FROM guardian_risk_scores
                WHERE timestamp > NOW() - ($1 || ' days')::interval
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                """,
                str(days),
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"Failed to query risk trend: {e}")
        return []


async def get_latest_risk_score() -> dict | None:
    """Get the most recent risk score snapshot."""
    pool = await _get_pool()
    if pool is None:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM guardian_risk_scores
                ORDER BY timestamp DESC LIMIT 1
                """
            )
            return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Failed to get latest risk score: {e}")
        return None


# ============================================================================
# Sync wrappers (for standalone evaluator scripts that aren't in an event loop)
# ============================================================================

# Persistent event loop for sync wrappers — keeps the asyncpg pool alive
# across multiple sync calls within the same process.
_sync_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    """Run async coroutine from synchronous context.

    Uses a persistent event loop so the asyncpg pool survives across calls.
    """
    global _sync_loop

    # Check if we're already inside an event loop (e.g., called from async code)
    try:
        asyncio.get_running_loop()
        # Already in an event loop — run in a thread with its own loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result(timeout=15)
    except RuntimeError:
        pass

    # No running loop — use our persistent one
    if _sync_loop is None or _sync_loop.is_closed():
        _sync_loop = asyncio.new_event_loop()

    return _sync_loop.run_until_complete(coro)


def log_decision_sync(
    run_id: str,
    component: str,
    check_type: str,
    finding: str,
    severity: str,
    action_taken: str,
    rationale: str | None = None,
    rollback_plan: str | None = None,
    risk_score: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Sync wrapper for log_decision."""
    _run_async(log_decision(
        run_id, component, check_type, finding, severity, action_taken,
        rationale, rollback_plan, risk_score, metadata,
    ))


def log_risk_score_sync(
    overall: int,
    rbac: int,
    api_contract: int,
    cache: int,
    dead_code: int,
    red_team_survival: float | None = None,
    seo_health: float | None = None,
    ragas_quality: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Sync wrapper for log_risk_score."""
    _run_async(log_risk_score(
        overall, rbac, api_contract, cache, dead_code,
        red_team_survival, seo_health, ragas_quality, metadata,
    ))
