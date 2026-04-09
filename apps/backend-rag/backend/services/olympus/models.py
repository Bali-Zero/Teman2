"""Pydantic models for the Olympus DB Guardian.

Covers heartbeat snapshots, pulse actions, rules, insights, and skills.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    """Return current UTC time (used as default factory)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# HeartbeatSnapshot — metrics collected every heartbeat
# ---------------------------------------------------------------------------

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
        """Fraction of pool currently in use (0.0 – 1.0)."""
        if self.pool_size == 0:
            return 0.0
        return round(1 - self.pool_idle / self.pool_size, 2)


# ---------------------------------------------------------------------------
# PulseAction — a single pulse action
# ---------------------------------------------------------------------------

class PulseAction(BaseModel):
    """Record of a single action taken during a pulse rhythm."""

    rhythm: str = Field(default="pulse")
    action_type: str
    target: str | None = Field(default=None)
    detail: dict[str, Any] = Field(default_factory=dict)
    outcome: str | None = Field(default=None)
    duration_ms: int | None = Field(default=None)
    rule_applied: str | None = Field(default=None)
    reflection: str | None = Field(default=None)
    executed_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# OlympusRule — rule from DB
# ---------------------------------------------------------------------------

class OlympusRule(BaseModel):
    """A self-tuning rule stored in the olympus_rules table."""

    id: int
    rule_name: str
    category: str
    config: dict[str, Any]
    source: str
    confidence: float = Field(default=1.0)
    applied_count: int = Field(default=0)
    last_applied: datetime | None = Field(default=None)
    superseded_by: int | None = Field(default=None)

    def get_value(self, key: str = "value") -> Any:
        """Extract a value from the rule config dict."""
        return self.config.get(key)


# ---------------------------------------------------------------------------
# Insight — shared wisdom
# ---------------------------------------------------------------------------

class Insight(BaseModel):
    """An insight distilled from Olympus observations."""

    insight_type: str
    title: str
    content: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="")
    confidence: float = Field(default=0.8)
    applicable_to: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Skill — reusable SQL procedure (Voyager pattern)
# ---------------------------------------------------------------------------

class Skill(BaseModel):
    """A learned SQL procedure that Olympus can replay."""

    skill_name: str
    description: str
    sql_template: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    success_criteria: str | None = Field(default=None)
    learned_from: str | None = Field(default=None)
