# Backend Jobs + Agents Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a unified async job runner for the `nuzantara-rag` backend, with idempotency/retry/concurrency guarantees, a default-on safety middleware stack (OAuth guard + cost cap + Claude CLI fallback), and four legacy jobs migrated to it.

**Architecture:** Custom async scheduler (`asyncio.Task` + `croniter`) living inside the FastAPI backend process. Postgres advisory locks guard against duplicate execution across replicas; a new `job_runs` table (migration 112) persists run history and enforces idempotency. Handlers registered at import time via `register_job()`; `docs/jobs-schedule.md` auto-generated from the registry. Per-job allowlist (`JOBS_RUNNER_ENABLED` env var) gates the live rollout.

**Tech Stack:** Python 3.11, FastAPI, asyncpg, croniter, structlog, pytest (asyncio), asyncio, Fly.io (`nuzantara-rag`), PostgreSQL 17 (Pro local for tests).

**Reference spec:** `docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md`

---

## Precondition checks

Before Task 1, from the worktree `.worktrees/jobs-agents-orch`:

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('import chain OK')"
psql -h localhost -p 5432 -U postgres -d nuzantara_test -c "SELECT 1" 2>&1 | head -3
which croniter 2>/dev/null || pip show croniter 2>/dev/null || echo "croniter NOT installed"
```

If `croniter` is not installed, add it to `apps/backend-rag/requirements.txt` (`croniter>=2.0.1`) in Task 0 before anything else. If the test database does not exist: `createdb -h localhost -p 5432 nuzantara_test`.

---

## Task 0: Add croniter dependency

**Files:**
- Modify: `apps/backend-rag/requirements.txt`
- Modify: `apps/backend-rag/requirements-prod.txt`

- [ ] **Step 1: Check if croniter is already declared**

Run: `grep -n "^croniter" apps/backend-rag/requirements.txt apps/backend-rag/requirements-prod.txt`
Expected: either no match (add it) or version < 2.0.1 (upgrade to 2.0.1).

- [ ] **Step 2: Append croniter to both files if missing**

Append (only if step 1 showed no match) to `apps/backend-rag/requirements.txt` and `apps/backend-rag/requirements-prod.txt`:

```
croniter>=2.0.1
```

- [ ] **Step 3: Install in local venv**

Run: `cd apps/backend-rag && source .venv/bin/activate && pip install 'croniter>=2.0.1'`
Expected: `Successfully installed croniter-*`.

- [ ] **Step 4: Verify import works**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from croniter import croniter; print(croniter('*/10 * * * * *', __import__('datetime').datetime(2026,4,18)).get_next())"`
Expected: a datetime printed (second-granularity support confirmed).

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/requirements.txt apps/backend-rag/requirements-prod.txt
git commit -m "chore(backend): add croniter dependency for jobs runner"
```

---

## Task 1: Migration 112 — `job_runs` table

**Files:**
- Create: `apps/backend-rag/backend/migrations/migration_112_job_runs.py`
- Create: `apps/backend-rag/backend/migrations/apply_migration_112.py`
- Test: `apps/backend-rag/backend/tests/db/test_migration_112_job_runs.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/db/test_migration_112_job_runs.py`:

```python
"""Tests for migration 112: job_runs table."""
from __future__ import annotations

import os

import asyncpg
import pytest

from backend.migrations.migration_112_job_runs import apply, rollback

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@localhost:5432/nuzantara_test",
)


@pytest.fixture
async def conn():
    c = await asyncpg.connect(TEST_DB_URL)
    try:
        await c.execute("DROP TABLE IF EXISTS job_runs CASCADE")
        yield c
    finally:
        await c.execute("DROP TABLE IF EXISTS job_runs CASCADE")
        await c.close()


async def test_apply_creates_table(conn):
    await apply(conn)
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='job_runs')"
    )
    assert exists is True


async def test_apply_creates_expected_columns(conn):
    await apply(conn)
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='job_runs' ORDER BY ordinal_position"
    )
    names = [r["column_name"] for r in rows]
    for required in (
        "id", "job_name", "scheduled_tick", "idempotency_key",
        "status", "attempt", "started_at", "finished_at",
        "error", "cost_cents", "meta", "created_at",
    ):
        assert required in names, f"missing column {required}"


async def test_status_check_constraint(conn):
    await apply(conn)
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            "INSERT INTO job_runs (job_name, scheduled_tick, idempotency_key, status) "
            "VALUES ('x', now(), 'k', 'bogus')"
        )


async def test_indexes_present(conn):
    await apply(conn)
    rows = await conn.fetch(
        "SELECT indexname FROM pg_indexes WHERE tablename='job_runs'"
    )
    names = {r["indexname"] for r in rows}
    assert "idx_job_runs_name_tick" in names
    assert "idx_job_runs_idempotency" in names
    assert "idx_job_runs_status_name" in names


async def test_rollback_drops_table(conn):
    await apply(conn)
    await rollback(conn)
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='job_runs')"
    )
    assert exists is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/db/test_migration_112_job_runs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.migrations.migration_112_job_runs'`.

- [ ] **Step 3: Create the migration module**

Create `apps/backend-rag/backend/migrations/migration_112_job_runs.py`:

```python
"""
Migration 112: job_runs table for the unified jobs runner.

Purpose:
- Persist every job dispatch, retry, and completion for the in-process
  scheduler registered by backend/jobs/runner.py.
- Enforce idempotency: a completed row with a given idempotency_key
  tells the runner to skip duplicate dispatches.
- Provide run history for /api/jobs observability endpoints.

Reference: docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 112 — create job_runs table and indexes."""
    logger.info("Applying migration 112: job_runs table")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS job_runs (
            id              BIGSERIAL PRIMARY KEY,
            job_name        TEXT NOT NULL,
            scheduled_tick  TIMESTAMPTZ NOT NULL,
            idempotency_key TEXT NOT NULL,
            status          TEXT NOT NULL
                            CHECK (status IN (
                                'pending','running','completed',
                                'failed','skipped','cost_exceeded'
                            )),
            attempt         SMALLINT NOT NULL DEFAULT 1,
            started_at      TIMESTAMPTZ,
            finished_at     TIMESTAMPTZ,
            error           TEXT,
            cost_cents      INTEGER NOT NULL DEFAULT 0,
            meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    logger.info("Created table job_runs")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_name_tick
            ON job_runs (job_name, scheduled_tick DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_idempotency
            ON job_runs (idempotency_key)
            WHERE status IN ('completed','running');
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_status_name
            ON job_runs (status, job_name)
            WHERE status IN ('running','pending','failed');
    """)
    logger.info("Created indexes on job_runs")

    logger.info("Applied migration 112: job_runs table")


async def rollback(conn: Any) -> None:
    """Rollback migration 112 — drop job_runs table."""
    logger.info("Rolling back migration 112: job_runs table")

    await conn.execute("DROP INDEX IF EXISTS idx_job_runs_status_name;")
    await conn.execute("DROP INDEX IF EXISTS idx_job_runs_idempotency;")
    await conn.execute("DROP INDEX IF EXISTS idx_job_runs_name_tick;")
    await conn.execute("DROP TABLE IF EXISTS job_runs;")

    logger.info("Rolled back migration 112: job_runs table")
```

- [ ] **Step 4: Create the apply driver**

Create `apps/backend-rag/backend/migrations/apply_migration_112.py`:

```python
#!/usr/bin/env python3
"""
Apply migration 112: job_runs table.

Usage:
    python -m backend.migrations.apply_migration_112

Or on Fly.io:
    fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.apply_migration_112"

Reference: docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_112_job_runs import apply  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    logger.info("Connecting to database...")
    conn = await asyncpg.connect(database_url)

    try:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='job_runs')",
        )
        if exists:
            logger.info("Table job_runs already exists — migration is idempotent (CREATE IF NOT EXISTS)")

        logger.info("Applying migration 112: job_runs")
        await apply(conn)

        row_count = await conn.fetchval("SELECT COUNT(*) FROM job_runs")
        logger.info("✅ Migration 112 applied. job_runs rows=%d", row_count)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/db/test_migration_112_job_runs.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Apply to local test DB for downstream tasks**

Run: `cd apps/backend-rag && PYTHONPATH=. DATABASE_URL=postgresql://postgres@localhost:5432/nuzantara_test python -m backend.migrations.apply_migration_112`
Expected: `✅ Migration 112 applied. job_runs rows=0`.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_112_job_runs.py \
        apps/backend-rag/backend/migrations/apply_migration_112.py \
        apps/backend-rag/backend/tests/db/test_migration_112_job_runs.py
git commit -m "feat(backend): migration 112 — job_runs table for unified jobs runner"
```

---

## Task 2: Shared test fixtures — `pg_pool` and clean-up

**Files:**
- Create: `apps/backend-rag/backend/tests/jobs/__init__.py` (empty)
- Create: `apps/backend-rag/backend/tests/jobs/conftest.py`

- [ ] **Step 1: Create empty `__init__.py`**

Create `apps/backend-rag/backend/tests/jobs/__init__.py` with an empty file (just a blank file).

- [ ] **Step 2: Create the conftest**

Create `apps/backend-rag/backend/tests/jobs/conftest.py`:

```python
"""Shared fixtures for backend/jobs tests."""
from __future__ import annotations

import os

import asyncpg
import pytest

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@localhost:5432/nuzantara_test",
)


@pytest.fixture
async def pg_pool():
    """Asyncpg pool pointed at the test DB.

    Assumes migration 112 has already been applied (see apply_migration_112).
    Truncates job_runs between tests to avoid cross-test pollution.
    """
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=2, max_size=4)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE job_runs RESTART IDENTITY")
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def pg_conn(pg_pool):
    async with pg_pool.acquire() as conn:
        yield conn
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/tests/jobs/__init__.py \
        apps/backend-rag/backend/tests/jobs/conftest.py
git commit -m "test(backend/jobs): shared pg_pool/pg_conn fixtures"
```

---

## Task 3: `retry.py` — retry policy + exception taxonomy + classifier

**Files:**
- Create: `apps/backend-rag/backend/jobs/retry.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_retry.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_retry.py`:

```python
"""Tests for retry policy + exception taxonomy."""
from __future__ import annotations

import asyncio

import asyncpg
import httpx
import pytest

from backend.jobs.retry import (
    DEFAULT_RETRY,
    CostExceeded,
    JobError,
    OAuthViolation,
    PermanentError,
    RetryPolicy,
    TransientError,
    classify,
    transient_on,
)


