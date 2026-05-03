"""Shared vocabulary — all dataclasses that every cell uses."""
from __future__ import annotations

import math
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class Phase(StrEnum):
    """Lifecycle phases — from embryo to elder."""
    EMBRIONE = "embrione"
    NEONATO = "neonato"
    GIOVANE = "giovane"
    ADULTO = "adulto"
    ANZIANO = "anziano"


@dataclass
class CellConfig:
    """Configuration for one organ/agent."""
    name: str
    dna_path: str
    pulse_interval_seconds: int = 60
    birth_date: datetime | None = None
    memory_backend: str = "sqlite"
    db_path: str = "cell.db"
    sleep_hours: tuple[int, int] = (2, 6)


@dataclass
class SensorReading:
    """One sensor's perception of the environment."""
    sensor_name: str
    status: Literal["green", "yellow", "red"]
    value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Proposal:
    """A reasoner's proposed action."""
    action: str
    reason: str
    confidence: float
    tier_used: int
    cost_usd: float = 0.0


_RECENCY_WEIGHT = 1.0
_FREQUENCY_WEIGHT = 0.5
_BASE_ACTIVATION = 0.5


@dataclass
class Episode:
    """A single episodic memory — a moment the cell experienced."""
    situation: dict[str, Any]
    emotion: str
    action_taken: str
    outcome: str
    lesson: str
    id: int = 0
    timestamp: float = 0.0
    recall_count: int = 0
    activation: float = 0.0

    def compute_activation(self) -> float:
        """ACT-R activation: base + recency + frequency."""
        ts = self.timestamp if self.timestamp > 0 else time.time()
        age_seconds = max(time.time() - ts, 1.0)
        age_days = age_seconds / 86400.0
        recency = _RECENCY_WEIGHT * (1.0 / (1.0 + math.log1p(age_days)))
        frequency = _FREQUENCY_WEIGHT * math.log1p(self.recall_count)
        return _BASE_ACTIVATION + recency + frequency


@dataclass
class LearnedRule:
    """A condensed rule extracted from episodic memory."""
    rule_text: str
    support_count: int
    created_at: str = ""


@dataclass
class HomeostaticState:
    """The organism's internal physiological state."""
    stress_level: float = 0.0
    energy_level: float = 1.0
    arousal: float = 0.5
    comfort_zone: tuple[float, float] = (50.0, 200.0)
    setpoint_rt_ms: float = 100.0
    circadian_phase: str = "awake"

    def __post_init__(self) -> None:
        self.stress_level = _clamp(self.stress_level)
        self.energy_level = _clamp(self.energy_level)
        self.arousal = _clamp(self.arousal)


def _default_pulse_id() -> str:
    """Generate a 26-char Crockford-base32 ULID-style pulse id (sortable).

    Format: 10-char timestamp ms + 16-char random. Good enough for log correlation
    without adding a `ulid-py` dependency.
    """
    ts_ms = int(time.time() * 1000)
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    enc = ""
    n = ts_ms
    for _ in range(10):
        enc = alphabet[n & 0x1F] + enc
        n >>= 5
    rnd = "".join(secrets.choice(alphabet) for _ in range(16))
    return enc + rnd


@dataclass
class PulseResult:
    """Result of one lifecycle tick."""
    timestamp: datetime
    pulse_number: int
    halted: bool = False
    halt_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    health_status: str | None = None
    action_taken: str | None = None
    action_reason: str | None = None
    thought_tier: int | None = None
    error: str | None = None
    pulse_id: str = field(default_factory=_default_pulse_id)


@dataclass
class SafetyCheckResult:
    """Result of a safety gate check."""
    can_proceed: bool
    reason: str = ""
    detail: str = ""


@dataclass
class DNARule:
    """One immutable rule in the organism's DNA."""
    text: str
    priority: int


@dataclass
class DNAConfig:
    """Complete DNA configuration loaded from JSON."""
    rules: list[DNARule]
    constraints: dict[str, Any]
