"""Pydantic schemas for the Experience Library service.

Validation at the boundary (router <-> service): trajectory_id length, outcome
whitelist, confidence range, query limit bound.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TrajectoryOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class TrajectoryRecord(BaseModel):
    """Payload to register an execution trajectory in the Genome."""

    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    trajectory_id: str = Field(..., min_length=1, max_length=128)
    cell: str = Field(..., min_length=1, max_length=64)
    outcome: TrajectoryOutcome
    procedure: str = Field(..., min_length=1, max_length=4000)
    tokens: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=16)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class TrajectoryQuery(BaseModel):
    """Read request against the Experience Library."""

    model_config = ConfigDict(use_enum_values=True)

    query: str = Field(..., min_length=1, max_length=256)
    outcome: TrajectoryOutcome | None = None
    cell: str | None = Field(default=None, max_length=64)
    tag: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=20, ge=1, le=100)


class TrajectoryResult(BaseModel):
    """Response row from a query — flat projection of the Genome row."""

    trajectory_id: str
    cell: str
    outcome: TrajectoryOutcome
    procedure: str
    tokens: int | None = None
    duration_ms: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float
    valid_from: str