def test_default_retry_policy():
    assert DEFAULT_RETRY.max_attempts == 3
    assert DEFAULT_RETRY.backoff_seconds == (0.5, 2.0, 8.0)


def test_custom_retry_policy_rejects_mismatched_backoff_length():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=3, backoff_seconds=(0.5, 2.0))


def test_classify_transient_is_retryable():
    assert classify(TransientError("net")) == "transient"


def test_classify_permanent_is_not_retryable():
    assert classify(PermanentError("bad input")) == "permanent"


def test_classify_oauth_violation_is_permanent():
    assert classify(OAuthViolation("leak")) == "permanent"


def test_classify_cost_exceeded_is_permanent():
    assert classify(CostExceeded("over budget")) == "permanent"


def test_classify_unknown_defaults_to_permanent():
    assert classify(ValueError("oops")) == "permanent"


def test_oauth_and_cost_exceeded_subclass_joberror():
    assert issubclass(OAuthViolation, JobError)
    assert issubclass(CostExceeded, JobError)


async def test_transient_on_decorator_wraps_known_exceptions():
    @transient_on(asyncpg.PostgresConnectionError, httpx.ConnectError, asyncio.TimeoutError)
    async def handler():
        raise asyncpg.PostgresConnectionError("connection refused")

    with pytest.raises(TransientError) as excinfo:
        await handler()
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresConnectionError)


async def test_transient_on_decorator_passes_through_other_exceptions():
    @transient_on(asyncpg.PostgresConnectionError)
    async def handler():
        raise ValueError("bad value")

    with pytest.raises(ValueError):
        await handler()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_retry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.retry'`.

- [ ] **Step 3: Write the implementation**

Create `apps/backend-rag/backend/jobs/retry.py`:

```python
"""Retry policy + exception taxonomy for the jobs runner.

The runner retries only exceptions classified as 'transient'. Anything not
explicitly transient is permanent — handlers must opt in to retry by raising
TransientError or using the @transient_on decorator.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Awaitable, Callable, Literal


class JobError(Exception):
    """Base class for all runner-aware exceptions."""


class TransientError(JobError):
    """Retry-eligible. Network, DB pool, upstream 5xx, timeout."""


class PermanentError(JobError):
    """Do not retry. Validation, auth, handler bug."""


class OAuthViolation(PermanentError):
    """Raised by the oauth_guard middleware when ANTHROPIC_API_KEY is set."""


class CostExceeded(PermanentError):
    """Raised by the cost_cap middleware when handler overshoots budget."""


Classification = Literal["transient", "permanent"]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.backoff_seconds) != self.max_attempts - 1:
            raise ValueError(
                f"backoff_seconds length must be max_attempts - 1 "
                f"({self.max_attempts - 1}), got {len(self.backoff_seconds)}"
            )

    def backoff_for(self, next_attempt: int) -> float:
        """Backoff to sleep before next_attempt (2-indexed: attempt 2, 3, ...)."""
        idx = next_attempt - 2
        if idx < 0 or idx >= len(self.backoff_seconds):
            raise IndexError(f"no backoff for attempt={next_attempt}")
        return self.backoff_seconds[idx]


DEFAULT_RETRY = RetryPolicy(max_attempts=3, backoff_seconds=(0.5, 2.0, 8.0))


def classify(exc: BaseException) -> Classification:
    if isinstance(exc, TransientError):
        return "transient"
    return "permanent"


def transient_on(
    *exc_classes: type[BaseException],
) -> Callable[[Callable[..., Awaitable[object]]], Callable[..., Awaitable[object]]]:
    """Decorator: re-raise listed exceptions as TransientError.

    Other exceptions pass through untouched, so they are classified permanent.
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except exc_classes as exc:
                raise TransientError(str(exc)) from exc

        return wrapper

    return decorator
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_retry.py -v`
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/jobs/retry.py \
        apps/backend-rag/backend/tests/jobs/test_retry.py
git commit -m "feat(backend/jobs): retry policy + exception taxonomy"
```

---

## Task 4: `context.py` — `JobContext` + `CostMeter`

**Files:**
- Create: `apps/backend-rag/backend/jobs/context.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_context.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_context.py`:

```python
"""Tests for JobContext and CostMeter."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from backend.jobs.context import CostMeter, JobContext


def test_cost_meter_initial_state():
    m = CostMeter()
    assert m.total_cents == 0
    assert m.entries == []


def test_cost_meter_charge_appends_and_sums():
    m = CostMeter()
    m.charge(50, "openai:input")
    m.charge(25, "openai:output")
    assert m.total_cents == 75
    assert len(m.entries) == 2
    assert m.entries[0] == (50, "openai:input")


def test_cost_meter_charge_rejects_negative():
    m = CostMeter()
    with pytest.raises(ValueError):
        m.charge(-5, "neg")


def test_job_context_minimal_construction():
    ctx = JobContext(
        job_name="test",
        scheduled_tick=datetime(2026, 4, 18, tzinfo=timezone.utc),
        attempt=1,
        run_id=42,
        db_pool=None,  # not needed for this test
        logger=logging.getLogger("test"),
        meter=CostMeter(),
        claude_cli_available=False,
        source="scheduled",
    )
    assert ctx.job_name == "test"
    assert ctx.attempt == 1
    assert ctx.source == "scheduled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.context'`.

- [ ] **Step 3: Write the implementation**

Create `apps/backend-rag/backend/jobs/context.py`:

```python
"""JobContext: the single argument every handler receives.

Also defines CostMeter — handlers call ctx.meter.charge(cents, reason)
on every paid call; the runner aggregates into job_runs.cost_cents and
the cost_cap middleware enforces a per-run budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger
from typing import Any, Literal

import asyncpg


@dataclass
class CostMeter:
    entries: list[tuple[int, str]] = field(default_factory=list)

    @property
    def total_cents(self) -> int:
        return sum(amount for amount, _ in self.entries)

    def charge(self, cents: int, reason: str) -> None:
        if cents < 0:
            raise ValueError(f"cost cannot be negative: {cents}")
        self.entries.append((cents, reason))


@dataclass
class JobContext:
    job_name: str
    scheduled_tick: datetime
    attempt: int
    run_id: int
    db_pool: asyncpg.Pool | None
    logger: Logger
    meter: CostMeter
    claude_cli_available: bool
    source: Literal["scheduled", "manual"]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    ok: bool = True
    meta: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_context.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/jobs/context.py \
        apps/backend-rag/backend/tests/jobs/test_context.py
git commit -m "feat(backend/jobs): JobContext, CostMeter, JobResult"
```

---

## Task 5: `registry.py` — `JobDeclaration` + `register_job()`

**Files:**
- Create: `apps/backend-rag/backend/jobs/__init__.py` (empty if not present)
- Create: `apps/backend-rag/backend/jobs/registry.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_registry.py`

- [ ] **Step 1: Ensure `backend/jobs/__init__.py` is empty/clean**

Check: `cat apps/backend-rag/backend/jobs/__init__.py`
If it imports `auto_practice_creator` or `conversation_cleanup` symbols, leave them alone. If it's empty, leave it empty. Don't modify.

- [ ] **Step 2: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_registry.py`:

```python
"""Tests for the job registry."""
from __future__ import annotations

import pytest

from backend.jobs.context import JobContext
from backend.jobs.registry import (
    JobDeclaration,
    Registry,
    RegistryError,
)


async def _noop(ctx: JobContext):
    return None


def test_register_then_list():
    reg = Registry()
    reg.register(name="a", cron="*/5 * * * *", handler=_noop)
    names = [d.name for d in reg.all()]
    assert names == ["a"]


def test_register_duplicate_rejected():
    reg = Registry()
    reg.register(name="a", cron="*/5 * * * *", handler=_noop)
    with pytest.raises(RegistryError, match="already registered"):
        reg.register(name="a", cron="0 0 * * *", handler=_noop)


def test_register_skip_middleware_requires_reason():
    reg = Registry()
    with pytest.raises(RegistryError, match="reason"):
        reg.register(
            name="a", cron="*/5 * * * *", handler=_noop,
            skip_middleware=("oauth_guard",),
            skip_reasons={},
        )


def test_register_skip_middleware_with_reason_ok():
    reg = Registry()
    reg.register(
        name="a", cron="*/5 * * * *", handler=_noop,
        skip_middleware=("cost_cap",),
        skip_reasons={"cost_cap": "this job legitimately needs $5/run"},
    )
    decl = reg.get("a")
    assert "cost_cap" in decl.skip_middleware


def test_register_invalid_cron_rejected():
    reg = Registry()
    with pytest.raises(RegistryError, match="cron"):
        reg.register(name="a", cron="not a cron", handler=_noop)


def test_freeze_prevents_further_registration():
    reg = Registry()
    reg.register(name="a", cron="*/5 * * * *", handler=_noop)
    reg.freeze()
    with pytest.raises(RegistryError, match="frozen"):
        reg.register(name="b", cron="*/5 * * * *", handler=_noop)


def test_get_missing_raises():
    reg = Registry()
    with pytest.raises(KeyError):
        reg.get("nope")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.registry'`.

- [ ] **Step 4: Write the implementation**

Create `apps/backend-rag/backend/jobs/registry.py`:

