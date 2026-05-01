from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class ClassificationLabel(str, Enum):
    NORMAL = "normal"
    ANOMALY = "anomaly"
    CRITICAL = "critical"
    UNCERTAIN = "uncertain"


class PulseEventV1(BaseModel):
    """Schema for cell_pulse_observed events. Frozen v1 — bump to v2 if shape changes."""
    outbox_id: int = Field(alias="_outbox_id")
    event_version: Literal["v1"]
    cell_id: str
    cell_kind: str
    pulse_id: str
    pulse_timestamp: str  # ISO 8601 string; collector converts to int ms
    phase: str
    sensors: list[dict[str, Any]]
    pulse_result: dict[str, Any]
    homeostatic_state: dict[str, Any]
    scar_signals: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ClassificationOutput(BaseModel):
    """Strict schema for MiniMax classifier output (Pydantic v2 generate_structured pattern)."""
    reasoning: str = Field(min_length=1, max_length=500)
    label: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)


class ClassificationResult(BaseModel):
    """Persisted classification (output + metadata)."""
    outbox_id: int
    label: ClassificationLabel
    confidence: float
    reasoning: str
    label_diff: Literal["agree", "disagree"]
    model: str
    model_version: str | None = None
    cost_usd: float
    latency_ms: int
    error: str | None = None
