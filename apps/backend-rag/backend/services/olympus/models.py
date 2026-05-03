"""Pydantic models for Olympus DB Guardian v3."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HeartbeatSnapshot(BaseModel):
    """Metrics collected during a single heartbeat cycle."""

    pool_size: int
    pool_idle: int
    active_connections: int
    max_connections: int
    db_size_bytes: int
    bloat_top3: list[dict[str, Any]] = Field(default_factory=list)
    long_queries: int = Field(default=0)
    lock_waits: int = Field(default=0)
    alerts_sent: int = Field(default=0)
    # v3 extended metrics
    cache_hit_ratio: float | None = Field(default=None)
    top_tables_by_size: list[dict[str, Any]] = Field(default_factory=list)
    idx_scan_ratio: float | None = Field(default=None)
    health_score: int | None = Field(default=None)
    recorded_at: datetime = Field(default_factory=_utc_now)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pool_utilization(self) -> float:
        if self.pool_size == 0:
            return 0.0
        return round(1 - self.pool_idle / self.pool_size, 2)

    def compute_health_score(self, dead_tuple_ratio: float = 0.0) -> int:
        """Compute composite health score 0-100."""
        score = 0.0

        # Cache hit ratio: 25pt at >=95%, linear below
        if self.cache_hit_ratio is not None:
            score += min(25.0, 25.0 * min(self.cache_hit_ratio, 95.0) / 95.0)
        else:
            score += 25.0  # assume healthy if no data yet

        # Pool utilization: 20pt at <50%, linear above
        pool_pct = self.pool_utilization * 100
        if pool_pct <= 50:
            score += 20.0
        else:
            score += max(0.0, 20.0 * (100 - pool_pct) / 50.0)

        # Dead tuple ratio: 20pt at <2%, linear above
        if dead_tuple_ratio <= 2.0:
            score += 20.0
        else:
            score += max(0.0, 20.0 * (1 - (dead_tuple_ratio - 2.0) / 20.0))

        # Index scan ratio: 15pt at >80%, linear below
        if self.idx_scan_ratio is not None:
            score += min(15.0, 15.0 * min(self.idx_scan_ratio, 80.0) / 80.0)
        else:
            score += 15.0  # assume healthy if no data yet

        # Long queries: 10pt at 0, -2pt per query
        score += max(0.0, 10.0 - self.long_queries * 2.0)

        # Lock waits: 10pt at 0, -5pt per lock
        score += max(0.0, 10.0 - self.lock_waits * 5.0)

        return max(0, min(100, int(round(score))))


class PulseAction(BaseModel):
    """Record of a single pulse action.

    outcome MUST be one of: success, failure, skipped, proposed
    to match the CHECK constraint on olympus_actions.
    """

    rhythm: str = Field(default="pulse")
    action_type: str
    target: str | None = Field(default=None)
    detail: dict[str, Any] = Field(default_factory=dict)
    outcome: str | None = Field(default=None)
    duration_ms: int | None = Field(default=None)
    rule_applied: str | None = Field(default=None)
    reflection: str | None = Field(default=None)
    executed_at: datetime = Field(default_factory=_utc_now)


class OlympusRule(BaseModel):
    """A rule from olympus_rules. Config is JSON text in DB."""

    id: int
    rule_name: str
    category: str
    config: dict[str, Any]
    source: str
    confidence: float = Field(default=1.0)
    applied_count: int = Field(default=0)
    last_applied: datetime | None = Field(default=None)
    superseded_by: int | None = Field(default=None)

    @field_validator("config", mode="before")
    @classmethod
    def _parse_json_config(cls, v: Any) -> dict[str, Any]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    def get_value(self, key: str = "value") -> Any:
        return self.config.get(key)


class InsightRecord(BaseModel):
    """A record to persist in olympus_insights."""

    insight_type: str  # pattern | anomaly | recommendation
    title: str
    content: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str  # query_intelligence | bloat_intelligence | autovacuum_advisor
    confidence: float = Field(default=1.0)
    applicable_to: list[str] = Field(default_factory=list)