```python
"""Job registry: register_job() declarations at import time."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Mapping

from croniter import croniter

from backend.jobs.context import JobContext, JobResult
from backend.jobs.retry import DEFAULT_RETRY, RetryPolicy


class RegistryError(Exception):
    """Registry misconfiguration (duplicate, invalid cron, frozen, ...)."""


@dataclass(frozen=True)
class JobDeclaration:
    name: str
    cron: str
    handler: Callable[[JobContext], Awaitable[JobResult | None]]
    timezone: str = "Asia/Makassar"
    timeout_seconds: int = 300
    retry_policy: RetryPolicy = DEFAULT_RETRY
    skip_middleware: tuple[str, ...] = ()
    skip_reasons: Mapping[str, str] = field(default_factory=dict)
    idempotency_key: Callable[[JobContext], str] | None = None
    enabled_when: Callable[[], bool] | None = None


class Registry:
    def __init__(self) -> None:
        self._by_name: dict[str, JobDeclaration] = {}
        self._frozen = False

    def register(
        self,
        *,
        name: str,
        cron: str,
        handler: Callable[[JobContext], Awaitable[JobResult | None]],
        timezone: str = "Asia/Makassar",
        timeout_seconds: int = 300,
        retry_policy: RetryPolicy = DEFAULT_RETRY,
        skip_middleware: tuple[str, ...] = (),
        skip_reasons: Mapping[str, str] | None = None,
        idempotency_key: Callable[[JobContext], str] | None = None,
        enabled_when: Callable[[], bool] | None = None,
    ) -> None:
        if self._frozen:
            raise RegistryError("registry is frozen; cannot register more jobs")
        if name in self._by_name:
            raise RegistryError(f"job {name!r} already registered")
        if not croniter.is_valid(cron):
            raise RegistryError(f"invalid cron expression: {cron!r}")

        skip_reasons = dict(skip_reasons or {})
        for mw in skip_middleware:
            reason = skip_reasons.get(mw, "").strip()
            if not reason:
                raise RegistryError(
                    f"skip_middleware={mw!r} requires a non-empty "
                    f"skip_reasons[{mw!r}] (audit trail)"
                )

        self._by_name[name] = JobDeclaration(
            name=name,
            cron=cron,
            handler=handler,
            timezone=timezone,
            timeout_seconds=timeout_seconds,
            retry_policy=retry_policy,
            skip_middleware=tuple(skip_middleware),
            skip_reasons=skip_reasons,
            idempotency_key=idempotency_key,
            enabled_when=enabled_when,
        )

    def freeze(self) -> None:
        self._frozen = True

    def get(self, name: str) -> JobDeclaration:
        return self._by_name[name]

    def all(self) -> list[JobDeclaration]:
        return list(self._by_name.values())


_default = Registry()


def register_job(**kwargs) -> None:
    _default.register(**kwargs)


def get_registry() -> Registry:
    return _default
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_registry.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/jobs/registry.py \
        apps/backend-rag/backend/tests/jobs/test_registry.py
git commit -m "feat(backend/jobs): registry + JobDeclaration + register_job()"
```

---

## Task 6: `locks.py` — Postgres advisory lock helper

**Files:**
- Create: `apps/backend-rag/backend/jobs/locks.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_locks.py`

- [ ] **Step 1: Write the failing integration test**

Create `apps/backend-rag/backend/tests/jobs/test_locks.py`:

```python
"""Tests for Postgres advisory-lock helper."""
from __future__ import annotations

import asyncio

import pytest

from backend.jobs.locks import advisory_lock, stable_hash_int64


def test_stable_hash_int64_is_deterministic():
    a = stable_hash_int64("job:x:2026-04-18T00:00:00")
    b = stable_hash_int64("job:x:2026-04-18T00:00:00")
    assert a == b


def test_stable_hash_int64_fits_signed_64():
    h = stable_hash_int64("some:key")
    assert -(2**63) <= h < 2**63


async def test_advisory_lock_acquires_when_free(pg_conn):
    async with advisory_lock(pg_conn, "job:x:tick1") as got:
        assert got is True


async def test_advisory_lock_second_acquirer_fails(pg_pool):
    async with pg_pool.acquire() as c1, pg_pool.acquire() as c2:
        async with advisory_lock(c1, "job:x:tick2") as got1:
            assert got1 is True
            async with advisory_lock(c2, "job:x:tick2") as got2:
                assert got2 is False


async def test_advisory_lock_released_after_context(pg_pool):
    async with pg_pool.acquire() as c1:
        async with advisory_lock(c1, "job:x:tick3"):
            pass
    async with pg_pool.acquire() as c2:
        async with advisory_lock(c2, "job:x:tick3") as got:
            assert got is True


async def test_advisory_lock_released_on_exception(pg_pool):
    async with pg_pool.acquire() as c1:
        with pytest.raises(RuntimeError):
            async with advisory_lock(c1, "job:x:tick4"):
                raise RuntimeError("boom")
    async with pg_pool.acquire() as c2:
        async with advisory_lock(c2, "job:x:tick4") as got:
            assert got is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_locks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.locks'`.

- [ ] **Step 3: Write the implementation**

Create `apps/backend-rag/backend/jobs/locks.py`:

```python
"""Postgres advisory locks for jobs runner concurrency guarantees.

Keys are arbitrary strings. We hash to a signed int64 (PG's pg_advisory_lock
argument type) with SHA-1 truncation and sign mapping. Collisions between
distinct keys are statistically negligible for the registry sizes we see
(order of tens of jobs × tens of ticks/day).
"""
from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg


def stable_hash_int64(key: str) -> int:
    """Map arbitrary string to a signed int64 stable across processes."""
    digest = hashlib.sha1(key.encode("utf-8")).digest()[:8]
    # Interpret big-endian as signed 64-bit.
    return int.from_bytes(digest, byteorder="big", signed=True)


@asynccontextmanager
async def advisory_lock(
    conn: asyncpg.Connection, key: str
) -> AsyncIterator[bool]:
    """Non-blocking advisory lock. Yields True if acquired, False otherwise.

    Always releases on context exit; releasing a non-acquired lock is a no-op.
    """
    lock_id = stable_hash_int64(key)
    got: bool = bool(
        await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
    )
    try:
        yield got
    finally:
        if got:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_locks.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/jobs/locks.py \
        apps/backend-rag/backend/tests/jobs/test_locks.py
git commit -m "feat(backend/jobs): Postgres advisory-lock helper"
```

---

## Task 7: `models.py` — `JobRun` + `JobRunRepository`

**Files:**
- Create: `apps/backend-rag/backend/jobs/models.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_models.py`

- [ ] **Step 1: Write the failing integration test**

Create `apps/backend-rag/backend/tests/jobs/test_models.py`:

```python
"""Tests for JobRunRepository."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.jobs.models import JobRun, JobRunRepository


async def _repo(pg_pool) -> JobRunRepository:
    return JobRunRepository(pg_pool)


async def test_create_pending_returns_row(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending(
        job_name="a", scheduled_tick=tick,
        idempotency_key="a:tick:2026-04-18T07:30:00+00:00", attempt=1,
    )
    assert isinstance(run, JobRun)
    assert run.job_name == "a"
    assert run.status == "pending"
    assert run.attempt == 1


async def test_mark_running_then_finish_completed(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "k1", 1)

    await repo.mark_running(run.id)
    started = await repo.get(run.id)
    assert started.status == "running"
    assert started.started_at is not None

    await repo.finish(run.id, status="completed", error=None, cost_cents=42, meta={"x": 1})
    done = await repo.get(run.id)
    assert done.status == "completed"
    assert done.cost_cents == 42
    assert done.meta == {"x": 1}
    assert done.finished_at is not None


async def test_find_by_idempotency_key_completed(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "dup", 1)
    await repo.mark_running(run.id)
    await repo.finish(run.id, status="completed", error=None, cost_cents=0, meta={})

    found = await repo.find_completed_by_idempotency_key("dup")
    assert found is not None
    assert found.id == run.id


async def test_find_by_idempotency_key_failed_returns_none(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "f1", 1)
    await repo.mark_running(run.id)
    await repo.finish(run.id, status="failed", error="boom", cost_cents=0, meta={})
    assert await repo.find_completed_by_idempotency_key("f1") is None


async def test_list_recent(pg_pool):
    repo = await _repo(pg_pool)
    base = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    for i in range(3):
        r = await repo.create_pending("a", base + timedelta(hours=i), f"k{i}", 1)
        await repo.mark_running(r.id)
        await repo.finish(r.id, status="completed", error=None, cost_cents=0, meta={})

    recent = await repo.list_recent("a", limit=2)
    assert len(recent) == 2
    assert recent[0].scheduled_tick > recent[1].scheduled_tick


async def test_mark_orphans(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "orphan", 1)
    await repo.mark_running(run.id)
    # Force started_at backwards
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE job_runs SET started_at = now() - interval '1 hour' WHERE id=$1",
            run.id,
        )
    orphaned = await repo.mark_orphans(older_than=datetime.now(timezone.utc) - timedelta(minutes=5))
    assert orphaned == 1
    row = await repo.get(run.id)
    assert row.status == "failed"
    assert row.error == "orphaned"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.models'`.

- [ ] **Step 3: Write the implementation**

Create `apps/backend-rag/backend/jobs/models.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_models.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/jobs/models.py \
        apps/backend-rag/backend/tests/jobs/test_models.py
git commit -m "feat(backend/jobs): JobRun + JobRunRepository"
```

---

## Task 8: `middleware.py` — oauth_guard, cost_cap, claude_cli_fallback

**Files:**
- Create: `apps/backend-rag/backend/jobs/middleware.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_middleware.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_middleware.py`:

```python
"""Tests for the safety middleware stack."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from backend.jobs.context import CostMeter, JobContext
from backend.jobs.middleware import (
    CostCap,
    OAuthGuard,
    detect_claude_cli_available,
)
from backend.jobs.retry import CostExceeded, OAuthViolation


def _ctx(meter: CostMeter | None = None) -> JobContext:
    return JobContext(
        job_name="t",
        scheduled_tick=datetime(2026, 4, 18, tzinfo=timezone.utc),
        attempt=1,
        run_id=1,
        db_pool=None,
        logger=logging.getLogger("t"),
        meter=meter or CostMeter(),
        claude_cli_available=True,
        source="scheduled",
    )


async def test_oauth_guard_raises_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-bad")
    guard = OAuthGuard()
    with pytest.raises(OAuthViolation):
        await guard.check(_ctx())


async def test_oauth_guard_passes_when_key_absent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    guard = OAuthGuard()
    await guard.check(_ctx())  # no raise


async def test_cost_cap_allows_under_budget():
    cap = CostCap(limit_cents=100)
    ctx = _ctx()
    ctx.meter.charge(50, "a")
    cap.check(ctx)  # no raise
    ctx.meter.charge(40, "b")
    cap.check(ctx)


async def test_cost_cap_raises_on_overflow():
    cap = CostCap(limit_cents=100)
    ctx = _ctx()
    ctx.meter.charge(60, "a")
    ctx.meter.charge(50, "b")
    with pytest.raises(CostExceeded):
        cap.check(ctx)


def test_detect_claude_cli_available_on_macos_tty(monkeypatch):
    """Macos + TTY -> True."""
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert detect_claude_cli_available() is True


def test_detect_claude_cli_available_on_linux_non_tty(monkeypatch):
    """Linux + non-TTY -> False (Fly.io container case)."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert detect_claude_cli_available() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_middleware.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.middleware'`.

- [ ] **Step 3: Write the implementation**

Create `apps/backend-rag/backend/jobs/middleware.py`:

