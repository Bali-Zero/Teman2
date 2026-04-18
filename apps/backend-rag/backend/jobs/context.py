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
