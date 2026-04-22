"""Event + ActionDecision + IncidentContext schemas.

Pydantic v2 models used across event bus, Supervisor, Actuators.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
import json


class Severity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Event(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    severity: Severity
    source: str  # e.g. "guardian.system_doctor"
    kind: str    # e.g. "cron_agent_failure"
    payload: dict[str, Any]
    correlation_id: str
    is_actuation: bool = False
    host: Literal["Pro", "Air"]

    @field_validator("payload")
    @classmethod
    def _max_2kb(cls, v: dict) -> dict:
        if len(json.dumps(v, default=str)) > 2048:
            raise ValueError("payload_too_large: max 2KB")
        return v


class ActionDecision(BaseModel):
    actuator: str            # e.g. "restart_agent"
    params: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    tier: Literal["L0_yaml", "L1_ollama", "L2_claude", "L3_consiglio"]
    reasoning: str | None = None


class IncidentContext(BaseModel):
    correlation_id: str
    events: list[Event] = Field(default_factory=list)
    ollama_bucket: str | None = None  # set by L1 classifier
    last_action: ActionDecision | None = None
    quarantined: bool = False
