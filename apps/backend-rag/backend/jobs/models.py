"""JobRun dataclass + JobRunRepository (asyncpg)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import asyncpg

JobStatus = Literal[
    "pending", "running", "completed", "failed", "skipped", "cost_exceeded"
]


@dataclass
class JobRun:
    id: int
    job_name: str
    scheduled_tick: datetime
    idempotency_key: str
    status: JobStatus
    attempt: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    cost_cents: int
    meta: dict[str, Any]
    created_at: datetime


def _row_to_job_run(row: asyncpg.Record) -> JobRun:
    meta = row["meta"]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return JobRun(
        id=row["id"],
        job_name=row["job_name"],
        scheduled_tick=row["scheduled_tick"],
        idempotency_key=row["idempotency_key"],
        status=row["status"],
        attempt=row["attempt"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
        cost_cents=row["cost_cents"],
        meta=meta or {},
        created_at=row["created_at"],
    )


class JobRunRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_pending(
        self,
        job_name: str,
        scheduled_tick: datetime,
        idempotency_key: str,
        attempt: int,
    ) -> JobRun:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO job_runs (
                    job_name, scheduled_tick, idempotency_key, status, attempt
                ) VALUES ($1, $2, $3, 'pending', $4)
                RETURNING *
                """,
                job_name, scheduled_tick, idempotency_key, attempt,
            )
        return _row_to_job_run(row)

    async def mark_running(self, run_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE job_runs SET status='running', started_at=now() WHERE id=$1",
                run_id,
            )

    async def finish(
        self,
        run_id: int,
        status: JobStatus,
        error: str | None,
        cost_cents: int,
        meta: dict[str, Any],
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE job_runs
                SET status=$2, finished_at=now(),
                    error=$3, cost_cents=$4, meta=$5::jsonb
                WHERE id=$1
                """,
                run_id, status, error, cost_cents, json.dumps(meta),
            )

    async def get(self, run_id: int) -> JobRun:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM job_runs WHERE id=$1", run_id)
        if row is None:
            raise KeyError(f"job_run id={run_id} not found")
        return _row_to_job_run(row)

    async def find_completed_by_idempotency_key(
        self, key: str
    ) -> JobRun | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM job_runs
                WHERE idempotency_key=$1 AND status='completed'
                ORDER BY finished_at DESC LIMIT 1
                """,
                key,
            )
        return _row_to_job_run(row) if row else None

    async def list_recent(self, job_name: str, limit: int = 50) -> list[JobRun]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM job_runs
                WHERE job_name=$1
                ORDER BY scheduled_tick DESC, attempt DESC
                LIMIT $2
                """,
                job_name, limit,
            )
        return [_row_to_job_run(r) for r in rows]

    async def mark_orphans(self, older_than: datetime) -> int:
        """Mark still-running rows older than `older_than` as failed."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE job_runs
                SET status='failed', finished_at=now(),
                    error='orphaned'
                WHERE status='running' AND started_at < $1
                """,
                older_than,
            )
        # asyncpg execute returns "UPDATE <count>"
        return int(result.split()[-1])