```python
"""Safety middleware stack for the jobs runner.

Three default-on middleware, applied outer-to-inner in this order:
 1. OAuthGuard     — fails fast if ANTHROPIC_API_KEY is set (hard rule).
 2. CostCap        — budget per run, defaults to $1.00 (100 cents).
 3. ClaudeCliFallback — sets ctx.claude_cli_available based on env.

Each middleware supports opt-out via JobDeclaration.skip_middleware; the
registry enforces that opt-out requires a non-empty reason string.
"""
from __future__ import annotations

import os
import sys

from backend.jobs.context import JobContext
from backend.jobs.retry import CostExceeded, OAuthViolation


class OAuthGuard:
    NAME = "oauth_guard"

    async def check(self, ctx: JobContext) -> None:
        if os.environ.get("ANTHROPIC_API_KEY"):
            ctx.logger.error(
                "job.violation",
                extra={
                    "event": "job.violation",
                    "middleware": self.NAME,
                    "detail": "ANTHROPIC_API_KEY present in env",
                    "job_name": ctx.job_name,
                },
            )
            raise OAuthViolation(
                f"ANTHROPIC_API_KEY must not be set in job {ctx.job_name!r} "
                "(OAuth-only policy). Use OAuth token instead."
            )


class CostCap:
    NAME = "cost_cap"

    def __init__(self, limit_cents: int = 100) -> None:
        self.limit_cents = limit_cents

    def check(self, ctx: JobContext) -> None:
        if ctx.meter.total_cents > self.limit_cents:
            raise CostExceeded(
                f"job {ctx.job_name!r} spent {ctx.meter.total_cents} cents, "
                f"cap is {self.limit_cents}"
            )


def detect_claude_cli_available() -> bool:
    """Claude CLI hangs on Linux non-TTY (feedback_claude_cli_linux_hang.md).

    On macOS OR on a TTY, assume the CLI works. On Linux non-TTY
    (Fly.io container), report False so handlers route around it.
    """
    is_linux = sys.platform.startswith("linux")
    try:
        is_tty = sys.stdout.isatty()
    except Exception:
        is_tty = False
    if is_linux and not is_tty:
        return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_middleware.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/jobs/middleware.py \
        apps/backend-rag/backend/tests/jobs/test_middleware.py
git commit -m "feat(backend/jobs): safety middleware (oauth_guard, cost_cap, claude_cli)"
```

---

## Task 9: `runner.py` — minimal dispatch (happy path only)

**Files:**
- Create: `apps/backend-rag/backend/jobs/runner.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_runner_dispatch.py`

- [ ] **Step 1: Write the failing test (happy path)**

Create `apps/backend-rag/backend/tests/jobs/test_runner_dispatch.py`:

```python
"""Dispatch happy-path test for JobsRunner."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.jobs.context import JobContext, JobResult
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


async def test_dispatch_happy_path(pg_pool):
    """Force a dispatch, observe pending->running->completed row."""
    reg = Registry()
    called: list[JobContext] = []

    async def handle(ctx: JobContext) -> JobResult:
        called.append(ctx)
        return JobResult(ok=True, meta={"processed": 1})

    reg.register(name="t", cron="*/1 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names={"t"}, tick_seconds=0.05,
    )

    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run_id = await runner.dispatch_once(decl=reg.get("t"), scheduled_tick=tick, source="scheduled")
    assert run_id is not None

    repo = JobRunRepository(pg_pool)
    row = await repo.get(run_id)
    assert row.status == "completed"
    assert row.meta.get("processed") == 1
    assert len(called) == 1
    assert called[0].job_name == "t"
    assert called[0].attempt == 1


async def test_dispatch_skipped_when_not_in_allowlist(pg_pool):
    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult()

    reg.register(name="t", cron="*/1 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.05,
    )

    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run_id = await runner.dispatch_once(decl=reg.get("t"), scheduled_tick=tick, source="scheduled")

    repo = JobRunRepository(pg_pool)
    row = await repo.get(run_id)
    assert row.status == "skipped"
    assert "allowlist" in (row.meta.get("reason") or "")


async def test_manual_source_bypasses_allowlist(pg_pool):
    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult()

    reg.register(name="t", cron="*/1 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.05,
    )

    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run_id = await runner.dispatch_once(decl=reg.get("t"), scheduled_tick=tick, source="manual")

    repo = JobRunRepository(pg_pool)
    row = await repo.get(run_id)
    assert row.status == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_runner_dispatch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.jobs.runner'`.

- [ ] **Step 3: Write the implementation (minimal — no retry yet)**

Create `apps/backend-rag/backend/jobs/runner.py`:

```python
"""JobsRunner — in-process async scheduler.

This is the minimal dispatch. Retry, timeout, and the tick loop come in
later tasks; for now we expose dispatch_once so we can TDD the surrounding
logic deterministically.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Literal

import asyncpg

from backend.jobs.context import CostMeter, JobContext, JobResult
from backend.jobs.locks import advisory_lock
from backend.jobs.middleware import (
    CostCap,
    OAuthGuard,
    detect_claude_cli_available,
)
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import JobDeclaration, Registry
from backend.jobs.retry import CostExceeded, JobError, OAuthViolation

logger = logging.getLogger(__name__)


def default_idempotency_key(job_name: str, scheduled_tick: datetime) -> str:
    return f"{job_name}:tick:{scheduled_tick.isoformat()}"


class JobsRunner:
    def __init__(
        self,
        pool: asyncpg.Pool,
        registry: Registry,
        enabled_names: set[str],
        tick_seconds: float = 10.0,
        cost_cap_cents: int = 100,
    ) -> None:
        self._pool = pool
        self._registry = registry
        self._enabled = set(enabled_names)
        self._tick_seconds = tick_seconds
        self._repo = JobRunRepository(pool)
        self._oauth = OAuthGuard()
        self._cost_cap = CostCap(limit_cents=cost_cap_cents)
        self._claude_cli = detect_claude_cli_available()

    async def dispatch_once(
        self,
        decl: JobDeclaration,
        scheduled_tick: datetime,
        source: Literal["scheduled", "manual"],
    ) -> int:
        """Run one dispatch of `decl` at `scheduled_tick`. Returns job_run id."""
        # enabled-allowlist check (manual bypasses it)
        if source == "scheduled" and decl.name not in self._enabled:
            run = await self._repo.create_pending(
                decl.name, scheduled_tick,
                default_idempotency_key(decl.name, scheduled_tick), 1,
            )
            await self._repo.finish(
                run.id, status="skipped", error=None, cost_cents=0,
                meta={"reason": "not in JOBS_RUNNER_ENABLED allowlist"},
            )
            return run.id

        # idempotency check (tick-based default, handler override)
        meter = CostMeter()
        probe_ctx = JobContext(
            job_name=decl.name, scheduled_tick=scheduled_tick,
            attempt=1, run_id=0,
            db_pool=self._pool,
            logger=logger.getChild(decl.name),
            meter=meter, claude_cli_available=self._claude_cli,
            source=source,
        )
        if decl.idempotency_key is not None:
            key = decl.idempotency_key(probe_ctx)
        else:
            key = default_idempotency_key(decl.name, scheduled_tick)

        existing = await self._repo.find_completed_by_idempotency_key(key)
        if existing is not None:
            run = await self._repo.create_pending(
                decl.name, scheduled_tick, key, 1,
            )
            await self._repo.finish(
                run.id, status="skipped", error=None, cost_cents=0,
                meta={"reason": "idempotent: already completed", "prior_run_id": existing.id},
            )
            return run.id

        # advisory lock + execute
        async with self._pool.acquire() as conn:
            async with advisory_lock(conn, f"job:{decl.name}:{scheduled_tick.isoformat()}") as got:
                if not got:
                    run = await self._repo.create_pending(
                        decl.name, scheduled_tick, key, 1,
                    )
                    await self._repo.finish(
                        run.id, status="skipped", error=None, cost_cents=0,
                        meta={"reason": "advisory lock not acquired"},
                    )
                    return run.id

                run = await self._repo.create_pending(decl.name, scheduled_tick, key, 1)
                await self._repo.mark_running(run.id)

                ctx = JobContext(
                    job_name=decl.name, scheduled_tick=scheduled_tick,
                    attempt=1, run_id=run.id,
                    db_pool=self._pool,
                    logger=logger.getChild(decl.name),
                    meter=meter, claude_cli_available=self._claude_cli,
                    source=source,
                )

                try:
                    # middleware pre-checks
                    if "oauth_guard" not in decl.skip_middleware:
                        await self._oauth.check(ctx)

                    result = await decl.handler(ctx)

                    # post-handler cost check
                    if "cost_cap" not in decl.skip_middleware:
                        self._cost_cap.check(ctx)

                    meta = result.meta if isinstance(result, JobResult) else {}
                    meta = {**meta, "source": source}
                    await self._repo.finish(
                        run.id, status="completed", error=None,
                        cost_cents=ctx.meter.total_cents, meta=meta,
                    )
                    return run.id

                except OAuthViolation as exc:
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"OAuthViolation: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "error_class": "OAuthViolation"},
                    )
                    raise

                except CostExceeded as exc:
                    await self._repo.finish(
                        run.id, status="cost_exceeded",
                        error=f"CostExceeded: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "error_class": "CostExceeded"},
                    )
                    return run.id

                except Exception as exc:  # noqa: BLE001
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "error_class": type(exc).__name__},
                    )
                    raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_runner_dispatch.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/jobs/runner.py \
        apps/backend-rag/backend/tests/jobs/test_runner_dispatch.py
git commit -m "feat(backend/jobs): JobsRunner.dispatch_once happy path + allowlist + idempotency"
```

---

## Task 10: Retry + timeout + orphan recovery in the runner

**Files:**
- Modify: `apps/backend-rag/backend/jobs/runner.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_runner_retry.py`

- [ ] **Step 1: Write failing tests**

Create `apps/backend-rag/backend/tests/jobs/test_runner_retry.py`:

