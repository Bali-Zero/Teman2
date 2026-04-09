"""Pydantic models for Olympus DB Guardian v2.

Three models only — no speculative Insight/Skill.
"""

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
    recorded_at: datetime = Field(default_factory=_utc_now)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pool_utilization(self) -> float:
        if self.pool_size == 0:
            return 0.0
        return round(1 - self.pool_idle / self.pool_size, 2)


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
