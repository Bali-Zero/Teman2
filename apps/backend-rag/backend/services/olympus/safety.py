"""Olympus — Safety Envelope primitives (P0).

Small, reusable helpers that bound what the guardian can do to the DB and to
itself:

- `action_timeouts()` — per-action statement/lock timeout on a fresh connection
  (P0.1). Caps how long any single maintenance statement can run and how long it
  will wait for a lock before failing cleanly.
- `PulseBudget` — per-pulse action/runtime budget (P0.2). Prevents a runaway
  pulse from exhausting the shared asyncpg pool on a 2GB machine.

These are deliberately dependency-light (asyncpg + stdlib only) and reuse the
existing `SET statement_timeout` idiom already present in service_initializer.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg


@asynccontextmanager
async def action_timeouts(
    pool: asyncpg.Pool,
    statement_timeout_s: int,
    lock_timeout_s: int,
) -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection with per-action statement/lock timeouts applied.

    Uses session-level SET (not SET LOCAL) so the timeout governs autonomous
    statements like VACUUM that run outside an explicit transaction block.
    The connection is returned to the pool on exit; asyncpg resets session
    state on release, so the timeouts do not leak to the next borrower.

    Args:
        pool: the asyncpg pool.
        statement_timeout_s: max seconds a single statement may run (0 = disabled).
        lock_timeout_s: max seconds to wait for a lock before erroring.
    """
    async with pool.acquire() as conn:
        # Guard against nonsensical/negative config; 0 means "no limit" in PG.
        st = max(0, int(statement_timeout_s))
        lk = max(0, int(lock_timeout_s))
        await conn.execute(f"SET statement_timeout = '{st}s'")
        await conn.execute(f"SET lock_timeout = '{lk}s'")
        yield conn


class PulseBudget:
    """Bounds a single pulse run by action count and wall-clock runtime.

    Call `record()` after each action is produced; check `exceeded()` between
    action groups in run_full_pulse to stop early. Cheap stdlib-only counter.
    """

    def __init__(self, max_actions: int, max_runtime_s: float) -> None:
        self.max_actions = max(1, int(max_actions))
        self.max_runtime_s = max(1.0, float(max_runtime_s))
        self._count = 0
        self._t0 = time.monotonic()

    def record(self, n: int = 1) -> None:
        self._count += n

    @property
    def count(self) -> int:
        return self._count

    def elapsed_s(self) -> float:
        return time.monotonic() - self._t0

    def exceeded(self) -> bool:
        return self._count >= self.max_actions or self.elapsed_s() >= self.max_runtime_s

    def reason(self) -> str:
        if self._count >= self.max_actions:
            return f"max_actions_per_pulse={self.max_actions} reached ({self._count})"
        return f"max_pulse_runtime_s={self.max_runtime_s:.0f} reached ({self.elapsed_s():.0f}s)"