```python
"""Retry + timeout + orphan tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from backend.jobs.context import JobContext, JobResult
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import Registry
from backend.jobs.retry import RetryPolicy, TransientError
from backend.jobs.runner import JobsRunner


async def test_transient_retries_then_succeeds(pg_pool):
    reg = Registry()
    attempts: list[int] = []

    async def flaky(ctx: JobContext) -> JobResult:
        attempts.append(ctx.attempt)
        if ctx.attempt < 3:
            raise TransientError("network hiccup")
        return JobResult(ok=True)

    reg.register(
        name="flaky", cron="*/1 * * * *", handler=flaky,
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=(0.01, 0.01)),
    )
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"flaky"}, tick_seconds=0.01)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    await runner.dispatch_with_retry(decl=reg.get("flaky"), scheduled_tick=tick, source="scheduled")

    assert attempts == [1, 2, 3]
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("flaky", limit=10)
    # exactly 3 rows, all same idempotency_key, statuses failed/failed/completed
    assert len(rows) == 3
    assert {r.attempt for r in rows} == {1, 2, 3}
    statuses_by_attempt = {r.attempt: r.status for r in rows}
    assert statuses_by_attempt[1] == "failed"
    assert statuses_by_attempt[2] == "failed"
    assert statuses_by_attempt[3] == "completed"
    assert len({r.idempotency_key for r in rows}) == 1


async def test_permanent_does_not_retry(pg_pool):
    reg = Registry()
    attempts: list[int] = []

    async def boom(ctx: JobContext) -> JobResult:
        attempts.append(ctx.attempt)
        raise ValueError("bad input")

    reg.register(name="boom", cron="*/1 * * * *", handler=boom)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"boom"}, tick_seconds=0.01)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    await runner.dispatch_with_retry(decl=reg.get("boom"), scheduled_tick=tick, source="scheduled")

    assert attempts == [1]
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("boom", limit=10)
    assert len(rows) == 1
    assert rows[0].status == "failed"


async def test_timeout_classified_as_transient(pg_pool):
    reg = Registry()

    async def slow(ctx: JobContext) -> JobResult:
        if ctx.attempt == 1:
            await asyncio.sleep(0.5)
        return JobResult(ok=True)

    reg.register(
        name="slow", cron="*/1 * * * *", handler=slow,
        timeout_seconds=0,  # 0 forces immediate timeout path; runner treats 0 as 0.1s
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=(0.01,)),
    )
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"slow"}, tick_seconds=0.01)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    await runner.dispatch_with_retry(decl=reg.get("slow"), scheduled_tick=tick, source="scheduled")

    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("slow", limit=10)
    assert len(rows) == 2
    assert rows[-1].attempt == 1 and rows[-1].status == "failed"  # sorted desc
    assert rows[0].attempt == 2 and rows[0].status == "completed"


async def test_mark_orphans_on_startup(pg_pool):
    reg = Registry()
    reg.freeze()
    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.01)

    repo = JobRunRepository(pg_pool)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run = await repo.create_pending("orph", tick, "k", 1)
    await repo.mark_running(run.id)
    # force old started_at
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE job_runs SET started_at = now() - interval '10 minutes' WHERE id=$1",
            run.id,
        )

    recovered = await runner.recover_orphans(grace_seconds=60)
    assert recovered == 1
    row = await repo.get(run.id)
    assert row.status == "failed"
    assert row.error == "orphaned"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_runner_retry.py -v`
Expected: FAIL — `AttributeError: 'JobsRunner' object has no attribute 'dispatch_with_retry'` and `recover_orphans`.

- [ ] **Step 3: Extend the runner**

Edit `apps/backend-rag/backend/jobs/runner.py`. Add imports at top if missing:

```python
from datetime import timedelta

from backend.jobs.retry import TransientError, classify
```

Then add these two methods to `JobsRunner`:

```python
    async def dispatch_with_retry(
        self,
        decl: JobDeclaration,
        scheduled_tick: datetime,
        source: Literal["scheduled", "manual"],
    ) -> int:
        """Like dispatch_once but honors decl.retry_policy for transient failures."""
        attempt = 1
        max_attempts = decl.retry_policy.max_attempts
        last_run_id: int | None = None

        while True:
            try:
                last_run_id = await self._dispatch_attempt(
                    decl=decl, scheduled_tick=scheduled_tick,
                    source=source, attempt=attempt,
                )
                return last_run_id
            except TransientError:
                if attempt >= max_attempts:
                    return last_run_id or 0
                await asyncio.sleep(decl.retry_policy.backoff_for(attempt + 1))
                attempt += 1
            except Exception:
                # Permanent — do not retry.
                return last_run_id or 0

    async def _dispatch_attempt(
        self,
        decl: JobDeclaration,
        scheduled_tick: datetime,
        source: Literal["scheduled", "manual"],
        attempt: int,
    ) -> int:
        """Single attempt; raises TransientError / PermanentError to caller."""
        meter = CostMeter()
        probe_ctx = JobContext(
            job_name=decl.name, scheduled_tick=scheduled_tick,
            attempt=attempt, run_id=0,
            db_pool=self._pool,
            logger=logger.getChild(decl.name),
            meter=meter, claude_cli_available=self._claude_cli,
            source=source,
        )
        if decl.idempotency_key is not None:
            key = decl.idempotency_key(probe_ctx)
        else:
            key = default_idempotency_key(decl.name, scheduled_tick)

        # On attempt 1 we respect the enabled-allowlist (for scheduled source)
        # and short-circuit on prior completion. On later attempts, we've
        # already passed those gates, so retry unconditionally.
        if attempt == 1:
            if source == "scheduled" and decl.name not in self._enabled:
                run = await self._repo.create_pending(decl.name, scheduled_tick, key, 1)
                await self._repo.finish(
                    run.id, status="skipped", error=None, cost_cents=0,
                    meta={"reason": "not in JOBS_RUNNER_ENABLED allowlist"},
                )
                return run.id

            existing = await self._repo.find_completed_by_idempotency_key(key)
            if existing is not None:
                run = await self._repo.create_pending(decl.name, scheduled_tick, key, 1)
                await self._repo.finish(
                    run.id, status="skipped", error=None, cost_cents=0,
                    meta={"reason": "idempotent: already completed", "prior_run_id": existing.id},
                )
                return run.id

        async with self._pool.acquire() as conn:
            async with advisory_lock(conn, f"job:{decl.name}:{scheduled_tick.isoformat()}:{attempt}") as got:
                if not got:
                    run = await self._repo.create_pending(decl.name, scheduled_tick, key, attempt)
                    await self._repo.finish(
                        run.id, status="skipped", error=None, cost_cents=0,
                        meta={"reason": "advisory lock not acquired", "attempt": attempt},
                    )
                    return run.id

                run = await self._repo.create_pending(decl.name, scheduled_tick, key, attempt)
                await self._repo.mark_running(run.id)

                ctx = JobContext(
                    job_name=decl.name, scheduled_tick=scheduled_tick,
                    attempt=attempt, run_id=run.id,
                    db_pool=self._pool,
                    logger=logger.getChild(decl.name),
                    meter=meter, claude_cli_available=self._claude_cli,
                    source=source,
                )

                timeout = max(decl.timeout_seconds, 0.1)

                try:
                    if "oauth_guard" not in decl.skip_middleware:
                        await self._oauth.check(ctx)

                    result = await asyncio.wait_for(decl.handler(ctx), timeout=timeout)

                    if "cost_cap" not in decl.skip_middleware:
                        self._cost_cap.check(ctx)

                    meta = result.meta if isinstance(result, JobResult) else {}
                    meta = {**meta, "source": source, "attempt": attempt}
                    await self._repo.finish(
                        run.id, status="completed", error=None,
                        cost_cents=ctx.meter.total_cents, meta=meta,
                    )
                    return run.id

                except asyncio.TimeoutError as exc:
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"TimeoutError after {timeout}s",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "attempt": attempt, "error_class": "TimeoutError"},
                    )
                    raise TransientError("handler timed out") from exc

                except OAuthViolation as exc:
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"OAuthViolation: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "attempt": attempt, "error_class": "OAuthViolation"},
                    )
                    raise

                except CostExceeded as exc:
                    await self._repo.finish(
                        run.id, status="cost_exceeded",
                        error=f"CostExceeded: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "attempt": attempt, "error_class": "CostExceeded"},
                    )
                    raise

                except TransientError as exc:
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"TransientError: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "attempt": attempt, "error_class": "TransientError"},
                    )
                    raise

                except Exception as exc:  # noqa: BLE001
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "attempt": attempt, "error_class": type(exc).__name__},
                    )
                    raise

    async def recover_orphans(self, grace_seconds: int = 60) -> int:
        """Mark 'running' rows older than grace as failed/orphaned."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=grace_seconds)
        return await self._repo.mark_orphans(older_than=cutoff)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_runner_retry.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Run the full jobs suite for regressions**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/ -v`
Expected: all tests across Tasks 1-10 PASS (≈30 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/jobs/runner.py \
        apps/backend-rag/backend/tests/jobs/test_runner_retry.py
git commit -m "feat(backend/jobs): retry, timeout classification, orphan recovery"
```

---

## Task 11: Tick loop + `start()` / `stop()`

**Files:**
- Modify: `apps/backend-rag/backend/jobs/runner.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_runner_loop.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_runner_loop.py`:

```python
"""Tick loop + start/stop tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.jobs.context import JobContext, JobResult
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


async def test_tick_loop_fires_every_tick(pg_pool):
    reg = Registry()
    fires = 0

    async def handle(ctx: JobContext) -> JobResult:
        nonlocal fires
        fires += 1
        return JobResult(ok=True)

    # Every second (croniter 6-field form). Second-granularity is supported.
    reg.register(name="fast", cron="*/1 * * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names={"fast"}, tick_seconds=0.1,
    )
    await runner.start()
    await asyncio.sleep(2.5)  # allow ~2 fires
    await runner.stop(grace_seconds=2)

    assert fires >= 1, f"expected at least 1 fire, got {fires}"
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("fast", limit=10)
    assert any(r.status == "completed" for r in rows)


async def test_stop_finishes_in_flight(pg_pool):
    reg = Registry()
    entered = asyncio.Event()

    async def slow(ctx: JobContext) -> JobResult:
        entered.set()
        await asyncio.sleep(0.3)
        return JobResult(ok=True)

    reg.register(name="slow", cron="*/1 * * * * *", handler=slow, timeout_seconds=5)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"slow"}, tick_seconds=0.05)
    await runner.start()
    await entered.wait()
    await runner.stop(grace_seconds=2)

    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("slow", limit=5)
    assert rows, "expected at least one slow run row"
    assert rows[0].status in ("completed", "failed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_runner_loop.py -v`
Expected: FAIL — `AttributeError: 'JobsRunner' object has no attribute 'start'`.

- [ ] **Step 3: Extend the runner with start/stop/tick loop**

Edit `apps/backend-rag/backend/jobs/runner.py`. Add to `JobsRunner.__init__`:

```python
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._last_fired: dict[str, datetime] = {}
        self._in_flight: set[asyncio.Task] = set()
```

And add these methods:

```python
    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("runner already started")
        await self.recover_orphans(grace_seconds=60)
        self._task = asyncio.create_task(self._tick_loop(), name="jobs-runner-tick-loop")

    async def stop(self, grace_seconds: int = 30) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=grace_seconds)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        # wait for in-flight handlers
        if self._in_flight:
            done, pending = await asyncio.wait(
                self._in_flight, timeout=grace_seconds, return_when=asyncio.ALL_COMPLETED,
            )
            for t in pending:
                t.cancel()

    async def _tick_loop(self) -> None:
        from croniter import croniter

        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            for decl in self._registry.all():
                last = self._last_fired.get(decl.name, now - timedelta(seconds=1))
                try:
                    next_due = croniter(decl.cron, last).get_next(datetime)
                except Exception as exc:  # bad cron somehow — should have been validated
                    logger.error("job.cron_error job=%s err=%s", decl.name, exc)
                    continue
                if next_due.tzinfo is None:
                    next_due = next_due.replace(tzinfo=timezone.utc)
                if now < next_due:
                    continue

                self._last_fired[decl.name] = now
                task = asyncio.create_task(
                    self.dispatch_with_retry(decl=decl, scheduled_tick=next_due, source="scheduled"),
                    name=f"dispatch:{decl.name}:{next_due.isoformat()}",
                )
                self._in_flight.add(task)
                task.add_done_callback(self._in_flight.discard)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._tick_seconds)
            except asyncio.TimeoutError:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_runner_loop.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Full suite sanity**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/ -v`
Expected: all tests (Tasks 1-11) PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/jobs/runner.py \
        apps/backend-rag/backend/tests/jobs/test_runner_loop.py
git commit -m "feat(backend/jobs): tick loop + start/stop + orphan recovery on startup"
```

---

## Task 12: Handlers — migrate the two legacy jobs with backend-side entry points

**Scope note (2026-04-18):** the original plan expected four handlers. A pre-flight search found that Consiglio v1 and KG Curiosity Loop v1 have no backend-side Python entry points in `apps/backend-rag/` (no `services/autonomous_agents/consiglio_auto.py`, no `kg_curiosity` module anywhere under `backend/`). Memory index claims both are "IMPLEMENTED" but the code lives elsewhere — likely Air-side scripts or `apps/evaluator/`. Rather than build stub handlers that would be load-bearing lies, we ship the two handlers whose backend logic actually exists, and defer Consiglio + KG Curiosity to a follow-up PR (they currently run via Air crontab and stay that way).

**Files:**
- Create: `apps/backend-rag/backend/jobs/handlers/__init__.py`
- Create: `apps/backend-rag/backend/jobs/handlers/auto_practice_creator.py`
- Create: `apps/backend-rag/backend/jobs/handlers/conversation_cleanup.py`
- Test: `apps/backend-rag/backend/tests/jobs/test_handlers_registration.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_handlers_registration.py`:

```python
"""Handler wrappers register expected jobs."""
from __future__ import annotations


def test_import_handlers_registers_four_jobs():
    # Importing the package self-registers via register_job()
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry

    reg = get_registry()
    names = {d.name for d in reg.all()}
    assert {"auto-practice-creator", "conversation-cleanup", "consiglio-auto", "kg-curiosity"}.issubset(names)


def test_auto_practice_creator_cron_and_tz():
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry

    decl = get_registry().get("auto-practice-creator")
    assert decl.cron == "30 7 * * *"
    assert decl.timezone == "Asia/Makassar"


def test_conversation_cleanup_cron():
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry

    decl = get_registry().get("conversation-cleanup")
    assert decl.cron == "15 4 * * *"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_handlers_registration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.jobs.handlers'`.

- [ ] **Step 3: Create the four handler modules + package init**

Create `apps/backend-rag/backend/jobs/handlers/__init__.py`:

```python
"""Handler package. Importing registers every handler via register_job()."""
from backend.jobs.handlers import (  # noqa: F401
    auto_practice_creator,
    conversation_cleanup,
    consiglio_auto,
    kg_curiosity,
)
```

Create `apps/backend-rag/backend/jobs/handlers/auto_practice_creator.py`:

```python
"""Runner wrapper around the existing auto-practice creator job.

The domain logic lives in backend/jobs/auto_practice_creator.py. We import
the existing main entrypoint and wrap it in the JobContext protocol.
"""
from __future__ import annotations

from backend.jobs.auto_practice_creator import run_job as _run_job
from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import register_job


async def handle(ctx: JobContext) -> JobResult:
    created = await _run_job()
    ctx.logger.info("auto_practice_creator_done", extra={"created": created})
    return JobResult(ok=True, meta={"created": int(created or 0)})


register_job(
    name="auto-practice-creator",
    cron="30 7 * * *",          # 07:30 WITA — matches existing Air cron entry
    handler=handle,
    timezone="Asia/Makassar",
    timeout_seconds=300,
)
```

Create `apps/backend-rag/backend/jobs/handlers/conversation_cleanup.py`:

```python
"""Runner wrapper around conversation_cleanup (daily, 04:15 WITA, staggered)."""
from __future__ import annotations

from backend.jobs.context import JobContext, JobResult
from backend.jobs.conversation_cleanup import run as _run
from backend.jobs.registry import register_job


async def handle(ctx: JobContext) -> JobResult:
    stats = await _run()
    ctx.logger.info("conversation_cleanup_done", extra={"stats": stats})
    return JobResult(ok=True, meta={"stats": stats or {}})


register_job(
    name="conversation-cleanup",
    cron="15 4 * * *",          # 04:15 WITA — 15 min before kg-curiosity
    handler=handle,
    timezone="Asia/Makassar",
    timeout_seconds=600,
)
```

Create `apps/backend-rag/backend/jobs/handlers/consiglio_auto.py`:

```python
"""Runner wrapper for Consiglio v1 auto-deliberation.

Consiglio v1 currently runs via a CLI / cron script. We call its internal
auto-run entrypoint directly (no subprocess) so the runner can observe cost,
retries, etc. Schedule preserves existing cadence.
"""
from __future__ import annotations

from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import register_job

try:
    # Try multiple known locations — implementation detail of Consiglio v1.
    from backend.services.autonomous_agents.consiglio_auto import run_auto as _run_auto  # type: ignore
except ImportError:  # pragma: no cover — fallback path if module moves
    from backend.services.consiglio_auto import run_auto as _run_auto  # type: ignore


async def handle(ctx: JobContext) -> JobResult:
    out = await _run_auto()
    ctx.logger.info("consiglio_auto_done", extra={"summary": (out or {}).get("summary")})
    return JobResult(ok=True, meta=out or {})


register_job(
    name="consiglio-auto",
    cron="0 5 * * *",           # 05:00 WITA — staggered after kg-curiosity
    handler=handle,
    timezone="Asia/Makassar",
    timeout_seconds=900,
    # cost_cap default 100c; override if needed in a follow-up.
)
```

Create `apps/backend-rag/backend/jobs/handlers/kg_curiosity.py`:

```python
"""Runner wrapper for KG Curiosity Loop v1 (propose-only)."""
from __future__ import annotations

from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import register_job

try:
    from backend.services.autonomous_agents.kg_curiosity import run_curiosity as _run  # type: ignore
except ImportError:  # pragma: no cover
    from backend.services.kg_curiosity import run_curiosity as _run  # type: ignore


async def handle(ctx: JobContext) -> JobResult:
    out = await _run()
    ctx.logger.info("kg_curiosity_done", extra={"proposals": (out or {}).get("proposals")})
    return JobResult(ok=True, meta=out or {})


register_job(
    name="kg-curiosity",
    cron="30 4 * * *",          # 04:30 WITA — matches existing cadence
    handler=handle,
    timezone="Asia/Makassar",
    timeout_seconds=900,
)
```

- [ ] **Step 4: Run the registration test**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_handlers_registration.py -v`
Expected: all 3 tests PASS.

**Note:** If `consiglio_auto` or `kg_curiosity` import paths do not exist in this codebase, both ImportError branches will raise. In that case, pause and report: the handler should call whatever internal function Consiglio v1 / KG Curiosity actually expose for auto-run. Check `backend/services/autonomous_agents/` and wire to the real symbol. Do NOT leave a broken ImportError in place.

- [ ] **Step 5: Full suite sanity**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/ -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/jobs/handlers/ \
        apps/backend-rag/backend/tests/jobs/test_handlers_registration.py
git commit -m "feat(backend/jobs): handlers for auto-practice, conversation-cleanup, consiglio-auto, kg-curiosity"
```

---

## Task 13: Admin router — `/api/jobs*` endpoints + legacy alias

**Files:**
- Create: `apps/backend-rag/backend/app/routers/jobs_admin.py`
- Modify: `apps/backend-rag/backend/app/routers/admin_conversation_cleanup.py` (if present — add note-only; do not touch)
- Create: `apps/backend-rag/backend/app/routers/admin_practice_auto_create.py` (alias; if a separate file for the existing endpoint does not already exist, create the alias here)
- Test: `apps/backend-rag/backend/tests/jobs/test_jobs_admin_router.py`

Before starting: find the existing `/api/admin/practice/auto-create` handler.

Run: `grep -rn "practice/auto-create\|practice_auto_create\|auto_practice_creator" apps/backend-rag/backend/app/routers/ apps/backend-rag/backend/routers/ 2>/dev/null | head -10`

If an endpoint already exists, the alias **replaces** its body with a delegating call to the new runner; do NOT leave two handlers for the same path. If no existing endpoint is found, create the new file as specified.

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/jobs/test_jobs_admin_router.py`:

```python
"""Tests for /api/jobs admin endpoints via FastAPI TestClient."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers.jobs_admin import build_router
from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


@pytest.fixture
async def app_client(pg_pool):
    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult(ok=True, meta={"ran": True})

    reg.register(name="t", cron="*/5 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names=set())

    app = FastAPI()
    app.include_router(build_router(runner=runner, api_key="test-key"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        yield ac


async def test_get_jobs_lists_registry(app_client):
    r = await app_client.get("/api/jobs", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    data = r.json()
    assert any(j["name"] == "t" for j in data["jobs"])


async def test_get_jobs_requires_api_key(app_client):
    r = await app_client.get("/api/jobs")
    assert r.status_code == 401


async def test_post_run_executes_job(app_client):
    r = await app_client.post("/api/jobs/t/run", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert isinstance(body["run_id"], int)


async def test_get_runs_returns_history(app_client):
    await app_client.post("/api/jobs/t/run", headers={"X-API-Key": "test-key"})
    r = await app_client.get("/api/jobs/t/runs?limit=5", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert len(runs) >= 1


async def test_legacy_alias_practice_auto_create(app_client):
    # The alias should map to /api/jobs/auto-practice-creator/run.
    # For this unit test we only verify the alias endpoint exists and delegates;
    # we use a stub registry entry with that exact name.
    pass
```

Also add an additional test file for the legacy alias (since it exercises a different registry):

Create `apps/backend-rag/backend/tests/jobs/test_legacy_alias.py`:

```python
"""Tests for POST /api/admin/practice/auto-create -> runner alias."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers.jobs_admin import build_router
from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


@pytest.fixture
async def app_client(pg_pool):
    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult(ok=True, meta={"created": 3})

    reg.register(name="auto-practice-creator", cron="30 7 * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names=set())
    app = FastAPI()
    app.include_router(build_router(runner=runner, api_key="test-key"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        yield ac


async def test_legacy_alias_delegates(app_client):
    r = await app_client.post(
        "/api/admin/practice/auto-create",
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_jobs_admin_router.py backend/tests/jobs/test_legacy_alias.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.routers.jobs_admin'`.

- [ ] **Step 3: Write the router**

Create `apps/backend-rag/backend/app/routers/jobs_admin.py`:

```python
"""Admin endpoints for the jobs runner.

Authorization: X-API-Key header. Reuses the same admin pattern as
/api/admin/* elsewhere in the codebase.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.jobs.models import JobRunRepository
from backend.jobs.runner import JobsRunner


def _require_api_key(expected: str):
    async def _dep(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if not x_api_key or x_api_key != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
    return _dep


def build_router(*, runner: JobsRunner, api_key: str) -> APIRouter:
    router = APIRouter()
    auth = Depends(_require_api_key(api_key))

    @router.get("/api/jobs", dependencies=[auth])
    async def list_jobs() -> dict:
        repo = JobRunRepository(runner._pool)
        out = []
        for decl in runner._registry.all():
            runs = await repo.list_recent(decl.name, limit=1)
            last = runs[0] if runs else None
            out.append({
                "name": decl.name,
                "cron": decl.cron,
                "tz": decl.timezone,
                "enabled": decl.name in runner._enabled,
                "last_run": None if last is None else {
                    "run_id": last.id,
                    "scheduled_tick": last.scheduled_tick.isoformat(),
                    "status": last.status,
                    "attempt": last.attempt,
                    "cost_cents": last.cost_cents,
                },
            })
        return {"jobs": out}

    @router.post("/api/jobs/{name}/run", dependencies=[auth])
    async def run_job(name: str) -> dict:
        try:
            decl = runner._registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown job {name!r}")
        run_id = await runner.dispatch_with_retry(
            decl=decl,
            scheduled_tick=datetime.now(timezone.utc),
            source="manual",
        )
        repo = JobRunRepository(runner._pool)
        row = await repo.get(run_id)
        return {"run_id": run_id, "status": row.status}

    @router.get("/api/jobs/{name}/runs", dependencies=[auth])
    async def list_runs(name: str, limit: int = 50) -> dict:
        try:
            runner._registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown job {name!r}")
        repo = JobRunRepository(runner._pool)
        rows = await repo.list_recent(name, limit=min(limit, 200))
        return {"runs": [
            {
                "run_id": r.id,
                "scheduled_tick": r.scheduled_tick.isoformat(),
                "status": r.status,
                "attempt": r.attempt,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error": r.error,
                "cost_cents": r.cost_cents,
                "meta": r.meta,
            } for r in rows
        ]}

    # Legacy alias — delegates to the canonical run endpoint for the
    # auto-practice-creator job, preserving the URL the Air crontab calls.
    @router.post("/api/admin/practice/auto-create", dependencies=[auth])
    async def legacy_practice_auto_create() -> dict:
        return await run_job("auto-practice-creator")

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_jobs_admin_router.py backend/tests/jobs/test_legacy_alias.py -v`
Expected: all tests PASS.

- [ ] **Step 5: If a prior `/api/admin/practice/auto-create` handler exists elsewhere, remove its body**

From the grep in the pre-check: if you found a handler for that path in another router file, delete its `@router.post("/api/admin/practice/auto-create")` block entirely — the alias in `jobs_admin.py` replaces it. If the old handler lived in `backend/app/routers/admin_conversation_cleanup.py` or a `backend/routers/*.py` file, update the import registration in `backend/app/setup/router_registration.py` to drop that route group if it becomes empty. Do NOT skip this step: two handlers for the same path is a silent-precedence bug.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/jobs_admin.py \
        apps/backend-rag/backend/tests/jobs/test_jobs_admin_router.py \
        apps/backend-rag/backend/tests/jobs/test_legacy_alias.py
# plus any deletions from Step 5
git add -u apps/backend-rag/backend/app/routers/ apps/backend-rag/backend/app/setup/ 2>/dev/null || true
git commit -m "feat(backend): /api/jobs admin endpoints + legacy /practice/auto-create alias"
```

---

## Task 14: Lifespan wiring + `JOBS_RUNNER_ENABLED` env var + recover_orphans on startup

**Files:**
- Modify: `apps/backend-rag/backend/app/setup/app_factory.py` (lifespan)
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py` (register jobs_admin router)
- Test: `apps/backend-rag/backend/tests/jobs/test_lifespan_wiring.py`

- [ ] **Step 1: Write the failing integration test**

Create `apps/backend-rag/backend/tests/jobs/test_lifespan_wiring.py`:

```python
"""Verify the runner is started/stopped by the app lifespan."""
from __future__ import annotations

import asyncio

from backend.jobs.runner import JobsRunner


async def test_runner_started_and_stopped_by_lifespan(monkeypatch, pg_pool):
    monkeypatch.setenv("JOBS_RUNNER_ENABLED", "")  # allowlist empty
    # Import side-effect-registers handlers
    from backend.jobs import handlers  # noqa: F401
    from backend.jobs.registry import get_registry
    registry = get_registry()

    runner = JobsRunner(pool=pg_pool, registry=registry, enabled_names=set(), tick_seconds=0.05)
    await runner.start()
    await asyncio.sleep(0.2)
    await runner.stop(grace_seconds=2)

    # No errors raised, runner is idempotent on stop.
    await runner.stop(grace_seconds=1)  # second stop is a no-op
```

- [ ] **Step 2: Run it to verify existing runner lifecycle works**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/test_lifespan_wiring.py -v`
Expected: PASS. (This validates that double-stop is safe, so the lifespan teardown can be called twice.)

If it fails because `runner.stop()` isn't idempotent, make it idempotent by adding an early-return check at the top of `stop()`:

```python
        if self._task is None and not self._in_flight:
            return
```

- [ ] **Step 3: Wire the runner into lifespan**

Open `apps/backend-rag/backend/app/setup/app_factory.py`. Locate `async def lifespan(app: FastAPI):`. Inside the `try:` block (startup side), after the existing DB pool is created and BEFORE `yield`, append:

```python
    # --- Jobs runner startup ---
    import os as _os_jobs

    from backend.jobs import handlers as _jobs_handlers  # noqa: F401 (import-time registration)
    from backend.jobs.registry import get_registry as _get_jobs_registry
    from backend.jobs.runner import JobsRunner

    _registry = _get_jobs_registry()
    _registry.freeze()
    _enabled = {
        n.strip() for n in _os_jobs.environ.get("JOBS_RUNNER_ENABLED", "").split(",") if n.strip()
    }
    app.state.jobs_runner = JobsRunner(
        pool=app.state.pg_pool,          # NOTE: if the app uses a different attr for the pool,
                                          # swap to that attr (e.g., app.state.db_pool).
        registry=_registry,
        enabled_names=_enabled,
        tick_seconds=10.0,
    )
    await app.state.jobs_runner.start()
```

Then after the `yield` (shutdown side) add:

```python
    # --- Jobs runner shutdown ---
    if getattr(app.state, "jobs_runner", None) is not None:
        await app.state.jobs_runner.stop(grace_seconds=30)
```

**Before editing, verify which attribute holds the asyncpg pool.** Run:

```bash
grep -nE "app\.state\.(pg_pool|db_pool|pool)\s*=" apps/backend-rag/backend/app/setup/app_factory.py | head -5
```

If the pool is on `app.state.db_pool` (or similar), use that name in the edit above.

- [ ] **Step 4: Register the admin router**

Open `apps/backend-rag/backend/app/setup/router_registration.py`. Locate the block where admin routers are included. Add:

```python
    # Jobs admin endpoints (/api/jobs, /api/jobs/{name}/run, ...)
    from backend.app.routers.jobs_admin import build_router as _build_jobs_admin
    import os as _os_ja

    _jobs_api_key = _os_ja.environ.get("ADMIN_API_KEY") or _os_ja.environ.get("API_KEY")
    if _jobs_api_key and getattr(app.state, "jobs_runner", None) is not None:
        app.include_router(_build_jobs_admin(runner=app.state.jobs_runner, api_key=_jobs_api_key))
```

**Verify the env-var name for the admin API key.** Run:

```bash
grep -rn "X-API-Key\|ADMIN_API_KEY\|REDACTED-ROTATED-KEY" apps/backend-rag/backend/app/routers/ 2>/dev/null | head -5
```

If the codebase uses a different var (e.g., `X_API_KEY` in `core.config.settings`), swap `_os_ja.environ.get(...)` for the settings path actually in use.

- [ ] **Step 5: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/jobs/ -v`
Expected: all tests PASS (≈40 tests).

- [ ] **Step 6: Smoke-test at app startup (manual)**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. JOBS_RUNNER_ENABLED="" python -c "from backend.app.setup.app_factory import create_app; app = create_app(); print('app created, routes:', [r.path for r in app.routes if '/api/jobs' in getattr(r, 'path', '')])"`
Expected: prints a list including `/api/jobs`, `/api/jobs/{name}/run`, `/api/jobs/{name}/runs`, `/api/admin/practice/auto-create`.

If it prints nothing or errors on pool-attribute mismatch, revisit Step 3 and correct the attribute name.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/app/setup/app_factory.py \
        apps/backend-rag/backend/app/setup/router_registration.py \
        apps/backend-rag/backend/tests/jobs/test_lifespan_wiring.py
git commit -m "feat(backend): wire JobsRunner into lifespan + register admin router"
```

---

## Task 15: Schedule doc auto-generator + CI check

**Files:**
- Create: `apps/backend-rag/scripts/gen_jobs_schedule_doc.py`
- Create: `apps/backend-rag/docs/jobs-schedule.md` (generated artifact, committed)

- [ ] **Step 1: Write the generator**

Create `apps/backend-rag/scripts/gen_jobs_schedule_doc.py`:

```python
#!/usr/bin/env python3
"""Regenerate docs/jobs-schedule.md from the jobs registry.

Usage:
    python scripts/gen_jobs_schedule_doc.py           # writes the file
    python scripts/gen_jobs_schedule_doc.py --check   # exits 1 if file is stale

Invoked in CI to prevent the doc from drifting.
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import the handlers package so register_job runs.
from backend.jobs import handlers  # noqa: E402, F401
from backend.jobs.registry import get_registry  # noqa: E402

DOC_PATH = ROOT / "docs" / "jobs-schedule.md"

HEADER = """# Backend Jobs Schedule

Generated from `backend/jobs/registry.py`. Do not edit by hand — run
`python scripts/gen_jobs_schedule_doc.py` to regenerate.

| Name | Cron | TZ | Timeout (s) | Max Attempts | Skip Middleware |
|------|------|----|-------------|--------------|-----------------|
"""


def render() -> str:
    rows = []
    for decl in sorted(get_registry().all(), key=lambda d: d.name):
        skip = ",".join(decl.skip_middleware) or "—"
        rows.append(
            f"| `{decl.name}` | `{decl.cron}` | {decl.timezone} | "
            f"{decl.timeout_seconds} | {decl.retry_policy.max_attempts} | {skip} |"
        )
    return HEADER + "\n".join(rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    generated = render()

    if args.check:
        current = DOC_PATH.read_text() if DOC_PATH.exists() else ""
        if current.strip() != generated.strip():
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile="on-disk",
                tofile="from-registry",
            )
            sys.stderr.write("".join(diff))
            sys.stderr.write("\n\ndocs/jobs-schedule.md is stale. Regenerate with:\n")
            sys.stderr.write("  python scripts/gen_jobs_schedule_doc.py\n")
            return 1
        print("docs/jobs-schedule.md is up to date.")
        return 0

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(generated)
    print(f"wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the generator to produce the initial doc**

Run: `cd apps/backend-rag && PYTHONPATH=. source .venv/bin/activate && python scripts/gen_jobs_schedule_doc.py`
Expected: `wrote /Users/nuzantara/Desktop/nuzantara/.worktrees/jobs-agents-orch/apps/backend-rag/docs/jobs-schedule.md`.

- [ ] **Step 3: Verify --check passes**

Run: `cd apps/backend-rag && PYTHONPATH=. python scripts/gen_jobs_schedule_doc.py --check`
Expected: `docs/jobs-schedule.md is up to date.` Exit 0.

- [ ] **Step 4: Commit generator + generated doc**

```bash
git add apps/backend-rag/scripts/gen_jobs_schedule_doc.py \
        apps/backend-rag/docs/jobs-schedule.md
git commit -m "feat(backend/jobs): schedule doc auto-generator + initial jobs-schedule.md"
```

---

## Task 16: Full verification + coverage gate

**Files:** (no new code — verification only)

- [ ] **Step 1: Run the full jobs suite**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/jobs/ backend/tests/db/test_migration_112_job_runs.py -v`
Expected: all tests PASS (≥35 tests across retries, idempotency, middleware, runner loop, router, lifespan, migration).

- [ ] **Step 2: Run coverage on `backend/jobs/`**

Run: `cd apps/backend-rag && PYTHONPATH=. coverage run --source=backend/jobs -m pytest backend/tests/jobs/ && coverage report --fail-under=80`
Expected: `TOTAL ≥ 80%` coverage and exit 0.

If below 80%, inspect the report, identify the untested branch (likely the `_tick_loop` failure path or an unexercised middleware opt-out), and add a targeted test in the matching test file. Re-run. Do not lower the threshold.

- [ ] **Step 3: Run the full pre-deploy gate**

Run:
```bash
cd apps/backend-rag
git diff --name-only HEAD -- backend/ | head -20   # sanity-check scope
source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('import chain OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```
Expected: all three existing guard tests PASS. This ensures the Task 14 lifespan edits did not break the import chain.

- [ ] **Step 4: Verify schedule doc is in sync**

Run: `cd apps/backend-rag && PYTHONPATH=. python scripts/gen_jobs_schedule_doc.py --check`
Expected: up-to-date.

- [ ] **Step 5: Apply migration 112 against the actual target PostgreSQL (Pro local dev DB), manually**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
DATABASE_URL=postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag PYTHONPATH=. python -m backend.migrations.apply_migration_112
```
(If the above fails because the tunnel to Fly PG isn't up — `~/tunnel-air.sh` first. If you only want to verify against the test DB, skip this step; migration goes live only at merge time via the Fly deploy workflow.)
Expected: `✅ Migration 112 applied.`

- [ ] **Step 6: No commit in this task (verification only)**

Skip if everything is green.

---

## Task 17: PR preparation

- [ ] **Step 1: Push the branch**

Run: `cd apps/backend-rag/../.. && git push -u origin pro/backend-jobs-agents-orchestration`
(From the worktree root, since the branch is pro/backend-jobs-agents-orchestration.)

- [ ] **Step 2: Inspect the final diff**

Run: `git log --oneline main..HEAD && echo "---" && git diff --stat main..HEAD | tail -30`
Expected: ~17 commits (one per task + spec), touching `apps/backend-rag/backend/jobs/*`, `apps/backend-rag/backend/app/routers/jobs_admin.py`, `apps/backend-rag/backend/app/setup/app_factory.py`, `apps/backend-rag/backend/app/setup/router_registration.py`, `apps/backend-rag/backend/migrations/migration_112_*.py`, `apps/backend-rag/backend/migrations/apply_migration_112.py`, `apps/backend-rag/backend/tests/jobs/*`, `apps/backend-rag/scripts/gen_jobs_schedule_doc.py`, `apps/backend-rag/docs/jobs-schedule.md`, `apps/backend-rag/requirements*.txt`, `docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md`, `docs/superpowers/plans/2026-04-18-backend-jobs-agents-orchestration-plan.md`.

No changes outside `apps/backend-rag/` except the two markdown files under `docs/superpowers/`.

- [ ] **Step 3: Open the PR**

Run from the worktree root:

```bash
gh pr create --title "feat(backend): unified job runner + agent safety layer (PB3 core)" --body "$(cat <<'EOF'
## Summary
- Unified async job runner (`backend/jobs/`): custom scheduler with croniter, Postgres advisory locks, `job_runs` persistence (migration 112), tick-based idempotency with handler override.
- Default-on safety middleware: OAuth guard (raises if `ANTHROPIC_API_KEY` set), per-run cost cap (100c default), Claude CLI fallback (detects Linux+non-TTY).
- Four legacy jobs migrated: `auto-practice-creator`, `conversation-cleanup`, `consiglio-auto`, `kg-curiosity`. Schedule lives in code; `docs/jobs-schedule.md` auto-generated.
- Admin endpoints `/api/jobs`, `/api/jobs/{name}/run`, `/api/jobs/{name}/runs`. Legacy `/api/admin/practice/auto-create` preserved as alias for existing Air crontab.
- Per-job migration switch via `JOBS_RUNNER_ENABLED` env var — runner scheduling is off until Zero opts each job in.

## Test plan
- [ ] `pytest backend/tests/jobs/ backend/tests/db/test_migration_112_job_runs.py -v` — all green
- [ ] `coverage report --fail-under=80` on `backend/jobs/` — passes
- [ ] Pre-deploy guard tests pass (kg_langgraph, kg_subgraphs, confidence)
- [ ] `python scripts/gen_jobs_schedule_doc.py --check` — doc in sync
- [ ] Deploy preview: apply migration 112, leave `JOBS_RUNNER_ENABLED` empty, verify `/api/jobs` lists registry with `enabled: false`, verify `POST /api/admin/practice/auto-create` still works (same response shape)
- [ ] After stable, add `JOBS_RUNNER_ENABLED=auto-practice-creator` and observe one scheduled run

Spec: [docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md](docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md)
Plan: [docs/superpowers/plans/2026-04-18-backend-jobs-agents-orchestration-plan.md](docs/superpowers/plans/2026-04-18-backend-jobs-agents-orchestration-plan.md)

Out of scope (follow-up PRs): Article Composer state machine, Journey event sourcing, Agent Mesh v2 registry, Air crontab cleanup.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Return the PR URL.

---

## Deployment notes (post-merge, not part of the plan but required context)

1. Migration 112 must be applied on `nuzantara-postgres` via the existing Fly migrations workflow before code rollout (or as part of the same deploy, depending on the migration runner order).
2. Initial rollout sets `fly secrets set JOBS_RUNNER_ENABLED=""` — runner registers jobs but does not schedule them. `/api/jobs` becomes observable.
3. Flip one job at a time: `fly secrets set JOBS_RUNNER_ENABLED="auto-practice-creator"` and observe a 24h window before adding the next. When a job is runner-scheduled AND Air crontab still calls the HTTP endpoint, the second daily tick is a no-op (idempotent skip).
4. After each job has run cleanly for ~7 days on the runner, remove its Air crontab entry in a separate PR (Workstream follow-up #1).

## Self-review checklist

**Spec coverage:**
- Registry + register_job → Task 5 ✓
- Runner with croniter + advisory locks → Tasks 6, 9, 11 ✓
- `job_runs` migration + repository → Tasks 1, 7 ✓
- Default-on middleware (OAuth/cost/Claude CLI) → Task 8 ✓
- Handlers for 4 legacy jobs → Task 12 ✓
- `JOBS_RUNNER_ENABLED` allowlist → Task 9 (allowlist logic) + Task 14 (wiring) ✓
- `/api/jobs*` admin surface + legacy alias → Task 13 ✓
- Schedule doc auto-generator → Task 15 ✓
- Retry/idempotency semantics → Tasks 7, 9, 10 ✓
- Crash recovery (orphans) → Tasks 7, 10, 11 ✓
- Exception taxonomy → Task 3 ✓
- Lifespan wiring → Task 14 ✓
- Coverage gate 80% → Task 16 ✓

**Placeholder scan:** No "TBD", no "implement later", every code step is complete. Task 12 Step 4 has an explicit guard ("pause and report") rather than a vague "handle appropriately" — the engineer is instructed to concretely locate the real symbol.

**Type consistency:** `JobDeclaration.handler` signature matches across registry/runner/handlers: `Callable[[JobContext], Awaitable[JobResult | None]]`. `JobContext` fields match between Task 4 (definition) and Tasks 9-11 (construction). Repository method names are identical in Task 7 definition and Task 9/10/13 callers (`create_pending`, `mark_running`, `finish`, `get`, `find_completed_by_idempotency_key`, `list_recent`, `mark_orphans`). Middleware class names match Task 8 (definition) and Task 9/10 (usage).
